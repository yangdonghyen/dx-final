from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
AgeGroup = Literal["UNDER_20", "20S", "30S", "40S", "50S", "60S", "70S_PLUS"]
WalkingTolerance = Literal["VERY_LOW", "LOW", "NORMAL", "HIGH"]
RestFrequency = Literal["LOW", "NORMAL", "HIGH"]
TravelStyle = Literal["SLOW", "STANDARD", "FOOD_FOCUSED"]
class PreferencesResponse(BaseModel):
    interests: list[str]
    walking_tolerance: WalkingTolerance | None
    rest_frequency: RestFrequency | None
    avoid_stairs: bool
    avoid_hills: bool
    taxi_allowed: bool
    travel_style: TravelStyle | None
    senior_mode: bool
class UserMeResponse(BaseModel):
    user_id: int
    nickname: str | None
    age_group: AgeGroup | None
    profile_completed: bool
    preferences: PreferencesResponse
class UpdateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nickname: str | None = Field(default=None, max_length=50)
    age_group: AgeGroup | None = None
class UpdateUserResponse(BaseModel):
    user_id: int
    nickname: str | None
    age_group: AgeGroup | None
    profile_completed: bool
class UpdatePreferencesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interests: list[str] | None = None
    walking_tolerance: WalkingTolerance | None = None
    rest_frequency: RestFrequency | None = None
    avoid_stairs: bool | None = None
    avoid_hills: bool | None = None
    taxi_allowed: bool | None = None
    travel_style: TravelStyle | None = None
    senior_mode: bool | None = None
    @model_validator(mode="after")
    def normalize(self):
        if not self.model_fields_set: raise ValueError("At least one preference field is required")
        if self.interests is not None:
            self.interests = [x.strip().upper() for x in self.interests]
            if len(self.interests) != len(set(self.interests)): raise ValueError("Interest codes must be unique")
        return self
