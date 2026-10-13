"""Read-only, opt-in NAVER Local diagnosis for two REST-cafe name mismatches.

Without ``--confirm``, this script reads only the two already stored Kakao
places in a MySQL READ ONLY transaction and writes a UTF-8 report.  ``--confirm``
additionally calls the application's existing NAVER API-HUB provider, at most
twice per place and four times in total.  It never calls Kakao, NAVER Blog,
Kakao Mobility, Ollama, or plan generation.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.services.cafe_evidence_service import CafeEvidenceService, _norm, business_match  # noqa: E402
from app.services.external.factory import get_naver_cafe_evidence_provider  # noqa: E402
from app.services.external.naver_api_hub_provider import NaverLocalPlace  # noqa: E402
from app.services.plan_quality_rules import distance_meters  # noqa: E402


TARGET_PLACE_IDS = (513, 547)
MAX_NAVER_LOCAL_CALLS_PER_CAFE = 2
MAX_NAVER_LOCAL_CALLS_TOTAL = 4
SQL_TARGETS = """
SELECT place_id, name, address, category, latitude, longitude, kakao_place_id
FROM places
WHERE place_id IN (513, 547)
ORDER BY place_id
"""


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _stored_places() -> list[dict[str, Any]]:
    """Read the fixed targets without exposing connection settings."""
    with get_engine().connect() as connection:
        connection.execute(text("SET SESSION TRANSACTION READ ONLY"))
        connection.execute(text("START TRANSACTION READ ONLY"))
        try:
            rows = [dict(row._mapping) for row in connection.execute(text(SQL_TARGETS))]
        finally:
            connection.rollback()
    return [{
        "place_id": int(row["place_id"]),
        "name": str(row["name"]),
        "address": str(row["address"] or ""),
        "category": str(row["category"] or ""),
        "latitude": _number(row["latitude"]),
        "longitude": _number(row["longitude"]),
        "kakao_place_id": str(row["kakao_place_id"] or ""),
    } for row in rows]


def _as_place(row: dict[str, Any]):
    """The production matcher only requires these public Kakao place fields."""
    from types import SimpleNamespace

    return SimpleNamespace(**row)


def _public_local(row: NaverLocalPlace) -> dict[str, Any]:
    return {
        "name": row.name,
        "normalized_name": _norm(row.name),
        "address": row.address,
        "road_address": row.road_address,
        "latitude": row.latitude,
        "longitude": row.longitude,
    }


def _comparison(place, row: NaverLocalPlace) -> dict[str, Any]:
    decision = business_match(place, row)
    distance = distance_meters(place, row)
    return {
        "naver": _public_local(row),
        "matched": decision.matched,
        "reason": decision.reason,
        "relaxed_name": decision.relaxed_name,
        "distance_meters": round(distance, 1) if distance is not None else None,
    }


def _diagnose_with_naver(stored: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, str | None]:
    """Use the real provider and production query/matching rules within hard caps."""
    provider = get_naver_cafe_evidence_provider(Settings())
    total_calls, stopped_error, results = 0, None, []
    for stored_place in stored:
        place = _as_place(stored_place)
        queries = CafeEvidenceService._local_queries(place)[:MAX_NAVER_LOCAL_CALLS_PER_CAFE]
        stages, first_match = [], None
        for query in queries:
            if total_calls >= MAX_NAVER_LOCAL_CALLS_TOTAL:
                stopped_error = "DIAGNOSIS_NAVER_LOCAL_TOTAL_LIMIT"
                stages.append({"query": query, "status": "NOT_CALLED_LIMIT", "rows": []})
                break
            total_calls += 1
            try:
                rows = provider.search_local(query)
            except AppError as error:
                stopped_error = error.code
                stages.append({"query": query, "status": "API_ERROR", "error_code": error.code, "rows": []})
                break
            comparisons = [_comparison(place, row) for row in rows]
            stages.append({"query": query, "status": "OK", "response_count": len(rows), "rows": comparisons})
            first_match = next((row for row in comparisons if row["matched"]), None)
            # Same behavior as local_match_result: inspect every row returned
            # by this query, then stop before the fallback query on a match.
            if first_match is not None:
                break
        flat = [row for stage in stages for row in stage["rows"]]
        if first_match:
            result = "MATCHED"
        elif any(stage["status"] == "API_ERROR" for stage in stages):
            result = "API_ERROR"
        elif not flat:
            result = "NAVER_EMPTY"
        else:
            result = "NAVER_NO_SAME_BUSINESS"
        results.append({"kakao": stored_place, "queries": list(queries), "stages": stages, "result": result})
        if stopped_error:
            break
    return results, total_calls, stopped_error


def _markdown(payload: dict[str, Any]) -> str:
    lines = ["# REST cafe NAVER name-match diagnosis", "", "## Stored Kakao places", "", "| place_id | name | address | category | latitude | longitude |", "|---:|---|---|---|---:|---:|"]
    for row in payload["stored_places"]:
        lines.append(f"| {row['place_id']} | {row['name']} | {row['address']} | {row['category']} | {row['latitude']} | {row['longitude']} |")
    lines += ["", "## NAVER Local comparison", ""]
    if not payload["confirmed"]:
        lines.append("External NAVER Local calls were not made. Pass `--confirm` to run the bounded diagnosis.")
    else:
        lines += ["| Kakao place | query | NAVER place | matched | reason | relaxed name | distance m |", "|---|---|---|---|---|---|---:|"]
        for result in payload["diagnosis"]:
            for stage in result["stages"]:
                for row in stage["rows"]:
                    lines.append(f"| {result['kakao']['name']} | {stage['query']} | {row['naver']['name']} | {row['matched']} | {row['reason']} | {row['relaxed_name']} | {row['distance_meters'] or ''} |")
                if stage["status"] != "OK":
                    lines.append(f"| {result['kakao']['name']} | {stage['query']} |  | False | {stage['status']} |  |  |")
    lines += ["", "## Limits", "", json.dumps(payload["limits"], ensure_ascii=False), "", "## Safety", "", "- MySQL uses only the listed SELECT in a READ ONLY transaction.", "- No NAVER Blog, Kakao, Kakao Mobility, Ollama, or travel generation call is made.", "- Reports do not contain credentials, tokens, user identifiers, or NAVER blog content."]
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    directory = Path(tempfile.gettempdir()) / "dx-all-rest-cafe-name-diagnosis"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = directory / f"rest_cafe_name_match_{stamp}.json"
    markdown_path = directory / f"rest_cafe_name_match_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="required before NAVER Local is called")
    args = parser.parse_args()
    stored = _stored_places()
    payload: dict[str, Any] = {
        "confirmed": args.confirm,
        "target_place_ids": list(TARGET_PLACE_IDS),
        "stored_places": stored,
        "sql_select_statements": [SQL_TARGETS.strip()],
        "limits": {"naver_local_per_cafe": MAX_NAVER_LOCAL_CALLS_PER_CAFE, "naver_local_total": MAX_NAVER_LOCAL_CALLS_TOTAL},
        "diagnosis": [],
    }
    if args.confirm:
        diagnosis, calls, error = _diagnose_with_naver(stored)
        payload["diagnosis"] = diagnosis
        payload["limits"]["naver_local_calls_made"] = calls
        payload["stopped_error_code"] = error
    else:
        payload["plan"] = "No external call made. --confirm enables NAVER Local only (<=2 per cafe, <=4 total)."
    json_path, markdown_path = _write(payload)
    print(f"UTF-8 reports written: {json_path} and {markdown_path}")


if __name__ == "__main__":
    main()
