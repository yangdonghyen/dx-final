from app.core.exceptions import AppError
from app.repositories.user_repository import InterestCodeRepository, UserInterestRepository, UserPreferenceRepository, UserRepository
from app.schemas.user import PreferencesResponse

class UserService:
    def __init__(self, session):
        self.session=session; self.users=UserRepository(session); self.prefs=UserPreferenceRepository(session); self.interests=UserInterestRepository(session); self.codes=InterestCodeRepository(session)
    def get(self,user_id):
        user=self.users.get(user_id)
        if user is None: raise AppError("USER_NOT_FOUND", "User not found", 401)
        if user.status != "ACTIVE": raise AppError("USER_INACTIVE", "User is inactive", 403)
        return user
    def response(self,user_id):
        p=self.prefs.get(user_id)
        return PreferencesResponse(interests=self.interests.list_codes(user_id),walking_tolerance=p.walking_tolerance if p else None,rest_frequency=p.rest_frequency if p else None,avoid_stairs=p.avoid_stairs if p else False,avoid_hills=p.avoid_hills if p else False,taxi_allowed=p.taxi_allowed if p else True,travel_style=p.travel_style if p else None,senior_mode=p.senior_mode if p else False)
    def _complete(self,user):
        self.users.update(user,profile_completed=bool(user.nickname and user.age_group and self.prefs.get(user.user_id) and self.interests.list_codes(user.user_id)))
    def update_profile(self,user,values):
        try: self.users.update(user,**values); self._complete(user); self.session.commit(); return user
        except Exception: self.session.rollback(); raise
    def update_preferences(self,user,request):
        try:
            p=self.prefs.get_or_create(user.user_id); self.prefs.update(p,**request.model_dump(exclude_unset=True,exclude={"interests"}))
            if "interests" in request.model_fields_set:
                codes=request.interests or []
                if len(self.codes.active_codes(codes)) != len(codes): raise AppError("INVALID_INTEREST_CODE", "Invalid interest code", 400)
                self.interests.replace(user.user_id,codes)
            self._complete(user); self.session.commit(); return self.response(user.user_id)
        except Exception: self.session.rollback(); raise
