# Task 11-B — YouTube Real Content Provider 구현 프롬프트

작업 경로:

`C:\dev\프로젝트백엔드`

현재 상태:

- Task 11-A Kakao Real Provider 완료
- 전체 테스트: `201 passed`
- Kakao 실제 Smoke Test 완료
- `CONTENT_PROVIDER` 설정 및 Provider Factory 구조는 이미 존재
- 기본값은 `mock`
- YouTube Mock Content Provider / protocol은 이미 존재
- `YouTubeSourceService`는 기존 Content Provider abstraction을 사용
- 실제 YouTube API Key는 로컬 `.env`의 `YOUTUBE_API_KEY`에 저장되어 있음
- `.env.example`의 `YOUTUBE_API_KEY=`는 비어 있음
- YouTube Data API v3 실제 직접 호출 성공:
  - endpoint: `GET https://www.googleapis.com/youtube/v3/videos`
  - `part=snippet`
  - 테스트 video id: `dQw4w9WgXcQ`
  - 실제 title/channel/published_at 응답 확인 완료

이번 세션에서는 **YouTube Real Content Provider만 구현**하세요.

다음은 하지 마세요.

- Naver Provider 구현
- EXAONE/Plan Real Provider 구현
- Preference Real Provider 구현
- Kakao 구조 변경
- DB schema 변경
- migration
- commit
- push

---

# 1. 기존 구조 먼저 확인

수정 전에 반드시 다음 파일/구조를 확인하세요.

- `app/services/external/content/provider.py`
- `app/services/external/content/mock_provider.py`
- `app/services/external/factory.py`
- `app/services/youtube_source_service.py`
- `app/core/config.py`
- `.env.example`
- YouTube source 관련 schema/model/repository
- `tests/unit/test_youtube_preference_services.py`
- `tests/unit/test_mock_external_providers.py`
- provider mode 관련 기존 테스트

기존 protocol, DTO, Service interface를 그대로 우선 사용하세요.

Task 11-B 때문에 서비스 contract를 불필요하게 변경하지 마세요.

---

# 2. YouTube Real Provider 구현

기존 Content Provider protocol을 만족하는 실제 구현체를 추가하세요.

권장 파일명 예시:

`app/services/external/content/youtube_provider.py`

단, 프로젝트 convention에 더 맞는 위치/이름이 있다면 기존 구조를 따르세요.

YouTube Data API v3의 `videos.list`를 사용하세요.

기본 endpoint:

`GET https://www.googleapis.com/youtube/v3/videos`

API Key는:

`Settings.youtube_api_key`

를 사용하세요.

실제 key를 코드에 하드코딩하거나 로그에 출력하지 마세요.

OAuth는 이번 Task에서 사용하지 않습니다.

---

# 3. 기존 Provider protocol 준수

실제 `content/provider.py`를 확인해서 현재 protocol method signature를 그대로 구현하세요.

예를 들어 현재 protocol이:

```python
get_video(...)
```

형태라면 그 signature를 그대로 유지하세요.

Real Provider 도입을 위해 `YouTubeSourceService`의 외부 contract를 바꾸지 마세요.

Mock과 Real이 같은 DTO를 반환해야 합니다.

---

# 4. YouTube URL / Video ID 처리

기존 서비스가 source URL을 넘기는 구조인지 video ID를 넘기는 구조인지 먼저 확인하세요.

URL을 provider가 처리해야 하는 구조라면 최소한 다음 형태를 안전하게 파싱하세요.

- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/shorts/VIDEO_ID`

추가 query string이 있어도 video ID를 올바르게 얻도록 하세요.

예:

```text
https://www.youtube.com/watch?v=abc123&feature=share
```

잘못된 URL 또는 video ID를 추출할 수 없는 입력은
기존 프로젝트 exception convention에 맞춰 명확하게 처리하세요.

이미 상위 Service가 URL 파싱을 담당하고 있다면 중복 구현하지 마세요.

책임은 한 곳에만 두세요.

---

# 5. YouTube API 요청

기존 DTO가 필요로 하는 필드만 요청하세요.

현재 직접 smoke test에서는:

```text
part=snippet
```

으로 다음 값이 정상 확인되었습니다.

- video id
- title
- channelTitle
- publishedAt

기존 DTO가 description, thumbnail 등의 snippet 필드를 사용한다면
현재 contract에 필요한 만큼만 매핑하세요.

만약 기존 DTO가 duration 등 `contentDetails` 필드를 요구한다면
그때만 `contentDetails`를 추가하세요.

불필요하게 `statistics`, `status` 등 범위를 넓히지 마세요.

---

# 6. DTO Mapping

기존 Content Provider DTO를 실제로 확인한 뒤
YouTube API 응답을 정확히 그 DTO에 매핑하세요.

개념적 mapping 예:

- `items[0].id` → video/external id
- `snippet.title` → title
- `snippet.channelTitle` → channel
- `snippet.description` → description (기존 DTO가 요구할 때)
- `snippet.publishedAt` → published_at (기존 DTO가 요구할 때)
- canonical URL 또는 기존 source URL → source_url

필드명을 새로 invent하지 말고,
현재 Mock Provider가 반환하는 DTO와 완전히 호환되게 하세요.

---

# 7. HTTP Client

프로젝트에서 이미 사용하는 HTTP 방식이 있다면 그 convention을 우선하세요.

Kakao Real Provider가 표준 라이브러리 `urllib`를 사용 중이므로,
특별한 이유가 없다면 새로운 HTTP dependency를 추가하지 마세요.

timeout은 기존:

`Settings.external_api_timeout_seconds`

를 사용하세요.

테스트에서 실제 YouTube API를 호출하지 않도록
HTTP layer를 mock/stub 가능하게 구성하세요.

---

# 8. Factory 연결

현재 Factory에서:

```text
CONTENT_PROVIDER=mock
```

→ 기존 Mock Content Provider

```text
CONTENT_PROVIDER=real
```

→ 새 YouTube Real Provider

가 되도록 연결하세요.

다른 provider의 Factory 동작은 변경하지 마세요.

기본값은 계속 `mock`이어야 합니다.

테스트 환경에서도 설정이 없으면 Mock이어야 합니다.

---

# 9. 오류 처리

기존 프로젝트 exception convention을 따라 다음을 처리하세요.

- `YOUTUBE_API_KEY` 누락
- 잘못된 YouTube URL / video ID
- HTTP 400
- HTTP 401 / 403
- quota exceeded
- timeout
- network error
- YouTube 5xx
- malformed JSON
- `items=[]` (존재하지 않거나 조회 불가한 video)
- 필수 response field 누락

중요:

- API key를 로그에 출력하지 마세요.
- 요청 URL 전체를 key가 포함된 상태로 로그에 남기지 마세요.
- 외부 원문 response를 무조건 그대로 로그에 남기지 마세요.

---

# 10. 기존 YouTube Source 기능 유지

기존 API와 Service 흐름을 유지하세요.

현재 Task 07에서 구현된:

- YouTube source 추가
- YouTube source 삭제
- Preference Analysis와의 연결

동작이 깨지면 안 됩니다.

이번 Task는 **Mock Content Provider를 실제 YouTube Provider로 교체 가능하게 만드는 것**이 핵심입니다.

DB model/repository를 불필요하게 변경하지 마세요.

---

# 11. 테스트

자동 테스트에서는 실제 Google/YouTube API를 호출하지 마세요.

HTTP response를 mock하여 최소 다음을 검증하세요.

## Factory

- `CONTENT_PROVIDER=mock` → Mock Content Provider
- `CONTENT_PROVIDER=real` → YouTube Real Provider

## 정상 응답 Mapping

mock YouTube API response를 사용하여 기존 Content DTO의 필드가 올바르게 변환되는지 확인:

- video id
- title
- channel
- 기존 DTO가 요구하는 snippet 필드들

## URL parsing

URL parsing 책임이 provider에 있다면:

- youtube.com/watch?v=
- youtu.be/
- youtube.com/shorts/
- query string 포함 URL
- invalid URL

검증.

## Error

- API key 누락
- HTTP 400
- HTTP 403
- quota exceeded 형태의 403
- timeout
- network error
- 5xx
- malformed JSON
- `items=[]`
- 필수 field 누락

## Regression

기존:

`tests/unit/test_youtube_preference_services.py`

를 포함한 모든 기존 테스트가 그대로 통과해야 합니다.

기존 테스트를 삭제하거나 skip하거나 expectation을 완화하지 마세요.

---

# 12. DB 변경

이번 Task는 외부 Content Provider 구현입니다.

- migration 생성 금지
- DB schema 변경 금지

현재 YouTube source 저장 구조를 그대로 사용하세요.

---

# 13. 실제 API Smoke Test

자동 테스트 전체 통과 후에만,
로컬 `.env`의 실제 `YOUTUBE_API_KEY`를 사용한 수동 smoke test를 수행할 수 있습니다.

단:

- API key 값을 출력하지 말 것
- 실제 key가 포함된 request URL을 로그로 남기지 말 것
- unit/integration test에 실제 API 호출을 넣지 말 것

가능하면 기존 API endpoint를 통해 실제 YouTube source 추가까지 확인하세요.

예시 흐름:

```text
Trip 생성/기존 Trip 사용
→ POST /api/v1/trips/{trip_id}/sources/youtube
→ 실제 YouTube URL 전달
→ YouTube Real Provider 조회
→ source 저장
→ API response 확인
```

정확한 request body는 기존 API schema를 확인해서 사용하세요.

---

# 14. 전체 Regression

현재 기준:

`201 passed`

작업 완료 후 반드시:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=".pytest_tmp_youtube_real"
```

를 실행하세요.

목표:

- 기존 201개 유지
- 신규 테스트 모두 통과
- failed = 0
- errors = 0

warnings는 개수만 보고하세요.

---

# 15. 토큰 / 컨텍스트 관리

이번 세션에서는 **YouTube Real Content Provider 하나만 완성**하세요.

우선순위:

1. 기존 Content Provider protocol/DTO 확인
2. YouTubeRealProvider 구현
3. Factory 연결
4. unit tests
5. 전체 regression
6. optional manual smoke test

컨텍스트가 부족할 것 같으면
깨진 상태로 넓게 진행하지 말고 완성된 단위에서 중단하세요.

---

# 16. 금지사항

- Naver 구현 금지
- EXAONE 구현 금지
- Preference Real Provider 구현 금지
- Kakao 코드 리팩토링 금지
- migration 금지
- DB schema 변경 금지
- commit 금지
- push 금지
- API key 하드코딩 금지
- API key 출력 금지
- 실제 YouTube API를 unit/integration test에서 호출 금지
- 기존 테스트 삭제/skip 금지
- expectation 완화 금지
- Task 범위 밖 대규모 리팩토링 금지

---

# 완료 보고 형식

## [Task 11-B YouTube Real Provider 작업 결과]

### 생성 파일
- ...

### 수정 파일
- ...

### 기존 Content Provider Contract
- protocol method:
- DTO:
- URL parsing 책임:

### YouTube Real Provider
- endpoint:
- requested part:
- HTTP client:
- timeout:
- DTO mapping:

### URL / Video ID 처리
- watch URL:
- youtu.be:
- shorts:
- invalid URL:

### Factory
- mock:
- real:

### 오류 처리
- API key:
- 400:
- 401/403:
- quota:
- timeout:
- 5xx:
- malformed response:
- items empty:

### DB 변경
- Migration:
- Schema:

### 테스트
- 기존 기준: 201
- 신규 테스트:
- 총 collected:
- passed:
- failed:
- errors:
- warnings:

### 실제 YouTube Smoke Test
- 직접 YouTube API key 검증: 이미 성공
- 백엔드 API smoke test 수행 여부:
- source 저장 여부:
- secret 노출 여부:

### 발견 이슈
- ...

### Task 11-B 완료 여부
- 완료 / 미완료

### 다음 단계
- Naver/EXAONE 등은 시작하지 말고 후보만 보고

Task 11-B까지만 수행하세요.
