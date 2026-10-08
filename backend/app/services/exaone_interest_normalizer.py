"""Translate stored application interests into EXAONE's canonical vocabulary.

Trip interests are user input and must remain unchanged in the database.  This
module is intentionally used only at the AI-provider boundary.
"""

EXAONE_CANONICAL_INTEREST_CODES = frozenset(
    {
        "FOOD",
        "CAFE",
        "NATURE",
        "CULTURE",
        "HISTORY",
        "SHOPPING",
        "EXHIBITION",
        "ACTIVITY",
    }
)

# The application exposes these extra preference codes in addition to the
# codes understood by EXAONE.  SEA is a nature preference in EXAONE's own
# vocabulary.  CITY has no evidence-based equivalent, and REST is represented
# separately by trip_preferences.rest_frequency, so neither becomes an AI
# interest code.
APP_TO_EXAONE_INTEREST_CODES = {"SEA": "NATURE"}
EXCLUDED_EXAONE_INTEREST_CODES = frozenset({"CITY", "REST"})
RAW_INTEREST_CODES = frozenset({"SEA", "CITY", "REST"})


def normalize_exaone_interest_codes(interest_codes: list[str]) -> list[str]:
    """Return ordered, de-duplicated interest codes accepted by EXAONE."""
    normalized: list[str] = []
    seen: set[str] = set()
    for value in interest_codes:
        code = value.strip().upper()
        code = APP_TO_EXAONE_INTEREST_CODES.get(code, code)
        if code in EXCLUDED_EXAONE_INTEREST_CODES or code not in EXAONE_CANONICAL_INTEREST_CODES:
            continue
        if code not in seen:
            normalized.append(code)
            seen.add(code)
    return normalized


def raw_exaone_interest_codes(interest_codes: list[str]) -> list[str]:
    """Return non-canonical setup codes whose original meaning must reach AI.

    These values are context only: they never relax the strict canonical
    interest validation used for EXAONE's structured interest list.
    """
    raw: list[str] = []
    for value in interest_codes:
        code = value.strip().upper()
        if code in RAW_INTEREST_CODES and code not in raw:
            raw.append(code)
    return raw
