# Task 11-B Hotfix — FastAPI Provider Dependency에서 Settings가 Request Body로 노출되는 문제 수정

작업 경로:

`C:\dev\프로젝트백엔드`

현재 상태:

- Task 11-B YouTube Real Provider 구현 완료
- 전체 테스트: `212 passed`
- `CONTENT_PROVIDER=real`
- `YOUTUBE_API_KEY` 로딩 정상
- 직접 YouTube Data API 호출 성공
- Fake social login 성공
- Trip 생성 성공 (`trip_id=1`)
- 실제 백엔드 YouTube source POST에서 422 발생

실제 요청:

```text
POST /api/v1/trips/1/sources/youtube
```

의도한 body:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

실제 응답:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed"
  }
}
```

OpenAPI 확인 결과 실제 request body schema가 다음처럼 생성됨:

```json
{
  "properties": {
    "request": {
      "$ref": "#/components/schemas/YouTubeSourceRequest"
    },
    "settings": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/Settings"
        },
        {
          "type": "null"
        }
      ]
    }
  },
  "required": ["request"]
}
```

즉 `settings`가 HTTP request body에 잘못 노출되고 있음.

---

# 1. 원인

현재 `app/services/external/factory.py`의 provider factory들이 아래 구조임:

```python
def get_content_provider(settings: Settings | None = None):
    settings = settings or get_settings()
    ...

def get_preference_analysis_provider(settings: Settings | None = None):
    settings = settings or get_settings()
    ...

def get_place_provider(settings: Settings | None = None):
    settings = settings or get_settings()
    ...

def get_plan_generation_provider(settings: Settings | None = None):
    settings = settings or get_settings()
    ...
```

그리고 API에서 예를 들어:

```python
provider=Depends(get_content_provider)
```

로 직접 사용하고 있음.

FastAPI가 `get_content_provider()`의 `settings: Settings | None = None` 파라미터를
dependency 내부 설정값이 아니라 request input으로 해석하여
YouTube POST body에 `settings` 필드를 추가함.

이 문제는 Content Provider만이 아니라
같은 signature를 가진 Place / Plan / Preference provider factory에도 잠재적으로 존재함.

---

# 2. 수정 목표

다음 contract를 복원하세요.

YouTube source API:

```text
POST /api/v1/trips/{trip_id}/sources/youtube
```

request body는 다시 정확히:

```json
{
  "youtube_url": "..."
}
```

하나만 받아야 함.

OpenAPI에서 `settings`가 request body/query/path 등 사용자 입력으로 노출되면 안 됨.

---

# 3. 설계 원칙

기존 factory 함수의 pure-Python 사용성을 가능하면 유지하세요.

즉 테스트나 코드에서 필요할 경우:

```python
get_content_provider(custom_settings)
```

처럼 Settings를 직접 넣을 수 있는 구조를 보존하는 것이 좋습니다.

동시에 FastAPI는
`Settings | None = None` 파라미터를 직접 introspection하면 안 됩니다.

권장 방식:

- 기존 `get_*_provider(settings: Settings | None = None)`는 pure factory로 유지
- FastAPI용으로 **인자가 없는 별도 dependency wrapper**를 추가

개념 예:

```python
def provide_content_provider():
    return get_content_provider()

def provide_place_provider():
    return get_place_provider()

def provide_preference_analysis_provider():
    return get_preference_analysis_provider()

def provide_plan_generation_provider():
    return get_plan_generation_provider()
```

그리고 API에서는:

```python
Depends(provide_content_provider)
```

형태로 사용.

실제 함수명은 프로젝트 naming convention에 맞춰도 됨.

중요:

- `Depends(get_settings)`를 factory default 값으로 직접 넣어서 pure factory 호출을 깨뜨리지 마세요.
- API layer에서 Settings가 사용자 입력으로 노출되지 않게 해야 함.
- Provider factory의 기존 테스트 가능성은 유지하세요.
- unnecessary architecture refactor 금지.

---

# 4. 적용 범위

이번 문제는 동일 signature를 가진 factory 전체를 일관되게 점검하세요.

대상:

- Content Provider
- Preference Analysis Provider
- Place Provider
- Plan Generation Provider

API layer에서 각각 factory가 `Depends(...)`로 직접 사용되고 있다면
FastAPI용 wrapper를 통해 사용하도록 수정하세요.

관련 예상 파일:

- `app/services/external/factory.py`
- `app/api/v1/trips.py`
- `app/api/v1/places.py`
- `app/api/v1/plans.py`

실제 사용 위치를 검색해서 필요한 파일만 수정하세요.

---

# 5. 절대 변경하지 말 것

- YouTube Real Provider 내부 동작
- Kakao Real Provider 내부 동작
- RegionResolver
- DB schema
- migration
- API response schema
- 기존 비즈니스 서비스 contract
- Provider mode 이름
- `.env`
- 실제 API key
- commit
- push

---

# 6. 테스트

기존 테스트 삭제/skip/완화 금지.

현재 baseline:

```text
212 passed
```

다음 regression test를 추가하세요.

## YouTube OpenAPI

다음 endpoint:

```text
POST /api/v1/trips/{trip_id}/sources/youtube
```

의 request body가
`YouTubeSourceRequest`에 해당하는 `youtube_url`만 요구하는지 검증.

최소한 OpenAPI schema에 사용자 입력용 `settings` property가 없어야 함.

가능하면 실제 TestClient 요청으로:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

형태가 더 이상 422 schema validation으로 실패하지 않는 것도 검증.

실제 YouTube 네트워크는 unit/integration test에서 호출하지 말고 provider override/mock 사용.

## 다른 provider endpoint regression

Place / Plan / Preference 관련 endpoint에서도
OpenAPI 또는 실제 요청 contract에 `settings`가 노출되지 않는지 점검.

기존 API body/query contract를 바꾸지 마세요.

---

# 7. 전체 테스트

수정 완료 후:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=".pytest_tmp_provider_dependency_hotfix"
```

실행.

목표:

- 기존 212개 유지
- 신규 regression test 통과
- failed = 0
- errors = 0

---

# 8. 완료 후 수동 Smoke Test

코드 수정 후 자동 테스트가 모두 통과하면
사용자가 기존 PowerShell session 또는 새 로그인 session으로 다시 다음 flow를 실행할 예정:

```text
Fake social login
→ Trip 생성
→ POST /api/v1/trips/{trip_id}/sources/youtube
→ CONTENT_PROVIDER=real
→ YouTubeContentProvider
→ YouTube Data API
→ metadata 저장
```

수정 후에는 다음 body가 그대로 통과해야 함:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

---

# 9. 완료 보고 형식

## [Task 11-B Provider Dependency Hotfix 결과]

### 원인
- ...

### 수정 파일
- ...

### FastAPI Dependency 구조
- Content:
- Preference:
- Place:
- Plan:

### OpenAPI
- YouTube source request body:
- settings 노출 여부:
- 기타 endpoint 점검:

### 기존 Factory 직접 호출 호환
- `get_*_provider(settings)` 유지 여부:

### 테스트
- 기존 기준: 212
- 신규 테스트:
- 총 collected:
- passed:
- failed:
- errors:
- warnings:

### DB 변경
- Migration:
- Schema:

### 완료 여부
- 완료 / 미완료

이 Hotfix만 수행하세요.
Naver/EXAONE/Preference Real Provider 구현은 시작하지 마세요.
commit/push 하지 마세요.
