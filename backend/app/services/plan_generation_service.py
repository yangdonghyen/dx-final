from datetime import date, time

import logging
import threading
from contextlib import nullcontext
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
from app.repositories.user_repository import UserPreferenceRepository
from app.schemas.plan import PlanDayResponse, PlanGenerateResponse, PlanItemResponse
from app.schemas.trip import TripSelectedPlaceResponse
from app.services.exaone_interest_normalizer import normalize_exaone_interest_codes, raw_exaone_interest_codes
from app.services.external.ai.provider import GeneratedPlanDraft, PlanDraftDay, PlanDraftItem
from app.services.external.place.region_resolver import (
    RegionResolver,
    city_level_region,
    normalize_administrative_name,
)
from app.services.external.routing.cached_provider import CachedRouteProvider
from app.services.external.routing.provider import UnavailableRouteProvider
from app.services.external.naver_api_hub_provider import UnavailableNaverCafeEvidenceProvider
from app.services.cafe_evidence_service import CafeEvidence, CafeEvidenceService, is_travel_rest_cafe
from app.services.place_search_service import PlaceSearchService
from app.services.place_hours_enrichment_service import PlaceHoursEnrichmentService
from app.services.plan_travel_time import TravelShiftConflict, route_legs, shift_day_for_travel, travel_columns, travel_response_fields, travel_statuses
from app.services.plan_quality_rules import CANDIDATE_AREA_METERS, PlanQualityRules, candidate_supply, distance_meters, is_cafe, is_restaurant, same_location
from app.services.plan_validation_service import PlanValidationService
from app.services.plan_opening_hours_adjustment import adjust_day_for_opening_hours
from app.services.plan_quality_rules import DayStop, review_plan
from app.services.plan_route_optimizer import far_meals, insert_rest_breaks, optimize_routes, route_length, route_metric_length
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
# Searched when the destination's cached places are mostly restaurants.
ACTIVITY_SEARCH_QUERIES = ("관광지", "문화시설", "공원", "박물관")
# Verified non-food places wanted per trip day before the model is asked.
ACTIVITY_CANDIDATES_PER_DAY = 2
# A STANDARD pace can use a third sight a day unless the traveller rests often.
ACTIVITY_CANDIDATES_PER_DAY_BY_STYLE = {"STANDARD": 3}
# Lunch and dinner each need a verified restaurant; food-focused trips get one spare.
RESTAURANT_CANDIDATES_PER_DAY = 2
RESTAURANT_CANDIDATES_PER_DAY_BY_STYLE = {"FOOD_FOCUSED": 3}
# Searched when there are fewer verified restaurants than meal slots.
MEAL_SEARCH_QUERIES = ("맛집", "음식점")
# A sightseeing area should have a verified restaurant this close (straight line);
# otherwise "<district> 맛집" is searched for it, for at most this many areas.
NEAR_MEAL_METERS = 3000
AREA_MEAL_SEARCHES = 3
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
REST_CAFE_RADII_METERS = (500, 1500)
REST_CAFE_LIMIT = 5
REST_CAFE_REASON = "검증된 Kakao 카페를 기존 휴식 시간에 연결했습니다. 영업시간 정보가 없으면 영업 중이라고 단정하지 않습니다."
REST_CAFE_UNDECIDED = "휴식 장소 미정"
# A normal cafe stop is a drink/rest activity, not a sightseeing block.  There
# is currently no trip-preference field for a user-requested long cafe stay,
# so an anchor is deliberately left unchanged: it is the only explicit user
# selection signal available to this layer.
DEFAULT_CAFE_VISIT_MINUTES = 60
# Missing-meal repair runs before route-order optimisation.  Reserve half of
# the fixed candidate-route budget for it, so two meal slots can compare real
# incoming/outgoing legs without starving the later optimiser and REST checks.
MEAL_ROUTE_CANDIDATE_MAX_CALLS = 8
# A restaurant just before the dinner window can be delayed into that window
# only when its existing duration and all neighbouring slots still fit.  This
# is a bounded timetable correction, never a reclassification of a 16:42 meal.
MAX_MEAL_WINDOW_SHIFT_MINUTES = 30

# A Kakao category leaf can identify a chain (for example, a coffee brand),
# while generic leaves only describe a type of venue.  The key is used solely
# to spread a fixed NAVER lookup budget across the already returned candidates;
# it is not a brand preference or exclusion rule.
_GENERIC_CAFE_CATEGORY_LEAVES = frozenset({
    "\uce74\ud398", "\ucee4\ud53c\uc804\ubb38\uc810", "\ubca0\uc774\ucee4\ub9ac", "\ub514\uc800\ud2b8",
    "\ub85c\uc2a4\ud130\ub9ac", "\ube0c\ub7f0\uce58", "\ucc3b\uc9d1", "\ud2f0\ud558\uc6b0\uc2a4", "\uc74c\ub8cc", "ce7",
})
_GENERIC_CAFE_CATEGORY_SUFFIXES = ("\uce74\ud398",)

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


def _is_generic_cafe_category_leaf(normalized_leaf: str) -> bool:
    """Keep venue-type categories out of chain grouping.

    Category text such as ``북카페`` or ``루프탑카페`` describes an
    independent venue type, not a reliable business identity.  A false
    negative here only loses lookup interleaving; a false positive could make
    unrelated cafes compete for the same scarce evidence turn.
    """
    return (not normalized_leaf or normalized_leaf in _GENERIC_CAFE_CATEGORY_LEAVES
            or normalized_leaf.endswith(_GENERIC_CAFE_CATEGORY_SUFFIXES))


def _cafe_lookup_family_key(cafe):
    """Return a generic chain-family key only when Kakao supplies one.

    Generic category leaves are deliberately kept unique: they cannot safely
    establish that two independently named cafes are part of one business.
    """
    category = str(getattr(cafe, "category", "") or "")
    leaf = category.split(">")[-1].strip()
    normalized_leaf = "".join(char for char in leaf.casefold() if char.isalnum())
    if not _is_generic_cafe_category_leaf(normalized_leaf):
        return "category", normalized_leaf
    return "place", getattr(cafe, "place_id", id(cafe))


def _diverse_cafe_lookup_order(cafes):
    """Interleave Kakao chain families without changing the candidate set.

    Input order remains the distance order supplied by Kakao.  This only
    changes which candidates receive the fixed, scarce NAVER evidence checks
    first; routing and final selection retain their own explicit ranking.
    """
    families = {}
    for cafe in cafes:
        families.setdefault(_cafe_lookup_family_key(cafe), []).append(cafe)
    ordered = []
    while families:
        for key in tuple(families):
            ordered.append(families[key].pop(0))
            if not families[key]:
                del families[key]
    return ordered

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


class _GenerationRegistry:
    """Trips whose first plan is being generated by this server process.

    The model call can outlive the client's HTTP connection.  While it runs,
    a second generate request must not start another model call, and a
    client that lost its connection can ask whether the plan is still coming.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._trip_ids = set()

    def acquire(self, trip_id) -> bool:
        with self._lock:
            if trip_id in self._trip_ids:
                return False
            self._trip_ids.add(trip_id)
            return True

    def release(self, trip_id) -> None:
        with self._lock:
            self._trip_ids.discard(trip_id)

    def is_running(self, trip_id) -> bool:
        with self._lock:
            return trip_id in self._trip_ids


GENERATIONS_IN_PROGRESS = _GenerationRegistry()


def plan_generation_in_progress_error(trip_id):
    return AppError(
        "PLAN_GENERATION_IN_PROGRESS",
        "A plan is still being generated for this trip",
        409,
        {"trip_id": trip_id},
    )


def plan_already_exists_error(plan):
    return AppError(
        "PLAN_ALREADY_EXISTS",
        "A plan already exists for this trip",
        409,
        {"plan_id": plan.plan_id},
    )


class PlanGenerationService:
    def __init__(self, session, provider, place_provider=None, route_provider=None, naver_cafe_provider=None, tour_hours_provider=None, tour_hours_max_places=8):
        self.session = session
        self.provider = provider
        self.place_provider = place_provider
        self.route_provider = route_provider or UnavailableRouteProvider()
        self.naver_cafe_provider = naver_cafe_provider or UnavailableNaverCafeEvidenceProvider()
        self.tour_hours_provider = tour_hours_provider
        self.tour_hours_max_places = tour_hours_max_places
        self.trips = TripRepository(session)
        self.preferences = TripPreferenceRepository(session)
        self.user_preferences = UserPreferenceRepository(session)
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

    def _recover_lunch_from_rest(self, draft, candidate_places, anchor_ids, used, trip, preferences, meal_route_start):
        """Create a lunch between a preserved REST and the next fixed visit.

        This is intentionally a narrow recovery for a SLOW/high-rest day: a
        non-anchor sightseeing visit immediately before an unlocated REST may
        be shortened, but never below one hour; the REST keeps its full
        duration and only moves earlier.  A real restaurant is inserted only
        when both adjacent route facts fit before the existing next visit.
        """
        preferences = preferences or {}
        if not (preferences.get("travel_style") == "SLOW" or preferences.get("rest_frequency") == "HIGH"):
            return
        if isinstance(self.route_provider, UnavailableRouteProvider):
            return
        rules = self.quality_rules
        cached_routes = isinstance(self.route_provider, CachedRouteProvider)
        route_ceiling = (
            min(getattr(self.route_provider, "max_candidate_calls", 0), meal_route_start + MEAL_ROUTE_CANDIDATE_MAX_CALLS)
            if cached_routes else None
        )

        def clock(value):
            try:
                return time.fromisoformat(value) if value else None
            except (TypeError, ValueError):
                return None

        def minute(value):
            return value.hour * 60 + value.minute

        def text(value):
            return f"{value.hour:02d}:{value.minute:02d}"

        def duration_seconds(first, second):
            estimate = self._route_estimate(first, second, getattr(trip, "transport_mode", None))
            value = getattr(estimate, "duration_seconds", None)
            return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

        for day in draft.days:
            timed = [item for item in day.items if clock(item.start_time) and clock(item.end_time)]
            if not timed:
                continue
            day_start = min(clock(item.start_time) for item in timed)
            day_end = max(clock(item.end_time) for item in timed)
            if not rules.expects_meal(day_start, day_end, rules.lunch):
                continue
            if any(
                item.place_id in candidate_places
                and is_restaurant(candidate_places[item.place_id])
                and rules.lunch.contains(clock(item.start_time))
                for item in day.items
            ):
                continue
            rest_index = next((
                index for index, item in enumerate(day.items)
                if item.item_type == "REST" and item.place_id is None
                and clock(item.start_time) is not None and clock(item.end_time) is not None
            ), None)
            if rest_index is None:
                continue
            previous_index = next((
                index for index in range(rest_index - 1, -1, -1)
                if day.items[index].place_id in candidate_places
            ), None)
            next_index = next((
                index for index in range(rest_index + 1, len(day.items))
                if day.items[index].place_id in candidate_places
            ), None)
            if previous_index is None or next_index is None:
                continue
            previous_item, rest_item, next_item = day.items[previous_index], day.items[rest_index], day.items[next_index]
            previous_place = candidate_places[previous_item.place_id]
            next_place = candidate_places[next_item.place_id]
            previous_start, rest_start, rest_end, next_start = (
                clock(previous_item.start_time), clock(rest_item.start_time), clock(rest_item.end_time), clock(next_item.start_time)
            )
            if (
                previous_item.place_id in anchor_ids
                or _is_food_or_cafe(previous_place)
                or previous_start is None or rest_start is None or rest_end is None or next_start is None
            ):
                continue
            rest_minutes = minute(rest_end) - minute(rest_start)
            if rest_minutes <= 0:
                continue
            restaurant_ids = [
                place_id for place_id, place in candidate_places.items()
                if place_id not in used and is_restaurant(place) and not is_event_candidate(place)
            ]
            scored = []
            context = self.route_provider.candidate_phase() if cached_routes else nullcontext()
            with context:
                for place_id in restaurant_ids:
                    if cached_routes and self.route_provider.candidate_calls + 2 > route_ceiling:
                        break
                    restaurant = candidate_places[place_id]
                    before_seconds = duration_seconds(previous_place, restaurant)
                    after_seconds = duration_seconds(restaurant, next_place)
                    if before_seconds is None or after_seconds is None:
                        continue
                    before_minutes = -(-before_seconds // 60)
                    after_minutes = -(-after_seconds // 60)
                    lunch_end = minute(next_start) - after_minutes
                    lunch_start = lunch_end - 60
                    rest_end_new = lunch_start - before_minutes
                    rest_start_new = rest_end_new - rest_minutes
                    if (
                        lunch_start < minute(rules.lunch.start)
                        or lunch_end > minute(rules.lunch.end)
                        or rest_start_new - minute(previous_start) < 60
                    ):
                        continue
                    lunch_start_time = time(lunch_start // 60, lunch_start % 60)
                    lunch_end_time = time(lunch_end // 60, lunch_end % 60)
                    if opening_hours_match(restaurant, day.visit_date, lunch_start_time, lunch_end_time) is False:
                        continue
                    scored.append((before_seconds + after_seconds, place_id, rest_start_new, rest_end_new, lunch_start, lunch_end))
            if not scored:
                continue
            _, place_id, rest_start_new, rest_end_new, lunch_start, lunch_end = min(scored)
            restaurant = candidate_places[place_id]
            changed = list(day.items)
            changed[previous_index] = PlanDraftItem(
                previous_item.sequence, previous_item.item_type, previous_item.title, previous_item.place_id,
                previous_item.start_time, text(time(rest_start_new // 60, rest_start_new % 60)), previous_item.recommendation_reason,
            )
            changed[rest_index] = PlanDraftItem(
                rest_item.sequence, rest_item.item_type, rest_item.title, None,
                text(time(rest_start_new // 60, rest_start_new % 60)), text(time(rest_end_new // 60, rest_end_new % 60)), rest_item.recommendation_reason,
            )
            changed.append(PlanDraftItem(0, "MEAL", restaurant.name, place_id, text(time(lunch_start // 60, lunch_start % 60)), text(time(lunch_end // 60, lunch_end % 60)), "Verified route-feasible lunch inserted while preserving the rest break."))
            changed.sort(key=lambda item: (clock(item.start_time) or time.max, item.sequence))
            # PlanDraftDay is frozen, while its item list is intentionally
            # mutable during deterministic draft repair.
            day.items[:] = [
                PlanDraftItem(index, item.item_type, item.title, item.place_id, item.start_time, item.end_time, item.recommendation_reason)
                for index, item in enumerate(changed, start=1)
            ]
            used.add(place_id)
            logger.info(
                "plan_lunch_recovered trip_id=%s visit_date=%s place_id=%s rest_preserved_minutes=%s shortened_place_id=%s",
                getattr(trip, "trip_id", None), day.visit_date, place_id, rest_minutes, previous_item.place_id,
            )

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
        # A request-scoped cache caps these calls so itinerary validation keeps its budget.
        cached = isinstance(self.route_provider, CachedRouteProvider)
        with self.route_provider.candidate_phase() if cached else nullcontext():
            estimates_by_candidate = [
                (candidate, [self._route_estimate(anchor, candidate, mode) for anchor in anchors])
                for candidate in candidates
                if candidate not in anchors
            ]
        for candidate, estimates in estimates_by_candidate:
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
    def _candidate_targets(trip_days, preferences=None):
        """Verified places wanted before the model is asked, from the trip's own facts.

        Sights follow the chosen pace (a traveller who rests often gets the
        slower count); restaurants cover lunch and dinner on every day; areas
        ask for at least two sightseeing areas on a multi-day trip.
        """
        preferences = preferences or {}
        style = preferences.get("travel_style")
        sights_per_day = ACTIVITY_CANDIDATES_PER_DAY_BY_STYLE.get(style, ACTIVITY_CANDIDATES_PER_DAY)
        if preferences.get("rest_frequency") == "HIGH":
            sights_per_day = ACTIVITY_CANDIDATES_PER_DAY
        return {
            "sights": trip_days * sights_per_day,
            "restaurants": trip_days * RESTAURANT_CANDIDATES_PER_DAY_BY_STYLE.get(style, RESTAURANT_CANDIDATES_PER_DAY),
            "areas": min(trip_days, 2) if trip_days >= 2 else 1,
        }

    @staticmethod
    def _interleave_by_area(places):
        """Round-robin over sightseeing areas so one shore cannot fill the reserve.

        Areas group places within CANDIDATE_AREA_METERS of an area's first
        place (stored coordinates only).  Places without coordinates keep their
        order at the end.  Order inside an area is unchanged.
        """
        areas, unplaced = [], []
        for place in places:
            if getattr(place, "latitude", None) is None or getattr(place, "longitude", None) is None:
                unplaced.append(place)
                continue
            home = next((area for area in areas if (distance_meters(area[0], place) or float("inf")) <= CANDIDATE_AREA_METERS), None)
            if home is None:
                areas.append([place])
            else:
                home.append(place)
        ordered = []
        for index in range(max((len(area) for area in areas), default=0)):
            ordered.extend(area[index] for area in areas if index < len(area))
        return ordered + unplaced

    @staticmethod
    def _sight_areas(places):
        areas = []
        for place in places:
            if getattr(place, "latitude", None) is None or getattr(place, "longitude", None) is None:
                continue
            home = next((area for area in areas if (distance_meters(area[0], place) or float("inf")) <= CANDIDATE_AREA_METERS), None)
            if home is None:
                areas.append([place])
            else:
                home.append(place)
        return areas

    @classmethod
    def _restaurants_by_area(cls, restaurants, sights):
        """Nearest verified restaurant for each sight area in turn, then the rest.

        Only restaurants within NEAR_MEAL_METERS (straight line) of an area count
        as that area's; distance only ranks, it is never a travel time."""
        ordered, taken = [], set()
        queues = []
        for area in cls._sight_areas(sights):
            near = sorted(
                (row for row in restaurants if (distance_meters(area[0], row) or float("inf")) <= NEAR_MEAL_METERS),
                key=lambda row: distance_meters(area[0], row),
            )
            queues.append(near)
        for index in range(max((len(queue) for queue in queues), default=0)):
            for queue in queues:
                if index < len(queue) and queue[index].place_id not in taken:
                    ordered.append(queue[index])
                    taken.add(queue[index].place_id)
        return ordered + [row for row in restaurants if row.place_id not in taken]

    @classmethod
    def _balanced_candidate_pool(cls, candidates, anchors, trip, targets=None):
        """Reserve verified sights (spread over areas) and meal restaurants first."""
        anchor_ids = {anchor.place_id for anchor in anchors}
        selected = [candidate for candidate in candidates if candidate.place_id in anchor_ids]
        automatic = [candidate for candidate in candidates if candidate.place_id not in anchor_ids]
        activities = cls._interleave_by_area([candidate for candidate in automatic if not _is_food_or_cafe(candidate)])
        food_or_cafes = [candidate for candidate in automatic if _is_food_or_cafe(candidate)]
        restaurants = cls._restaurants_by_area([candidate for candidate in food_or_cafes if is_restaurant(candidate)], activities)
        trip_days = (trip.end_date - trip.start_date).days + 1
        targets = targets or cls._candidate_targets(trip_days)
        # Reserve about half the pool (at least two per day) for activities so
        # the model cannot fill whole days with restaurants.
        reserve_count = min(len(activities), max(trip_days * 2, MAX_PLAN_CANDIDATES // 2))
        meal_reserve = min(len(restaurants), targets["restaurants"])

        def append_until_limit(rows):
            for row in rows:
                if row not in selected and len(selected) < MAX_PLAN_CANDIDATES:
                    selected.append(row)

        # The reserve makes an actual activity available for each full day
        # when the verified pool has enough distinct activity candidates, and a
        # restaurant for each lunch and dinner before cafes take the room.
        append_until_limit(activities[:reserve_count])
        append_until_limit(restaurants[:meal_reserve])
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
        # A pool can reach desired_count with restaurants alone (trip 67 had one
        # sight for three days), so sights are searched for on their own, and
        # also when every cached sight sits in one area (trip 68).  Restaurants
        # for lunch and dinner are checked the same way.
        targets = self._candidate_targets(trip_days, preferences)
        self._append_unique(candidates, self._activity_backfill(trip, candidates, targets["sights"], targets["areas"]))
        self._append_unique(candidates, self._meal_backfill(trip, candidates, targets["restaurants"]))
        candidates = self._drop_same_location(candidates, anchor_ids)
        if len(candidates) < MIN_PLAN_CANDIDATES:
            raise AppError(
                "INSUFFICIENT_PLACE_CANDIDATES",
                "Could not find enough verified places near the selected locations",
                422,
            )
        candidates = self._mobility_candidates(candidates, anchors, trip, preferences or {})
        pool = self._balanced_candidate_pool(candidates, anchors, trip, targets)
        self._log_activity_shortage(trip, pool, trip_days, targets)
        return pool

    def _activity_backfill(self, trip, candidates, needed, areas_needed=1):
        """Verified non-food places from the destination when too few are cached,
        or when the cached ones cover fewer sightseeing areas than the trip needs."""
        have = sum(not _is_food_or_cafe(place) for place in candidates)

        def enough(found):
            if have + len(found) < needed:
                return False
            return candidate_supply(list(candidates) + list(found), 1)["areas"] >= areas_needed

        if enough([]) or self.place_provider is None or not hasattr(self.place_provider, "search"):
            return []
        search_service = PlaceSearchService(self.session, self.place_provider)
        found = []
        excluded_ids = {place.place_id for place in candidates}
        for query in ACTIVITY_SEARCH_QUERIES:
            try:
                upserted = search_service.upsert_candidates(
                    self.place_provider.search(query, trip.destination), trip.destination
                )
            except AppError:
                continue
            additions = []
            for item in upserted:
                place = self.places.get(item.place_id)
                if (place is not None and place.place_id not in excluded_ids
                        and self._matches_destination(place, trip.destination)
                        and _is_usable_plan_candidate(place)
                        and not _is_food_or_cafe(place)
                        and self._is_temporally_eligible(place, trip)):
                    additions.append(place)
            self._append_unique(found, additions)
            excluded_ids.update(place.place_id for place in found)
            if enough(found):
                break
        logger.info(
            "plan_candidate_activity_backfill trip_id=%s needed=%s areas_needed=%s cached=%s found=%s",
            getattr(trip, "trip_id", None), needed, areas_needed, have, len(found),
        )
        return found

    @staticmethod
    def _district(place):
        """The 구/군 (else 시) token of a stored address, e.g. '사하구'."""
        tokens = (getattr(place, "address", None) or "").split()
        return next((token for token in tokens[1:] if token.endswith(("구", "군"))), None) or next(
            (token for token in tokens[1:] if token.endswith("시")), None)

    def _area_meal_backfill(self, trip, candidates, search_service, excluded_ids):
        """Search "<district> 맛집" for sight areas with no verified restaurant nearby.

        Keeps only provider results that are restaurants within NEAR_MEAL_METERS
        of that area; an area with none stays without one (reported, not invented)."""
        sights = [place for place in candidates if not _is_food_or_cafe(place)]
        restaurants = [place for place in candidates if is_restaurant(place)]
        found, searched = [], 0
        for area in self._sight_areas(sights):
            center = area[0]
            if any((distance_meters(center, row) or float("inf")) <= NEAR_MEAL_METERS for row in restaurants + found):
                continue
            district = self._district(center)
            if district is None or searched >= AREA_MEAL_SEARCHES:
                continue
            searched += 1
            try:
                upserted = search_service.upsert_candidates(self.place_provider.search(f"{district} 맛집", trip.destination), trip.destination)
            except AppError:
                continue
            for item in upserted:
                place = self.places.get(item.place_id)
                if (place is not None and place.place_id not in excluded_ids and is_restaurant(place)
                        and self._matches_destination(place, trip.destination) and _is_usable_plan_candidate(place)
                        and self._is_temporally_eligible(place, trip)
                        and (distance_meters(center, place) or float("inf")) <= NEAR_MEAL_METERS):
                    found.append(place)
                    excluded_ids.add(place.place_id)
                    break
        if searched:
            logger.info("plan_candidate_area_meal_backfill trip_id=%s searched=%s found=%s",
                        getattr(trip, "trip_id", None), searched, len(found))
        return found

    def _meal_backfill(self, trip, candidates, needed):
        """Verified restaurants from the existing place provider when there are
        fewer than lunch and dinner slots.  Only provider results are used."""
        have = sum(is_restaurant(place) for place in candidates)
        if self.place_provider is None or not hasattr(self.place_provider, "search"):
            return []
        search_service = PlaceSearchService(self.session, self.place_provider)
        found = []
        excluded_ids = {place.place_id for place in candidates}
        found.extend(self._area_meal_backfill(trip, candidates, search_service, excluded_ids))
        excluded_ids.update(place.place_id for place in found)
        for query in MEAL_SEARCH_QUERIES if have + len(found) < needed else ():
            try:
                upserted = search_service.upsert_candidates(
                    self.place_provider.search(query, trip.destination), trip.destination
                )
            except AppError:
                continue
            additions = []
            for item in upserted:
                place = self.places.get(item.place_id)
                if (place is not None and place.place_id not in excluded_ids
                        and self._matches_destination(place, trip.destination)
                        and _is_usable_plan_candidate(place)
                        and is_restaurant(place)
                        and self._is_temporally_eligible(place, trip)):
                    additions.append(place)
            self._append_unique(found, additions)
            excluded_ids.update(place.place_id for place in found)
            if have + len(found) >= needed:
                break
        logger.info(
            "plan_candidate_meal_backfill trip_id=%s needed=%s cached=%s found=%s",
            getattr(trip, "trip_id", None), needed, have, len(found),
        )
        return found

    @staticmethod
    def _drop_same_location(candidates, anchor_ids):
        """Keep one row per real spot (two Kakao entries can share one address)."""
        kept = []
        for place in candidates:
            if place.place_id not in anchor_ids and any(same_location(place, other) for other in kept):
                continue
            kept.append(place)
        return kept

    @staticmethod
    def _log_activity_shortage(trip, pool, trip_days, targets=None):
        """Fewer verified sights than days: some days can only be meals.

        Generation still runs (an error would leave the user with nothing);
        validation stores a FOOD_ONLY_DAY warning on each such day instead.
        """
        supply = candidate_supply(pool, trip_days, targets=targets)
        logger.info(
            "plan_candidate_supply trip_id=%s days=%s pool=%s sights=%s restaurants=%s areas=%s sight_types=%s problems=%s shortfall=%s",
            getattr(trip, "trip_id", None), trip_days, supply["total"], supply["sights"], supply["restaurants"], supply["areas"],
            len(supply["sight_types"]), ",".join(supply["problems"]) or "none",
            ",".join(f"{key}:{value}" for key, value in supply["shortfall"].items() if value) or "none",
        )
        activities = sum(not _is_food_or_cafe(place) for place in pool)
        if activities < trip_days:
            logger.info(
                "plan_candidate_activity_shortage trip_id=%s days=%s activities=%s pool=%s",
                getattr(trip, "trip_id", None), trip_days, activities, len(pool),
            )

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
        # This only consults TourAPI for places that already hold a trusted
        # Tour content ID.  It never guesses a cross-provider identity.
        PlaceHoursEnrichmentService(
            self.session, self.tour_hours_provider, max_places=self.tour_hours_max_places,
        ).enrich(places)
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

    def _prepare_draft(self, draft, candidate_places, anchor_ids, trip=None, preferences=None):
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
        self._normalize_cafe_durations(draft, candidate_places, anchor_ids)
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
            self._repair_meal_slots(draft, candidate_places, anchor_ids, available, used, getattr(trip, "trip_id", None))
            meal_route_start = getattr(self.route_provider, "candidate_calls", 0)
            self._repair_missing_meals(draft, candidate_places, anchor_ids, available, used, trip, preferences, meal_route_start)
            self._recover_lunch_from_rest(draft, candidate_places, anchor_ids, used, trip, preferences, meal_route_start)
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
    def _normalize_cafe_durations(draft, candidate_places, anchor_ids):
        """Keep an unanchored cafe from consuming a sightseeing-length slot.

        Candidate category is the only verified role fact here.  The released
        portion simply becomes an earlier end of the cafe visit; it is not
        labelled as walking, rest, or a location-specific activity.  An anchor
        is retained exactly as requested because this service has no separate,
        persisted "long cafe stay" preference.
        """
        for day in draft.days:
            for index, item in enumerate(day.items):
                place = candidate_places.get(item.place_id)
                if place is None or item.place_id in anchor_ids or not is_cafe(place):
                    continue
                try:
                    start, end = time.fromisoformat(item.start_time), time.fromisoformat(item.end_time)
                except (TypeError, ValueError):
                    continue
                duration = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
                if duration <= DEFAULT_CAFE_VISIT_MINUTES:
                    continue
                finish = start.hour * 60 + start.minute + DEFAULT_CAFE_VISIT_MINUTES
                if finish >= 24 * 60:
                    continue
                end_text = f"{finish // 60:02d}:{finish % 60:02d}"
                day.items[index] = PlanDraftItem(
                    item.sequence, item.item_type, item.title, item.place_id,
                    item.start_time, end_text, item.recommendation_reason,
                )
                logger.info(
                    "plan_cafe_duration_normalized visit_date=%s sequence=%s place_id=%s from_minutes=%s to_minutes=%s",
                    day.visit_date, item.sequence, item.place_id, duration, DEFAULT_CAFE_VISIT_MINUTES,
                )

    def _quality_findings(self, draft, candidate_places, route_seconds=None):
        """Quality findings, optionally carrying verified route facts per leg.

        A supplied callback returns provider seconds only.  It is used while a
        real-route optimisation is being considered so the quality rules do
        not label that same measured leg as an *unverified* straight-line
        distance.  Missing facts remain ``None`` and retain their warning.
        """
        days = []
        for number, day in enumerate(draft.days, start=1):
            stops = []
            previous_place = None
            for item in day.items:
                try:
                    start = time.fromisoformat(item.start_time) if item.start_time else None
                    end = time.fromisoformat(item.end_time) if item.end_time else None
                except (TypeError, ValueError):
                    start = end = None
                place = candidate_places.get(item.place_id)
                travel_minutes = None
                if place is not None and previous_place is not None and route_seconds is not None:
                    seconds = route_seconds(previous_place, place)
                    if isinstance(seconds, int) and not isinstance(seconds, bool) and seconds > 0:
                        travel_minutes = -(-seconds // 60)
                stops.append(DayStop(item.sequence, item.item_type, start, end, place, travel_minutes))
                if place is not None:
                    previous_place = place
            days.append((f"{number}일차", stops))
        return review_plan(days, self.quality_rules)

    def _checked(self, candidate, baseline, candidate_places, trip, route_seconds=None):
        """None when ``candidate`` passes the model draft's validation and adds no quality warning."""
        try:
            checked = self._validate_draft(candidate, set(candidate_places))
            self._validate_temporal_draft(checked, candidate_places)
            self._validate_activity_diversity(checked, candidate_places, trip)
        except AppError as exc:
            return f"validation:{exc.code}"
        if len(self._quality_findings(candidate, candidate_places, route_seconds)) > len(self._quality_findings(baseline, candidate_places, route_seconds)):
            return "more_quality_warnings"
        return None

    def _optimize_routes(self, draft, candidate_places, anchor_ids, trip, preferences=None):
        """Initial generation only: same-slot swaps that shorten each day's route.

        With an unavailable provider, the established straight-line heuristic
        remains the conservative fallback.  With a configured provider, only
        complete verified route-duration comparisons can change a slot order;
        UNKNOWN alternatives are not converted into estimates.  The optimized
        draft is kept only if it passes the same draft, temporal, diversity,
        and quality validation as the model's draft.
        """
        trip_id = getattr(trip, "trip_id", None)
        before_m, longest_before = route_length(draft.days, candidate_places)
        report = {"applied": False, "moves": [], "before_m": round(before_m), "after_m": round(before_m),
                  "longest_leg_before_m": round(longest_before), "longest_leg_after_m": round(longest_before),
                  "metric": "STRAIGHT_LINE", "route_seconds_before": None, "route_seconds_after": None}
        self.last_route_optimization = report
        try:
            if isinstance(self.route_provider, UnavailableRouteProvider):
                optimized, moves = optimize_routes(draft, candidate_places, set(anchor_ids))
            else:
                mode = getattr(trip, "transport_mode", None)

                def route_seconds(first, second):
                    estimate = self._route_estimate(first, second, mode)
                    seconds = getattr(estimate, "duration_seconds", None)
                    return seconds if isinstance(seconds, int) and not isinstance(seconds, bool) and seconds > 0 else None

                cached = isinstance(self.route_provider, CachedRouteProvider)
                with self.route_provider.candidate_phase() if cached else nullcontext():
                    before_route = route_metric_length(draft.days, candidate_places, route_seconds)
                    optimized, moves = optimize_routes(
                        draft,
                        candidate_places,
                        set(anchor_ids),
                        route_metric=route_seconds,
                        minimum_gain=60,
                        gain_key="gain_seconds",
                    )
                    after_route = route_metric_length(optimized.days, candidate_places, route_seconds)
                report.update(
                    metric="ROUTE_SECONDS",
                    route_seconds_before=round(before_route[0]) if before_route is not None else None,
                    route_seconds_after=round(after_route[0]) if after_route is not None else None,
                )
        except (TypeError, ValueError) as exc:  # never block generation on an optimizer fault
            logger.info("plan_route_optimization_skipped trip_id=%s reason=%s", trip_id, type(exc).__name__)
            return draft
        chosen = draft
        if moves:
            reason = self._checked(
                optimized, draft, candidate_places, trip,
                route_seconds if report["metric"] == "ROUTE_SECONDS" else None,
            )
            if reason is None:
                chosen = optimized
                after_m, longest_after = route_length(optimized.days, candidate_places)
                report.update(applied=True, moves=moves, after_m=round(after_m), longest_leg_after_m=round(longest_after))
            else:
                report["reverted"] = reason
        # Rest breaks from stated rest/pace/walking preferences, checked the same way.
        rested, breaks = insert_rest_breaks(chosen, candidate_places, set(anchor_ids), preferences)
        report["rest_breaks"] = []
        if breaks:
            reason = self._checked(rested, chosen, candidate_places, trip)
            if reason is None:
                chosen = rested
                report["rest_breaks"] = breaks
            else:
                report["rest_reverted"] = reason
        report["far_meals"] = far_meals(chosen, candidate_places)
        logger.info(
            "plan_route_optimized trip_id=%s applied=%s moves=%s before_m=%s after_m=%s longest_before_m=%s longest_after_m=%s far_meals=%s rest_breaks=%s reverted=%s",
            trip_id, report["applied"], len(report["moves"]), report["before_m"], report["after_m"],
            report["longest_leg_before_m"], report["longest_leg_after_m"], len(report["far_meals"]), len(report["rest_breaks"]),
            report.get("reverted") or report.get("rest_reverted"),
        )
        return chosen

    def _attach_rest_cafes(self, draft, candidate_places, trip, preferences):
        """Replace at most one REST slot/day with a verified nearby cafe.

        REST remains a null-place contract.  A selected cafe is therefore a
        normal PLACE in exactly the same slot, preserving schema, map and
        Preview/Approve behaviour.  Both adjacent legs must have real route
        facts that fit; UNKNOWN is never treated as travel permission.
        """
        # senior_mode is a user-profile preference, not a users-table field.
        senior_mode = bool(getattr(self.user_preferences.get(trip.user_id), "senior_mode", False))
        wants_rest = senior_mode or preferences.get("rest_frequency") == "HIGH" or preferences.get("travel_style") == "SLOW"
        if not wants_rest or self.place_provider is None:
            return draft
        if isinstance(self.route_provider, UnavailableRouteProvider):
            return GeneratedPlanDraft(days=[PlanDraftDay(day.visit_date, [
                PlanDraftItem(item.sequence, item.item_type, REST_CAFE_UNDECIDED, None, item.start_time, item.end_time,
                              "실제 이동시간을 확인할 수 없어 휴식 장소를 확정하지 않았습니다.")
                if item.item_type == "REST" and item.place_id is None else item
                for item in day.items
            ]) for day in draft.days])
        search_service = PlaceSearchService(self.session, self.place_provider)
        evidence_service = CafeEvidenceService(self.naver_cafe_provider)
        selection_report = []
        optimization_report = getattr(self, "last_route_optimization", None)
        # One cafe is selected per day, so later REST items on that day are not
        # candidates.  Reserve the shared NAVER budget for the remaining days.
        rest_slots_remaining = sum(
            any(item.item_type == "REST" and item.place_id is None for item in day.items)
            for day in draft.days
        )

        def record(visit_date, result, **details):
            # This is diagnostic data only: all route durations below originate
            # from the provider and are never used as a straight-line estimate.
            selection_report.append({"visit_date": visit_date.isoformat(), "result": result, **details})

        days = []
        for day in draft.days:
            items = list(day.items)
            chosen_today = False
            for index, slot in enumerate(items):
                if chosen_today or slot.item_type != "REST" or slot.place_id is not None:
                    continue
                evidence_service.begin_rest_slot(rest_slots_remaining)
                rest_slots_remaining -= 1
                diagnostics = {
                    "kakao_candidates": 0, "industry_pass": 0,
                    "naver_matches": 0, "blog_checks": 0, "route_checks": 0,
                    "naver_local_error": None, "naver_blog_error": None,
                    "local_match_reasons": {}, "local_business_failures": {}, "review_statuses": {},
                }
                start, end = time.fromisoformat(slot.start_time), time.fromisoformat(slot.end_time)
                before = next((item for item in reversed(items[:index]) if item.place_id in candidate_places), None)
                after = next((item for item in items[index + 1:] if item.place_id in candidate_places), None)
                if before is None:
                    items[index] = PlanDraftItem(slot.sequence, "REST", REST_CAFE_UNDECIDED, None, slot.start_time, slot.end_time, "이전 방문지 좌표가 없어 실제 카페 이동을 검증할 수 없습니다.")
                    record(day.visit_date, "UNDECIDED", reason="NO_PREVIOUS_PLACE")
                    continue
                origin = candidate_places[before.place_id]
                viable = []
                cached = isinstance(self.route_provider, CachedRouteProvider)
                # The wider lookup is only used when the nearer radius had no
                # viable, route-confirmed cafe -- not merely because a cafe was
                # returned by Local search.
                for radius in REST_CAFE_RADII_METERS:
                    try:
                        found = self.place_provider.search_nearby(
                            float(origin.latitude), float(origin.longitude), radius, ["CE7"], REST_CAFE_LIMIT
                        )
                        diagnostics["kakao_candidates"] += len(found)
                        upserted = search_service.upsert_candidates(found, trip.destination) if found else []
                    except AppError:
                        upserted = []
                    raw_cafes = [self.places.get(row.place_id) for row in upserted]
                    kakao_ranks = {}
                    cafes = []
                    for kakao_rank, cafe in enumerate(raw_cafes, start=1):
                        if cafe is None:
                            logger.debug(
                                "rest_cafe_candidate trip_id=%s date=%s rest_slot=%s kakao_rank=%s outcome=PLACE_NOT_FOUND",
                                getattr(trip, "trip_id", None), day.visit_date.isoformat(), slot.sequence, kakao_rank,
                            )
                            continue
                        kakao_ranks[cafe.place_id] = kakao_rank
                        industry_pass = (
                            is_cafe(cafe) and is_travel_rest_cafe(cafe)
                            and opening_hours_match(cafe, day.visit_date, start, end) is not False
                        )
                        logger.debug(
                            "rest_cafe_candidate trip_id=%s date=%s rest_slot=%s kakao_rank=%s place_id=%s name=%r category=%r chain_group=%s industry_pass=%s outcome=%s",
                            getattr(trip, "trip_id", None), day.visit_date.isoformat(), slot.sequence, kakao_rank,
                            cafe.place_id, cafe.name, cafe.category, _cafe_lookup_family_key(cafe), industry_pass,
                            "CANDIDATE_ELIGIBLE" if industry_pass else "INDUSTRY_REJECTED",
                        )
                        if industry_pass:
                            cafes.append(cafe)
                    # Start from Kakao distance order, then spread the fixed
                    # trip-wide NAVER budget across distinct category families.
                    cafes.sort(key=lambda cafe: (distance_meters(origin, cafe) is None, distance_meters(origin, cafe) or float("inf"), cafe.place_id))
                    cafes = _diverse_cafe_lookup_order(cafes)
                    diagnostics["industry_pass"] += len(cafes)
                    with self.route_provider.candidate_phase() if cached else nullcontext():
                        for lookup_rank, cafe in enumerate(cafes, start=1):
                            try:
                                local_result = evidence_service.local_match_result(cafe)
                            except AppError as error:
                                diagnostics["naver_local_error"] = error.code
                                local_result = None
                            local_reason = getattr(local_result, "reason", "API_ERROR")
                            diagnostics["local_match_reasons"][local_reason] = diagnostics["local_match_reasons"].get(local_reason, 0) + 1
                            mismatch_condition = getattr(local_result, "mismatch_condition", None)
                            if mismatch_condition:
                                diagnostics["local_business_failures"][mismatch_condition] = diagnostics["local_business_failures"].get(mismatch_condition, 0) + 1
                            local_match = getattr(local_result, "local", None)
                            if getattr(local_result, "error_code", None):
                                diagnostics["naver_local_error"] = local_result.error_code
                            if local_match is None and local_reason == "API_ERROR":
                                logger.debug(
                                    "rest_cafe_candidate trip_id=%s date=%s rest_slot=%s kakao_rank=%s lookup_rank=%s place_id=%s name=%r naver_status=%s naver_failure=%s review_status=NOT_CHECKED preference_features=() incoming_seconds=None outgoing_seconds=None adjacent_route_seconds=None outcome=NAVER_API_ERROR",
                                    getattr(trip, "trip_id", None), day.visit_date.isoformat(), slot.sequence,
                                    kakao_ranks.get(cafe.place_id), lookup_rank, cafe.place_id, cafe.name,
                                    local_reason, mismatch_condition,
                                )
                                continue
                            if local_match is not None:
                                diagnostics["naver_matches"] += 1
                                before_blog_checks = evidence_service.blog_lookups
                                try:
                                    evidence = evidence_service.review_evidence(cafe, local_match, preferences)
                                except AppError as error:
                                    diagnostics["naver_blog_error"] = error.code
                                    evidence = None
                                if evidence is None:
                                    logger.debug(
                                        "rest_cafe_candidate trip_id=%s date=%s rest_slot=%s kakao_rank=%s lookup_rank=%s place_id=%s name=%r naver_status=%s naver_failure=%s review_status=API_ERROR preference_features=() incoming_seconds=None outgoing_seconds=None adjacent_route_seconds=None outcome=NAVER_BLOG_API_ERROR",
                                        getattr(trip, "trip_id", None), day.visit_date.isoformat(), slot.sequence,
                                        kakao_ranks.get(cafe.place_id), lookup_rank, cafe.place_id, cafe.name,
                                        local_reason, mismatch_condition,
                                    )
                                    continue
                                diagnostics["blog_checks"] += evidence_service.blog_lookups - before_blog_checks
                            else:
                                # A non-match is not proof that the Kakao venue
                                # is fictional.  It never receives review
                                # attributes, but remains route-eligible.
                                evidence = CafeEvidence(False, review_status=local_reason)
                            review_status = evidence.review_status
                            diagnostics["review_statuses"][review_status] = diagnostics["review_statuses"].get(review_status, 0) + 1
                            diagnostics["route_checks"] += 1
                            incoming = self._route_estimate(origin, cafe, trip.transport_mode)
                            outgoing = self._route_estimate(cafe, candidate_places[after.place_id], trip.transport_mode) if after else None
                            # A REST is normally carved out immediately after a
                            # long visit, so it has no *preceding* blank gap.
                            # The verified legs are instead passed to the same
                            # bounded timing-shift check used by all plan items.
                            incoming_fits = incoming is not None
                            outgoing_fits = after is None or outgoing is not None
                            route_seconds = (
                                incoming.duration_seconds + (outgoing.duration_seconds if outgoing else 0)
                                if incoming_fits and outgoing_fits else None
                            )
                            outcome = (
                                "ROUTE_ELIGIBLE" if route_seconds is not None
                                else "ROUTE_UNKNOWN_INCOMING" if not incoming_fits
                                else "ROUTE_UNKNOWN_OUTGOING"
                            )
                            logger.debug(
                                "rest_cafe_candidate trip_id=%s date=%s rest_slot=%s kakao_rank=%s lookup_rank=%s place_id=%s name=%r chain_group=%s naver_status=%s naver_failure=%s review_status=%s preference_features=%s incoming_seconds=%s outgoing_seconds=%s adjacent_route_seconds=%s outcome=%s",
                                getattr(trip, "trip_id", None), day.visit_date.isoformat(), slot.sequence,
                                kakao_ranks.get(cafe.place_id), lookup_rank, cafe.place_id, cafe.name,
                                _cafe_lookup_family_key(cafe), local_reason, mismatch_condition,
                                evidence.review_status, evidence.feature_tags,
                                incoming.duration_seconds if incoming else None,
                                outgoing.duration_seconds if outgoing else None,
                                route_seconds, outcome,
                            )
                            if incoming_fits and outgoing_fits:
                                viable.append((
                                    # A local-business match corroborates the
                                    # venue but does not itself establish
                                    # visit quality.  Only a qualifying recent
                                    # visit receives priority over another
                                    # Kakao-and-route-verified candidate.
                                    0 if evidence.verified else 1,
                                    -evidence_service.preference_score(evidence, preferences),
                                    incoming.duration_seconds + (outgoing.duration_seconds if outgoing else 0),
                                    cafe, incoming, outgoing, evidence,
                                ))
                    if viable:
                        break
                if not viable:
                    items[index] = PlanDraftItem(slot.sequence, "REST", REST_CAFE_UNDECIDED, None, slot.start_time, slot.end_time, "주변 카페 또는 실제 이동시간을 확인하지 못해 휴식 장소를 확정하지 않았습니다.")
                    if diagnostics["kakao_candidates"] == 0:
                        reason = "NO_KAKAO_CAFE"
                    elif diagnostics["industry_pass"] == 0:
                        reason = "NO_TRAVEL_REST_CAFE"
                    elif diagnostics["naver_local_error"]:
                        reason = "NAVER_LOCAL_API_FAILED"
                    elif diagnostics["naver_local_error"]:
                        reason = "NAVER_LOCAL_API_FAILED"
                    elif diagnostics["naver_blog_error"]:
                        reason = "NAVER_BLOG_API_FAILED"
                    elif diagnostics["route_checks"] == 0:
                        reason = "NO_ROUTE_CONFIRMED_CAFE"
                    else:
                        reason = "NO_ROUTE_CONFIRMED_CAFE"
                    record(day.visit_date, "UNDECIDED", reason=reason, **diagnostics)
                    continue
                _, _, route_seconds, cafe, incoming, outgoing, evidence = min(viable, key=lambda value: (value[0], value[1], value[2], value[3].place_id))
                for _, _, candidate_route_seconds, candidate, _, _, candidate_evidence in viable:
                    logger.debug(
                        "rest_cafe_candidate_final trip_id=%s date=%s rest_slot=%s place_id=%s name=%r review_status=%s preference_features=%s adjacent_route_seconds=%s outcome=%s",
                        getattr(trip, "trip_id", None), day.visit_date.isoformat(), slot.sequence,
                        candidate.place_id, candidate.name, candidate_evidence.review_status,
                        candidate_evidence.feature_tags, candidate_route_seconds,
                        "SELECTED" if candidate.place_id == cafe.place_id else "NOT_SELECTED_RANKED_LOWER",
                    )
                candidate_places[cafe.place_id] = cafe
                feature_labels = {"VIEW": "전망", "DESSERT": "디저트", "QUIET": "조용한 휴식"}
                confirmed_features = [feature_labels[tag] for tag in evidence.feature_tags if tag in feature_labels]
                reason = REST_CAFE_REASON if not confirmed_features else (
                    "검증된 Kakao 카페와 네이버 검색의 실제 방문 후기에서 언급된 "
                    f"{', '.join(confirmed_features)} 특징을 기존 휴식 시간에 연결했습니다."
                )
                items[index] = PlanDraftItem(slot.sequence, "PLACE", cafe.name, cafe.place_id, slot.start_time, slot.end_time, reason)
                record(
                    day.visit_date,
                    "SELECTED",
                    place_id=cafe.place_id,
                    route_seconds=route_seconds,
                    incoming_seconds=incoming.duration_seconds,
                    outgoing_seconds=outgoing.duration_seconds if outgoing else None,
                    incoming_distance_meters=getattr(incoming, "distance_meters", None),
                    outgoing_distance_meters=getattr(outgoing, "distance_meters", None) if outgoing else None,
                    matched_preference_features=evidence.feature_tags,
                    recent_visit_evidence=evidence.recent_visit_count,
                    **diagnostics,
                )
                chosen_today = True
            days.append(PlanDraftDay(day.visit_date, items))
        if isinstance(optimization_report, dict):
            optimization_report["rest_cafe_selection"] = selection_report
        logger.info(
            "plan_rest_cafe_selection trip_id=%s selected=%s undecided=%s slots=%s",
            getattr(trip, "trip_id", None),
            sum(row["result"] == "SELECTED" for row in selection_report),
            sum(row["result"] == "UNDECIDED" for row in selection_report),
            selection_report,
        )
        return GeneratedPlanDraft(days=days)

    @property
    def quality_rules(self):
        rules = getattr(self, "_quality_rules", None)
        if rules is None:
            rules = self._quality_rules = PlanQualityRules.from_settings()
        return rules

    def _repair_meal_slots(self, draft, candidate_places, anchor_ids, available, used, trip_id=None):
        """Fix restaurants the model put where no meal belongs.

        A restaurant outside every meal window, a second meal in one window, or
        a meal past the daily limit is swapped for an unused verified sight in
        the same time slot.  Without a sight, an extra meal becomes free time
        and an off-hours meal is kept for validation to warn about.  Selected
        anchors are never touched.  Every repair is logged so model mistakes
        and server corrections can be told apart.
        """
        rules = self.quality_rules

        def start_of(item):
            try:
                return time.fromisoformat(item.start_time) if item.start_time else None
            except (TypeError, ValueError):
                return None

        def end_of(item):
            try:
                return time.fromisoformat(item.end_time) if item.end_time else None
            except (TypeError, ValueError):
                return None

        def minute_of(value):
            return value.hour * 60 + value.minute

        def shift_into_next_meal_window(day, index, item, place):
            """Return a bounded, conflict-free later meal time or ``None``.

            Only a restaurant immediately before a real meal window is moved.
            It must retain its duration, fit verified opening hours when those
            are known, and leave every neighbouring scheduled item untouched.
            """
            start, end = start_of(item), end_of(item)
            if start is None or end is None:
                return None
            duration = minute_of(end) - minute_of(start)
            if duration <= 0 or duration > rules.max_meal_minutes:
                return None
            for target in rules.meal_windows:
                delay = minute_of(target.start) - minute_of(start)
                shifted_end_minutes = minute_of(target.start) + duration
                if not 0 < delay <= MAX_MEAL_WINDOW_SHIFT_MINUTES or shifted_end_minutes > minute_of(target.end):
                    continue
                if any(
                    other_index != index
                    and (other_place := candidate_places.get(other.place_id)) is not None
                    and is_restaurant(other_place)
                    and rules.meal_window(start_of(other)) is not None
                    and rules.meal_window(start_of(other)).name == target.name
                    for other_index, other in enumerate(day.items)
                ):
                    continue
                shifted_end = time(shifted_end_minutes // 60, shifted_end_minutes % 60)
                if opening_hours_match(place, day.visit_date, target.start, shifted_end) is False:
                    continue
                previous_ends = [end_of(other) for other in day.items[:index] if end_of(other) is not None]
                next_starts = [start_of(other) for other in day.items[index + 1:] if start_of(other) is not None]
                if (previous_ends and max(previous_ends) > target.start) or (next_starts and min(next_starts) < shifted_end):
                    continue
                return target, f"{target.start:%H:%M}", f"{shifted_end:%H:%M}"
            return None

        for day in draft.days:
            windows_used, meals = set(), 0
            order = sorted(range(len(day.items)), key=lambda index: (start_of(day.items[index]) is None, start_of(day.items[index]) or time(0)))
            for index in order:
                item = day.items[index]
                place = candidate_places.get(item.place_id) if item.place_id is not None else None
                if place is None or not is_restaurant(place) or item.place_id in anchor_ids:
                    continue
                window = rules.meal_window(start_of(item))
                if window is None:
                    shifted = shift_into_next_meal_window(day, index, item, place)
                    if shifted is not None:
                        target, shifted_start, shifted_end = shifted
                        day.items[index] = PlanDraftItem(
                            item.sequence, item.item_type, item.title, item.place_id,
                            shifted_start, shifted_end, item.recommendation_reason,
                        )
                        windows_used.add(target.name)
                        meals += 1
                        logger.info(
                            "plan_draft_repaired trip_id=%s reason=MEAL_TIME_SHIFTED visit_date=%s sequence=%s place_id=%s from_start=%s to_start=%s",
                            trip_id, day.visit_date, item.sequence, item.place_id, item.start_time, shifted_start,
                        )
                        continue
                    reason = "MEAL_OUTSIDE_WINDOW"
                elif window.name in windows_used:
                    reason = "DUPLICATE_MEAL"
                elif meals >= rules.max_meals_per_day:
                    reason = "TOO_MANY_MEALS"
                else:
                    windows_used.add(window.name)
                    meals += 1
                    continue
                if available:
                    replacement_id = available.pop(0)
                    replacement = candidate_places[replacement_id]
                    day.items[index] = PlanDraftItem(item.sequence, self._canonical_item_type(replacement), replacement.name, replacement_id, item.start_time, item.end_time, item.recommendation_reason)
                    used.add(replacement_id)
                elif reason != "MEAL_OUTSIDE_WINDOW":
                    replacement_id = None
                    day.items[index] = PlanDraftItem(item.sequence, "FREE_TIME", "자유 시간", None, item.start_time, item.end_time, item.recommendation_reason)
                else:
                    continue
                logger.info(
                    "plan_draft_repaired trip_id=%s reason=%s visit_date=%s sequence=%s start=%s model_place_id=%s server_place_id=%s",
                    trip_id, reason, day.visit_date, item.sequence, item.start_time, item.place_id, replacement_id,
                )

    def _repair_missing_meals(self, draft, candidate_places, anchor_ids, available, used, trip, preferences=None, meal_route_start=None):
        """Fill a missing lunch or dinner only from an unused verified restaurant.

        The slot keeps its own times (no overlap can appear) and must start in
        the relevant meal window and fit a meal.  An empty FREE_TIME slot is
        used first; a REST slot is retained for SLOW/high-rest trips.  Otherwise
        a non-anchor sight (or a dinner-time cafe),
        only when the day keeps another sight.  A displaced sight goes back to
        the unused activity pool.  Restaurants
        with verified hours that exclude the slot, or dated events, are never
        used.  With no such restaurant the day is left for MISSING_LUNCH to warn.
        """
        rules = self.quality_rules
        preferences = preferences or {}
        protects_rest = preferences.get("rest_frequency") == "HIGH" or preferences.get("travel_style") == "SLOW"
        trip_id = getattr(trip, "trip_id", None)
        cached_routes = isinstance(self.route_provider, CachedRouteProvider)
        # This is a sub-budget, never an increase: later candidate work still
        # retains at least the other half of CachedRouteProvider's 16 calls.
        # Its ceiling is shared fairly by travel day so an earlier day's lunch
        # cannot use every comparison before a later day's lunch is considered.
        meal_route_start = (
            getattr(self.route_provider, "candidate_calls", 0)
            if meal_route_start is None else meal_route_start
        )
        meal_route_ceiling = (
            min(
                getattr(self.route_provider, "max_candidate_calls", 0),
                meal_route_start + MEAL_ROUTE_CANDIDATE_MAX_CALLS,
            )
            if cached_routes else None
        )

        def clock(value):
            try:
                return time.fromisoformat(value) if value else None
            except (TypeError, ValueError):
                return None

        def minutes(item):
            start, end = clock(item.start_time), clock(item.end_time)
            return None if start is None or end is None else (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)

        def adjacent_places(items, index):
            before = next((item for item in reversed(items[:index]) if item.place_id in candidate_places), None)
            after = next((item for item in items[index + 1:] if item.place_id in candidate_places), None)
            return before, after

        def route_order(candidate, before, after):
            """Verified adjacent-route seconds, or None when a needed fact is unknown."""
            route_seconds = 0
            for neighbour, incoming in ((before, True), (after, False)):
                if neighbour is None:
                    continue
                first, second = (candidate_places[neighbour.place_id], candidate) if incoming else (candidate, candidate_places[neighbour.place_id])
                estimate = self._route_estimate(first, second, getattr(trip, "transport_mode", None))
                duration = getattr(estimate, "duration_seconds", None)
                if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
                    return None
                route_seconds += duration
            return route_seconds

        def route_heuristic(candidate, before, after):
            # Coordinates only reduce the number of candidates that spend the
            # fixed API budget.  Final ranking always uses provider seconds.
            nearby = [candidate_places[item.place_id] for item in (before, after) if item is not None]
            distances = [distance_meters(candidate, place) for place in nearby]
            return sum(distance if distance is not None else float("inf") for distance in distances)

        day_count = max(1, len(draft.days))
        for day_index, day in enumerate(draft.days):
            # Cumulative ceilings let an unused earlier share flow forward,
            # while reserving an equal share for each later day.
            meal_route_limit = (
                meal_route_start
                + ((meal_route_ceiling - meal_route_start) * (day_index + 1) + day_count - 1) // day_count
                if cached_routes else None
            )
            for window in (rules.lunch, rules.dinner):
                timed = [item for item in day.items if clock(item.start_time) and clock(item.end_time)]
                if not timed:
                    continue
                day_start = min(clock(item.start_time) for item in timed)
                day_end = max(clock(item.end_time) for item in timed)
                # Match the final quality check: avoid treating a 17:19 finish
                # as dinner time, but do not let a long evening cafe hide a meal.
                if not rules.expects_meal(day_start, day_end, window):
                    continue
                if any(item.place_id in candidate_places and is_restaurant(candidate_places[item.place_id])
                       and window.contains(clock(item.start_time)) for item in day.items):
                    continue
                sights = [item for item in day.items if item.place_id in candidate_places and not _is_food_or_cafe(candidate_places[item.place_id])]

                def usable(item):
                    if not window.contains(clock(item.start_time)) or (minutes(item) or 0) > rules.max_meal_minutes or (minutes(item) or 0) <= 0:
                        return False
                    if item.place_id is None:
                        # A SLOW/high-rest schedule's only declared REST slot
                        # is not expendable evidence for lunch.  Without a
                        # distinct, safe lunch slot the plan remains incomplete.
                        return item.item_type == "FREE_TIME" or (item.item_type == "REST" and not protects_rest)
                    place = candidate_places.get(item.place_id)
                    if place is None or item.place_id in anchor_ids:
                        return False
                    # A dinner-time cafe must not silently become the meal.
                    # It can be replaced only by an actual unused restaurant.
                    if window.name == "DINNER" and is_cafe(place):
                        return True
                    return not _is_food_or_cafe(place) and len(sights) >= 2

                slots = sorted((index for index, item in enumerate(day.items) if usable(item)),
                               key=lambda index: (day.items[index].place_id is not None, clock(day.items[index].start_time)))
                if not slots:
                    continue
                index = slots[0]
                item = day.items[index]
                restaurant_ids = [
                    place_id for place_id, place in candidate_places.items()
                    if place_id not in used and is_restaurant(place) and not is_event_candidate(place)
                    and opening_hours_match(place, day.visit_date, clock(item.start_time), clock(item.end_time)) is not False
                ]
                before, after = adjacent_places(day.items, index)
                if isinstance(self.route_provider, UnavailableRouteProvider) or (before is None and after is None):
                    restaurant_id = restaurant_ids[0] if restaurant_ids else None
                else:
                    ordered_ids = sorted(
                        restaurant_ids,
                        key=lambda place_id: (route_heuristic(candidate_places[place_id], before, after), place_id),
                    )
                    scored = []
                    context = self.route_provider.candidate_phase() if cached_routes else nullcontext()
                    with context:
                        for place_id in ordered_ids:
                            # Never borrow the reserved optimisation/REST half.
                            needed_legs = int(before is not None) + int(after is not None)
                            if cached_routes and self.route_provider.candidate_calls + needed_legs > meal_route_limit:
                                break
                            seconds = route_order(candidate_places[place_id], before, after)
                            if seconds is not None:
                                scored.append((seconds, place_id))
                    restaurant_id = min(scored, default=(None, None))[1]
                    logger.info(
                        "plan_missing_meal_route_selection trip_id=%s visit_date=%s window=%s candidates=%s verified=%s selected_place_id=%s candidate_calls=%s candidate_limit=%s",
                        trip_id, day.visit_date, window.name, len(restaurant_ids), len(scored), restaurant_id,
                        getattr(self.route_provider, "candidate_calls", None), meal_route_limit,
                    )
                if restaurant_id is None:
                    continue
                restaurant = candidate_places[restaurant_id]
                day.items[index] = PlanDraftItem(item.sequence, self._canonical_item_type(restaurant), restaurant.name, restaurant_id, item.start_time, item.end_time, item.recommendation_reason)
                used.add(restaurant_id)
                if item.place_id is not None:
                    used.discard(item.place_id)
                    displaced = candidate_places.get(item.place_id)
                    if displaced is not None and not _is_food_or_cafe(displaced):
                        available.append(item.place_id)
                logger.info(
                    "plan_draft_repaired trip_id=%s reason=MISSING_%s visit_date=%s sequence=%s start=%s model_place_id=%s server_place_id=%s",
                    trip_id, window.name, day.visit_date, item.sequence, item.start_time, item.place_id, restaurant_id,
                )

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

    def _adjust_route_timing(self, days, candidate_places, trip):
        """Move later items so verified travel fits; never drop or re-day places.

        Uses the same legs and (request-cached) route facts as
        ``_validate_route_timing``.  A leg without a route fact is left as is.
        """
        mode = getattr(trip, "transport_mode", None)

        def travel_seconds(previous_item, current_item):
            estimate = self._route_estimate(
                candidate_places[previous_item.place_id], candidate_places[current_item.place_id], mode
            )
            duration = getattr(estimate, "duration_seconds", None)
            return duration if isinstance(duration, int) and not isinstance(duration, bool) and duration > 0 else None

        adjusted = []
        for visit_date, rows in days:
            try:
                adjusted.append((visit_date, shift_day_for_travel(rows, travel_seconds)))
            except TravelShiftConflict as conflict:
                logger.info("route_time_shift_failed visit_date=%s reason=%s", visit_date, conflict.message)
                raise AppError("ROUTE_TIME_CONFLICT", f"{visit_date.isoformat()}: {conflict.message}", 422) from None
        return adjusted

    def _adjust_opening_hours_timing(self, days, candidate_places, anchor_ids, preferences):
        """Use only flexible FREE_TIME to repair proven official-hours conflicts."""
        adjusted, all_adjustments, all_unresolved = [], [], []
        for visit_date, rows in days:
            shifted, adjustments, unresolved = adjust_day_for_opening_hours(
                rows, visit_date, candidate_places, anchor_ids, preferences,
            )
            adjusted.append((visit_date, shifted))
            all_adjustments.extend({"visit_date": visit_date.isoformat(), **row} for row in adjustments)
            all_unresolved.extend({"visit_date": visit_date.isoformat(), **row} for row in unresolved)
        self.last_official_hours_adjustments = all_adjustments
        if all_adjustments or all_unresolved:
            logger.info(
                "official_hours_time_adjustment adjusted=%s unresolved=%s",
                all_adjustments, all_unresolved,
            )
        return adjusted

    def _validate_route_timing(self, days, candidate_places, trip):
        """Reject only conflicts proven by a directions provider.

        No result means route data is unavailable, not that a guessed duration
        is acceptable.  In that case the plan carries no travel-time, route, or
        transit-connection claim.

        Returns the verified legs as {(visit_date, sequence): RouteEstimate}
        so callers can store them without asking the provider again.
        """
        legs = {}
        for visit_date, items in days:
            for previous, current in route_legs(items):
                previous_item, _, previous_end = previous
                current_item, current_start, _ = current
                estimate = self._route_estimate(
                    candidate_places[previous_item.place_id],
                    candidate_places[current_item.place_id],
                    getattr(trip, "transport_mode", None),
                )
                if estimate is None:
                    continue
                legs[(visit_date, current_item.sequence)] = estimate
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
        return legs

    def _require_complete_meal_schedule(self, days, candidate_places):
        """Reject a full-day plan when required meal slots remain unresolved.

        Meal expectation is still determined by ``PlanQualityRules`` from the
        actual schedule span, so short arrival/departure days are not forced
        to add a meal.  There is no persisted user "skip meals" preference;
        until one exists, a required lunch/dinner cannot be silently waived.
        """
        quality_days = []
        for number, (_, rows) in enumerate(days, start=1):
            stops = [
                DayStop(item.sequence, item.item_type, start, end, candidate_places.get(item.place_id))
                for item, start, end in rows
            ]
            quality_days.append((f"{number}일차", stops))
        blocking_codes = {"MISSING_LUNCH", "MISSING_DINNER", "MEAL_OUTSIDE_WINDOW"}
        blockers = [finding for finding in review_plan(quality_days, self.quality_rules) if finding.code in blocking_codes]
        if blockers:
            codes = sorted({finding.code for finding in blockers})
            logger.info("plan_generation_incomplete_meals codes=%s", codes)
            raise AppError(
                "MEAL_SCHEDULE_INCOMPLETE",
                "Required meal slots could not be scheduled safely with verified restaurant candidates",
                422,
                {"codes": codes},
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
        if not GENERATIONS_IN_PROGRESS.acquire(trip_id):
            raise plan_generation_in_progress_error(trip_id)
        try:
            return self._generate(trip, trip_id, selected_place_ids)
        finally:
            GENERATIONS_IN_PROGRESS.release(trip_id)

    def _generate(self, trip, trip_id, selected_place_ids):
        existing = self.plans.get_by_trip_id(trip_id)
        if existing is not None:
            raise plan_already_exists_error(existing)
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
        draft = self._optimize_routes(self._prepare_draft(draft, candidate_places, anchor_ids, trip, preferences), candidate_places, anchor_ids, trip, preferences)
        draft = self._attach_rest_cafes(draft, candidate_places, trip, preferences)
        days = self._validate_draft(draft, set(candidate_places))
        days = self._adjust_route_timing(days, candidate_places, trip)
        days = self._adjust_opening_hours_timing(days, candidate_places, anchor_ids, preferences)
        self._validate_temporal_draft(days, candidate_places)
        legs = self._validate_route_timing(days, candidate_places, trip) or {}
        self._validate_activity_diversity(days, candidate_places, trip)
        # The production factory wraps a configured route provider in this
        # request-scoped cache.  Only then do we have the route-fact contract
        # required to reject a missing meal instead of guessing a restaurant.
        if isinstance(self.route_provider, CachedRouteProvider):
            self._require_complete_meal_schedule(days, candidate_places)
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
                        **travel_columns(legs.get((visit_date, draft_item.sequence))),
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
                    items=self._response_items(created_items, candidate_places),
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

    @classmethod
    def _response_items(cls, items, candidate_places):
        statuses = travel_statuses(items)
        return [cls._response_item(item, candidate_places, statuses[id(item)]) for item in items]

    @staticmethod
    def _response_item(item, candidate_places, travel_status=None):
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
            **travel_response_fields(item, travel_status),
        )
