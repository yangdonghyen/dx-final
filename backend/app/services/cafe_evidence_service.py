"""Conservative matching of Kakao cafes to NAVER Search results.

Search titles and snippets are transient, untrusted input.  They are not
stored, logged, rendered to users, or passed to the plan model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.core.exceptions import AppError
from app.services.external.naver_api_hub_provider import NaverBlogPost, NaverCafeEvidenceProvider, NaverLocalPlace
from app.services.plan_quality_rules import distance_meters

EXCLUDED_CAFE_TERMS = ("pc방", "피시방", "키즈카페", "게임카페", "만화카페", "보드카페", "스터디카페", "방탈출", "오락실", "노래방")
_VISIT_TERMS = ("방문", "다녀", "후기", "들렀", "갔다", "가봤")
_AD_TERMS = ("협찬", "광고", "원고료", "제공받", "체험단")
_FEATURES = {
    "VIEW": ("뷰", "전망", "오션", "바다", "테라스"),
    "DESSERT": ("디저트", "케이크", "베이커리", "커피"),
    "QUIET": ("조용", "한적", "차분"),
}


def _norm(value: object) -> str:
    return re.sub(r"[\W_]", "", str(value or "").casefold())


def _tokens(value: object) -> set[str]:
    normalized = re.sub(r"(\uD2B9\uBCC4\uC790\uCE58\uB3C4|\uD2B9\uBCC4\uC790\uCE58\uC2DC|\uD2B9\uBCC4\uC2DC|\uAD11\uC5ED\uC2DC)", "", str(value or "").casefold())
    return {token for token in re.split(r"\s+", normalized) if len(token) >= 2}


def is_travel_rest_cafe(place) -> bool:
    text = " ".join(str(getattr(place, field, "") or "") for field in ("name", "category", "address")).casefold()
    return not any(term in text for term in EXCLUDED_CAFE_TERMS)


@dataclass(frozen=True)
class BusinessMatch:
    matched: bool
    reason: str
    relaxed_name: bool = False


def _branch_tokens(value: object) -> set[str]:
    """Extract only explicit Korean branch suffix tokens, never infer a branch."""
    tokens = re.findall(r"\S+", str(value or "").casefold())
    return {
        _norm(token) for token in tokens
        if re.fullmatch(r"(?:\uBCF8\uC810|\d+\uD638\uC810|\S+(?:\uC9C0\uC810|\uC810))", token)
    }


_GENERIC_BUSINESS_NAMES = frozenset({
    _norm("\uBCA0\uC774\uCEE4\uB9AC"), _norm("\uCE74\uD398"), _norm("\uCEE4\uD53C"),
    _norm("\uB514\uC800\uD2B8"), _norm("\uB85C\uC2A4\uD130\uB9AC"),
})


def _address_region_stems(address: object) -> set[str]:
    """Use only administrative suffixes present in this Kakao address."""
    stems = set()
    for token in re.findall(r"\S+", str(address or "").casefold()):
        match = re.fullmatch(r"(.+?)(?:\uC2DC|\uAD6C|\uAD70|\uB3D9|\uC74D|\uBA74|\uB9AC)", token)
        if match and len(_norm(match.group(1))) >= 2:
            stems.add(_norm(match.group(1)))
    return stems


def _address_province_stem(address: object) -> str | None:
    """Return the first address token's province/city stem without a lookup table."""
    tokens = re.findall(r"\S+", str(address or "").casefold())
    if not tokens:
        return None
    first = re.sub(r"(\uD2B9\uBCC4\uC790\uCE58\uB3C4|\uD2B9\uBCC4\uC790\uCE58\uC2DC|\uD2B9\uBCC4\uC2DC|\uAD11\uC5ED\uC2DC)", "", tokens[0])
    match = re.fullmatch(r"(.+?)(?:\uC2DC|\uB3C4)", first)
    stem = _norm(match.group(1) if match else first)
    return stem if len(stem) >= 2 else None


def _strip_province_branch_prefix(branches: set[str], province: str | None) -> set[str]:
    if not province:
        return branches
    stripped = set()
    for branch in branches:
        remainder = branch.removeprefix(province)
        stripped.add(remainder if remainder else branch)
    return stripped


def _without_province_branch_prefix(name: str, branches: set[str], province: str | None) -> str:
    normalized = _norm(name)
    if not province:
        return normalized
    for branch in branches:
        remainder = branch.removeprefix(province)
        if remainder:
            normalized = normalized.replace(branch, remainder, 1)
    return normalized


def _remove_independent_region_tokens(value: object, stems: set[str]) -> str:
    return _norm(" ".join(token for token in re.findall(r"\S+", str(value or "")) if _norm(token) not in stems))


def _naver_only_address_branch_matches(source_name: str, local_name: str, local_branches: set[str], address: object) -> bool:
    """Allow one NAVER-only geographic branch suffix derived from Kakao's address.

    This deliberately requires exact base-name equality after removing a single
    terminal branch token.  Address and the relaxed 150 m coordinate check are
    still enforced by ``business_match``.
    """
    if len(local_branches) != 1:
        return False
    branch = next(iter(local_branches))
    match = re.fullmatch(r"(.+?)(?:\uC9C0\uC810|\uC810)", branch)
    if not match:
        return False
    region = _norm(match.group(1))
    if not region or region not in _address_region_stems(address):
        return False
    return local_name.endswith(branch) and local_name.removesuffix(branch) == source_name


def _names_match(source: object, local: object, address: object = "") -> tuple[bool, bool]:
    source_name, local_name = _norm(source), _norm(local)
    if not source_name or not local_name:
        return False, False
    if source_name == local_name:
        return True, False
    source_branches, local_branches = _branch_tokens(source), _branch_tokens(local)
    source_comparison = source_name
    branch_prefix_relaxed = False
    # Any explicit branch token must agree on both sides.  This prevents a
    # common brand from joining different branches even under containment.
    if source_branches or local_branches:
        if not source_branches:
            # Kakao sometimes omits a geographic branch suffix carried by
            # NAVER.  Accept only an exact base name plus one suffix whose
            # region is present in the Kakao address; mark it relaxed so the
            # existing 150 m check, rather than the standard 300 m check,
            # applies in business_match.
            if _naver_only_address_branch_matches(source_name, local_name, local_branches, address):
                return True, True
            return False, False
        if source_branches != local_branches:
            province = _address_province_stem(address)
            if _strip_province_branch_prefix(source_branches, province) != local_branches:
                return False, False
            source_comparison = _without_province_branch_prefix(source_name, source_branches, province)
            branch_prefix_relaxed = True
    # NAVER may insert a city/district token as its own name word.  Only a
    # token derived from this Kakao address is removable; branch words such as
    # "haeundae-branch" stay intact because they are not independent tokens.
    local_without_region = _remove_independent_region_tokens(local, _address_region_stems(address))
    if source_comparison == local_name:
        return True, branch_prefix_relaxed
    if source_comparison == local_without_region:
        return True, True
    shorter = source_comparison if len(source_comparison) <= len(local_name) else local_name
    if len(shorter) < 3 or shorter in _GENERIC_BUSINESS_NAMES:
        return False, False
    return source_comparison in local_name or local_name in source_comparison, True


def _address_reason(source: object, local: object) -> str | None:
    source_tokens, local_tokens = _tokens(source), _tokens(local)
    if len(source_tokens & local_tokens) < 2:
        return "ADDRESS_TOKENS"
    source_digits = set(re.findall(r"\d+", str(source or "")))
    local_digits = set(re.findall(r"\d+", str(local or "")))
    if source_digits and local_digits and not source_digits & local_digits:
        return "ADDRESS_DIGITS"
    return None


def business_match(place, local: NaverLocalPlace) -> BusinessMatch:
    """Return the first conservative mismatch reason without logging source text."""
    names_match, relaxed_name = _names_match(getattr(place, "name", ""), local.name, getattr(place, "address", ""))
    if not names_match:
        return BusinessMatch(False, "NAME")
    source_addresses = [getattr(place, "address", ""), getattr(place, "road_address", "")]
    address_reasons = [_address_reason(source, local_address)
                       for source in source_addresses if source
                       for local_address in (local.address, local.road_address) if local_address]
    if not address_reasons or all(reason is not None for reason in address_reasons):
        # A token disagreement is the earlier (less specific) failed condition.
        return BusinessMatch(False, "ADDRESS_TOKENS" if "ADDRESS_TOKENS" in address_reasons else "ADDRESS_DIGITS", relaxed_name)
    if local.latitude is None or local.longitude is None:
        return BusinessMatch(False, "NO_COORD", relaxed_name)
    distance = distance_meters(place, local)
    maximum = 150 if relaxed_name else 300
    if distance is None or distance > maximum:
        return BusinessMatch(False, "DISTANCE", relaxed_name)
    return BusinessMatch(True, "MATCHED", relaxed_name)


def same_business(place, local: NaverLocalPlace) -> bool:
    """Compatibility wrapper for callers that only need the boolean contract."""
    return business_match(place, local).matched


@dataclass(frozen=True)
class CafeEvidence:
    verified: bool
    feature_tags: tuple[str, ...] = ()
    recent_visit_count: int = 0
    review_status: str = "NOT_CHECKED"


@dataclass(frozen=True)
class LocalMatchResult:
    local: NaverLocalPlace | None
    reason: str
    error_code: str | None = None
    mismatch_condition: str | None = None


class CafeEvidenceService:
    # Four route-proximate candidates, each with a primary and fallback query.
    # This remains a trip-wide cap and is shared by every REST slot.
    MAX_LOCAL_CANDIDATES = 4
    MAX_LOCAL_LOOKUPS = 8
    MAX_BLOG_LOOKUPS = 2
    BLOG_RESULTS_PER_CAFE = 5

    def __init__(self, provider: NaverCafeEvidenceProvider):
        self.provider = provider
        self.local_lookups = self.blog_lookups = 0
        self._local_cache: dict[tuple[object, str, str], LocalMatchResult] = {}
        self._evidence_cache: dict[tuple[object, str, str], CafeEvidence] = {}
        self._local_candidate_keys: set[tuple[object, str, str]] = set()
        self._active_slot_keys: set[tuple[object, str, str]] = set()
        self._active_slot_candidate_limit = self.MAX_LOCAL_CANDIDATES
        self._local_disabled_error: str | None = None

    @staticmethod
    def _key(place) -> tuple[object, str, str]:
        return getattr(place, "place_id", None), str(getattr(place, "name", "")), str(getattr(place, "address", ""))

    @staticmethod
    def _local_queries(place) -> tuple[str, ...]:
        address = str(getattr(place, "address", "") or "")
        region = [token for token in re.split(r"\s+", address) if token.endswith(("\uC2DC", "\uAD6C", "\uAD70"))]
        primary = " ".join([*region[:2], str(getattr(place, "name", "") or "").strip()]).strip()
        fallback = str(getattr(place, "name", "") or "").strip()
        return tuple(dict.fromkeys(query for query in (primary, fallback) if query))

    def begin_rest_slot(self, remaining_slots: int | None) -> None:
        """Reserve candidate capacity for later REST slots without raising caps."""
        self._active_slot_keys = set()
        available = max(0, self.MAX_LOCAL_CANDIDATES - len(self._local_candidate_keys))
        if not remaining_slots or remaining_slots < 1:
            self._active_slot_candidate_limit = min(2, available)
        else:
            self._active_slot_candidate_limit = min(2, (available + remaining_slots - 1) // remaining_slots)

    def local_match_result(self, place) -> LocalMatchResult:
        key = self._key(place)
        if key in self._local_cache:
            return self._local_cache[key]
        if not is_travel_rest_cafe(place):
            return LocalMatchResult(None, "EXCLUDED_BY_INDUSTRY")
        if self._local_disabled_error:
            return LocalMatchResult(None, "API_ERROR", self._local_disabled_error)
        if len(self._local_candidate_keys) >= self.MAX_LOCAL_CANDIDATES or self.local_lookups >= self.MAX_LOCAL_LOOKUPS:
            return LocalMatchResult(None, "LOCAL_LOOKUP_LIMIT")
        if key not in self._active_slot_keys and len(self._active_slot_keys) >= self._active_slot_candidate_limit:
            return LocalMatchResult(None, "LOCAL_SLOT_BUDGET")
        self._local_candidate_keys.add(key)
        self._active_slot_keys.add(key)
        saw_rows, failures = False, []
        for query in self._local_queries(place):
            if self.local_lookups >= self.MAX_LOCAL_LOOKUPS:
                break
            self.local_lookups += 1
            try:
                rows = self.provider.search_local(query)
            except AppError as error:
                code = getattr(error, "code", error.__class__.__name__)
                if code in {"NAVER_API_HUB_AUTH_FAILED", "NAVER_API_HUB_NOT_CONFIGURED"}:
                    self._local_disabled_error = code
                result = LocalMatchResult(None, "API_ERROR", code)
                self._local_cache[key] = result
                return result
            saw_rows = saw_rows or bool(rows)
            for row in rows:
                decision = business_match(place, row)
                if decision.matched:
                    result = LocalMatchResult(row, "MATCHED")
                    self._local_cache[key] = result
                    return result
                failures.append(decision.reason)
        reason = "NAVER_EMPTY" if not saw_rows else "NAVER_NO_SAME_BUSINESS"
        result = LocalMatchResult(None, reason, mismatch_condition=failures[0] if failures else None)
        self._local_cache[key] = result
        return result

    def local_match(self, place) -> NaverLocalPlace | None:
        """Compatibility API; use ``local_match_result`` for diagnostics."""
        return self.local_match_result(place).local

    def review_evidence(self, place, local: NaverLocalPlace, preferences: dict) -> CafeEvidence:
        key = self._key(place)
        if key in self._evidence_cache:
            return self._evidence_cache[key]
        if self.blog_lookups >= self.MAX_BLOG_LOOKUPS:
            return CafeEvidence(False, review_status="LOOKUP_LIMIT")
        self.blog_lookups += 1
        posts = self.provider.search_blog(f"{place.name} {local.road_address or local.address}", self.BLOG_RESULTS_PER_CAFE)
        place_name, area = _norm(place.name), _tokens(local.road_address or local.address)
        feature_tags, visits = set(), 0
        for post in posts:
            text = f"{post.title} {post.summary}".casefold()
            normalized = _norm(text)
            # Search snippets are evidence only; ignore promotional and stale,
            # ambiguous, or non-visit text instead of interpreting directives.
            age_days = (date.today() - post.published_on).days if post.published_on else None
            if (place_name not in normalized or not any(term in text for term in _VISIT_TERMS)
                    or any(term in text for term in _AD_TERMS) or age_days is None or not 0 <= age_days <= 730):
                continue
            if area and not any(token in text for token in area):
                continue
            visits += 1
            for tag, terms in _FEATURES.items():
                if any(term in text for term in terms):
                    feature_tags.add(tag)
        self._evidence_cache[key] = CafeEvidence(bool(visits), tuple(sorted(feature_tags)), visits,
                                                  "VERIFIED" if visits else "NO_RECENT_EVIDENCE")
        return self._evidence_cache[key]

    @staticmethod
    def preference_score(evidence: CafeEvidence, preferences: dict) -> int:
        desired = set()
        source = " ".join(str(value or "") for value in preferences.values()).casefold()
        if any(word in source for word in ("전망", "뷰", "자연")): desired.add("VIEW")
        if any(word in source for word in ("디저트", "음식")): desired.add("DESSERT")
        if any(word in source for word in ("조용", "휴식")): desired.add("QUIET")
        return len(desired & set(evidence.feature_tags))
