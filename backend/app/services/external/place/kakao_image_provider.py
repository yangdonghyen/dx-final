"""Kakao Daum image-search adapter for destination representative images."""

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.exceptions import AppError


KAKAO_IMAGE_ENDPOINT = "https://dapi.kakao.com/v2/search/image"


class KakaoImageProvider:
    def __init__(self, api_key: str, timeout: float):
        self.api_key = api_key
        self.timeout = timeout

    def search_destination_image(self, destination_name: str) -> str | None:
        if not self.api_key:
            raise AppError(
                "KAKAO_API_KEY_NOT_CONFIGURED",
                "Kakao API key is not configured",
                503,
            )

        if not destination_name or not destination_name.strip():
            return None

        params = {
            "query": f"{destination_name.strip()} 여행",
            "sort": "accuracy",
            "size": 20,
        }

        request = Request(
            f"{KAKAO_IMAGE_ENDPOINT}?{urlencode(params)}",
            headers={
                "Authorization": f"KakaoAK {self.api_key}",
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                status = response.status
                body = response.read()
        except HTTPError as error:
            status = error.code
            body = b""
        except (TimeoutError, socket.timeout):
            raise AppError(
                "KAKAO_IMAGE_TIMEOUT",
                "Kakao image search timed out",
                504,
            ) from None
        except URLError:
            raise AppError(
                "KAKAO_IMAGE_NETWORK_ERROR",
                "Kakao image search is unavailable",
                502,
            ) from None

        if status in {401, 403}:
            raise AppError(
                "KAKAO_IMAGE_AUTH_FAILED",
                "Kakao API authentication failed",
                502,
            )

        if status == 429:
            raise AppError(
                "KAKAO_IMAGE_RATE_LIMITED",
                "Kakao API rate limit exceeded",
                429,
            )

        if status < 200 or status >= 300:
            raise AppError(
                "KAKAO_IMAGE_API_ERROR",
                "Kakao image search failed",
                502,
            )

        try:
            payload = json.loads(body.decode("utf-8"))
            documents = payload.get("documents", [])

            if not isinstance(documents, list):
                return None

            # 대표 카드에 어울리도록 가로형 이미지를 우선 선택한다.
            candidates = []

            for document in documents:
                if not isinstance(document, dict):
                    continue

                image_url = document.get("image_url")
                width = document.get("width")
                height = document.get("height")

                if not isinstance(image_url, str) or not image_url:
                    continue

                if not isinstance(width, int) or not isinstance(height, int):
                    continue

                if width >= height and width >= 500:
                    candidates.append((width * height, image_url))

            if candidates:
                candidates.sort(reverse=True)
                return candidates[0][1]

            # 적당한 가로 이미지가 없으면 첫 유효 이미지 사용
            for document in documents:
                image_url = document.get("image_url")
                if isinstance(image_url, str) and image_url:
                    return image_url

            return None

        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AppError(
                "KAKAO_IMAGE_MALFORMED_RESPONSE",
                "Kakao returned an invalid image response",
                502,
            ) from None
