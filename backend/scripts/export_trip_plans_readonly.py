"""Read-only export of saved trips and plans for offline quality review.

Usage (from backend/):
    C:\\Python314\\python.exe scripts\\export_trip_plans_readonly.py 66 67 68

Writes ../docs/task75q_trip_export.json. The MySQL session is put in READ ONLY
mode and rolled back; nothing is inserted, updated or deleted. Secrets, user
ids and companion names are not exported.
"""

import json
import re
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_engine  # noqa: E402

HIDDEN = re.compile(r"(user_id|email|password|token|secret|name_snapshot|phone)", re.I)
OUTPUT = Path(__file__).resolve().parents[2] / "docs" / "task75q_trip_export.json"


def rows(connection, sql, **params):
    result = connection.execute(text(sql), params)
    keys = list(result.keys())
    return [{key: value for key, value in zip(keys, row) if not HIDDEN.search(key)} for row in result]


def table_exists(connection, name):
    return bool(connection.execute(text("SHOW TABLES LIKE :name"), {"name": name}).fetchall())


def export_trip(connection, trip_id):
    trip = rows(connection, "SELECT * FROM trips WHERE trip_id = :id", id=trip_id)
    data = {"trip": trip[0] if trip else None}
    for table in ("trip_preferences", "trip_interests", "trip_selected_places", "trip_companions"):
        data[table] = rows(connection, f"SELECT * FROM {table} WHERE trip_id = :id", id=trip_id) if table_exists(connection, table) else "TABLE_MISSING"
    plans = rows(connection, "SELECT * FROM travel_plans WHERE trip_id = :id", id=trip_id)
    data["travel_plans"] = plans
    plan_ids = [plan["plan_id"] for plan in plans]
    data["plan_items"], data["plan_revisions"], data["plan_validation_issues"], data["previews"] = [], [], [], []
    for plan_id in plan_ids:
        data["plan_items"] += rows(connection, "SELECT * FROM plan_items WHERE plan_id = :id ORDER BY visit_date, sequence_no", id=plan_id)
        for table, key in (("plan_revisions", "plan_revisions"), ("plan_validation_issues", "plan_validation_issues"), ("plan_regeneration_previews", "previews")):
            if table_exists(connection, table):
                data[key] += rows(connection, f"SELECT * FROM {table} WHERE plan_id = :id", id=plan_id)
    place_ids = sorted({item["place_id"] for item in data["plan_items"] if item.get("place_id")}
                       | {row["place_id"] for row in data["trip_selected_places"] if isinstance(row, dict) and row.get("place_id")})
    data["places"] = [rows(connection, "SELECT * FROM places WHERE place_id = :id", id=place_id)[0] for place_id in place_ids]
    return data


def main(trip_ids):
    settings = get_settings()
    summary = {
        "settings": {
            "plan_provider": settings.plan_provider,
            "place_provider": settings.place_provider,
            "route_provider": settings.route_provider,
            "exaone_model": settings.exaone_model,
            "exaone_num_ctx": settings.exaone_num_ctx,
            "ai_api_timeout_seconds": settings.ai_api_timeout_seconds,
            "kakao_rest_api_key": "SET" if settings.kakao_rest_api_key.get_secret_value() else "EMPTY",
        },
        "trips": {},
    }
    with get_engine().connect() as connection:
        connection.execute(text("SET SESSION TRANSACTION READ ONLY"))
        connection.execute(text("START TRANSACTION READ ONLY"))
        try:
            for trip_id in trip_ids:
                summary["trips"][str(trip_id)] = export_trip(connection, trip_id)
        finally:
            connection.rollback()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"wrote {OUTPUT} trips={','.join(map(str, trip_ids))}")


if __name__ == "__main__":
    main([int(value) for value in sys.argv[1:]] or [66, 67, 68])
