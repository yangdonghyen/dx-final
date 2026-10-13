# Cafe recommendation code review

## Ranking / helper logic
```python
    "VERY_LOW": 10 * 60,
    "LOW": 20 * 60,
    "NORMAL": 35 * 60,
    "HIGH": 60 * 60,
}
REST_CAFE_RADII_METERS = (500, 1500)
REST_CAFE_LIMIT = 5
REST_CAFE_REASON = "검증된 Kakao 카페를 기존 휴식 시간에 연결했습니다. 영업시간 정보가 없으면 영업 중이라고 단정하지 않습니다."
REST_CAFE_UNDECIDED = "휴식 장소 미정"

# A Kakao category leaf can identify a chain (for example, a coffee brand),
# while generic leaves only describe a type of venue.  The key is used solely
# to spread a fixed NAVER lookup budget across the already returned candidates;
# it is not a brand preference or exclusion rule.
_GENERIC_CAFE_CATEGORY_LEAVES = frozenset({
    "\uce74\ud398", "\ucee4\ud53c\uc804\ubb38\uc810", "\ubca0\uc774\ucee4\ub9ac", "\ub514\uc800\ud2b8",
})

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


def _cafe_lookup_family_key(cafe):
    """Return a generic chain-family key only when Kakao supplies one.

    Generic category leaves are deliberately kept unique: they cannot safely
    establish that two independently named cafes are part of one business.
    """
    category = str(getattr(cafe, "category", "") or "")
    leaf = category.split(">")[-1].strip()
    normalized_leaf = "".join(char for char in leaf.casefold() if char.isalnum())
    if normalized_leaf and normalized_leaf not in _GENERIC_CAFE_CATEGORY_LEAVES:
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
```

## REST cafe selection
```python
        model's draft and adds no quality warning; otherwise the model's draft
        is used unchanged.  Travel legs stay UNKNOWN: distances only rank.
        """
        trip_id = getattr(trip, "trip_id", None)
        before_m, longest_before = route_length(draft.days, candidate_places)
        report = {"applied": False, "moves": [], "before_m": round(before_m), "after_m": round(before_m),
                  "longest_leg_before_m": round(longest_before), "longest_leg_after_m": round(longest_before)}
        self.last_route_optimization = report
        try:
            optimized, moves = optimize_routes(draft, candidate_places, set(anchor_ids))
        except (TypeError, ValueError) as exc:  # never block generation on an optimizer fault
            logger.info("plan_route_optimization_skipped trip_id=%s reason=%s", trip_id, type(exc).__name__)
            return draft
        chosen = draft
        if moves:
            reason = self._checked(optimized, draft, candidate_places, trip)
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
                    cafes = [self.places.get(row.place_id) for row in upserted]
                    cafes = [cafe for cafe in cafes if cafe is not None and is_cafe(cafe) and is_travel_rest_cafe(cafe) and opening_hours_match(cafe, day.visit_date, start, end) is not False]
                    # Start from Kakao distance order, then spread the fixed
                    # trip-wide NAVER budget across distinct category families.
                    cafes.sort(key=lambda cafe: (distance_meters(origin, cafe) is None, distance_meters(origin, cafe) or float("inf"), cafe.place_id))
                    cafes = _diverse_cafe_lookup_order(cafes)
                    diagnostics["industry_pass"] += len(cafes)
                    with self.route_provider.candidate_phase() if cached else nullcontext():
                        for cafe in cafes:
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
```
