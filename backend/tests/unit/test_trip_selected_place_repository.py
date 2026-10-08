from types import SimpleNamespace

from app.repositories.trip_repository import TripSelectedPlaceRepository


class Session:
    def __init__(self):
        self.deleted = []
        self.added = []
        self.flushes = 0

    def delete(self, row):
        self.deleted.append(row)

    def add(self, row):
        self.added.append(row)

    def flush(self):
        self.flushes += 1


def test_replace_is_order_preserving_deduplicated_and_flushes_deletes_before_inserts(monkeypatch):
    session = Session()
    repository = TripSelectedPlaceRepository(session)
    existing = [SimpleNamespace(place_id=163), SimpleNamespace(place_id=170)]
    monkeypatch.setattr(repository, "list", lambda trip_id: existing)

    repository.replace(17, [SimpleNamespace(place_id=163), SimpleNamespace(place_id=163), SimpleNamespace(place_id=170), SimpleNamespace(place_id=180)])

    assert [row.place_id for row in session.deleted] == [163, 170]
    assert [row.place_id for row in session.added] == [163, 170, 180]
    assert [row.selected_order for row in session.added] == [1, 2, 3]
    assert session.flushes == 2


def test_replace_does_not_write_when_selected_places_are_already_identical(monkeypatch):
    session = Session()
    repository = TripSelectedPlaceRepository(session)
    monkeypatch.setattr(repository, "list", lambda trip_id: [SimpleNamespace(place_id=163)])

    repository.replace(17, [SimpleNamespace(place_id=163), SimpleNamespace(place_id=163)])

    assert session.deleted == []
    assert session.added == []
    assert session.flushes == 0
