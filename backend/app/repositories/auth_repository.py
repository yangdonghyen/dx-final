from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.auth import OAuthLoginState, RefreshToken, UserAuth
class UserAuthRepository:
    def __init__(self, s: Session): self.s=s
    def get(self, p, pid): return self.s.scalar(select(UserAuth).where(UserAuth.provider==p, UserAuth.provider_user_id==pid))
    def create(self, uid,p,pid):
        x=UserAuth(user_id=uid,provider=p,provider_user_id=pid); self.s.add(x); self.s.flush(); return x
    def touch(self,x,now:datetime): x.last_login_at=now; self.s.flush()
class RefreshTokenRepository:
    def __init__(self,s:Session): self.s=s
    def create(self,uid,h,expiry):
        x=RefreshToken(user_id=uid,token_hash=h,expires_at=expiry); self.s.add(x); self.s.flush(); return x
    def get(self,h): return self.s.scalar(select(RefreshToken).where(RefreshToken.token_hash==h))
    def revoke(self,x,now): x.revoked_at=now; self.s.flush()
class OAuthLoginStateRepository:
    def __init__(self, s: Session): self.s=s
    def create(self, provider, state_hash, expiry):
        x=OAuthLoginState(provider=provider,state_hash=state_hash,expires_at=expiry); self.s.add(x); self.s.flush(); return x
    def get(self, provider, state_hash):
        return self.s.scalar(select(OAuthLoginState).where(OAuthLoginState.provider==provider, OAuthLoginState.state_hash==state_hash))
    def consume(self, state, now): state.consumed_at=now; self.s.flush()
