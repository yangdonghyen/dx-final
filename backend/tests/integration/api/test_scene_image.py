import pytest

from app.dependencies import get_current_user
from app.api.v1.discovery import get_scene_image_service
from app.core.exceptions import AppError
from app.services.external.scene.provider import ScenePlaceCandidate, SceneRecognitionResult
from app.services.external.place.provider import PlaceCandidate
from app.services.scene_image_service import SceneImageService


@pytest.fixture
def authenticated_client(client):
    client.app.dependency_overrides[get_current_user] = lambda: object()
    yield client
    client.app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [("tv.jpg", "image/jpeg"), ("tv.png", "image/png")],
)
def test_scene_image_accepts_supported_images(
    authenticated_client, filename, content_type
):
    response = authenticated_client.post(
        "/api/v1/discovery/scene-image",
        files={"file": (filename, b"scene-bytes", content_type)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "received": True,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": 11,
    }


def test_scene_image_requires_authentication(client):
    response = client.post(
        "/api/v1/discovery/scene-image",
        files={"file": ("tv.jpg", b"scene", "image/jpeg")},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(
    ("case", "content_type", "status", "code"),
    [
        ("not-an-image", "text/plain", 415, "UNSUPPORTED_IMAGE_TYPE"),
        ("empty", "image/jpeg", 400, "EMPTY_IMAGE"),
        ("oversized", "image/jpeg", 413, "IMAGE_TOO_LARGE"),
    ],
)
def test_scene_image_rejects_invalid_files(
    authenticated_client, case, content_type, status, code
):
    content = b"x" * (10 * 1024 * 1024 + 1) if case == "oversized" else (
        b"text" if case == "not-an-image" else b""
    )
    response = authenticated_client.post(
        "/api/v1/discovery/scene-image",
        files={"file": ("tv.jpg", content, content_type)},
    )

    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_scene_image_analyzes_once_and_returns_place_candidates(authenticated_client):
    class Provider:
        def recognize_scene(self, image_bytes, content_type):
            assert image_bytes == b"scene-bytes"
            assert content_type == "image/jpeg"
            candidate = ScenePlaceCandidate("성산일출봉", "서귀포시", "제주특별자치도", "대한민국", "관광지")
            return SceneRecognitionResult(True, candidate, [candidate], ["화산 분화구 형태"], "HIGH")

    authenticated_client.app.dependency_overrides[get_scene_image_service] = lambda: SceneImageService(Provider())
    response = authenticated_client.post(
        "/api/v1/discovery/scene-image",
        data={"analyze": "true"},
        files={"file": ("tv.jpg", b"scene-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["recognized"] is True
    assert response.json()["primary_candidate"]["place_name"] == "성산일출봉"
    assert response.json()["needs_verification"] is True


def test_scene_image_returns_unrecognized_result_without_an_error(authenticated_client):
    class Provider:
        def recognize_scene(self, image_bytes, content_type):
            return SceneRecognitionResult(False, None, [], [], "LOW")

    authenticated_client.app.dependency_overrides[get_scene_image_service] = lambda: SceneImageService(Provider())
    response = authenticated_client.post(
        "/api/v1/discovery/scene-image",
        data={"analyze": "true"},
        files={"file": ("tv.jpg", b"scene-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["recognized"] is False
    assert response.json()["candidates"] == []
    assert response.json()["confidence"] == "LOW"


def test_scene_image_provider_failures_use_the_common_error_envelope(authenticated_client):
    class Provider:
        def recognize_scene(self, image_bytes, content_type):
            raise AppError("GEMINI_TIMEOUT", "Unable to analyze the place. Please try again.", 504)

    authenticated_client.app.dependency_overrides[get_scene_image_service] = lambda: SceneImageService(Provider())
    response = authenticated_client.post(
        "/api/v1/discovery/scene-image",
        data={"analyze": "true"},
        files={"file": ("tv.jpg", b"scene-bytes", "image/jpeg")},
    )

    assert response.status_code == 504
    assert response.json() == {
        "error": {
            "code": "GEMINI_TIMEOUT",
            "message": "Unable to analyze the place. Please try again.",
        }
    }


def test_scene_image_verifies_a_recognized_candidate_with_kakao(authenticated_client):
    class SceneProvider:
        def recognize_scene(self, image_bytes, content_type):
            candidate = ScenePlaceCandidate("성산일출봉", "서귀포시", "제주특별자치도", "대한민국", "관광지")
            return SceneRecognitionResult(True, candidate, [candidate], ["화산 분화구"], "HIGH")

    class PlaceProvider:
        def search(self, query, region=None):
            assert (query, region) == ("성산일출봉", "서귀포시")
            return [PlaceCandidate("KAKAO", "123", "성산 일출봉", "관광명소", "제주특별자치도 서귀포시 성산읍", 33.458, 126.942, None, None, "제주특별자치도 서귀포시 성산읍 성산리")]

    authenticated_client.app.dependency_overrides[get_scene_image_service] = lambda: SceneImageService(SceneProvider(), PlaceProvider())
    response = authenticated_client.post(
        "/api/v1/discovery/scene-image",
        data={"analyze": "true"},
        files={"file": ("tv.jpg", b"scene-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["verified_place"] == {
        "verified": True,
        "place_name": "성산 일출봉",
        "address": "제주특별자치도 서귀포시 성산읍",
        "road_address": "제주특별자치도 서귀포시 성산읍 성산리",
        "latitude": 33.458,
        "longitude": 126.942,
        "category": "관광명소",
        "source": "KAKAO",
    }
    assert response.json()["place_verified"] is True


@pytest.mark.parametrize("provider", [
    lambda: type("NoMatchProvider", (), {"search": lambda self, query, region=None: []})(),
    lambda: type("FailingProvider", (), {"search": lambda self, query, region=None: (_ for _ in ()).throw(AppError("KAKAO_TIMEOUT", "timeout", 504))})(),
])
def test_scene_image_keeps_gemini_result_when_kakao_cannot_verify(authenticated_client, provider):
    class SceneProvider:
        def recognize_scene(self, image_bytes, content_type):
            candidate = ScenePlaceCandidate("성산일출봉", "서귀포시", None, None, None)
            return SceneRecognitionResult(True, candidate, [candidate], ["화산 분화구"], "HIGH")

    authenticated_client.app.dependency_overrides[get_scene_image_service] = lambda: SceneImageService(SceneProvider(), provider())
    response = authenticated_client.post(
        "/api/v1/discovery/scene-image",
        data={"analyze": "true"},
        files={"file": ("tv.jpg", b"scene-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["recognized"] is True
    assert response.json()["primary_candidate"]["place_name"] == "성산일출봉"
    assert response.json()["place_verified"] is False
    assert "verified_place" not in response.json()


def test_scene_image_uses_second_gemini_candidate_when_kakao_confirms_it():
    primary = ScenePlaceCandidate("Gwanghwamun", "Seoul")
    second = ScenePlaceCandidate("Gyeongbokgung Palace", "Seoul")
    third = ScenePlaceCandidate("Heunginjimun (Dongdaemun)", "Seoul")

    class SceneProvider:
        def recognize_scene(self, image_bytes, content_type):
            return SceneRecognitionResult(True, primary, [primary, second, third], [], "HIGH")

    class PlaceProvider:
        def __init__(self):
            self.calls = []

        def search(self, query, region=None):
            self.calls.append((query, region))
            if query == "Gwanghwamun":
                return [PlaceCandidate(
                    "KAKAO", "gwanghwamun-square", "\uad11\ud654\ubb38\uad11\uc7a5", "square",
                    "\uc11c\uc6b8 \uc885\ub85c\uad6c \uc138\uc885\ub300\ub85c 172", 37.5726, 126.9769,
                    None, None, None,
                )]
            if query == "Gyeongbokgung Palace":
                return [PlaceCandidate(
                    "KAKAO", "gyeongbokgung", "\uacbd\ubcf5\uad81", "attraction",
                    "\uc11c\uc6b8 \uc885\ub85c\uad6c \uc0ac\uc9c1\ub85c 161", 37.5796, 126.9770,
                    None, None, "\uc11c\uc6b8 \uc885\ub85c\uad6c \uc0ac\uc9c1\ub85c 161",
                )]
            return []

    places = PlaceProvider()
    response = SceneImageService(SceneProvider(), places).receive(
        filename="tv.jpg", content_type="image/jpeg", image_bytes=b"scene", analyze=True
    )

    assert places.calls == [("Gwanghwamun", None), ("Gyeongbokgung Palace", None)]
    assert response.place_verified is True
    assert response.verified_place.place_name == "\uacbd\ubcf5\uad81"


def test_scene_image_does_not_verify_a_cross_script_result_in_a_conflicting_region():
    candidate = ScenePlaceCandidate("Gyeongbokgung Palace", "\uc11c\uc6b8")

    class SceneProvider:
        def recognize_scene(self, image_bytes, content_type):
            return SceneRecognitionResult(True, candidate, [candidate], [], "HIGH")

    class PlaceProvider:
        def search(self, query, region=None):
            assert (query, region) == ("Gyeongbokgung Palace", "\uc11c\uc6b8")
            return [PlaceCandidate(
                "KAKAO", "wrong-region", "\uacbd\ubcf5\uad81", "attraction",
                "\ubd80\uc0b0 \uc911\uad6c \uc608\uc2dc\ub85c 1", 35.1, 129.0, None, None, None,
            )]

    response = SceneImageService(SceneProvider(), PlaceProvider()).receive(
        filename="tv.jpg", content_type="image/jpeg", image_bytes=b"scene", analyze=True
    )

    assert response.place_verified is False
    assert response.verified_place is None


def test_scene_image_does_not_verify_a_same_script_partial_name_match():
    candidate = ScenePlaceCandidate("Gwanghwamun")

    class SceneProvider:
        def recognize_scene(self, image_bytes, content_type):
            return SceneRecognitionResult(True, candidate, [candidate], [], "HIGH")

    class PlaceProvider:
        def search(self, query, region=None):
            return [PlaceCandidate(
                "KAKAO", "station", "Gwanghwamun Station", "subway station",
                "Seoul Jongno-gu", 37.57, 126.98, None, None, None,
            )]

    response = SceneImageService(SceneProvider(), PlaceProvider()).receive(
        filename="tv.jpg", content_type="image/jpeg", image_bytes=b"scene", analyze=True
    )

    assert response.place_verified is False
    assert response.verified_place is None
