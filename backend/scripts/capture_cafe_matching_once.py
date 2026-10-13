"""One opt-in, bounded capture of Kakao CE7 candidates and NAVER local matching.

No database, route, blog, Ollama, or plan-generation code is used.  Without
--confirm this script only prints its fixed network-call plan and exits.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.cafe_evidence_service import CafeEvidenceService, business_match
from app.services.external.factory import get_kakao_region_geocoder, get_naver_cafe_evidence_provider
from app.services.external.naver_api_hub_provider import NaverLocalPlace
from app.services.plan_generation_service import REST_CAFE_RADII_METERS
from app.services.plan_quality_rules import distance_meters


MAX_KAKAO_LOCAL_CALLS = 1
MAX_NAVER_LOCAL_CALLS = 10
LATITUDE = 35.1587
LONGITUDE = 129.1604
CATEGORY_CODES = ["CE7"]
CANDIDATE_LIMIT = 5


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _public_local(row: NaverLocalPlace) -> dict[str, Any]:
    return {
        "name": row.name,
        "address": row.address,
        "road_address": row.road_address,
        "latitude": row.latitude,
        "longitude": row.longitude,
    }


def _public_candidate(row) -> dict[str, Any]:
    return {
        "name": row.name,
        "address": row.address,
        "latitude": row.latitude,
        "longitude": row.longitude,
    }


class BoundedNaverLocalProvider:
    """Delegates to the existing provider while recording no blog/text content."""

    def __init__(self, provider):
        self.provider = provider
        self.calls = 0
        self.events: list[dict[str, Any]] = []

    def search_local(self, query: str) -> list[NaverLocalPlace]:
        if self.calls >= MAX_NAVER_LOCAL_CALLS:
            raise AppError("CAPTURE_NAVER_LOCAL_LIMIT", "NAVER local capture limit reached", 429)
        self.calls += 1
        try:
            rows = self.provider.search_local(query)
        except AppError as error:
            self.events.append({"query": query, "response_count": None, "error_code": error.code, "responses": []})
            raise
        self.events.append({
            "query": query,
            "response_count": len(rows),
            "error_code": None,
            "responses": [_public_local(row) for row in rows],
        })
        return rows

    def search_blog(self, query: str, limit: int = 5):  # pragma: no cover - safety guard
        raise RuntimeError("NAVER blog search is disabled in this capture")


def _matching_rows(candidate, naver_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for event in naver_events:
        for raw in event["responses"]:
            local = NaverLocalPlace(
                raw["name"], "", raw["address"], raw["road_address"],
                _number(raw["latitude"]), _number(raw["longitude"]),
            )
            decision = business_match(candidate, local)
            distance = distance_meters(candidate, local)
            rows.append({
                "naver": raw,
                "business_match": {
                    "matched": decision.matched,
                    "reason": decision.reason,
                    "relaxed_name": decision.relaxed_name,
                },
                "distance_meters": round(distance, 1) if distance is not None else None,
            })
    return rows


def _markdown(payload: dict[str, Any]) -> str:
    lines = ["# One-time cafe matching capture", "", "| Kakao candidate | address | latitude | longitude | result |", "|---|---|---:|---:|---|"]
    for item in payload["candidates"]:
        cafe = item["kakao"]
        lines.append(f"| {cafe['name']} | {cafe['address']} | {cafe['latitude']} | {cafe['longitude']} | {item['local_match_result']} |")
    lines += ["", "## NAVER local response comparisons", "", "| Kakao candidate | NAVER business | parcel address | road address | latitude | longitude | matched | reason | relaxed | distance m |", "|---|---|---|---|---:|---:|---|---|---|---:|"]
    for item in payload["candidates"]:
        for comparison in item["business_matches"]:
            naver, match = comparison["naver"], comparison["business_match"]
            lines.append(
                f"| {item['kakao']['name']} | {naver['name']} | {naver['address']} | {naver['road_address']} | "
                f"{naver['latitude']} | {naver['longitude']} | {match['matched']} | {match['reason']} | "
                f"{match['relaxed_name']} | {comparison['distance_meters'] or ''} |"
            )
    lines += ["", "## Summary", "", json.dumps(payload["summary"], ensure_ascii=False)]
    return "\n".join(lines) + "\n"


def _write_reports(payload: dict[str, Any]) -> tuple[Path, Path]:
    output_dir = Path(tempfile.gettempdir()) / "dx-all-cafe-matching-capture"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"capture_{stamp}.json"
    markdown_path = output_dir / f"capture_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def _plan() -> str:
    return (
        "External calls are disabled: pass --confirm to run one bounded capture.\n"
        f"Plan: Kakao Local <= {MAX_KAKAO_LOCAL_CALLS}; NAVER local <= {MAX_NAVER_LOCAL_CALLS}; "
        f"center=({LATITUDE}, {LONGITUDE}); radius={REST_CAFE_RADII_METERS[0]}; CE7 limit={CANDIDATE_LIMIT}.\n"
        "No MySQL, Kakao Mobility, NAVER blog, Ollama, or plan generation is used."
    )


def capture() -> dict[str, Any]:
    settings = Settings()
    kakao = get_kakao_region_geocoder(settings)
    naver = BoundedNaverLocalProvider(get_naver_cafe_evidence_provider(settings))
    service = CafeEvidenceService(naver)
    payload: dict[str, Any] = {
        "center": {"latitude": LATITUDE, "longitude": LONGITUDE},
        "radius_meters": REST_CAFE_RADII_METERS[0],
        "limits": {"kakao_local": MAX_KAKAO_LOCAL_CALLS, "naver_local": MAX_NAVER_LOCAL_CALLS},
        "candidates": [],
        "summary": {},
    }
    kakao_calls = 0
    if kakao_calls >= MAX_KAKAO_LOCAL_CALLS:
        payload["summary"] = {"kakao_local_calls": 0, "naver_local_calls": 0, "stopped_error_code": "CAPTURE_KAKAO_LOCAL_LIMIT"}
        return payload
    try:
        kakao_calls += 1
        candidates = kakao.search_nearby(LATITUDE, LONGITUDE, REST_CAFE_RADII_METERS[0], CATEGORY_CODES, CANDIDATE_LIMIT)
    except AppError as error:
        payload["summary"] = {"kakao_local_calls": kakao_calls, "naver_local_calls": 0, "stopped_error_code": error.code}
        return payload

    stopped_error = None
    for candidate in candidates:
        before = len(naver.events)
        result = service.local_match_result(candidate)
        events = naver.events[before:]
        item = {
            "kakao": _public_candidate(candidate),
            "naver_query_stages": events,
            "local_match_result": result.reason,
            "local_match_error_code": result.error_code,
            "business_matches": _matching_rows(candidate, events),
        }
        payload["candidates"].append(item)
        if result.reason == "API_ERROR":
            stopped_error = result.error_code
            break
    counts = {code: sum(item["local_match_result"] == code for item in payload["candidates"])
              for code in ("NAVER_EMPTY", "NAVER_NO_SAME_BUSINESS", "MATCHED", "LOCAL_LOOKUP_LIMIT", "LOCAL_SLOT_BUDGET", "API_ERROR")}
    payload["summary"] = {
        "kakao_local_calls": kakao_calls,
        "naver_local_calls": naver.calls,
        "result_counts": counts,
        "stopped_error_code": stopped_error,
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="required before any external API call")
    args = parser.parse_args()
    if not args.confirm:
        print(_plan())
        return
    payload = capture()
    json_path, markdown_path = _write_reports(payload)
    print(f"capture complete; UTF-8 reports written: {json_path} and {markdown_path}")


if __name__ == "__main__":
    main()
