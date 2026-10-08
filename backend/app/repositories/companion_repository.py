from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.companion import Companion, CompanionInterest, CompanionPreference


class CompanionRepository:
    def __init__(self, session: Session): self.session = session

    def get(self, companion_id: int):
        return self.session.get(Companion, companion_id)

    def list_active_for_user(self, user_id: int):
        return list(self.session.scalars(
            select(Companion).where(Companion.user_id == user_id, Companion.status == "ACTIVE").order_by(Companion.companion_id)
        ))

    def create(self, user_id: int, **fields):
        companion = Companion(user_id=user_id, **fields)
        self.session.add(companion)
        self.session.flush()
        return companion

    def update(self, companion, **fields):
        for field, value in fields.items(): setattr(companion, field, value)
        self.session.flush()
        return companion


class CompanionPreferenceRepository:
    def __init__(self, session: Session): self.session = session

    def for_companions(self, companion_ids: list[int]):
        if not companion_ids: return {}
        rows = self.session.scalars(select(CompanionPreference).where(CompanionPreference.companion_id.in_(companion_ids)))
        return {row.companion_id: row for row in rows}

    def get(self, companion_id: int):
        return self.session.scalar(select(CompanionPreference).where(CompanionPreference.companion_id == companion_id))

    def create(self, companion_id: int, **fields):
        preference = CompanionPreference(companion_id=companion_id, **fields)
        self.session.add(preference)
        self.session.flush()
        return preference

    def update(self, preference, **fields):
        for field, value in fields.items(): setattr(preference, field, value)
        self.session.flush()
        return preference


class CompanionInterestRepository:
    def __init__(self, session: Session): self.session = session

    def for_companions(self, companion_ids: list[int]):
        if not companion_ids: return {}
        rows = self.session.execute(
            select(CompanionInterest.companion_id, CompanionInterest.interest_code)
            .where(CompanionInterest.companion_id.in_(companion_ids))
            .order_by(CompanionInterest.companion_id, CompanionInterest.interest_code)
        )
        result = {companion_id: [] for companion_id in companion_ids}
        for companion_id, interest_code in rows: result[companion_id].append(interest_code)
        return result

    def list_codes(self, companion_id: int):
        return list(self.session.scalars(
            select(CompanionInterest.interest_code).where(CompanionInterest.companion_id == companion_id).order_by(CompanionInterest.interest_code)
        ))

    def replace(self, companion_id: int, codes: list[str]):
        for interest in self.session.scalars(select(CompanionInterest).where(CompanionInterest.companion_id == companion_id)).all():
            self.session.delete(interest)
        self.session.flush()
        self.session.add_all([CompanionInterest(companion_id=companion_id, interest_code=code) for code in codes])
        self.session.flush()
