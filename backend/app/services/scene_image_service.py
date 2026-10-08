import re

from app.core.exceptions import AppError
from app.schemas.scene_image import (
    SceneImageResponse,
    ScenePlaceCandidateResponse,
    SceneVerifiedPlaceResponse,
)
from app.services.external.scene.provider import SceneRecognitionProvider


class SceneImageService:
    """Validates scene-image request bytes; later tasks can pass them to Vision."""

    allowed_content_types = frozenset({"image/jpeg", "image/png", "image/webp"})
    maximum_size_bytes = 10 * 1024 * 1024

    def __init__(
        self,
        recognition_provider: SceneRecognitionProvider | None = None,
        place_provider=None,
    ) -> None:
        self.recognition_provider = recognition_provider
        self.place_provider = place_provider

    def receive(
        self,
        *,
        filename: str | None,
        content_type: str | None,
        image_bytes: bytes,
        analyze: bool = False,
    ) -> SceneImageResponse:
        if content_type not in self.allowed_content_types:
            raise AppError(
                "UNSUPPORTED_IMAGE_TYPE",
                "Only JPEG, PNG, and WebP images can be uploaded.",
                415,
            )
        if not image_bytes:
            raise AppError("EMPTY_IMAGE", "The image file is empty.", 400)
        if len(image_bytes) > self.maximum_size_bytes:
            raise AppError(
                "IMAGE_TOO_LARGE", "The image file must be 10 MB or smaller.", 413
            )
        response = SceneImageResponse(
            filename=filename or "scene-image",
            content_type=content_type,
            size_bytes=len(image_bytes),
        )
        if not analyze:
            return response
        if self.recognition_provider is None:
            raise AppError("SCENE_RECOGNITION_NOT_CONFIGURED", "Scene recognition is not configured", 503)
        result = self.recognition_provider.recognize_scene(image_bytes, content_type)
        verified_place = self._verify_place(result) if result.recognized else None
        return response.model_copy(
            update={
                "recognized": result.recognized,
                "primary_candidate": self._candidate_response(result.primary_candidate),
                "candidates": [
                    self._candidate_response(candidate)
                    for candidate in result.candidates
                ],
                "evidence": result.evidence,
                "confidence": result.confidence,
                "needs_verification": result.needs_verification,
                "place_verified": verified_place is not None,
                "verified_place": verified_place,
            }
        )

    def _verify_place(self, result) -> SceneVerifiedPlaceResponse | None:
        """Confirm Gemini candidates with Kakao without treating them as facts."""
        if self.place_provider is None:
            return None
        candidates = []
        if result.primary_candidate is not None:
            candidates.append(result.primary_candidate)
        candidates.extend(candidate for candidate in result.candidates if candidate not in candidates)
        try:
            for candidate in candidates[:3]:
                region = self._search_region(candidate)
                matches = self.place_provider.search(candidate.place_name, region)
                match = self._verified_match(candidate, matches)
                if match is not None:
                    return SceneVerifiedPlaceResponse(
                        place_name=match.name,
                        address=match.address,
                        road_address=match.road_address,
                        latitude=match.latitude,
                        longitude=match.longitude,
                        category=match.category,
                    )
        except AppError:
            # Verification is supplementary; retain Gemini's successful result.
            return None
        return None

    @classmethod
    def _verified_match(cls, candidate, matches):
        kakao_matches = [
            match
            for match in matches
            if match.external_provider == "KAKAO" and cls._region_is_compatible(candidate, match)
        ]
        for match in kakao_matches:
            if cls._same_place_name(candidate.place_name, match.name):
                return match

        # Kakao's keyword ranking can resolve a direct Korean/English name pair
        # even when the two display names have no shared characters. Restrict
        # this fallback to a specific multi-word foreign name, the first result,
        # and different scripts. A vague name such as "Gwanghwamun" or a
        # same-script partial name such as "Foo Station" never qualifies.
        if (
            kakao_matches
            and cls._is_specific_foreign_name(candidate.place_name)
            and cls._uses_hangul(candidate.place_name) != cls._uses_hangul(kakao_matches[0].name)
        ):
            return kakao_matches[0]
        return None

    @staticmethod
    def _uses_hangul(value: str) -> bool:
        return any("\uac00" <= character <= "\ud7a3" for character in value)

    @staticmethod
    def _is_specific_foreign_name(value: str) -> bool:
        return len(re.findall(r"[A-Za-z0-9]+", value)) >= 2

    @classmethod
    def _search_region(cls, candidate) -> str | None:
        # RegionResolver compares Kakao's Korean address fields. Sending an
        # untranslated hint such as "Seoul" would filter every valid result.
        for value in (candidate.city, candidate.region):
            if isinstance(value, str) and value.strip() and cls._uses_hangul(value):
                return value
        return None

    @classmethod
    def _region_is_compatible(cls, candidate, match) -> bool:
        hints = [
            cls._normalize_name(value)
            for value in (candidate.city, candidate.region)
            if isinstance(value, str) and value.strip() and cls._uses_hangul(value)
        ]
        if not hints:
            return True
        addresses = " ".join(
            value for value in (match.address, match.road_address) if isinstance(value, str)
        )
        normalized_address = cls._normalize_name(addresses)
        return any(hint in normalized_address for hint in hints)

    @staticmethod
    def _same_place_name(candidate_name: str, kakao_name: str) -> bool:
        candidate_normalized = SceneImageService._normalize_name(candidate_name)
        return bool(candidate_normalized) and candidate_normalized == SceneImageService._normalize_name(kakao_name)

    @staticmethod
    def _normalize_name(value: str) -> str:
        return re.sub(r"[\s\W_]", "", value, flags=re.UNICODE).casefold()

    @staticmethod
    def _candidate_response(candidate) -> ScenePlaceCandidateResponse | None:
        if candidate is None:
            return None
        return ScenePlaceCandidateResponse(
            place_name=candidate.place_name,
            city=candidate.city,
            region=candidate.region,
            country=candidate.country,
            category=candidate.category,
        )
