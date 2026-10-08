"""Companion models matching docs/03_database/03_db_schema.md."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime,
                        Enum, ForeignKey, Integer, JSON, Numeric, String, Text,
                        Time, UniqueConstraint, text)
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Companion(Base):
    __tablename__ = 'companions'
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    companion_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.user_id', name='fk_companions_user', ondelete='CASCADE'), nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    relation: Mapped[str] = mapped_column(
        Enum('FATHER', 'MOTHER', 'SPOUSE', 'CHILD', 'FRIEND', 'OTHER', validate_strings=True), nullable=False
    )
    age_group: Mapped[str | None] = mapped_column(
        Enum('UNDER_20', '20S', '30S', '40S', '50S', '60S', '70S_PLUS', validate_strings=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Enum('ACTIVE', 'ARCHIVED', validate_strings=True), nullable=False, server_default=text("'ACTIVE'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    user = relationship('User', foreign_keys=[user_id])

class CompanionPreference(Base):
    __tablename__ = 'companion_preferences'
    __table_args__ = (
        UniqueConstraint('companion_id', name='uq_companion_preferences_companion'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    companion_preference_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    companion_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('companions.companion_id', name='fk_companion_preferences_companion', ondelete='CASCADE'), nullable=False
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    companion = relationship('Companion', foreign_keys=[companion_id])

class CompanionInterest(Base):
    __tablename__ = 'companion_interests'
    __table_args__ = (
        UniqueConstraint('companion_id', 'interest_code', name='uq_companion_interests_companion_code'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    companion_interest_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    companion_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('companions.companion_id', name='fk_companion_interests_companion', ondelete='CASCADE'), nullable=False
    )
    interest_code: Mapped[str] = mapped_column(
        String(50), ForeignKey('interest_codes.interest_code', name='fk_companion_interests_code', ondelete='RESTRICT'), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    companion = relationship('Companion', foreign_keys=[companion_id])
    interest = relationship('InterestCode', foreign_keys=[interest_code])
