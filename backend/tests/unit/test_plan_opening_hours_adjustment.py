from datetime import date, time
from types import SimpleNamespace

from app.services.external.ai.provider import PlanDraftItem
from app.services.plan_opening_hours_adjustment import adjust_day_for_opening_hours


def _place(hours=True):
    return SimpleNamespace(
        place_id=401, verification_status="VERIFIED" if hours else "UNKNOWN",
        opening_hours={"schedule": {"monday": {"open": "09:00", "close": "18:00"}}} if hours else None,
    )


def _row(sequence, kind, place_id, start, end):
    item = PlanDraftItem(sequence, kind, kind, place_id, start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes"), "reason")
    return item, start, end


def test_closing_conflict_uses_only_preceding_free_time_and_keeps_visit_duration():
    rows = [
        _row(1, "MEAL", 10, time(12, 31), time(14, 1)),
        _row(2, "FREE_TIME", None, time(14, 1), time(16, 1)),
        _row(3, "PLACE", 401, time(16, 32), time(18, 2)),
    ]
    changed, adjustments, unresolved = adjust_day_for_opening_hours(rows, date(2026, 10, 26), {401: _place()}, set(), {"travel_style": "SLOW"})

    assert unresolved == []
    assert adjustments == [{"place_id": 401, "minutes": 2, "reason": "VERIFIED_CLOSING_TIME"}]
    assert (changed[1][1], changed[1][2]) == (time(14, 1), time(15, 59))
    assert (changed[2][1], changed[2][2]) == (time(16, 30), time(18, 0))
    assert changed[0] == rows[0]  # meal is protected
    # The 31-minute verified CAR leg still fits after the FREE_TIME reduction.
    assert (changed[2][1].hour * 60 + changed[2][1].minute) >= 14 * 60 + 1 + 118 + 31


def test_anchor_and_slow_minimum_free_time_are_not_reduced():
    rows = [_row(1, "FREE_TIME", None, time(15), time(16)), _row(2, "PLACE", 401, time(16, 30), time(18, 30))]
    _, adjustments, unresolved = adjust_day_for_opening_hours(rows, date(2026, 10, 26), {401: _place()}, {401}, {"travel_style": "SLOW"})
    assert adjustments == [] and unresolved[0]["reason"] == "ANCHOR_OR_UNSUPPORTED_CONFLICT"


def test_unknown_hours_never_move_a_schedule():
    rows = [_row(1, "FREE_TIME", None, time(14), time(16)), _row(2, "PLACE", 401, time(16, 30), time(18, 30))]
    changed, adjustments, unresolved = adjust_day_for_opening_hours(rows, date(2026, 10, 26), {401: _place(hours=False)}, set(), {"travel_style": "SLOW"})
    assert changed == rows and adjustments == unresolved == []


def test_unresolvable_conflict_keeps_schedule_for_temporal_validation():
    rows = [_row(1, "MEAL", 10, time(15), time(16)), _row(2, "PLACE", 401, time(16, 30), time(18, 30))]
    changed, adjustments, unresolved = adjust_day_for_opening_hours(rows, date(2026, 10, 26), {401: _place()}, set(), {"travel_style": "SLOW"})
    assert changed == rows and adjustments == [] and unresolved[0]["reason"] == "NO_FLEXIBLE_FREE_TIME"
