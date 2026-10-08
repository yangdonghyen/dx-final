from datetime import date, time

import logging
from datetime import timedelta

from app.core.exceptions import AppError
from app.repositories.place_repository import PlaceRepository
from app.repositories.plan_repository import PlanItemRepository, PlanRepository
from app.repositories.trip_repository import (
    TripCompanionRepository,
    TripInterestRepository,
    TripPreferenceRepository,
    TripRepository,
    TripSelectedPlaceRepository,
)
from app.schemas.plan import PlanDayResponse, PlanGenerateResponse, PlanItemResponse
from app.schemas.trip import TripSelectedPlaceResponse
from app.services.exaone_interest_normalizer import normalize_exaone_interest_codes, raw_exaone_interest_codes
from app.services.external.ai.provider import GeneratedPlanDraft, PlanDraftDay, PlanDraftItem
from app.services.external.place.region_resolver import (
    RegionResolver,
    city_level_region,
    normalize_administrative_name,
)
from app.services.external.routing.provider import UnavailableRouteProvider
from app.services.place_search_service import PlaceSearchService
from app.services.plan_validation_service import PlanValidationService
from app.services.place_temporal_validation import (
    event_overlaps_trip,
    is_event_candidate,
    opening_hours_match,
    verified_hours,
)


logger = logging.getLogger("uvicorn.error")


NEARBY_RADIUS_METERS = 5000
KAKAO_NEARBY_CATEGORY_CODES = ("AT4", "CT1", "FD6", "CE7")
KAKAO_NEARBY_LIMIT_PER_CATEGORY = 5
MAX_PLAN_CANDIDATES = 15
MIN_PLAN_CANDIDATES = 2
MAX_NEARBY_CANDIDATES = 8
CITYWIDE_SEARCH_QUERIES = ("관광지", "문화시설", "맛집", "카페")
MAX_ROUTE_SECONDS = {
    "CAR": 60 * 60,
    "MIXED": 75 * 60,
    "PUBLIC_TRANSIT": 60 * 60,
    "WALK": 35 * 60,
    "OTHER": 35 * 60,
    None: 45 * 60,
}
MAX_WALKING_SECONDS = {
    "VERY_LOW": 10 * 60,
    "LOW": 20 * 60,
    "NORMAL": 35 * 60,
    "HIGH": 60 * 60,
}

BLOCKED_PLAN_PLACE_KEYWORDS = (
    "행정봉사실",
    "행정복지센터",
    "주민센터",
    "주민자치센터",
    "동사무소",
    "시청",
    "구청",
    "군청",
    "읍사무소",
    "면사무소",
    "경찰서",
    "파출소",
    "지구대",
    "소방서",
    "공중화장실",
    "화장실",
    "주차장",
    "주차타워",
    "부동산",
    "공인중개사",
    "호텔",
    "모텔",
    "게스트하우스",
    "펜션",
    "리조트",
    "숙박",
    "PC방",
    "피시방",
    "사무실",
    "오피스",
)

INTEREST_CATEGORY_TOKENS = {
    "SEA": ("AT4", "해변", "바다", "해양"),
    "FOOD": ("FD6", "음식", "식당", "맛집"),
    "CAFE": ("CE7", "카페"),
    "CULTURE": ("CT1", "문화", "미술", "박물관", "전시"),
    "CITY": ("CT1", "관광", "문화"),
    "REST": ("CE7", "공원", "해변", "카페"),
}


def _is_usable_plan_candidate(place) -> bool:
    name = getattr(place, "name", None) or ""
    category = getattr(place, "category", None) or ""
    searchable = f"{name} {category}".replace(" ", "").casefold()

    if any(
        keyword.replace(" ", "").casefold() in searchable
        for keyword in BLOCKED_PLAN_PLACE_KEYWORDS
    ):
        return False
    # Kakao's hierarchy is the authoritative automatic-candidate signal.  A
    # descriptive name only supplements it for cached/legacy data.
    category_code = (getattr(place, "category", None) or "").upper()
    allowed_kakao_groups = ("AT4", "CT1", "FD6", "CE7")
    category_words = ("CULTURE", "MUSEUM", "GALLERY", "PARK", "BEACH", "TOUR", "관광", "문화", "전시", "공원", "해변", "음식", "식당", "카페", "축제", "행사")
    return any(code in category_code for code in allowed_kakao_groups) or any(word.casefold() in searchable for word in category_words)


def _is_food_or_cafe(place) -> bool:
    """Classify only from verified provider category data, never place prose."""
    category = (getattr(place, "category", None) or "").casefold().replace(" ", "")
    return "fd6" in category or "ce7" in category or any(
        word in category for word in ("음식", "식당", "맛집", "카페", "restaurant", "cafe")
    )


class PlanGenerationService:
    def __init__(self, session, provider, place_provider=None, route_provider=None):
        self.session = session
        self.provider = provider
        self.place_provider = place_provider
        self.route_provider = route_provider or UnavailableRouteProvider()
        self.trips = TripRepository(session)
        self.preferences = TripPreferenceRepository(session)
        self.selected_places = TripSelectedPlaceRepository(session)
        self.companions = TripCompanionRepository(session)
        self.interests = TripInterestRepository(session)
        self.places = PlaceRepository(session)
        self.plans = PlanRepository(session)
        self.items = PlanItemRepository(session)
        self.validation = PlanValidationService(session)
        self.regions = RegionResolver()

    def _owned_active_trip(self, user_id, trip_id):
        trip = self.trips.get(trip_id)
        if trip is None:
            raise AppError("TRIP_NOT_FOUND", "Trip not found", 404)
        if trip.user_id != user_id:
            raise AppError("FORBIDDEN", "You do not own this trip", 403)
        if trip.status == "ARCHIVED":
            raise AppError("TRIP_ARCHIVED", "Trip is archived", 400)
        return trip

    @staticmethod
    def _provider_error():
        return AppError("AI_SCHEMA_VALIDATION_FAILED", "Plan provider returned an invalid draft", 502)

    @staticmethod
    def _same_region(left, right) -> bool:
        if not isinstance(left, str) or not isinstance(right, str):
            return False
        left_normalized = normalize_administrative_name(left)
        right_normalized = normalize_administrative_name(right)
        return bool(left_normalized and right_normalized and (
            left_normalized == right_normalized
            or left_normalized in right_normalized
            or right_normalized in left_normalized
        ))

    def _matches_destination(self, place, destination) -> bool:
        if not isinstance(destination, str) or not destination.strip():
            return True
        if isinstance(place.address, str) and place.address.strip():
            return self.regions.matches_region(place.address, destination)
        return self._same_region(place.region, destination)

    @staticmethod
    def _destination_from_anchors(anchors, fallback):
        destinations = {
            city_level_region(getattr(anchor, "address", None), getattr(anchor, "region", None))
            for anchor in anchors
        }
        destinations.discard(None)
        if len(destinations) > 1:
            raise AppError("ANCHORS_DIFFERENT_DESTINATIONS", "Selected places must belong to one trip destination", 422)
        return destinations.pop() if destinations else fallback

    @staticmethod
    def _has_destination(trip) -> bool:
        destination = getattr(trip, "destination", None)
        return isinstance(destination, str) and bool(destination.strip())

    def _selected_anchors(self, trip, selected_place_ids):
        anchor_ids = list(dict.fromkeys(selected_place_ids or []))
        if not anchor_ids:
            # With a known destination the plan is built from citywide
            # candidates only; without one there is nothing to plan around.
            if self._has_destination(trip):
                return []
            raise AppError("PLACE_IDS_REQUIRED", "At least one selected place is required", 422)
        anchors = []
        for place_id in anchor_ids:
            place = self.places.get(place_id)
            if place is None:
                raise AppError("PLACE_NOT_FOUND", f"Selected place {place_id} was not found", 404)
            if place.latitude is None or place.longitude is None:
                raise AppError("PLACE_COORDINATES_REQUIRED", "Selected place must have verified coordinates", 422)
            if not self._matches_destination(place, trip.destination):
                raise AppError("PLACE_OUTSIDE_DESTINATION", "Selected place is outside the trip destination", 422)
            anchors.append(place)
        return anchors

    def _stored_anchors(self, trip):
        selected = self.selected_places.list(trip.trip_id)
        anchors = [row.place for row in selected if row.place is not None]
        if not anchors and not self._has_destination(trip):
            raise AppError("PLACE_IDS_REQUIRED", "At least one selected place is required", 422)
        return anchors

    def _selected_place_responses(self, anchors):
        return [
            TripSelectedPlaceResponse(
                place_id=place.place_id,
                name=place.name,
                region=place.region,
                address=place.address,
                latitude=float(place.latitude) if place.latitude is not None else None,
                longitude=float(place.longitude) if place.longitude is not None else None,
                category=place.category,
                selected_order=index,
            )
            for index, place in enumerate(anchors, start=1)
        ]

    @staticmethod
    def _append_unique(places, additions):
        seen_place_ids = {place.place_id for place in places}
        seen_kakao_ids = {place.kakao_place_id for place in places if place.kakao_place_id}
        for place in additions:
            if place.place_id in seen_place_ids:
                continue
            if place.kakao_place_id and place.kakao_place_id in seen_kakao_ids:
                continue
            places.append(place)
            seen_place_ids.add(place.place_id)
            if place.kakao_place_id:
                seen_kakao_ids.add(place.kakao_place_id)

    def _database_candidates(self, trip, anchors):
        """Use cached destination-wide places as well as anchor-nearby places.

        Anchors are interests, not a geographic fence.  Nearby places are kept
        first for a coherent day, then cached places from other districts fill
        the candidate pool for multi-day variety.
        """
        candidates = []
        anchor_ids = {place.place_id for place in anchors}
        for anchor in anchors:
            nearby = self.places.list_nearby(
                float(anchor.latitude),
                float(anchor.longitude),
                NEARBY_RADIUS_METERS,
                anchor_ids,
            )
            self._append_unique(
                candidates,
                [
                    place
                    for place in nearby[:max(0, MAX_NEARBY_CANDIDATES - len(candidates))]
                    if self._matches_destination(place, trip.destination)
                    and _is_usable_plan_candidate(place)
                ],
            )
            if len(candidates) >= MAX_NEARBY_CANDIDATES:
                break
        citywide = [
            place for place in self.places.list()
            if place.place_id not in anchor_ids
            and self._matches_destination(place, trip.destination)
            and _is_usable_plan_candidate(place)
        ]
        # list() has repository ordering; append_unique retains it and prevents
        # an anchor area from crowding out all other cached destination places.
        self._append_unique(candidates, citywide)
        return candidates

    def _route_estimate(self, first, second, transport_mode):
        if any(getattr(place, value, None) is None for place in (first, second) for value in ("latitude", "longitude")):
            return None
        return self.route_provider.route(
            float(first.latitude), float(first.longitude), float(second.latitude), float(second.longitude), transport_mode
        )

    def _mobility_candidates(self, candidates, anchors, trip, preferences):
        """Apply factual routing constraints when data exists.

        With no route provider we retain verified destination candidates and
        omit route facts entirely.  Coordinates are not converted to minutes.
        """
        if not candidates or not anchors:
            return candidates
        mode = getattr(trip, "transport_mode", None)
        walking_tolerance = preferences.get("walking_tolerance") or "NORMAL"
        retained = list(anchors)
        for candidate in candidates:
            if candidate in anchors:
                continue
            estimates = [self._route_estimate(anchor, candidate, mode) for anchor in anchors]
            factual = [estimate for estimate in estimates if estimate is not None]
            if not factual:
                retained.append(candidate)
                continue
            best = min(factual, key=lambda estimate: estimate.duration_seconds)
            if best.duration_seconds > MAX_ROUTE_SECONDS.get(mode, MAX_ROUTE_SECONDS[None]):
                continue
            if mode in {"PUBLIC_TRANSIT", "WALK"} and best.walking_seconds is not None:
                if best.walking_seconds > MAX_WALKING_SECONDS.get(walking_tolerance, MAX_WALKING_SECONDS["NORMAL"]):
                    continue
            retained.append(candidate)
        return retained

    @staticmethod
    def _rank_for_interests(candidates, anchors, raw_interest_codes):
        """Prefer category-matched candidates without making an interest a fence."""
        interest_tokens = [
            token.casefold()
            for code in raw_interest_codes
            for token in INTEREST_CATEGORY_TOKENS.get(code, ())
        ]
        anchor_ids = {anchor.place_id for anchor in anchors}
        anchors_first = [candidate for candidate in candidates if candidate.place_id in anchor_ids]
        automatic = [candidate for candidate in candidates if candidate.place_id not in anchor_ids]

        def score(candidate):
            category = (getattr(candidate, "category", None) or "").casefold()
            return sum(token in category for token in interest_tokens)

        # Stable sorting preserves geographic/provider ordering among equal
        # quality candidates and avoids turning a single interest into an
        # all-day, every-day repetition.
        return anchors_first + sorted(automatic, key=score, reverse=True)

    @staticmethod
    def _balanced_candidate_pool(candidates, anchors, trip):
        """Reserve verified non-food activities before food/cafe backfill."""
        anchor_ids = {anchor.place_id for anchor in anchors}
        selected = [candidate for candidate in candidates if candidate.place_id in anchor_ids]
        automatic = [candidate for candidate in candidates if candidate.place_id not in anchor_ids]
        activities = [candidate for candidate in automatic if not _is_food_or_cafe(candidate)]
        food_or_cafes = [candidate for candidate in automatic if _is_food_or_cafe(candidate)]
        trip_days = (trip.end_date - trip.start_date).days + 1
        # Reserve about half the pool (at least two per day) for activities so
        # the model cannot fill whole days with restaurants.
        reserve_count = min(len(activities), max(trip_days * 2, MAX_PLAN_CANDIDATES // 2))

        def append_until_limit(rows):
            for row in rows:
                if row not in selected and len(selected) < MAX_PLAN_CANDIDATES:
                    selected.append(row)

        # The reserve makes an actual activity available for each full day
        # when the verified pool has enough distinct activity candidates.
        append_until_limit(activities[:reserve_count])
        append_until_limit(food_or_cafes)
        append_until_limit(activities[reserve_count:])
        return selected

    def _kakao_candidates(self, trip, anchors, existing):
        if self.place_provider is None:
            return []
        search_service = PlaceSearchService(self.session, self.place_provider)
        candidates = []
        excluded_ids = {place.place_id for place in existing}
        for anchor in anchors:
            try:
                external_candidates = self.place_provider.search_nearby(
                    float(anchor.latitude),
                    float(anchor.longitude),
                    NEARBY_RADIUS_METERS,
                    list(KAKAO_NEARBY_CATEGORY_CODES),
                    KAKAO_NEARBY_LIMIT_PER_CATEGORY,
                )
                upserted = search_service.upsert_candidates(
                    external_candidates,
                    trip.destination,
                )
            except AppError:
                continue
            places = [self.places.get(item.place_id) for item in upserted]
            allowed = []
            for place in places:
                if place is None or place.place_id in excluded_ids:
                    continue
                if not _is_usable_plan_candidate(place):
                    continue
                if not self._matches_destination(place, trip.destination):
                    continue
                distance = self.places._distance_meters(
                    float(anchor.latitude),
                    float(anchor.longitude),
                    float(place.latitude),
                    float(place.longitude),
                )
                if distance <= NEARBY_RADIUS_METERS:
                    allowed.append(place)
            self._append_unique(candidates, allowed)
            excluded_ids.update(place.place_id for place in candidates)
            if len(existing) + len(candidates) >= MAX_PLAN_CANDIDATES:
                break
        return candidates

    def _citywide_kakao_candidates(self, trip, existing):
        """Backfill the destination, rather than repeatedly searching anchors."""
        if self.place_provider is None or not hasattr(self.place_provider, "search"):
            return []
        search_service = PlaceSearchService(self.session, self.place_provider)
        candidates = []
        excluded_ids = {place.place_id for place in existing}
        for query in CITYWIDE_SEARCH_QUERIES:
            try:
                upserted = search_service.upsert_candidates(
                    self.place_provider.search(query, trip.destination), trip.destination
                )
            except AppError:
                continue
            allowed = []
            for item in upserted:
                place = self.places.get(item.place_id)
                if (place is not None and place.place_id not in excluded_ids
                        and self._matches_destination(place, trip.destination)
                        and _is_usable_plan_candidate(place)):
                    allowed.append(place)
            self._append_unique(candidates, allowed)
            excluded_ids.update(place.place_id for place in candidates)
            if len(existing) + len(candidates) >= MAX_PLAN_CANDIDATES:
                break
        return candidates

    def _candidate_places(self, trip, anchors, preferences=None):
        anchor_ids = {place.place_id for place in anchors}
        candidates = list(anchors)
        trip_days = (trip.end_date - trip.start_date).days + 1
        # A one-day trip can work with two verified choices. Longer trips need
        # a larger pool so the model can use distinct places and districts.
        desired_count = min(MAX_PLAN_CANDIDATES, max(MIN_PLAN_CANDIDATES, trip_days * 2))
        self._append_unique(candidates, self._database_candidates(trip, anchors))
        candidates = [
            place for place in candidates
            if place.place_id in anchor_ids or self._is_temporally_eligible(place, trip)
        ]
        if len(candidates) < desired_count:
            nearby = self._kakao_candidates(trip, anchors, candidates)
            self._append_unique(
                candidates,
                [place for place in nearby if self._is_temporally_eligible(place, trip)],
            )
        if len(candidates) < desired_count:
            citywide = self._citywide_kakao_candidates(trip, candidates)
            self._append_unique(
                candidates,
                [place for place in citywide if self._is_temporally_eligible(place, trip)],
            )
        if len(candidates) < MIN_PLAN_CANDIDATES:
            raise AppError(
                "INSUFFICIENT_PLACE_CANDIDATES",
                "Could not find enough verified places near the selected locations",
                422,
            )
        if len(candidates) < MIN_PLAN_CANDIDATES:
            raise AppError(
                "INSUFFICIENT_PLACE_CANDIDATES",
                "Could not find enough verified places with suitable dates",
                422,
            )
        candidates = self._mobility_candidates(candidates, anchors, trip, preferences or {})
        return self._balanced_candidate_pool(candidates, anchors, trip)

    @staticmethod
    def _is_temporally_eligible(place, trip):
        if is_event_candidate(place):
            # Events without a verified date range are not safe automatic
            # itinerary candidates. No calendar inference or invented dates.
            return event_overlaps_trip(place, trip.start_date, trip.end_date) is True
        return True

    def _input(self, trip, selected_place_ids=None):
        anchors = (
            self._stored_anchors(trip)
            if selected_place_ids is None
            else self._selected_anchors(trip, selected_place_ids)
        )
        preference = self.preferences.get(trip.trip_id)
        preferences = {
            "walking_tolerance": preference.walking_tolerance if preference else None,
            "rest_frequency": preference.rest_frequency if preference else None,
            "avoid_stairs": preference.avoid_stairs if preference else False,
            "avoid_hills": preference.avoid_hills if preference else False,
            "taxi_allowed": preference.taxi_allowed if preference else True,
            "travel_style": getattr(preference, "travel_style", None) if preference else None,
        }
        destination = self._destination_from_anchors(anchors, trip.destination)
        # Use a lightweight view so every collection path consistently treats
        # the anchor's city-level region as the destination boundary.
        trip_scope = type("TripScope", (), {**vars(trip), "destination": destination})()
        places = self._candidate_places(trip_scope, anchors, preferences)
        anchor_ids = {place.place_id for place in anchors}
        companions = [
            {
                "name": row.name_snapshot,
                "relation": row.relation_snapshot,
                "age_group": row.age_group_snapshot,
                "walking_tolerance": row.walking_tolerance,
                "rest_frequency": row.rest_frequency,
                "avoid_stairs": row.avoid_stairs,
                "avoid_hills": row.avoid_hills,
                "taxi_allowed": row.taxi_allowed,
                "interests": row.interests_snapshot or [],
            }
            for row in self.companions.list(trip.trip_id)
        ]
        stored_interest_codes = [row.interest_code for row in self.interests.list(trip.trip_id)]
        places = self._rank_for_interests(places, anchors, raw_exaone_interest_codes(stored_interest_codes))
        interests = normalize_exaone_interest_codes(stored_interest_codes)
        preference_context = {"raw_interest_codes": raw_exaone_interest_codes(stored_interest_codes)}
        logger.info(
            "plan generation input trip_id=%s raw_interests=%s canonical_interests=%s preference_context=%s ranking_interests=%s",
            trip.trip_id, preference_context["raw_interest_codes"], interests,
            preference_context, preference_context["raw_interest_codes"],
        )
        candidates = [
            {
                "place_id": row.place_id,
                "name": row.name,
                "category": row.category,
                "region": row.region,
                "address": row.address,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "is_anchor": row.place_id in anchor_ids,
                "activity_kind": "FOOD_OR_CAFE" if _is_food_or_cafe(row) else "NON_FOOD_ACTIVITY",
                "opening_hours": verified_hours(row),
                "event_start_date": getattr(row, "event_start_date", None),
                "event_end_date": getattr(row, "event_end_date", None),
            }
            for row in places
        ]
        trip_input = {
            "departure": trip.departure,
            "destination": destination,
            "start_date": trip.start_date,
            "end_date": trip.end_date,
            "budget_krw": trip.budget_krw,
            "transport_mode": trip.transport_mode,
        }
        return trip_input, preferences, companions, interests, preference_context, candidates, anchor_ids, {row.place_id: row for row in places}

    @staticmethod
    def _canonical_item_type(place):
        category = (getattr(place, "category", None) or "").casefold().replace(" ", "")
        # Kakao category group/hierarchy takes precedence over model prose.
        # CE7 cafes are visit activities, never meals.
        if "ce7" in category or "카페" in category or "cafe" in category:
            return "PLACE"
        return "MEAL" if "fd6" in category or any(word in category for word in ("음식", "식당", "맛집", "한식", "양식", "중식", "일식", "restaurant")) else "PLACE"

    @staticmethod
    def _date_skeleton(trip):
        return [trip.start_date + timedelta(days=index) for index in range((trip.end_date - trip.start_date).days + 1)]

    def _normalize_draft_dates(self, draft, trip):
        """Use the persisted trip range as the source of truth for dates."""
        if not isinstance(draft, GeneratedPlanDraft) or not isinstance(draft.days, list):
            raise self._provider_error()
        expected = self._date_skeleton(trip)
        by_date = {}
        for day in draft.days:
            if not isinstance(day, PlanDraftDay) or day.visit_date not in expected or day.visit_date in by_date:
                raise self._provider_error()
            by_date[day.visit_date] = day
        if not by_date:
            raise self._provider_error()
        normalized_days = [
            by_date.get(visit_date, PlanDraftDay(visit_date, [
                PlanDraftItem(1, "FREE_TIME", "자유 시간", None, "09:00", "18:00", "일정 미구성 시간"),
            ]))
            for visit_date in expected
        ]
        return GeneratedPlanDraft(days=normalized_days)

    def _prepare_draft(self, draft, candidate_places, anchor_ids, trip=None):
        """Canonicalize model output before strict validation/persistence.

        Candidate data is authoritative for names and roles. Repeated IDs are
        safely converted to free time; if an anchor is missing, duplicate slots
        are first repurposed to that verified anchor.
        """
        if not isinstance(draft, GeneratedPlanDraft):
            raise self._provider_error()
        used, duplicate_slots, empty_slots = set(), [], []
        for day in draft.days:
            for index, item in enumerate(day.items):
                if item.place_id is None:
                    if item.item_type in {"PLACE", "MEAL"}:
                        day.items[index] = PlanDraftItem(item.sequence, "FREE_TIME", "자유 시간", None, item.start_time, item.end_time, item.recommendation_reason)
                    continue
                place = candidate_places.get(item.place_id)
                if place is None:
                    continue  # _validate_draft reports unknown IDs; never persist them.
                if item.place_id in used:
                    duplicate_slots.append((day, index, item))
                    continue
                used.add(item.place_id)
                day.items[index] = PlanDraftItem(item.sequence, self._canonical_item_type(place), place.name, item.place_id, item.start_time, item.end_time, item.recommendation_reason)
        # An omitted anchor can safely replace a factual-free slot; the anchor
        # itself is verified candidate data, never a fabricated place.
        for day in draft.days:
            for index, item in enumerate(day.items):
                if item.place_id is None and item.item_type in {"REST", "FREE_TIME"}:
                    empty_slots.append((day, index, item))
        missing_anchors = [place_id for place_id in sorted(anchor_ids) if place_id not in used]
        replacement_slots = duplicate_slots + empty_slots
        for place_id, (day, index, item) in zip(missing_anchors, replacement_slots):
            place = candidate_places[place_id]
            day.items[index] = PlanDraftItem(item.sequence, self._canonical_item_type(place), place.name, place_id, item.start_time, item.end_time, item.recommendation_reason)
            used.add(place_id)
        # Only duplicate place slots are normalized to free time. Original REST
        # and FREE_TIME slots remain intact unless one was needed for a missing
        # required anchor.
        consumed_duplicates = min(len(missing_anchors), len(duplicate_slots))
        for day, index, item in duplicate_slots[consumed_duplicates:]:
            day.items[index] = PlanDraftItem(item.sequence, "FREE_TIME", "자유 시간", None, item.start_time, item.end_time, item.recommendation_reason)
        if trip is not None:
            available = [place_id for place_id, place in candidate_places.items() if place_id not in used and not _is_food_or_cafe(place)]
            for day in draft.days:
                has_non_food = any(item.place_id in candidate_places and not _is_food_or_cafe(candidate_places[item.place_id]) for item in day.items)
                if has_non_food or not available:
                    continue
                slot = next((index for index, item in enumerate(day.items) if item.place_id is None and item.item_type in {"REST", "FREE_TIME"}), None)
                if slot is None:
                    slot = self._excess_food_slot(day.items, candidate_places)
                if slot is None:
                    continue
                item = day.items[slot]
                place_id = available.pop(0)
                place = candidate_places[place_id]
                day.items[slot] = PlanDraftItem(item.sequence, self._canonical_item_type(place), place.name, place_id, item.start_time, item.end_time, item.recommendation_reason)
                used.add(place_id)
        return draft

    @staticmethod
    def _excess_food_slot(items, candidate_places):
        """A food/cafe item that follows another one, else the last of 2+ food items.
        Only such extra stops are swapped for an unused verified activity."""
        food = [
            index for index, item in enumerate(items)
            if item.place_id in candidate_places and _is_food_or_cafe(candidate_places[item.place_id])
        ]
        for previous, current in zip(food, food[1:]):
            if current == previous + 1:
                return current
        return food[-1] if len(food) >= 2 else None

    def _validate_draft(self, draft, candidate_ids):
        if not isinstance(draft, GeneratedPlanDraft) or not isinstance(draft.days, list) or not draft.days:
            raise self._provider_error()
        result = []
        for day in draft.days:
            if not isinstance(day, PlanDraftDay) or not isinstance(day.visit_date, date) or not isinstance(day.items, list):
                raise self._provider_error()
            sequences = set()
            valid_items = []
            for item in day.items:
                if not isinstance(item, PlanDraftItem) or not isinstance(item.sequence, int) or item.sequence in sequences:
                    raise self._provider_error()
                sequences.add(item.sequence)
                if item.item_type not in {"PLACE", "MEAL", "REST", "FREE_TIME"} or not isinstance(item.title, str) or not item.title:
                    raise self._provider_error()
                if item.place_id is not None and (not isinstance(item.place_id, int) or item.place_id not in candidate_ids):
                    raise self._provider_error()
                if item.item_type == "PLACE" and item.place_id is None:
                    raise self._provider_error()
                try:
                    start_time = time.fromisoformat(item.start_time) if item.start_time else None
                    end_time = time.fromisoformat(item.end_time) if item.end_time else None
                except (TypeError, ValueError):
                    raise self._provider_error()
                if start_time and end_time and end_time < start_time:
                    raise self._provider_error()
                valid_items.append((item, start_time, end_time))
            result.append((day.visit_date, valid_items))
        return result

    def _validate_temporal_draft(self, days, candidate_places):
        """Reject event/date and verified-hours conflicts before any writes."""
        for visit_date, items in days:
            for item, start_time, end_time in items:
                if item.place_id is None:
                    continue
                place = candidate_places[item.place_id]
                if is_event_candidate(place):
                    overlaps = event_overlaps_trip(place, visit_date, visit_date)
                    if overlaps is not True:
                        raise AppError(
                            "EVENT_DATE_MISMATCH",
                            "The event is not verified for the scheduled date",
                            422,
                        )
                if opening_hours_match(place, visit_date, start_time, end_time) is False:
                    raise AppError(
                        "OUTSIDE_OPENING_HOURS",
                        "The scheduled time is outside verified opening hours",
                        422,
                    )

    def _validate_route_timing(self, days, candidate_places, trip):
        """Reject only conflicts proven by a directions provider.

        No result means route data is unavailable, not that a guessed duration
        is acceptable.  In that case the plan carries no travel-time, route, or
        transit-connection claim.
        """
        for _, items in days:
            ordered = sorted(
                (entry for entry in items if entry[0].place_id is not None and entry[1] and entry[2]),
                key=lambda entry: entry[1],
            )
            for previous, current in zip(ordered, ordered[1:]):
                previous_item, _, previous_end = previous
                current_item, current_start, _ = current
                estimate = self._route_estimate(
                    candidate_places[previous_item.place_id],
                    candidate_places[current_item.place_id],
                    getattr(trip, "transport_mode", None),
                )
                if estimate is None:
                    continue
                required_seconds = (
                    previous_end.hour * 3600 + previous_end.minute * 60 + previous_end.second + estimate.duration_seconds
                )
                available_seconds = current_start.hour * 3600 + current_start.minute * 60 + current_start.second
                if available_seconds < required_seconds:
                    raise AppError(
                        "ROUTE_TIME_CONFLICT",
                        "The next visit starts before verified travel can be completed",
                        422,
                    )

    @staticmethod
    def _validate_activity_diversity(days, candidate_places, trip):
        """Keep verified activities as the itinerary backbone when available."""
        non_food_ids = {
            place_id for place_id, place in candidate_places.items()
            if not _is_food_or_cafe(place)
        }
        if not non_food_ids:
            return
        trip_days = (trip.end_date - trip.start_date).days + 1
        required_visits = min(trip_days, len(non_food_ids))
        non_food_by_day = [
            {
                item.place_id for item, _, _ in items
                if item.place_id in non_food_ids
            }
            for _, items in days
        ]
        actual_visits = set().union(*non_food_by_day) if non_food_by_day else set()
        if len(non_food_ids) >= trip_days:
            valid = len(non_food_by_day) >= trip_days and all(non_food_by_day)
        else:
            valid = len(actual_visits) >= required_visits
        if not valid:
            raise AppError(
                "INSUFFICIENT_NON_FOOD_ACTIVITY",
                "Verified non-food activity candidates must form the itinerary backbone",
                422,
            )

    def generate(self, user_id, trip_id, selected_place_ids):
        trip = self._owned_active_trip(user_id, trip_id)
        if self.plans.get_by_trip_id(trip_id) is not None:
            raise AppError("PLAN_ALREADY_EXISTS", "A plan already exists for this trip", 409)
        anchors = self._selected_anchors(trip, selected_place_ids)
        try:
            self.selected_places.replace(trip_id, anchors)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        trip_input, preferences, companions, interests, preference_context, candidates, anchor_ids, candidate_places = self._input(trip)
        draft = self.provider.generate_plan(trip_input, preferences, companions, interests, preference_context, candidates)
        draft = self._normalize_draft_dates(draft, trip)
        days = self._validate_draft(self._prepare_draft(draft, candidate_places, anchor_ids, trip), set(candidate_places))
        self._validate_temporal_draft(days, candidate_places)
        self._validate_route_timing(days, candidate_places, trip)
        self._validate_activity_diversity(days, candidate_places, trip)
        included_anchor_ids = {
            item.place_id
            for _, draft_items in days
            for item, _, _ in draft_items
            if item.place_id is not None
        }
        if not anchor_ids.issubset(included_anchor_ids):
            raise self._provider_error()
        try:
            plan = self.plans.create(trip_id)
            created_days = []
            for day_number, (visit_date, draft_items) in enumerate(days, start=1):
                created_items = []
                for draft_item, start_time, end_time in draft_items:
                    item = self.items.create(
                        plan.plan_id,
                        place_id=draft_item.place_id,
                        visit_date=visit_date,
                        sequence_no=draft_item.sequence,
                        item_type=draft_item.item_type,
                        title=draft_item.title,
                        start_time=start_time,
                        end_time=end_time,
                        recommendation_reason=draft_item.recommendation_reason,
                        validation_status="UNKNOWN",
                    )
                    created_items.append(item)
                created_days.append((day_number, visit_date, created_items))
            findings = self.validation.validate(plan, trip)
            if any(kind == "EVENT_DATE_MISMATCH" for _, kind, _, _ in findings):
                raise AppError("EVENT_DATE_MISMATCH", "Event dates do not match the itinerary", 422)
            if any(kind == "OUTSIDE_OPENING_HOURS" for _, kind, _, _ in findings):
                raise AppError("OUTSIDE_OPENING_HOURS", "Visit time is outside verified opening hours", 422)
            if any(severity == "CRITICAL" for _, _, severity, _ in findings):
                raise self._provider_error()
            response_days = [
                PlanDayResponse(
                    day=day_number,
                    visit_date=visit_date,
                    items=[self._response_item(item, candidate_places) for item in created_items],
                )
                for day_number, visit_date, created_items in created_days
            ]
            self.session.commit()
            return PlanGenerateResponse(
                plan_id=plan.plan_id,
                status=plan.status,
                days=response_days,
                warnings=[message for _, _, severity, message in findings if severity != "CRITICAL"],
                selected_places=self._selected_place_responses(self._stored_anchors(trip)),
            )
        except Exception:
            self.session.rollback()
            raise

    @staticmethod
    def _response_item(item, candidate_places):
        place = candidate_places.get(item.place_id) if item.place_id is not None else None
        return PlanItemResponse(
            item_id=item.item_id,
            place_id=item.place_id,
            name=place.name if place is not None else item.title,
            start_time=item.start_time,
            end_time=item.end_time,
            validation_status=item.validation_status,
            item_type=item.item_type,
            region=place.region if place is not None else None,
            address=place.address if place is not None else None,
            latitude=float(place.latitude) if place is not None and place.latitude is not None else None,
            longitude=float(place.longitude) if place is not None and place.longitude is not None else None,
            category=place.category if place is not None else None,
        )
