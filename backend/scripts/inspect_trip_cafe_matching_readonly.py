"""Offline, read-only cafe matching inspection for trips 70, 71 and 72.

This script never calls Kakao, NAVER, Ollama, or a plan-generation service.
It uses SELECT statements inside a MySQL READ ONLY transaction and writes a
UTF-8 JSON/Markdown report.  Database credentials and connection URLs are
never printed.

The five NAVER fixture names are the facts supplied with this investigation.
Their address/coordinate values were not present in the repository, so this
script deliberately marks a business-match result as ``FIXTURE_INCOMPLETE``
until the exact already-captured response is supplied with ``--fixture``.
It never invents those values.

Usage (from backend):
    python scripts/inspect_trip_cafe_matching_readonly.py
    python scripts/inspect_trip_cafe_matching_readonly.py --fixture C:\\safe\\captured_naver.json

Fixture format is a UTF-8 JSON array of objects with exactly these public
place fields: name, address, road_address, latitude, longitude.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_engine  # noqa: E402
from app.services.cafe_evidence_service import (  # noqa: E402
    _address_region_stems,
    _names_match,
    _norm,
    business_match,
)
from app.services.external.naver_api_hub_provider import NaverLocalPlace  # noqa: E402
from app.services.plan_quality_rules import distance_meters  # noqa: E402


TRIP_IDS = (70, 71, 72)
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# Only the five names were supplied in the task context.  Do not replace the
# missing fields with guessed web data.  --fixture accepts the exact response
# that was already captured by the operator without making an API request.
KNOWN_NAVER_FIXTURES = (
    {"name": "금송 덕미 해운대 해리단길점", "address": None, "road_address": None, "latitude": None, "longitude": None},
    {"name": "아틀리에 스미다 미포점", "address": None, "road_address": None, "latitude": None, "longitude": None},
    {"name": "모모스커피 마린시티점", "address": None, "road_address": None, "latitude": None, "longitude": None},
    {"name": "후스후무무 베이커리", "address": None, "road_address": None, "latitude": None, "longitude": None},
    {"name": "부산당 해운대본점", "address": None, "road_address": None, "latitude": None, "longitude": None},
)

SQL_PLAN_ITEMS = """
SELECT
    tp.trip_id,
    tp.plan_id,
    pi.visit_date,
    pi.sequence_no,
    pi.item_type,
    p.name AS place_name,
    p.address AS place_address,
    p.latitude AS place_latitude,
    p.longitude AS place_longitude,
    p.kakao_place_id
FROM travel_plans AS tp
JOIN plan_items AS pi ON pi.plan_id = tp.plan_id
LEFT JOIN places AS p ON p.place_id = pi.place_id
WHERE tp.trip_id IN (70, 71, 72)
ORDER BY tp.trip_id, tp.plan_id, pi.visit_date, pi.sequence_no
"""

SQL_LINKED_CE7 = """
SELECT DISTINCT
    tp.trip_id,
    tp.plan_id,
    p.name,
    p.address,
    p.latitude,
    p.longitude
FROM travel_plans AS tp
JOIN plan_items AS pi ON pi.plan_id = tp.plan_id
JOIN places AS p ON p.place_id = pi.place_id
WHERE tp.trip_id IN (70, 71, 72)
  AND p.category LIKE '%CE7%'
ORDER BY tp.trip_id, tp.plan_id, p.name
"""


@dataclass(frozen=True)
class PublicPlace:
    trip_id: int
    plan_id: int
    name: str
    address: str | None
    latitude: float | None
    longitude: float | None


def _rows(connection, sql: str) -> list[dict[str, Any]]:
    result = connection.execute(text(sql))
    return [dict(row._mapping) for row in result]


def _float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError, DecimalException):
        return None


class DecimalException(Exception):
    """Local compatibility guard; no values are transformed or persisted."""


def _fixture_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return [dict(row) for row in KNOWN_NAVER_FIXTURES]
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("fixture must be a JSON array")
    rows = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("each fixture requires a string name")
        rows.append({key: item.get(key) for key in ("name", "address", "road_address", "latitude", "longitude")})
    return rows


def _pattern(kakao: PublicPlace, naver_name: str) -> str:
    source, local = _norm(kakao.name), _norm(naver_name)
    if source == local:
        return "EXACT_NORMALIZED"
    _, relaxed = _names_match(kakao.name, naver_name, kakao.address or "")
    if relaxed and _norm(naver_name) != _norm(kakao.name):
        return "RELAXED_MATCH_CANDIDATE"
    stems = _address_region_stems(kakao.address or "")
    if any(_norm(token) in stems for token in naver_name.split()):
        return "NAVER_INDEPENDENT_ADDRESS_REGION"
    if source in local or local in source:
        return "PREFIX_SUFFIX_OR_MISSING_WORD"
    return "OTHER_NAME_DIFFERENCE"


def _complete_fixture(row: dict[str, Any]) -> bool:
    return bool(row.get("address") or row.get("road_address")) and row.get("latitude") is not None and row.get("longitude") is not None


def _match_rows(cafes: list[PublicPlace], fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    report = []
    for cafe in cafes:
        for fixture in fixtures:
            base = {
                "trip_id": cafe.trip_id,
                "plan_id": cafe.plan_id,
                "candidate_name": cafe.name,
                "candidate_normalized_name": _norm(cafe.name),
                "candidate_address": cafe.address,
                "candidate_latitude": cafe.latitude,
                "candidate_longitude": cafe.longitude,
                "naver_name": fixture["name"],
                "naver_normalized_name": _norm(fixture["name"]),
                "name_pattern": _pattern(cafe, fixture["name"]),
            }
            if not _complete_fixture(fixture):
                report.append({**base, "match": "NOT_RUN", "reason_code": "FIXTURE_INCOMPLETE", "distance_meters": None})
                continue
            naver = NaverLocalPlace(
                fixture["name"], "", fixture.get("address") or "", fixture.get("road_address") or "",
                _float(fixture["latitude"]), _float(fixture["longitude"]),
            )
            decision = business_match(cafe, naver)
            report.append({
                **base,
                "match": "MATCHED" if decision.matched else "NOT_MATCHED",
                "reason_code": decision.reason,
                "distance_meters": round(distance_meters(cafe, naver), 1) if distance_meters(cafe, naver) is not None else None,
            })
    return report


def _markdown(cafes: list[PublicPlace], matches: list[dict[str, Any]], fixture_complete: bool) -> str:
    lines = [
        "# Trip 70–72 cafe matching (read-only)",
        "",
        "## Stored itinerary-linked CE7 places",
        "",
        "| trip | candidate | normalized | parcel address | latitude | longitude |",
        "|---:|---|---|---|---:|---:|",
    ]
    for cafe in cafes:
        lines.append(f"| {cafe.trip_id} | {cafe.name} | {_norm(cafe.name)} | {cafe.address or ''} | {cafe.latitude or ''} | {cafe.longitude or ''} |")
    lines += ["", "## Fixture comparisons", "", "| candidate | normalized | NAVER name | normalized | result | reason | distance m |", "|---|---|---|---|---|---|---:|"]
    for row in matches:
        lines.append(
            f"| {row['candidate_name']} | {row['candidate_normalized_name']} | {row['naver_name']} | "
            f"{row['naver_normalized_name']} | {row['match']} | {row['reason_code']} | {row['distance_meters'] or ''} |"
        )
    lines += ["", "## Reproduction limits", ""]
    if not fixture_complete:
        lines.append("- NAVER fixture addresses/coordinates were not available in the repository or task payload; business_match and distance are therefore `FIXTURE_INCOMPLETE`, not guessed.")
    lines.append("- The schema stores itinerary-linked places but not the per-REST-slot Kakao search result list or prior NAVER response bodies. `NAVER_EMPTY`, `NAVER_NO_SAME_BUSINESS`, and `LOCAL_LOOKUP_LIMIT` distribution for the historical 10-candidate slots is therefore 재현 불가 from MySQL alone.")
    lines.append("- This script uses only the SELECT statements listed in its JSON output.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, help="UTF-8 JSON captured earlier; never fetched by this script")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    fixtures = _fixture_rows(args.fixture)
    with get_engine().connect() as connection:
        connection.execute(text("SET SESSION TRANSACTION READ ONLY"))
        connection.execute(text("START TRANSACTION READ ONLY"))
        try:
            linked = _rows(connection, SQL_LINKED_CE7)
            plan_items = _rows(connection, SQL_PLAN_ITEMS)
        finally:
            connection.rollback()

    cafes = [PublicPlace(
        trip_id=int(row["trip_id"]), plan_id=int(row["plan_id"]),
        name=str(row["name"]), address=row["address"], latitude=_float(row["latitude"]),
        longitude=_float(row["longitude"]),
    ) for row in linked]
    matches = _match_rows(cafes, fixtures)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "trip_ids": list(TRIP_IDS),
        "read_only": True,
        "sql_select_statements": [SQL_PLAN_ITEMS.strip(), SQL_LINKED_CE7.strip()],
        "stored_itinerary_linked_ce7_places": [asdict(cafe) for cafe in cafes],
        "fixture_complete": all(_complete_fixture(row) for row in fixtures),
        "fixture_comparisons": matches,
        "historical_reason_distribution": {
            "status": "REPRODUCTION_NOT_POSSIBLE",
            "reason": "Per-slot Kakao result lists and NAVER response bodies are not persisted in the MySQL schema.",
            "codes": ["NAVER_EMPTY", "NAVER_NO_SAME_BUSINESS", "LOCAL_LOOKUP_LIMIT"],
        },
        "plan_item_count_read": len(plan_items),
    }
    json_path = args.output_dir / "trip_70_72_cafe_matching_readonly.json"
    markdown_path = args.output_dir / "trip_70_72_cafe_matching_readonly.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    markdown_path.write_text(_markdown(cafes, matches, payload["fixture_complete"]), encoding="utf-8")
    print(f"wrote UTF-8 reports: {json_path.name}, {markdown_path.name}; linked_ce7={len(cafes)}")


if __name__ == "__main__":
    main()
