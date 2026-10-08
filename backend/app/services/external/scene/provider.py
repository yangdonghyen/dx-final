from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ScenePlaceCandidate:
    place_name: str
    city: str | None = None
    region: str | None = None
    country: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class SceneRecognitionResult:
    recognized: bool
    primary_candidate: ScenePlaceCandidate | None
    candidates: list[ScenePlaceCandidate]
    evidence: list[str]
    confidence: str
    needs_verification: bool = True


class SceneRecognitionProvider(Protocol):
    def recognize_scene(self, image_bytes: bytes, content_type: str) -> SceneRecognitionResult: ...
