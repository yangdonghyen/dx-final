from app.models.trip import TripSelectedPlace


def test_selected_place_table_keeps_trip_and_place_foreign_key_integrity():
    foreign_keys = {key.name: key.ondelete for key in TripSelectedPlace.__table__.foreign_keys}
    assert foreign_keys == {
        "fk_trip_selected_places_trip": "CASCADE",
        "fk_trip_selected_places_place": "RESTRICT",
    }
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in TripSelectedPlace.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("trip_id", "place_id") in unique_constraints
    assert ("trip_id", "selected_order") in unique_constraints
