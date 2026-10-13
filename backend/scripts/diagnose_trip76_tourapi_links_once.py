"""One-shot, opt-in TourAPI identity diagnostic for trip 76's two target places.

Without --confirm this script performs a read-only DB lookup only.  With
--confirm it makes at most six TourAPI calls: two keyword searches and, only
for a unique high-confidence match, common+intro detail calls.  It never
writes the database or calls Kakao, NAVER, Mobility, or Ollama.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.external.factory import get_tour_destination_image_provider


TRIP_ID = 76
# Confirmed from the read-only trip-76 inspection; no user fields are selected.
TARGET_PLACE_IDS = (401, 368)
MAX_SEARCH_CALLS = 2
MAX_DETAIL_CALLS = 4
MAX_EXTERNAL_CALLS = MAX_SEARCH_CALLS + MAX_DETAIL_CALLS


def _normalize_name(value: str | None) -> str:
    return "".join(char for char in str(value or "").casefold() if char.isalnum())


def _address_tokens(value: str | None) -> set[str]:
    normalized = str(value or "").replace("광역시", "").replace("특별시", "")
    return {token for token in re.findall(r"[가-힣]+|\d+(?:-\d+)?", normalized) if len(token) >= 2 or token[0].isdigit()}


def _distance_meters(a_lat, a_lng, b_lat, b_lng) -> float | None:
    if None in {a_lat, a_lng, b_lat, b_lng}:
        return None
    radians = math.pi / 180
    lat_delta = (float(b_lat) - float(a_lat)) * radians
    lng_delta = (float(b_lng) - float(a_lng)) * radians
    root = math.sin(lat_delta / 2) ** 2 + math.cos(float(a_lat) * radians) * math.cos(float(b_lat) * radians) * math.sin(lng_delta / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(root))


def _candidate_row(row: dict) -> dict:
    def number(key):
        try:
            return float(row.get(key))
        except (TypeError, ValueError):
            return None
    return {
        "content_id": str(row.get("contentid") or "").strip() or None,
        "name": str(row.get("title") or "").strip() or None,
        "address": str(row.get("addr1") or "").strip() or None,
        "latitude": number("mapy"),
        "longitude": number("mapx"),
        "content_type_id": str(row.get("contenttypeid") or "").strip() or None,
        "category": ">".join(str(row.get(key) or "").strip() for key in ("cat1", "cat2", "cat3") if row.get(key)),
    }


def _category_compatible(kakao_category: str | None, tour_type: str | None) -> bool:
    category = str(kakao_category or "").casefold()
    if any(token in category for token in ("fd6", "음식", "식당", "맛집")):
        return tour_type == "39"
    # The two explicitly targeted non-food places must be a tourism/culture type.
    return tour_type in {"12", "14", "28", "38"}


def _match(kakao: dict, tour: dict) -> dict:
    if _normalize_name(kakao["name"]) != _normalize_name(tour["name"]):
        return {"matched": False, "reason": "NAME"}
    kakao_tokens, tour_tokens = _address_tokens(kakao["address"]), _address_tokens(tour["address"])
    shared = kakao_tokens & tour_tokens
    shared_numbers = {token for token in shared if token[0].isdigit()}
    shared_words = {token for token in shared if not token[0].isdigit()}
    if not shared_numbers or len(shared_words) < 2:
        return {"matched": False, "reason": "ADDRESS", "shared_address_tokens": sorted(shared)}
    if not _category_compatible(kakao["category"], tour["content_type_id"]):
        return {"matched": False, "reason": "CATEGORY", "shared_address_tokens": sorted(shared)}
    distance = _distance_meters(kakao["latitude"], kakao["longitude"], tour["latitude"], tour["longitude"])
    if distance is None or distance > 150:
        return {"matched": False, "reason": "DISTANCE", "distance_meters": distance}
    return {"matched": True, "reason": "MATCHED", "distance_meters": distance}


def _places(settings: Settings) -> list[dict]:
    engine = create_engine(settings.require_mysql_url())
    query = text("""
        SELECT p.place_id, p.name, p.address, p.latitude, p.longitude, p.category,
               p.tour_content_id
        FROM plan_items pi
        JOIN travel_plans pl ON pl.plan_id = pi.plan_id
        JOIN places p ON p.place_id = pi.place_id
        WHERE pl.trip_id = :trip_id AND p.place_id IN :place_ids
        ORDER BY p.place_id
    """).bindparams(__import__("sqlalchemy").bindparam("place_ids", expanding=True))
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            rows = connection.execute(query, {"trip_id": TRIP_ID, "place_ids": list(TARGET_PLACE_IDS)}).mappings().all()
            connection.rollback()
    finally:
        engine.dispose()
    return [{key: (float(value) if isinstance(value, Decimal) else value) for key, value in dict(row).items()} for row in rows]


def _report_paths() -> tuple[Path, Path]:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = Path(tempfile.gettempdir()) / "dx_all_tourapi_link_diagnostics"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"trip76_tourapi_link_{stamp}.json", root / f"trip76_tourapi_link_{stamp}.md"


def _markdown(report: dict) -> str:
    lines = ["# Trip 76 TourAPI link diagnostic", "", f"External calls: {report['external_calls']}", ""]
    for target in report["targets"]:
        lines.extend([f"## {target.get('name') or target.get('place_id')}", "", "| Tour candidate | Result | Reason | Distance m |", "|---|---|---|---:|"])
        for candidate in target.get("tour_candidates", []):
            verdict = candidate.get("match", {})
            distance = verdict.get("distance_meters")
            lines.append(f"| {candidate.get('name') or '-'} | {verdict.get('matched', False)} | {verdict.get('reason', '-')} | {'' if distance is None else round(distance, 1)} |")
        if target.get("detail") is not None:
            detail = target["detail"]
            lines.extend(["", f"Hours: {detail.get('operating_hours') or 'not provided'}", "", f"Closed days: {detail.get('rest_date') or 'not provided'}"])
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="allow the capped TourAPI calls")
    args = parser.parse_args()
    settings = Settings()
    report = {
        "trip_id": TRIP_ID,
        "confirm": args.confirm,
        "external_call_plan": {"search_keyword2_max": MAX_SEARCH_CALLS, "detail_common_and_intro_max": MAX_DETAIL_CALLS, "total_max": MAX_EXTERNAL_CALLS},
        "external_calls": 0,
        "targets": _places(settings),
    }
    if not args.confirm:
        report["status"] = "DRY_RUN_NO_EXTERNAL_CALLS"
    else:
        provider = get_tour_destination_image_provider(settings)
        for target in report["targets"]:
            try:
                payload = provider._get_json("searchKeyword2", {"keyword": target["name"], "pageNo": 1, "numOfRows": 10})
                report["external_calls"] += 1
                candidates = [_candidate_row(row) for row in provider._response_rows(payload)]
                for candidate in candidates:
                    candidate["match"] = _match(target, candidate)
                target["tour_candidates"] = candidates
                matches = [candidate for candidate in candidates if candidate["match"]["matched"]]
                if len(matches) == 1:
                    target["detail"] = provider.get_place_detail(matches[0]["content_id"], include_images=False)
                    report["external_calls"] += 2
                else:
                    target["detail"] = None
                    target["link_outcome"] = "NO_UNIQUE_SAFE_MATCH"
            except AppError as error:
                target["provider_error"] = error.code
                report["status"] = "STOPPED_PROVIDER_ERROR"
                break
        else:
            report["status"] = "COMPLETED"
    json_path, markdown_path = _report_paths()
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    print(json_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
