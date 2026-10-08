"""User models matching docs/03_database/03_db_schema.md."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime,
                        Enum, ForeignKey, Integer, JSON, Numeric, String, Text,
                        Time, UniqueConstraint, text)
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = 'users'
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    nickname: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    age_group: Mapped[str | None] = mapped_column(
        Enum('UNDER_20', '20S', '30S', '40S', '50S', '60S', '70S_PLUS', validate_strings=True), nullable=True
    )
    profile_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text('FALSE')
    )
    status: Mapped[str] = mapped_column(
        Enum('ACTIVE', 'WITHDRAWN', 'SUSPENDED', validate_strings=True), nullable=False, server_default=text("'ACTIVE'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')
    )

class UserPreference(Base):
    __tablename__ = 'user_preferences'
    __table_args__ = (
        UniqueConstraint('user_id', name='uq_user_preferences_user'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    user_preference_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.user_id', name='fk_user_preferences_user', ondelete='CASCADE'), nullable=False
    )
    walking_tolerance: Mapped[str | None] = mapped_column(
        Enum('VERY_LOW', 'LOW', 'NORMAL', 'HIGH', validate_strings=True), nullable=True
    )
    rest_frequency: Mapped[str | None] = mapped_column(
        Enum('LOW', 'NORMAL', 'HIGH', validate_strings=True), nullable=True
    )
    avoid_stairs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text('FALSE')
    )
    avoid_hills: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text('FALSE')
    )
    taxi_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text('TRUE')
    )
    travel_style: Mapped[str | None] = mapped_column(
        Enum('SLOW', 'STANDARD', 'FOOD_FOCUSED', validate_strings=True), nullable=True
    )
    senior_mode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text('FALSE')
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    user = relationship('User', foreign_keys=[user_id])

class InterestCode(Base):
    __tablename__ = 'interest_codes'
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    interest_code: Mapped[str] = mapped_column(
        String(50), primary_key=True, nullable=False
    )
    label_ko: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text('TRUE')
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text('0')
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )

class UserInterest(Base):
    __tablename__ = 'user_interests'
    __table_args__ = (
        UniqueConstraint('user_id', 'interest_code', name='uq_user_interests_user_code'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    user_interest_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.user_id', name='fk_user_interests_user', ondelete='CASCADE'), nullable=False
    )
    interest_code: Mapped[str] = mapped_column(
        String(50), ForeignKey('interest_codes.interest_code', name='fk_user_interests_code', ondelete='RESTRICT'), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    user = relationship('User', foreign_keys=[user_id])
    interest = relationship('InterestCode', foreign_keys=[interest_code])
