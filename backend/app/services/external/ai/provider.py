from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


@dataclass(frozen=True)
class PreferenceAnalysisResult:
    interest_codes: list[str]
    summary: str


@dataclass(frozen=True)
class PlanDraftItem:
    sequence: int
    item_type: str
    title: str
    place_id: int | None
    start_time: str
    end_time: str
    recommendation_reason: str


@dataclass(frozen=True)
class PlanDraftDay:
    visit_date: date | None
    items: list[PlanDraftItem]


@dataclass(frozen=True)
class GeneratedPlanDraft:
    days: list[PlanDraftDay]


class PreferenceAnalysisProvider(Protocol):
    def analyze_preferences(self, text: str) -> PreferenceAnalysisResult: ...


class PlanGenerationProvider(Protocol):
    def generate_plan(self, trip: dict[str, Any], preferences: dict[str, Any], companions: list[dict[str, Any]], interests: list[str], preference_context: dict[str, Any], places: list[dict[str, Any]]) -> GeneratedPlanDraft: ...
    def regenerate_plan(self, trip: dict[str, Any], preferences: dict[str, Any], companions: list[dict[str, Any]], interests: list[str], preference_context: dict[str, Any], places: list[dict[str, Any]], reason: str, instruction: str, current_itinerary: list[dict[str, Any]] | None = None, feedback_codes: list[str] | None = None) -> GeneratedPlanDraft: ...
