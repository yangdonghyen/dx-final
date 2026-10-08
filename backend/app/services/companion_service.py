from app.core.exceptions import AppError
from app.repositories.companion_repository import CompanionInterestRepository, CompanionPreferenceRepository, CompanionRepository
from app.repositories.user_repository import InterestCodeRepository
from app.schemas.companion import CompanionPreferencesResponse, CompanionResponse


class CompanionService:
    def __init__(self, session):
        self.session = session
        self.companions = CompanionRepository(session)
        self.preferences = CompanionPreferenceRepository(session)
        self.interests = CompanionInterestRepository(session)
        self.codes = InterestCodeRepository(session)

    def _validate_codes(self, codes: list[str]):
        if len(self.codes.active_codes(codes)) != len(codes):
            raise AppError("INVALID_INTEREST_CODE", "Invalid interest code", 400)

    def _owned(self, user_id: int, companion_id: int):
        companion = self.companions.get(companion_id)
        if companion is None:
            raise AppError("COMPANION_NOT_FOUND", "Companion not found", 404)
        if companion.user_id != user_id:
            raise AppError("FORBIDDEN", "You do not own this companion", 403)
        return companion

    def _response(self, companion, preference=None, interests=None):
        preference = preference if preference is not None else self.preferences.get(companion.companion_id)
        interests = interests if interests is not None else self.interests.list_codes(companion.companion_id)
        return CompanionResponse(
            companion_id=companion.companion_id, name=companion.name, relation=companion.relation, age_group=companion.age_group,
            preferences=CompanionPreferencesResponse(
                interests=interests, walking_tolerance=preference.walking_tolerance, rest_frequency=preference.rest_frequency,
                avoid_stairs=preference.avoid_stairs, avoid_hills=preference.avoid_hills, taxi_allowed=preference.taxi_allowed,
            ),
        )

    def list(self, user_id: int):
        companions = self.companions.list_active_for_user(user_id)
        ids = [companion.companion_id for companion in companions]
        preferences = self.preferences.for_companions(ids)
        interests = self.interests.for_companions(ids)
        return [self._response(companion, preferences[companion.companion_id], interests[companion.companion_id]) for companion in companions]

    def create(self, user_id: int, request):
        preference_values = request.preferences.model_dump()
        codes = preference_values.pop("interests")
        self._validate_codes(codes)
        try:
            companion = self.companions.create(user_id, **request.model_dump(exclude={"preferences"}))
            preference = self.preferences.create(companion.companion_id, **preference_values)
            self.interests.replace(companion.companion_id, codes)
            self.session.commit()
            return self._response(companion, preference, codes)
        except Exception:
            self.session.rollback()
            raise

    def update(self, user_id: int, companion_id: int, request):
        companion = self._owned(user_id, companion_id)
        values = request.model_dump(exclude_unset=True, exclude={"preferences"})
        preference_input = request.preferences
        if preference_input is not None and "interests" in preference_input.model_fields_set:
            self._validate_codes(preference_input.interests)
        try:
            if values: self.companions.update(companion, **values)
            preference = self.preferences.get(companion_id)
            if preference_input is not None:
                preference_values = preference_input.model_dump(exclude_unset=True, exclude={"interests"})
                if preference_values: self.preferences.update(preference, **preference_values)
                if "interests" in preference_input.model_fields_set:
                    self.interests.replace(companion_id, preference_input.interests)
            self.session.commit()
            return self._response(companion)
        except Exception:
            self.session.rollback()
            raise

    def archive(self, user_id: int, companion_id: int):
        companion = self._owned(user_id, companion_id)
        try:
            self.companions.update(companion, status="ARCHIVED")
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
