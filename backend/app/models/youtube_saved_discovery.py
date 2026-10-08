"""Saved YouTube discoveries for each user."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class YouTubeSavedDiscovery(Base):
    __tablename__ = "youtube_saved_discoveries"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "video_id",
            "position_sec",
            name="uq_youtube_saved_discoveries_user_video_position",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
        },
    )

    saved_discovery_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.user_id",
            name="fk_youtube_saved_discoveries_user",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    video_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    position_sec: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    page_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    channel_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    thumbnail_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    destination_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    representative_image_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user = relationship(
        "User",
        foreign_keys=[user_id],
    )
