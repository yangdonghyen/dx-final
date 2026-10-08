"""Place models matching docs/03_database/03_db_schema.md."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime,
                        Enum, ForeignKey, Integer, JSON, Numeric, String, Text,
                        Time, UniqueConstraint, text)
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Place(Base):
    __tablename__ = 'places'
    __table_args__ = (
        UniqueConstraint('kakao_place_id', name='uq_places_kakao'),
        UniqueConstraint('tour_content_id', name='uq_places_tour'),
        CheckConstraint('latitude IS NULL OR latitude BETWEEN -90 AND 90', name='chk_places_latitude'),
        CheckConstraint('longitude IS NULL OR longitude BETWEEN -180 AND 180', name='chk_places_longitude'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    place_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    category: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    region: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    address: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(10,7), nullable=True
    )
    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(10,7), nullable=True
    )
    kakao_place_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    tour_content_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    phone: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    website: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    opening_hours: Mapped[Any] = mapped_column(
        JSON, nullable=True
    )
    closed_days: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    parking_info: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    verification_status: Mapped[str] = mapped_column(
        Enum('VERIFIED', 'PARTIAL', 'UNKNOWN', validate_strings=True), nullable=False, server_default=text("'UNKNOWN'")
    )
    details_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')
    )

class SourcePlace(Base):
    __tablename__ = 'source_places'
    __table_args__ = (
        UniqueConstraint('source_id', 'rank_no', name='uq_source_places_source_rank'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    source_place_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('trip_sources.source_id', name='fk_source_places_source', ondelete='CASCADE'), nullable=False
    )
    place_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('places.place_id', name='fk_source_places_place', ondelete='SET NULL'), nullable=True
    )
    candidate_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    rank_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False
    )
    extraction_method: Mapped[str] = mapped_column(
        Enum('METADATA_AI', 'MANUAL', validate_strings=True), nullable=False
    )
    verification_status: Mapped[str] = mapped_column(
        Enum('VERIFIED', 'PARTIAL', 'UNKNOWN', validate_strings=True), nullable=False, server_default=text("'UNKNOWN'")
    )
    user_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text('FALSE')
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    source = relationship('TripSource', foreign_keys=[source_id])
    place = relationship('Place', foreign_keys=[place_id])
