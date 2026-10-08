"""Auth models matching docs/03_database/03_db_schema.md."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime,
                        Enum, ForeignKey, Integer, JSON, Numeric, String, Text,
                        Time, UniqueConstraint, text)
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserAuth(Base):
    __tablename__ = 'user_auths'
    __table_args__ = (
        UniqueConstraint('provider', 'provider_user_id', name='uq_user_auths_provider_user'),
        UniqueConstraint('user_id', 'provider', name='uq_user_auths_user_provider'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    auth_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.user_id', name='fk_user_auths_user', ondelete='CASCADE'), nullable=False
    )
    provider: Mapped[str] = mapped_column(
        Enum('LOCAL', 'KAKAO', 'NAVER', validate_strings=True), nullable=False
    )
    provider_user_id: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    user = relationship('User', foreign_keys=[user_id])

class RefreshToken(Base):
    __tablename__ = 'refresh_tokens'
    __table_args__ = (
        UniqueConstraint('token_hash', name='uq_refresh_tokens_hash'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    refresh_token_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.user_id', name='fk_refresh_tokens_user', ondelete='CASCADE'), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    user = relationship('User', foreign_keys=[user_id])


class OAuthLoginState(Base):
    __tablename__ = 'oauth_login_states'
    __table_args__ = (
        UniqueConstraint('state_hash', name='uq_oauth_login_states_hash'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    oauth_login_state_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    provider: Mapped[str] = mapped_column(Enum('NAVER', validate_strings=True), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
