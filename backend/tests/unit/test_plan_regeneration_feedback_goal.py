import pytest

from app.core.exceptions import AppError
from app.services.plan_regeneration_preview_service import (
    PlanRegenerationPreviewService,
)

Service = PlanRegenerationPreviewService

candidates = {
    101: {"category": "AT4"},
    102: {"category": "AT4"},
    103: {"category": "AT4"},
    104: {"category": "CE7"},
    105: {"category": "FD6"},
}

anchors = {101}


def item(place_id, item_type="PLACE"):
    return {
        "place_id": place_id,
        "item_type": item_type,
    }


def test_places_rejects_unchanged_activity_count():
    before = [item(101), item(102), item(103)]
    after = [
        item(101), item(102), item(103),
        item(104), item(None, "REST"),
    ]

    with pytest.raises(AppError) as error:
        Service._validate_feedback_goal(
            before, after, ["places"], candidates, anchors
        )

    assert error.value.code == "FEEDBACK_GOAL_NOT_MET"


def test_places_accepts_reduced_activity_count():
    before = [item(101), item(102), item(103)]
    after = [
        item(101), item(102),
        item(104),
        item(105, "MEAL"),
        item(None, "REST"),
    ]

    Service._validate_feedback_goal(
        before, after, ["places"], candidates, anchors
    )


def test_places_rejects_no_optional_activity():
    before = [item(101)]
    after = [item(101), item(None, "REST")]

    with pytest.raises(AppError) as error:
        Service._validate_feedback_goal(
            before, after, ["places"], candidates, anchors
        )

    assert error.value.code == "FEEDBACK_GOAL_UNACHIEVABLE"


def test_other_feedback_is_not_affected():
    before = [item(101), item(102)]
    after = [item(101), item(102)]

    Service._validate_feedback_goal(
        before, after, ["walking"], candidates, anchors
    )

    with pytest.raises(AppError) as error:
        Service._validate_feedback_goal(
            before, after, ["rest"], candidates, anchors
        )

    assert error.value.code == "FEEDBACK_GOAL_NOT_MET"


def make_rest(start, end):
    return {
        "place_id": None,
        "item_type": "REST",
        "start_time": start,
        "end_time": end,
    }


def test_rest_rejects_unchanged_duration():
    before = [item(101), make_rest("12:00", "12:30")]
    after = [item(101), make_rest("12:00", "12:30")]

    with pytest.raises(AppError) as error:
        Service._validate_feedback_goal(
            before, after, ["rest"], candidates, anchors
        )

    assert error.value.code == "FEEDBACK_GOAL_NOT_MET"


def test_rest_accepts_increased_duration():
    before = [item(101), make_rest("12:00", "12:30")]
    after = [item(101), make_rest("12:00", "13:00")]

    Service._validate_feedback_goal(
        before, after, ["rest"], candidates, anchors
    )


def test_rest_accepts_new_rest_when_previous_had_none():
    before = [item(101)]
    after = [item(101), make_rest("12:00", "12:30")]

    Service._validate_feedback_goal(
        before, after, ["rest"], candidates, anchors
    )


def test_places_and_rest_must_both_improve():
    before = [
        item(101), item(102), item(103),
        make_rest("12:00", "12:30"),
    ]
    after = [
        item(101), item(102),
        make_rest("12:00", "12:30"),
    ]

    with pytest.raises(AppError) as error:
        Service._validate_feedback_goal(
            before, after, ["places", "rest"],
            candidates, anchors
        )

    assert error.value.code == "FEEDBACK_GOAL_NOT_MET"


def test_rest_rejects_unverifiable_time():
    before = [make_rest(None, None)]
    after = [make_rest("12:00", "13:00")]

    with pytest.raises(AppError) as error:
        Service._validate_feedback_goal(
            before, after, ["rest"], candidates, anchors
        )

    assert error.value.code == "FEEDBACK_GOAL_UNVERIFIABLE"
