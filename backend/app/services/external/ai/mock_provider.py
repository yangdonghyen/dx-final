from datetime import date
from pathlib import Path
from typing import Any

from app.core.exceptions import AppError
from app.services.external.ai.provider import GeneratedPlanDraft, PlanDraftDay, PlanDraftItem, PreferenceAnalysisResult
from app.services.external.mock_data import load_mock_collection


_ALLOWED_CODES = ("FOOD", "CAFE", "NATURE", "CULTURE", "HISTORY", "SHOPPING", "EXHIBITION", "ACTIVITY")
_KEYWORDS = (("cafe", "CAFE"), ("food", "FOOD"), ("nature", "NATURE"), ("culture", "CULTURE"), ("history", "HISTORY"), ("shop", "SHOPPING"), ("exhibition", "EXHIBITION"), ("activity", "ACTIVITY"))


class MockPreferenceAnalysisProvider:
    """Deterministic, local stand-in for an AI preference analyzer."""
    def analyze_preferences(self, text: str) -> PreferenceAnalysisResult:
        if not isinstance(text, str):
            raise AppError("INVALID_PROVIDER_INPUT", "text must be a string", 400)
        normalized = text.casefold()
        codes = [code for keyword, code in _KEYWORDS if keyword in normalized]
        if not codes:
            codes = ["CULTURE", "FOOD"] if normalized.strip() else []
        return PreferenceAnalysisResult(interest_codes=codes, summary="Deterministic mock preference analysis")


class MockPlanGenerationProvider:
    """Fixture-templated plan draft generator with no database or network access."""
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir

    def generate_plan(self, trip: dict[str, Any], preferences: dict[str, Any], companions: list[dict[str, Any]], interests: list[str], preference_context: dict[str, Any], places: list[dict[str, Any]]) -> GeneratedPlanDraft:
        if not isinstance(trip, dict) or not isinstance(places, list):
            raise AppError("INVALID_PROVIDER_INPUT", "trip and places are required", 400)
        templates = load_mock_collection("plans.json", "item_templates", {"sequence", "item_type", "title", "start_time", "end_time", "recommendation_reason"}, self.data_dir)
        provided_ids = {place.get("place_id") for place in places if isinstance(place, dict) and isinstance(place.get("place_id"), int)}
        visit_date = trip.get("start_date")
        if isinstance(visit_date, str):
            visit_date = date.fromisoformat(visit_date)
        if visit_date is not None and not isinstance(visit_date, date):
            raise AppError("INVALID_PROVIDER_INPUT", "start_date is invalid", 400)
        items = []
        for template in templates:
            place_id = template.get("place_id")
            if place_id not in provided_ids:
                place_id = None
            item_type = template["item_type"] if place_id is not None else "FREE_TIME"
            items.append(PlanDraftItem(sequence=template["sequence"], item_type=item_type, title=template["title"], place_id=place_id, start_time=template["start_time"], end_time=template["end_time"], recommendation_reason=template["recommendation_reason"]))
        return GeneratedPlanDraft(days=[PlanDraftDay(visit_date=visit_date, items=items)])

    def regenerate_plan(self, trip: dict[str, Any], preferences: dict[str, Any], companions: list[dict[str, Any]], interests: list[str], preference_context: dict[str, Any], places: list[dict[str, Any]], reason: str, instruction: str, current_itinerary: list[dict[str, Any]] | None = None, feedback_codes: list[str] | None = None) -> GeneratedPlanDraft:
        if reason not in {"USER_FATIGUE", "WEATHER_CHANGE"} or not isinstance(instruction, str) or not instruction.strip():
            raise AppError("INVALID_PROVIDER_INPUT", "A supported reason and instruction are required", 400)
        return self.generate_plan(trip, preferences, companions, interests, preference_context, places)
