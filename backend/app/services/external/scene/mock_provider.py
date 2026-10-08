from app.services.external.scene.provider import SceneRecognitionResult


class MockSceneRecognitionProvider:
    """Offline fallback used by tests and local development without Gemini."""

    def recognize_scene(self, image_bytes: bytes, content_type: str) -> SceneRecognitionResult:
        return SceneRecognitionResult(
            recognized=False,
            primary_candidate=None,
            candidates=[],
            evidence=[],
            confidence="LOW",
        )
