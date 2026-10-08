from datetime import UTC, datetime, timedelta
from sqlalchemy.orm import Session
from app.core.exceptions import AppError
import secrets
from app.core.passwords import hash_password, verify_password
from app.core.security import create_access_token, create_refresh_token, get_jwt_settings, hash_refresh_token, verify_refresh_token
from app.repositories.auth_repository import OAuthLoginStateRepository, RefreshTokenRepository, UserAuthRepository
from app.repositories.user_repository import UserRepository

class AuthService:
    def __init__(self, session: Session, provider):
        self.session=session; self.provider=provider; self.users=UserRepository(session); self.auths=UserAuthRepository(session); self.tokens=RefreshTokenRepository(session); self.oauth_states=OAuthLoginStateRepository(session)
    def _now(self): return datetime.now(UTC).replace(tzinfo=None)
    def _issue(self, user):
        access=create_access_token(str(user.user_id)); refresh=create_refresh_token(str(user.user_id))
        self.tokens.create(user.user_id, hash_refresh_token(refresh), self._now()+timedelta(days=get_jwt_settings().refresh_expire_days))
        return access,refresh
    def social_login(self, provider, access_token):
        identity=self.provider.verify(provider, access_token)
        return self.social_identity_login(identity)
    def social_identity_login(self, identity):
        try:
            auth=self.auths.get(identity.provider, identity.provider_user_id); is_new=auth is None
            if auth is None:
                user=self.users.create(); self.auths.create(user.user_id, identity.provider, identity.provider_user_id)
            else:
                user=self.users.get(auth.user_id)
                if user is None: raise AppError("USER_NOT_FOUND", "User not found", 401)
                self.auths.touch(auth,self._now())
            if user.status != "ACTIVE": raise AppError("USER_INACTIVE", "User is inactive", 403)
            self._fill_nickname(user, identity.nickname)
            access,refresh=self._issue(user); self.session.commit(); return user,is_new,access,refresh
        except Exception:
            self.session.rollback(); raise
    @staticmethod
    def _fill_nickname(user, provider_nickname):
        # Keep a name the user already has; only fill an empty one from Kakao/Naver.
        name=provider_nickname.strip()[:50] if isinstance(provider_nickname,str) else ""
        if name and not (user.nickname or "").strip(): user.nickname=name
    @staticmethod
    def _login_id(value): return value.strip().lower()
    def register_local(self, login_id, password, nickname=None):
        login_id=self._login_id(login_id)
        try:
            if self.auths.get('LOCAL', login_id) is not None:
                raise AppError('LOGIN_ID_ALREADY_EXISTS', 'Login ID is already registered', 409)
            user=self.users.create(nickname=nickname.strip() if nickname else None, password_hash=hash_password(password))
            self.auths.create(user.user_id, 'LOCAL', login_id)
            access,refresh=self._issue(user); self.session.commit(); return user,access,refresh
        except Exception:
            self.session.rollback(); raise
    def login_local(self, login_id, password):
        auth=self.auths.get('LOCAL', self._login_id(login_id))
        user=self.users.get(auth.user_id) if auth else None
        if user is None or not verify_password(password, user.password_hash):
            raise AppError('INVALID_CREDENTIALS', 'Invalid login ID or password', 401)
        if user.status != 'ACTIVE': raise AppError('USER_INACTIVE', 'User is inactive', 403)
        try:
            self.auths.touch(auth, self._now()); access,refresh=self._issue(user); self.session.commit(); return user,access,refresh
        except Exception:
            self.session.rollback(); raise
    def create_naver_state(self):
        state=secrets.token_urlsafe(32)
        try:
            self.oauth_states.create('NAVER', hash_refresh_token(state), self._now()+timedelta(minutes=10)); self.session.commit(); return state
        except Exception:
            self.session.rollback(); raise
    def consume_naver_state(self, state):
        record=self.oauth_states.get('NAVER', hash_refresh_token(state))
        if record is None or record.consumed_at is not None or record.expires_at <= self._now():
            raise AppError('INVALID_OAUTH_STATE', 'Invalid or expired OAuth state', 401)
        try: self.oauth_states.consume(record, self._now()); self.session.commit()
        except Exception: self.session.rollback(); raise
    def refresh(self, raw):
        claims=verify_refresh_token(raw); record=self.tokens.get(hash_refresh_token(raw))
        if record is None or record.revoked_at is not None: raise AppError("INVALID_TOKEN", "Invalid token", 401)
        if record.expires_at <= self._now(): raise AppError("TOKEN_EXPIRED", "Token has expired", 401)
        try: user_id=int(claims["sub"])
        except (ValueError,TypeError): raise AppError("INVALID_TOKEN", "Invalid token", 401) from None
        user=self.users.get(user_id)
        if record.user_id != user_id or user is None: raise AppError("INVALID_TOKEN", "Invalid token", 401)
        if user.status != "ACTIVE": raise AppError("USER_INACTIVE", "User is inactive", 403)
        return create_access_token(str(user_id)),raw
    def logout(self, raw):
        verify_refresh_token(raw); record=self.tokens.get(hash_refresh_token(raw))
        if record is None or record.revoked_at is not None: raise AppError("INVALID_TOKEN", "Invalid token", 401)
        try: self.tokens.revoke(record,self._now()); self.session.commit()
        except Exception: self.session.rollback(); raise
