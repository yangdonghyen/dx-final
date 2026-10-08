from pydantic import BaseModel


class ScenePlaceCandidateResponse(BaseModel):
    place_name: str
    city: str | None = None
    region: str | None = None
    country: str | None = None
    category: str | None = None


class SceneVerifiedPlaceResponse(BaseModel):
    verified: bool = True
    place_name: str
    address: str
    road_address: str | None = None
    latitude: float
    longitude: float
    category: str
    source: str = "KAKAO"


class SceneImageResponse(BaseModel):
    received: bool = True
    filename: str
    content_type: str
    size_bytes: int
    recognized: bool | None = None
    primary_candidate: ScenePlaceCandidateResponse | None = None
    candidates: list[ScenePlaceCandidateResponse] | None = None
    evidence: list[str] | None = None
    confidence: str | None = None
    needs_verification: bool | None = None
    place_verified: bool | None = None
    verified_place: SceneVerifiedPlaceResponse | None = None
