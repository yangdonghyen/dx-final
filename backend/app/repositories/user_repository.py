from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user import InterestCode, User, UserInterest, UserPreference
class UserRepository:
    def __init__(self,s:Session): self.s=s
    def get(self,uid): return self.s.get(User,uid)
    def create(self, **fields):
        x=User(**fields); self.s.add(x); self.s.flush(); return x
    def update(self,x,**fields):
        for k,v in fields.items(): setattr(x,k,v)
        self.s.flush(); return x
class UserPreferenceRepository:
    def __init__(self,s): self.s=s
    def get(self,uid): return self.s.scalar(select(UserPreference).where(UserPreference.user_id==uid))
    def get_or_create(self,uid):
        x=self.get(uid)
        if x is None: x=UserPreference(user_id=uid); self.s.add(x); self.s.flush()
        return x
    def update(self,x,**fields):
        for k,v in fields.items(): setattr(x,k,v)
        self.s.flush(); return x
class UserInterestRepository:
    def __init__(self,s): self.s=s
    def list_codes(self,uid): return list(self.s.scalars(select(UserInterest.interest_code).where(UserInterest.user_id==uid).order_by(UserInterest.interest_code)))
    def replace(self,uid,codes):
        for x in self.s.scalars(select(UserInterest).where(UserInterest.user_id==uid)).all(): self.s.delete(x)
        self.s.flush(); self.s.add_all([UserInterest(user_id=uid,interest_code=c) for c in codes]); self.s.flush()
class InterestCodeRepository:
    def __init__(self,s): self.s=s
    def active_codes(self,codes):
        values=list(codes)
        return set() if not values else set(self.s.scalars(select(InterestCode.interest_code).where(InterestCode.interest_code.in_(values),InterestCode.is_active.is_(True))))
