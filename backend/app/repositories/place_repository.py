from math import asin, cos, radians, sin, sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.place import Place


class PlaceRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, place_id: int):
        return self.session.get(Place, place_id)

    def get_by_kakao_place_id(self, kakao_place_id: str):
        return self.session.scalar(
            select(Place).where(Place.kakao_place_id == kakao_place_id)
        )

    def list(self):
        return list(self.session.scalars(select(Place).order_by(Place.place_id)))

    @staticmethod
    def _distance_meters(
        latitude_a: float,
        longitude_a: float,
        latitude_b: float,
        longitude_b: float,
    ) -> float:
        latitude_delta = radians(latitude_b - latitude_a)
        longitude_delta = radians(longitude_b - longitude_a)
        latitude_a_radians = radians(latitude_a)
        latitude_b_radians = radians(latitude_b)
        haversine = (
            sin(latitude_delta / 2) ** 2
            + cos(latitude_a_radians)
            * cos(latitude_b_radians)
            * sin(longitude_delta / 2) ** 2
        )
        return 6371000 * 2 * asin(sqrt(haversine))

    def list_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float,
        excluded_place_ids: set[int] | None = None,
    ):
        excluded_place_ids = excluded_place_ids or set()
        nearby = []
        for place in self.list():
            if (
                place.place_id in excluded_place_ids
                or place.latitude is None
                or place.longitude is None
            ):
                continue
            distance = self._distance_meters(
                latitude,
                longitude,
                float(place.latitude),
                float(place.longitude),
            )
            if distance <= radius_meters:
                nearby.append((distance, place))
        nearby.sort(key=lambda row: (row[0], row[1].place_id))
        return [place for _, place in nearby]

    def create(self, **fields):
        place = Place(**fields)
        self.session.add(place)
        self.session.flush()
        return place

    def update(self, place, **fields):
        for field, value in fields.items():
            setattr(place, field, value)

        self.session.flush()
        return place
