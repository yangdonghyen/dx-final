from app.core.exceptions import AppError
from app.repositories.trip_repository import TripInterestRepository, TripRepository, TripSourceRepository
from app.repositories.user_repository import InterestCodeRepository
from app.schemas.trip import AnalysisEvidence, PreferenceAnalysisResponse


class PreferenceAnalysisService:
    def __init__(self, session, analysis_provider):
        self.session = session
        self.trips = TripRepository(session)
        self.sources = TripSourceRepository(session)
        self.interests = TripInterestRepository(session)
        self.codes = InterestCodeRepository(session)
        self.analysis_provider = analysis_provider

    def _owned_active_trip(self, user_id, trip_id):
        trip = self.trips.get(trip_id)
        if trip is None: raise AppError("TRIP_NOT_FOUND", "Trip not found", 404)
        if trip.user_id != user_id: raise AppError("FORBIDDEN", "You do not own this trip", 403)
        if trip.status == "ARCHIVED": raise AppError("TRIP_ARCHIVED", "Trip is archived", 400)
        return trip

    def analyze(self, user_id, trip_id):
        self._owned_active_trip(user_id, trip_id)
        sources = self.sources.list_active(trip_id)
        if not sources: raise AppError("NO_ACTIVE_SOURCES", "No active sources to analyze", 400)
        text = "\n".join(" ".join(filter(None, [source.title, source.description, " ".join(source.tags or []), source.channel_title])) for source in sources)
        result = self.analysis_provider.analyze_preferences(text)
        codes = list(dict.fromkeys(result.interest_codes))
        if len(self.codes.active_codes(codes)) != len(codes): raise AppError("INVALID_INTEREST_CODE", "Invalid interest code", 400)
        try:
            existing = self.interests.list(trip_id)
            protected = {interest.interest_code for interest in existing if interest.source_type in {"PROFILE", "USER"}}
            self.interests.remove_content_ai(trip_id)
            for code in codes:
                if code not in protected: self.interests.create(trip_id, code, "CONTENT_AI", False)
            self.session.commit()
        except Exception:
            self.session.rollback(); raise
        evidence = [AnalysisEvidence(source="YOUTUBE", text=" ".join(filter(None, [source.title, source.description]))) for source in sources]
        return PreferenceAnalysisResponse(inferred_preferences=codes, destination_candidates=[], evidence=evidence)
