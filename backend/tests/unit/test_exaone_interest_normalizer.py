from app.services.exaone_interest_normalizer import normalize_exaone_interest_codes, raw_exaone_interest_codes


def test_maps_sea_to_nature_and_preserves_canonical_interest_order():
    assert normalize_exaone_interest_codes(["CAFE", "FOOD", "SEA"]) == ["CAFE", "FOOD", "NATURE"]


def test_deduplicates_after_normalizing_sea_to_nature():
    assert normalize_exaone_interest_codes(["SEA", "NATURE", "CAFE"]) == ["NATURE", "CAFE"]


def test_keeps_all_existing_exaone_codes():
    codes = ["FOOD", "CAFE", "NATURE", "CULTURE", "HISTORY", "SHOPPING", "EXHIBITION", "ACTIVITY"]
    assert normalize_exaone_interest_codes(codes) == codes


def test_city_and_rest_are_not_ai_interest_codes():
    assert normalize_exaone_interest_codes(["CITY", "REST", "FOOD"]) == ["FOOD"]


def test_sea_is_never_added_when_not_selected():
    assert normalize_exaone_interest_codes(["CITY"]) == []
    assert raw_exaone_interest_codes(["CITY"]) == ["CITY"]
    assert normalize_exaone_interest_codes(["FOOD"]) == ["FOOD"]
    assert raw_exaone_interest_codes(["FOOD"]) == []
    assert normalize_exaone_interest_codes([]) == []
    assert raw_exaone_interest_codes([]) == []
