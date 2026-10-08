"""EXAONE/Ollama implementation of the preference-analysis provider."""

import json

from app.core.exceptions import AppError
from app.services.external.ai.ollama_client import OllamaClient
from app.services.external.ai.provider import PreferenceAnalysisResult


ALLOWED_INTEREST_CODES = ("FOOD", "CAFE", "NATURE", "CULTURE", "HISTORY", "SHOPPING", "EXHIBITION", "ACTIVITY")
PREFERENCE_FORMAT = {
    "type": "object",
    "properties": {
        "interest_codes": {"type": "array", "maxItems": 3, "items": {"type": "string", "enum": list(ALLOWED_INTEREST_CODES)}},
        "summary": {"type": "string"},
    },
    "required": ["interest_codes", "summary"],
}
RELEVANCE_FORMAT = {"type": "object", "properties": {"is_travel_related": {"type": "boolean"}}, "required": ["is_travel_related"]}
RELEVANCE_SYSTEM_PROMPT = """당신은 여행 콘텐츠 관련성 판정기입니다.
입력 영상의 주제가 실제 여행, 관광, 방문 또는 여행 경험과 직접 연결될 때만 true를 출력하세요.
여행 관련 예: 여행지 소개, 관광지, 지역 맛집 탐방, 카페 투어, 호텔/숙소, 축제/전시/여행 중 체험, 자연경관 방문, 역사 문화 관광, 여행 브이로그, 여행 일정/코스.
비여행 예: 일반 음악 영상, 가사, 가수/앨범 소개, 영화/드라마 자체 내용, 일반 상품 광고, IT/게임/코딩 영상, 여행과 무관한 일상 영상.
FOOD나 CULTURE와 연관될 가능성만으로 true를 선택하지 마세요. 확실하지 않으면 false를 우선하세요.
Rick Astley - Never Gonna Give You Up 같은 음악 영상은 false입니다."""
PREFERENCE_SYSTEM_PROMPT = """당신은 여행 콘텐츠의 관심사 분류기입니다.
입력 텍스트에 명시적으로 등장하거나 직접적으로 의미가 확인되는 관심사만 선택하세요.
성격, 소비 성향, 라이프스타일을 추측하지 마세요.
허용 코드: FOOD, CAFE, NATURE, CULTURE, HISTORY, SHOPPING, EXHIBITION, ACTIVITY
FOOD = 맛집, 음식, 식당, 요리, 먹거리
CAFE = 카페, 커피, 베이커리, 디저트 카페
NATURE = 바다, 해변, 산, 숲, 자연경관, 공원, 호수
CULTURE = 공연, 문화공간, 전통문화
HISTORY = 역사, 유적지, 궁궐, 역사적 장소
SHOPPING = 쇼핑, 구매, 백화점, 쇼핑몰, 시장 구매
EXHIBITION = 전시회, 미술관 전시, 박람회
ACTIVITY = 체험 프로그램, 스포츠, 레저, 액티비티
중요:
- 해변을 보는 것은 ACTIVITY가 아닙니다.
- 카페에 가는 것은 SHOPPING이 아닙니다.
- 휴식은 ACTIVITY가 아닙니다.
- 감성적이라는 이유로 SHOPPING을 선택하지 마세요.
- 입력에 없는 취향을 추측하지 마세요.
- 같은 코드를 두 번 출력하지 마세요.
- 최대 3개까지만 선택하세요.
- 해당 코드가 없다면 빈 배열을 출력하세요.
- summary에는 입력 텍스트에서 직접 확인 가능한 내용만 요약하세요."""


class ExaonePreferenceAnalysisProvider:
    def __init__(self, base_url: str, model: str, timeout: float, client: OllamaClient | None = None):
        if not isinstance(model, str) or not model.strip():
            raise AppError("EXAONE_MODEL_NOT_CONFIGURED", "EXAONE model is required for real preference analysis", 503)
        self.model = model.strip()
        self.client = client or OllamaClient(base_url, timeout)

    @staticmethod
    def _parse(response: dict) -> PreferenceAnalysisResult:
        try:
            content = response["message"]["content"]
            if not isinstance(content, str):
                raise ValueError
            payload = json.loads(content)
            codes, summary = payload["interest_codes"], payload["summary"]
            if not isinstance(codes, list) or not isinstance(summary, str):
                raise ValueError
            normalized = []
            for code in codes:
                if not isinstance(code, str):
                    raise ValueError
                code = code.upper()
                if code not in ALLOWED_INTEREST_CODES:
                    raise ValueError
                if code not in normalized:
                    normalized.append(code)
            if len(normalized) > 3:
                raise ValueError
            return PreferenceAnalysisResult(interest_codes=normalized, summary=summary)
        except (KeyError, TypeError, json.JSONDecodeError, ValueError):
            raise AppError("EXAONE_INVALID_RESPONSE", "EXAONE returned an invalid preference analysis", 502) from None

    @staticmethod
    def _parse_relevance(response: dict) -> bool:
        try:
            content = response["message"]["content"]
            value = json.loads(content)["is_travel_related"]
            if not isinstance(value, bool):
                raise ValueError
            return value
        except (KeyError, TypeError, json.JSONDecodeError, ValueError):
            raise AppError("EXAONE_INVALID_RESPONSE", "EXAONE returned an invalid travel relevance response", 502) from None

    def analyze_preferences(self, text: str) -> PreferenceAnalysisResult:
        if not isinstance(text, str):
            raise AppError("INVALID_PROVIDER_INPUT", "text must be a string", 400)
        if not text.strip():
            return PreferenceAnalysisResult(interest_codes=[], summary="")
        relevance_response = self.client.chat(model=self.model, messages=[{"role": "system", "content": RELEVANCE_SYSTEM_PROMPT}, {"role": "user", "content": text}], format_schema=RELEVANCE_FORMAT, options={"temperature": 0})
        if not self._parse_relevance(relevance_response):
            return PreferenceAnalysisResult(interest_codes=[], summary="여행 관련 관심사를 확인할 수 없습니다.")
        preference_response = self.client.chat(model=self.model, messages=[{"role": "system", "content": PREFERENCE_SYSTEM_PROMPT}, {"role": "user", "content": text}], format_schema=PREFERENCE_FORMAT, options={"temperature": 0})
        return self._parse(preference_response)
