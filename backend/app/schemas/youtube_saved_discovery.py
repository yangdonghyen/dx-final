from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class YouTubeSavedDiscoveryCreate(BaseModel):
    video_id: str
    position_sec: int = Field(ge=0)
    page_url: str | None = None
    title: str | None = None
    channel_title: str | None = None
    thumbnail_url: str | None = None


class YouTubeSavedDiscoveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    saved_discovery_id: int
    video_id: str
    position_sec: int
    page_url: str | None = None
    title: str
    channel_title: str | None = None
    thumbnail_url: str | None = None
    destination_name: str | None = None
    representative_image_url: str | None = None
    created_at: datetime


class YouTubeSavedDiscoveryListResponse(BaseModel):
    items: list[YouTubeSavedDiscoveryResponse]


class DestinationRecommendationPlace(BaseModel):
    content_id: str
    title: str
    image_url: str
    category: str
    address: str | None = None
    content_type_id: int | None = None
    cat1: str | None = None
    cat2: str | None = None
    cat3: str | None = None
    map_x: float | None = None
    map_y: float | None = None


class TourPlaceDetailResponse(BaseModel):
    content_id: str
    content_type_id: int | None = None
    title: str | None = None
    address: str | None = None
    image_url: str | None = None
    overview: str | None = None
    homepage: str | None = None
    map_x: float | None = None
    map_y: float | None = None
    cat1: str | None = None
    cat2: str | None = None
    cat3: str | None = None
    operating_hours: str | None = None
    rest_date: str | None = None
    use_fee: str | None = None
    parking: str | None = None
    info_center: str | None = None


class DestinationRecommendationsResponse(BaseModel):
    destination_name: str
    themes: list[str] = Field(default_factory=list)
    places: list[DestinationRecommendationPlace]
