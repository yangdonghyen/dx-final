from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AgeGroup = Literal["UNDER_20", "20S", "30S", "40S", "50S", "60S", "70S_PLUS"]
CompanionRelation = Literal["FATHER", "MOTHER", "SPOUSE", "CHILD", "FRIEND", "OTHER"]
WalkingTolerance = Literal["VERY_LOW", "LOW", "NORMAL", "HIGH"]
RestFrequency = Literal["LOW", "NORMAL", "HIGH"]


class CompanionPreferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interests: list[str] = Field(default_factory=list)
    walking_tolerance: WalkingTolerance | None = None
    rest_frequency: RestFrequency | None = None
    avoid_stairs: bool = False
    avoid_hills: bool = False
    taxi_allowed: bool = True

    @model_validator(mode="after")
    def normalize_interests(self):
        self.interests = [code.strip().upper() for code in self.interests]
        if len(self.interests) != len(set(self.interests)):
            raise ValueError("Interest codes must be unique")
        return self


class CompanionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    relation: CompanionRelation
    age_group: AgeGroup | None = None
    preferences: CompanionPreferenceInput


class CompanionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=50)
    relation: CompanionRelation | None = None
    age_group: AgeGroup | None = None
    preferences: CompanionPreferenceInput | None = None

    @model_validator(mode="after")
    def has_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one companion field is required")
        return self


class CompanionPreferencesResponse(BaseModel):
    interests: list[str]
    walking_tolerance: WalkingTolerance | None
    rest_frequency: RestFrequency | None
    avoid_stairs: bool
    avoid_hills: bool
    taxi_allowed: bool


class CompanionResponse(BaseModel):
    companion_id: int
    name: str
    relation: CompanionRelation
    age_group: AgeGroup | None
    preferences: CompanionPreferencesResponse


class CompanionListResponse(BaseModel):
    companions: list[CompanionResponse]


class CompanionDeleteResponse(BaseModel):
    message: Literal["companion_archived"] = "companion_archived"
