"""Docent models matching docs/03_database/03_db_schema.md."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime,
                        Enum, ForeignKey, Integer, JSON, Numeric, String, Text,
                        Time, UniqueConstraint, text)
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocentAnalysis(Base):
    __tablename__ = 'docent_analyses'
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    analysis_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.user_id', name='fk_docent_analyses_user', ondelete='CASCADE'), nullable=False
    )
    trip_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('trips.trip_id', name='fk_docent_analyses_trip', ondelete='SET NULL'), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Enum('PROCESSING', 'COMPLETED', 'FAILED', validate_strings=True), nullable=False, server_default=text("'PROCESSING'")
    )
    selected_place_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('places.place_id', name='fk_docent_analyses_selected_place', ondelete='SET NULL'), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    user = relationship('User', foreign_keys=[user_id])
    trip = relationship('Trip', foreign_keys=[trip_id])
    selected_place = relationship('Place', foreign_keys=[selected_place_id])

class DocentCandidate(Base):
    __tablename__ = 'docent_candidates'
    __table_args__ = (
        UniqueConstraint('analysis_id', 'rank_no', name='uq_docent_candidates_rank'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

    candidate_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, nullable=False
    )
    analysis_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('docent_analyses.analysis_id', name='fk_docent_candidates_analysis', ondelete='CASCADE'), nullable=False
    )
    place_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('places.place_id', name='fk_docent_candidates_place', ondelete='SET NULL'), nullable=True
    )
    candidate_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    candidate_region: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    rank_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False
    )
    verification_status: Mapped[str] = mapped_column(
        Enum('VERIFIED', 'PARTIAL', 'UNKNOWN', validate_strings=True), nullable=False, server_default=text("'UNKNOWN'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )

    # Unidirectional navigation only; deletion semantics belong to DB foreign keys.
    analysis = relationship('DocentAnalysis', foreign_keys=[analysis_id])
    place = relationship('Place', foreign_keys=[place_id])
