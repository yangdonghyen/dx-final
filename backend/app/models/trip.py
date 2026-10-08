"""Trip models matching docs/03_database/03_db_schema.md."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime,
                        Enum, ForeignKey, Integer, JSON, Numeric, String, Text,
                        Time, UniqueConstraint, text)
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Trip(Base):
    __tablename__ = 'trips'
    __table_args__ = (
        CheckConstraint('end_date IS NULL OR start_date IS NULL OR end_date >= start_date', name='chk_trips_dates'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    trip_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.user_id', name='fk_trips_user', ondelete='CASCADE'), nullable=False
    )
    title: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    departure: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    destination: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    start_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    end_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    budget_krw: Mapped[int | None] = mapped_column(
        INTEGER(unsigned=True), nullable=True
    )
    transport_mode: Mapped[str | None] = mapped_column(
        Enum('PUBLIC_TRANSIT', 'CAR', 'WALK', 'MIXED', 'OTHER', validate_strings=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Enum('DRAFT', 'PLANNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'ARCHIVED', validate_strings=True), nullable=False, server_default=text("'DRAFT'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    user = relationship('User', foreign_keys=[user_id])

class TripPreference(Base):
    __tablename__ = 'trip_preferences'
    __table_args__ = (
        UniqueConstraint('trip_id', name='uq_trip_preferences_trip'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    trip_preference_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('trips.trip_id', name='fk_trip_preferences_trip', ondelete='CASCADE'), nullable=False
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
    # Snapshot the profile style when the trip is created.  Unlike the
    # operational comfort settings above, this is an itinerary intent and
    # must remain stable if the profile is changed after trip creation.
    travel_style: Mapped[str | None] = mapped_column(
        Enum('SLOW', 'STANDARD', 'FOOD_FOCUSED', validate_strings=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    trip = relationship('Trip', foreign_keys=[trip_id])


class TripSelectedPlace(Base):
    __tablename__ = 'trip_selected_places'
    __table_args__ = (
        UniqueConstraint('trip_id', 'place_id', name='uq_trip_selected_places_trip_place'),
        UniqueConstraint('trip_id', 'selected_order', name='uq_trip_selected_places_trip_order'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    trip_selected_place_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    trip_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('trips.trip_id', name='fk_trip_selected_places_trip', ondelete='CASCADE'),
        nullable=False,
    )
    place_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('places.place_id', name='fk_trip_selected_places_place', ondelete='RESTRICT'),
        nullable=False,
    )
    selected_order: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )

    trip = relationship('Trip', foreign_keys=[trip_id])
    place = relationship('Place', foreign_keys=[place_id])

class TripCompanion(Base):
    __tablename__ = 'trip_companions'
    __table_args__ = (
        UniqueConstraint('trip_id', 'companion_id', name='uq_trip_companions_trip_companion'),
        UniqueConstraint('trip_id', 'member_user_id', name='uq_trip_companions_trip_member'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    trip_companion_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('trips.trip_id', name='fk_trip_companions_trip', ondelete='CASCADE'), nullable=False
    )
    companion_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('companions.companion_id', name='fk_trip_companions_companion', ondelete='SET NULL'), nullable=True
    )
    # Set only when an app user joined through an invite link.
    member_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('users.user_id', name='fk_trip_companions_member_user', ondelete='SET NULL'), nullable=True
    )
    name_snapshot: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    relation_snapshot: Mapped[str] = mapped_column(
        Enum('FATHER', 'MOTHER', 'SPOUSE', 'CHILD', 'FRIEND', 'OTHER', validate_strings=True), nullable=False
    )
    age_group_snapshot: Mapped[str | None] = mapped_column(
        Enum('UNDER_20', '20S', '30S', '40S', '50S', '60S', '70S_PLUS', validate_strings=True), nullable=True
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
    interests_snapshot: Mapped[Any] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    trip = relationship('Trip', foreign_keys=[trip_id])
    companion = relationship('Companion', foreign_keys=[companion_id])
    member_user = relationship('User', foreign_keys=[member_user_id])

class TripInterest(Base):
    __tablename__ = 'trip_interests'
    __table_args__ = (
        UniqueConstraint('trip_id', 'interest_code', name='uq_trip_interests_trip_code'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    trip_interest_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('trips.trip_id', name='fk_trip_interests_trip', ondelete='CASCADE'), nullable=False
    )
    interest_code: Mapped[str] = mapped_column(
        String(50), ForeignKey('interest_codes.interest_code', name='fk_trip_interests_code', ondelete='RESTRICT'), nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        Enum('PROFILE', 'CONTENT_AI', 'USER', validate_strings=True), nullable=False
    )
    is_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text('FALSE')
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    trip = relationship('Trip', foreign_keys=[trip_id])
    interest = relationship('InterestCode', foreign_keys=[interest_code])

class TripShareLink(Base):
    __tablename__ = 'trip_share_links'
    __table_args__ = (
        UniqueConstraint('token_hash', name='uq_trip_share_links_token_hash'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    trip_share_link_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('trips.trip_id', name='fk_trip_share_links_trip', ondelete='CASCADE'), nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.user_id', name='fk_trip_share_links_user', ondelete='CASCADE'), nullable=False
    )
    # Only the SHA-256 hash is stored, like refresh_tokens.token_hash.
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    link_type: Mapped[str] = mapped_column(
        Enum('VIEW', 'INVITE', validate_strings=True), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    trip = relationship('Trip', foreign_keys=[trip_id])
    created_by = relationship('User', foreign_keys=[created_by_user_id])

class TripSource(Base):
    __tablename__ = 'trip_sources'
    __table_args__ = (
        UniqueConstraint('trip_id', 'source_type', 'external_id', name='uq_trip_sources_trip_external'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    source_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('trips.trip_id', name='fk_trip_sources_trip', ondelete='CASCADE'), nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        Enum('YOUTUBE', validate_strings=True), nullable=False
    )
    external_id: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    source_url: Mapped[str] = mapped_column(
        String(1000), nullable=False
    )
    title: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    tags: Mapped[Any] = mapped_column(
        JSON, nullable=True
    )
    channel_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    channel_title: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text('TRUE')
    )
    metadata_collected_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    trip = relationship('Trip', foreign_keys=[trip_id])
