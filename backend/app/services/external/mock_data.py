"""Deterministic UTF-8 JSON fixture loader for external-provider mocks."""
import json
from pathlib import Path

from app.core.exceptions import AppError


DEFAULT_MOCK_DATA_DIR = Path(__file__).resolve().parents[3] / "mock_data"


def load_mock_collection(filename: str, key: str, required_fields: set[str], data_dir: Path | None = None) -> list[dict]:
    path = (data_dir or DEFAULT_MOCK_DATA_DIR) / filename
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        raise AppError("MOCK_DATA_NOT_FOUND", "Mock data is not available", 404) from None
    except (OSError, json.JSONDecodeError):
        raise AppError("EXTERNAL_PROVIDER_ERROR", "Mock data is invalid", 500) from None
    values = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(values, list) or any(not isinstance(value, dict) or not required_fields <= value.keys() for value in values):
        raise AppError("EXTERNAL_PROVIDER_ERROR", "Mock data is invalid", 500)
    return values
