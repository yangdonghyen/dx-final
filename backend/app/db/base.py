from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata; import app.models to register all domain tables."""
