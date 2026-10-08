# Task 11-C — EXAONE Real Preference Provider (Local Ollama)

## Goal

Implement the real `PreferenceAnalysisProvider` using the locally running EXAONE model through Ollama.

The current project already has:

- `PreferenceAnalysisProvider` protocol
- `PreferenceAnalysisResult`
- Mock preference provider
- provider factory / FastAPI dependency wrapper
- YouTube real provider
- Kakao real provider
- `PREFERENCE_PROVIDER=mock|real`
- EXAONE-related settings in `app/core/config.py`

The target local model is:

```text
hf.co/LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-GGUF:Q4_K_M
```

Ollama local endpoint:

```text
http://127.0.0.1:11434
```

Do not use FriendliAI or any paid hosted API for this task.

---

## Important constraints

1. Inspect the existing project structure and conventions before editing.
2. Preserve all existing Mock provider behavior.
3. Do not break current APIs or tests.
4. Do not modify or expose `.env` secrets.
5. Do not require an API key for local Ollama.
6. Keep the implementation reusable enough that the same Ollama communication layer can later be used by `PlanGenerationProvider`.
7. Do not implement real plan generation yet.
8. Do not change the existing `PreferenceAnalysisProvider` protocol unless absolutely necessary.
9. Follow the same error-handling and timeout conventions already used by the Kakao / YouTube real providers where appropriate.
10. Prefer stdlib HTTP if that matches the current project convention. Do not add a new dependency unless clearly necessary.

---

## Existing provider contract

Inspect the actual file first, but the current contract is expected to be equivalent to:

```python
@dataclass(frozen=True)
class PreferenceAnalysisResult:
    interest_codes: list[str]
    summary: str


class PreferenceAnalysisProvider(Protocol):
    def analyze_preferences(self, text: str) -> PreferenceAnalysisResult:
        ...
```

The real provider must return exactly this domain object.

---

## Allowed interest codes

The database seed migration defines exactly these codes:

```text
FOOD
CAFE
NATURE
CULTURE
HISTORY
SHOPPING
EXHIBITION
ACTIVITY
```

Meanings:

```text
FOOD       = 맛집 / 음식 / 식당 / 요리 / 먹거리
CAFE       = 카페 / 커피 / 베이커리 / 디저트 카페
NATURE     = 바다 / 해변 / 산 / 숲 / 자연경관 / 공원 / 호수
CULTURE    = 공연 / 문화공간 / 전통문화
HISTORY    = 역사 / 유적지 / 궁궐 / 역사적 장소
SHOPPING   = 쇼핑 / 구매 / 백화점 / 쇼핑몰 / 시장 구매
EXHIBITION = 전시회 / 미술관 전시 / 박람회
ACTIVITY   = 체험 프로그램 / 스포츠 / 레저 / 액티비티
```

The provider must never return any code outside this set.

The service layer already validates active DB codes, but the real provider must also validate its model output before returning it.

---

## Model behavior already tested manually

The following local model was tested successfully:

```text
hf.co/LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-GGUF:Q4_K_M
```

Observed correct classifications:

```text
오션뷰 카페 + 조용한 해변
→ CAFE, NATURE

지역 유명 음식점 + 미술관 전시
→ FOOD, EXHIBITION

궁궐/역사 유적 + 전통 공연
→ HISTORY, CULTURE

현지 시장/쇼핑몰 + 서핑/카약
→ SHOPPING, ACTIVITY
```

The smaller EXAONE 4.0 1.2B model was not reliable enough for this classification task. Do not use it as the default real model.

---

## Ollama API

Use the local Ollama chat API:

```http
POST {EXAONE_BASE_URL}/api/chat
Content-Type: application/json; charset=utf-8
```

Typical base URL:

```text
http://127.0.0.1:11434
```

Request should conceptually look like:

```json
{
  "model": "hf.co/LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-GGUF:Q4_K_M",
  "messages": [
    {
      "role": "system",
      "content": "..."
    },
    {
      "role": "user",
      "content": "..."
    }
  ],
  "stream": false,
  "format": {
    "type": "object",
    "properties": {
      "interest_codes": {
        "type": "array",
        "maxItems": 3,
        "items": {
          "type": "string",
          "enum": [
            "FOOD",
            "CAFE",
            "NATURE",
            "CULTURE",
            "HISTORY",
            "SHOPPING",
            "EXHIBITION",
            "ACTIVITY"
          ]
        }
      },
      "summary": {
        "type": "string"
      }
    },
    "required": [
      "interest_codes",
      "summary"
    ]
  },
  "options": {
    "temperature": 0
  }
}
```

Use UTF-8 correctly.

Do not assume the JSON Schema alone is sufficient. Validate the returned content in Python too.

---

## System prompt requirements

Use a strict system prompt designed for classification, not free-form personality inference.

The prompt must communicate all of the following:

```text
당신은 여행 콘텐츠 분류기입니다.

입력 텍스트에 명시적으로 등장하거나 직접적으로 의미가 확인되는 관심사만 선택하세요.
성격, 소비 성향, 라이프스타일을 추측하지 마세요.

허용 코드:
FOOD
CAFE
NATURE
CULTURE
HISTORY
SHOPPING
EXHIBITION
ACTIVITY

분류 기준:
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
- summary에는 입력 텍스트에서 직접 확인 가능한 내용만 요약하세요.
```

A few-shot example may be included if useful, but keep the prompt maintainable.

Do not include the exact user input as a permanent example if doing so would make tests artificially pass only for that sentence.

---

## Output parsing and validation

Ollama returns a response object where the generated JSON text is expected in:

```text
response["message"]["content"]
```

The provider must:

1. confirm the top-level Ollama response has the expected structure,
2. read `message.content`,
3. parse that content as JSON,
4. require `interest_codes` to be a list,
5. require `summary` to be a string,
6. normalize returned codes to uppercase,
7. remove duplicates while preserving order,
8. reject any code outside the allowed 8 values,
9. enforce at most 3 codes,
10. return `PreferenceAnalysisResult`.

Do not silently map invented codes such as:

```text
beach_view
quiet_environment
coffee
```

to valid codes.

If the model returns an invalid / unknown code, treat it as a provider failure rather than guessing what it meant.

---

## Empty input behavior

Inspect the existing mock/service expectations and tests first.

Prefer preserving current contract behavior.

If empty or whitespace-only text currently produces an empty result in the Mock provider or service flow, preserve compatible behavior.

Do not invent a new API behavior without checking existing tests.

---

## Reusable Ollama layer

Because the same EXAONE model will later be used for real plan generation, avoid burying all HTTP transport logic directly inside the preference provider if a small reusable abstraction is appropriate.

A reasonable structure is:

```text
app/services/external/ai/
    provider.py
    mock_provider.py
    ollama_client.py              # reusable local HTTP transport
    exaone_preference_provider.py # preference-specific prompt/parsing
```

However, adapt to the repository's existing structure instead of forcing these exact filenames if another pattern is already established.

The reusable Ollama client should be small.

It should not contain preference-specific business logic.

Possible responsibility:

```python
chat(
    *,
    model: str,
    messages: list[dict[str, str]],
    format_schema: dict | None = None,
    options: dict | None = None,
) -> dict
```

This is preparation for a future `ExaonePlanGenerationProvider`, but do not implement plan generation now.

---

## Configuration

Inspect the actual `Settings` class before editing.

The project already has fields similar to:

```text
PREFERENCE_PROVIDER
EXAONE_API_KEY
EXAONE_BASE_URL
EXAONE_MODEL
AI_API_TIMEOUT_SECONDS
```

For local Ollama:

```env
PREFERENCE_PROVIDER=real
EXAONE_BASE_URL=http://127.0.0.1:11434
EXAONE_MODEL=hf.co/LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-GGUF:Q4_K_M
EXAONE_API_KEY=
```

Requirements:

- `EXAONE_API_KEY` is not required for local Ollama.
- Use `AI_API_TIMEOUT_SECONDS` for the Ollama request unless the existing codebase has a stronger convention.
- Missing/blank `EXAONE_BASE_URL` in real mode should fail clearly.
- Missing/blank `EXAONE_MODEL` in real mode should fail clearly.
- Normalize base URL to avoid accidental `//api/chat`.
- Do not change `PREFERENCE_PROVIDER` default behavior from mock unless existing project requirements explicitly say otherwise.

Update `.env.example` only if necessary.

Never put a real secret into `.env.example`.

---

## Provider factory

Inspect the current factory first.

Expected behavior:

```text
PREFERENCE_PROVIDER=mock
→ MockPreferenceAnalysisProvider

PREFERENCE_PROVIDER=real
→ EXAONE/Ollama real PreferenceAnalysisProvider
```

Keep the existing FastAPI dependency wrapper pattern.

There was a previous bug where provider factories with a `settings` argument were used directly in `Depends(...)`, causing FastAPI to expose `settings` as request input.

Do not reintroduce that bug.

The API layer should continue using the no-argument dependency wrapper such as:

```python
provide_preference_analysis_provider()
```

while pure factory functions may still accept `Settings` explicitly for tests.

---

## Error handling

Follow the existing project conventions used by the real Kakao / YouTube providers.

Cover at least:

```text
- Ollama is not running / connection refused
- timeout
- HTTP 4xx
- HTTP 5xx
- malformed top-level response
- missing message
- missing message.content
- non-JSON content
- malformed JSON object
- missing interest_codes
- missing summary
- interest_codes is not a list
- summary is not a string
- unknown interest code
- more than 3 returned codes
```

Error messages should be useful for logs/debugging but must not expose secrets.

Do not silently fall back to Mock when `PREFERENCE_PROVIDER=real`.

If real mode is selected and Ollama fails, surface the appropriate provider failure according to existing project conventions.

---

## Tests

Add focused unit tests for the real provider.

Do not require a real Ollama process in unit tests.

Mock/patch the HTTP boundary.

Cover at least:

### Success

- valid Ollama JSON response
- returns `PreferenceAnalysisResult`
- correct allowed codes
- duplicate codes are deduplicated while preserving order
- lowercase allowed code is normalized if model unexpectedly returns it
- empty code list is accepted if contract permits it
- Korean summary survives correctly
- request uses configured model
- request uses configured timeout
- request uses `stream=false`
- request uses `temperature=0`
- request includes the structured output schema / allowed enum

### Failure

- missing base URL in real mode
- missing model in real mode
- connection failure
- timeout
- HTTP 4xx
- HTTP 5xx
- malformed Ollama body
- missing `message.content`
- `message.content` is not valid JSON
- unknown interest code
- wrong data types
- more than 3 codes

### Factory

- mock mode returns Mock provider
- real mode returns EXAONE preference provider
- unknown preference provider mode fails clearly
- existing no-arg FastAPI dependency wrapper remains safe

---

## Existing service behavior that must remain intact

`PreferenceAnalysisService` currently:

1. gets active trip sources,
2. combines title / description / tags / channel title,
3. sends text to `analysis_provider.analyze_preferences(text)`,
4. receives `interest_codes`,
5. validates them against active DB interest codes,
6. preserves protected PROFILE / USER interests,
7. replaces CONTENT_AI interests,
8. commits the result.

Do not move DB access into the external provider.

Do not let the EXAONE provider query repositories or SQLAlchemy.

The provider is only responsible for:

```text
text
→ local EXAONE
→ validated PreferenceAnalysisResult
```

---

## Manual smoke test after implementation

After unit tests pass, document the exact local smoke-test steps.

Expected environment:

```env
PREFERENCE_PROVIDER=real
EXAONE_BASE_URL=http://127.0.0.1:11434
EXAONE_MODEL=hf.co/LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-GGUF:Q4_K_M
```

Verify Ollama:

```powershell
ollama list
```

The model should appear.

Then start the FastAPI server using the project's existing command.

Use the existing fake-auth flow and existing trip / YouTube source flow rather than creating new auth logic.

Perform a real end-to-end preference analysis using a trip with a YouTube source.

The goal is to verify:

```text
YouTube real metadata
        ↓
PreferenceAnalysisService
        ↓
EXAONE 3.5 7.8B via local Ollama
        ↓
valid DB interest codes
        ↓
trip CONTENT_AI interests saved
```

Do not perform the smoke test automatically if it would mutate important user data without explicit confirmation. It is okay to provide the commands/instructions.

---

## Regression requirement

Run the full current test suite.

The current baseline before this task is:

```text
213 passed
0 failed
0 errors
10 warnings
```

The exact number may increase due to new tests.

Requirement:

```text
0 failed
0 errors
```

Existing Kakao, YouTube, plan, auth, trip, and mock-provider tests must remain passing.

---

## Files to inspect before implementation

At minimum inspect:

```text
app/core/config.py
app/services/external/ai/provider.py
app/services/external/ai/mock_provider.py
app/services/external/factory.py
app/services/preference_analysis_service.py
app/repositories/user_repository.py
app/repositories/trip_repository.py
app/api/v1/trips.py
tests/unit/test_mock_external_providers.py
tests/unit/test_youtube_preference_services.py
tests/unit/test_youtube_content_provider.py
```

Also inspect the real Kakao / YouTube providers and their unit tests for current network/error-handling conventions.

Do not assume filenames or implementation details from this prompt are more authoritative than the actual repository.

---

## Deliverables

Implement the task and then report:

1. files created,
2. files modified,
3. provider/factory behavior,
4. Ollama request format,
5. validation rules,
6. error cases handled,
7. unit tests added,
8. full test result,
9. any remaining risks,
10. exact manual smoke-test commands.

Do not commit or push unless explicitly asked.

Do not delete the 1.2B local Ollama model.

Do not implement the real `PlanGenerationProvider` yet; that is the next task after preference-provider verification.
