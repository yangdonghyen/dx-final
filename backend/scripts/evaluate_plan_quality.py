"""Run the server's plan quality rules on an exported trip file (offline).

Reads the JSON written by scripts/export_trip_plans_readonly.py and prints,
per trip, the warnings the current rules would store.  It opens no database
connection and calls no external API, so saved trips (e.g. 67, 68) can be
used as regression material without changing them.

    python scripts/evaluate_plan_quality.py docs/task75q_trip_export.json 67 68
"""

import json
import sys
from datetime import date, time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.plan_quality_rules import DayStop, PlanQualityRules, review_plan  # noqa: E402


def _time(value):
    return time.fromisoformat(value.zfill(8)) if value else None


def evaluate(trip_export):
    places = {row["place_id"]: SimpleNamespace(**row) for row in trip_export.get("places", [])}
    start = date.fromisoformat(trip_export["trip"]["start_date"])
    by_date = {}
    for item in trip_export.get("plan_items", []):
        by_date.setdefault(item["visit_date"], []).append(item)
    days = []
    for visit_date, rows in sorted(by_date.items()):
        label = f"{(date.fromisoformat(visit_date) - start).days + 1}일차"
        days.append((label, [
            DayStop(
                row["sequence_no"], row["item_type"], _time(row["start_time"]), _time(row["end_time"]),
                places.get(row["place_id"]), row.get("travel_minutes_from_previous"),
            )
            for row in rows
        ]))
    return review_plan(days, PlanQualityRules())


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    exported = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    trip_ids = argv[2:] or list(exported["trips"])
    for trip_id in trip_ids:
        trip = exported["trips"].get(str(trip_id))
        if trip is None or not trip.get("plan_items"):
            print(f"trip {trip_id}: no saved plan")
            continue
        findings = evaluate(trip)
        print(f"trip {trip_id}: {len(findings)} warning(s)")
        for finding in findings:
            print(f"  [{finding.code}] {finding.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
