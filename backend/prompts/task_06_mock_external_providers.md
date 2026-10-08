# Codex Task 06 — Mock External Providers & Mock Data

Task 01~05는 완료되었다.

현재 상태:
- FastAPI Backend skeleton 완료
- MySQL 연결 완료
- SQLAlchemy Model 22개 완료
- Alembic 001_initial_schema 적용 완료
- Alembic 002_seed_interest_codes 적용 완료
- Auth/User/JWT/Refresh/Preferences 완료
- Companion API 완료
- Trip CRUD + Snapshot 완료
- pytest 131 passed
- Task 05까지 GitHub push 완료
- working tree clean

이번 Task에서는 **향후 YouTube / 장소 / AI 기능을 실제 외부 API 없이 개발·테스트할 수 있도록 Mock Provider 계층과 Mock Data만 구현**한다.

이번 Task는 API 기능 구현이 아니라 **외부 연동 추상화와 테스트 기반 준비 단계**다.

---

# 1. 구현 전 반드시 읽을 문서

다음 문서를 먼저 다시 읽어라.

1. `docs/01_planning/01_core_features.md`
2. `docs/02_api/02_api_spec.md`
3. `docs/04_external_api/04_external_apis.md`
4. `docs/05_architecture/05_project_structure.md`
5. `docs/06_mock/06_mock_data.md`
6. `docs/07_implementation/07_implementation_plan.md`

이번 Task의 Source of Truth:

- 외부 API 역할: `docs/04_external_api/04_external_apis.md`
- 프로젝트 구조: `docs/05_architecture/05_project_structure.md`
- Mock Data: `docs/06_mock/06_mock_data.md`
- 구현 순서: `docs/07_implementation/07_implementation_plan.md`

문서와 이 프롬프트가 충돌하면 문서를 우선하고,
충돌 내용을 결과에 보고해라.

---

# 2. 이번 Task의 목적

향후 Task 07~09에서 다음 흐름을 실제 외부 API 없이 구현할 수 있어야 한다.

```text
YouTube URL / videoId
→ Mock YouTube Metadata
→ Mock Preference Analysis
→ Mock Place Search
→ Mock Plan Generation
```

이번 Task에서는 **Provider / Adapter와 deterministic mock 응답만 준비**한다.

아직 위 흐름을 실제 API endpoint로 완성하지 마라.

---

# 3. 이번 Task에서 구현할 Mock Provider

문서 구조를 우선하되 최소 다음 영역을 준비한다.

## 3-1. YouTube / Content Provider

향후 실제 YouTube Data API v3로 교체 가능한 Interface/Protocol과 Mock 구현.

책임:
- video_id 기준 영상 메타데이터 조회
- title
- description
- channel 정보
- tags 등 문서에서 정의한 항목 반환

금지:
- 실제 YouTube HTTP 요청
- YouTube API Key 사용
- 영상 다운로드
- 자막/프레임 추출
- 장소 AI 판별

---

## 3-2. Preference Analysis Provider

향후 EXAONE으로 교체 가능한 Text AI Provider 구조를 준비한다.

책임:
- YouTube metadata 등 텍스트 입력을 받아
- 문서에 정의된 interest/preferences 구조의 deterministic mock 결과 반환

중요:
- 허용 interest code는 기존 `interest_codes` Master 기준
- 다음 코드 외 임의 코드 생성 금지:

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

- LLM 호출 금지
- EXAONE 실제 호출 금지

---

## 3-3. Place Search Provider

향후 Kakao Local / TourAPI 기반 구현으로 교체 가능한 Interface/Protocol과 Mock 구현.

책임:
- query 또는 mock search condition을 받아 장소 후보 반환
- place name
- address
- latitude / longitude
- external identifiers
- category
- verification 관련 문서 필드

정확한 반환 필드는 기존 API/DB/Mock 문서를 따른다.

금지:
- 실제 Kakao API 호출
- 실제 TourAPI 호출
- 임의 Web Search
- 네트워크 요청

---

## 3-4. Plan Generation Provider

향후 EXAONE 기반 일정 생성으로 교체 가능한 Interface/Protocol과 Mock 구현.

책임:
- Trip 조건
- preference
- companions snapshot
- interests
- place candidates

를 받아 deterministic mock itinerary/plan payload 반환.

중요:
- 아직 DB에 `travel_plans`를 저장하는 Service/API를 구현하지 마라.
- Task 09에서 사용할 수 있는 provider 수준의 결과만 준비한다.
- 실제 EXAONE 호출 금지.

---

# 4. 이번 Task에서 구현하지 말 것

다음 API는 이번 Task에서 구현하지 마라.

- `POST /trips/{trip_id}/sources/youtube`
- `DELETE /trips/{trip_id}/sources/{source_id}`
- `POST /trips/{trip_id}/analyze-preferences`
- `GET /places/search`
- `POST /trips/{trip_id}/plans/generate`
- `GET /plans/{plan_id}`
- Plan edit/regenerate/confirm
- Smart Docent

또한 다음 실제 외부 API 호출 금지:

- Kakao
- Naver
- YouTube
- TourAPI
- 기상청
- Gemini
- EXAONE
- Routing/Mobility API

---

# 5. 현재 external 폴더 구조를 우선 활용

Task 01에서 이미 생성된 구조를 재사용한다.

예:

```text
app/services/external/
├── auth/
├── content/
├── place/
├── ai/
└── weather/
```

이번 Task에서 필요한 파일만 최소 생성한다.

예시 구조:

```text
app/services/external/content/
├── provider.py
└── mock_provider.py

app/services/external/place/
├── provider.py
└── mock_provider.py

app/services/external/ai/
├── provider.py
└── mock_provider.py
```

실제 이름은 기존 프로젝트 스타일과 문서 구조에 맞춘다.

같은 개념의 Interface를 중복 생성하지 마라.

---

# 6. Mock Data

먼저 현재 `mock_data/` 상태를 확인한다.

## 이미 Mock JSON이 존재하는 경우

- 기존 데이터를 보존한다.
- `docs/06_mock/06_mock_data.md`와 일치하는지 검토한다.
- 필요한 최소 수정만 한다.
- 문서 밖 필드를 임의로 추가하지 마라.

## `mock_data/`가 비어 있는 경우

`docs/06_mock/06_mock_data.md`에서 정의한 파일명과 구조를 기준으로
향후 개발에 필요한 deterministic Mock JSON을 생성한다.

과거 계획상 다음 파일들이 사용될 수 있으나,
**실제 파일명/구조는 반드시 문서를 다시 확인하고 문서가 우선이다.**

```text
users.json
companions.json
trips.json
youtube.json
places.json
plans.json
docent.json
```

문서가 특정 파일을 정의하지 않았다면
억지로 모든 파일을 만들지 마라.

이번 Task에서 최소한 실제 Provider가 사용하는 Mock 데이터가 있어야 한다.

---

# 7. Mock Data 원칙

Mock Data는:

- deterministic 해야 함
- 테스트 재현 가능해야 함
- 실제 개인정보 사용 금지
- 실제 Secret 포함 금지
- 실제 API 응답을 그대로 복사할 필요 없음
- 문서에서 요구하는 구조만 표현
- 원문/문서 밖 사실을 실제 사실처럼 표현하지 않음

특히 장소 Mock은 실제 운영 데이터라고 오해되지 않도록
테스트용 데이터임이 명확해야 한다.

---

# 8. Provider Interface 원칙

향후 Mock → Real Provider 교체 시
Service 코드를 크게 바꾸지 않아야 한다.

즉:

```text
Business Service
→ Provider Interface
→ Mock Provider
```

후속 Task에서는:

```text
Business Service
→ 같은 Provider Interface
→ Real Provider
```

로 교체할 수 있어야 한다.

Business Service가 `if mock:` 같은 분기로 가득 차지 않게 한다.

---

# 9. Dependency Injection / Provider Factory

기존 프로젝트 구조를 우선한다.

필요하다면 최소한의 Provider Factory/Dependency를 추가한다.

예시 개념:

```text
get_content_provider()
get_place_provider()
get_ai_provider()
```

또는 하나의 provider registry/factory.

하지만 이번 Task에서는
실제 Endpoint에 억지로 연결할 필요는 없다.

테스트에서 Mock Provider를 쉽게 주입할 수 있으면 된다.

---

# 10. 설정값

현재 `.env`는 수정하지 마라.

Mock/Real Mode 구분을 위해 설정값이 꼭 필요하다면:

- `app/core/config.py`
- `.env.example`

에만 최소 변경을 고려할 수 있다.

예:

```text
EXTERNAL_PROVIDER_MODE=mock
```

단, 기존 구조상 설정 없이 DI로 충분하면 불필요한 환경변수를 추가하지 마라.

실제 API Key는 사용하거나 출력하지 마라.

---

# 11. 반환 DTO / Schema

외부 Provider 응답을 그대로 Business Layer에 퍼뜨리지 마라.

가능하면 내부 DTO / Typed Model을 사용한다.

예:

```text
VideoMetadata
PreferenceAnalysisResult
PlaceCandidate
GeneratedPlanDraft
```

정확한 필드는 문서/API/향후 Service 요구사항 기준으로 최소 정의한다.

실제 Kakao/YouTube 등의 원본 response shape에 Backend 전체가 종속되지 않게 한다.

---

# 12. Mock YouTube 동작

최소 다음 동작을 테스트할 수 있어야 한다.

- 존재하는 video_id → 정상 metadata
- 존재하지 않는 video_id → 명확한 not found / provider error
- tags가 없는 데이터도 안전하게 처리
- title/description 등 Unicode 처리

실제 URL parsing은 Task 07에서 구현해도 된다.
이번 Task에서는 provider 수준 video_id 조회가 중심이다.

---

# 13. Mock Preference Analysis 동작

입력 텍스트가 같으면 결과가 항상 같아야 한다.

결과 예시 개념:

```text
interests:
- CULTURE
- FOOD

reason/summary:
- 테스트용 분석 설명
```

정확한 Response Shape는 문서 기준.

금지:
- 랜덤 결과
- 현재 시간에 따라 결과 변경
- 임의 Master Code 생성

---

# 14. Mock Place Search 동작

최소 다음 테스트가 가능해야 한다.

- 알려진 검색어 → 장소 목록
- 검색 결과 없음 → 빈 목록
- 결과 순서 deterministic
- external id / 좌표 / 주소 구조 검증
- numeric AI confidence 임의 생성 금지

향후 Task 08에서 DB upsert 전에 사용할 수 있어야 한다.

---

# 15. Mock Plan Generation 동작

같은 Trip/Preference/Place 입력이면
동일한 Plan Draft를 반환한다.

최소:
- day/date 구분
- sequence/order
- place reference
- rest/free-time 표현 가능
- 이동 관련 Mock 값은 테스트용으로 명확히 고정

하지만:
- DB 저장 금지
- 실제 itinerary validation 구현 금지
- 날씨 실제 조회 금지
- routing 실제 조회 금지

---

# 16. Error Handling

Provider Layer 전용 오류를 정리한다.

예:
- PROVIDER_NOT_FOUND
- MOCK_DATA_NOT_FOUND
- INVALID_PROVIDER_INPUT
- EXTERNAL_PROVIDER_ERROR

기존 공통 Exception 구조와 충돌하지 않게 한다.

실제 HTTP status mapping은 향후 Endpoint 구현 단계에서 처리 가능하다.

---

# 17. 네트워크 차단 원칙

Task 06 테스트에서는 외부 네트워크를 절대 호출하지 않아야 한다.

테스트가 실수로:
- requests
- httpx
- aiohttp

등을 통해 외부 요청하지 않도록 한다.

가능하면 Mock Provider 테스트에서
네트워크 호출이 전혀 필요하지 않음을 명확히 검증한다.

---

# 18. 테스트

현재 기준:

```text
131 passed
```

이번 Task에서 최소 다음 테스트를 추가한다.

## Mock Data
- 필요한 JSON 파일 load 성공
- JSON schema/required fields 검증
- UTF-8 한글 처리

## YouTube Mock Provider
- 정상 조회
- 없는 video_id
- deterministic 반환

## Preference Mock Provider
- 동일 입력 동일 결과
- 허용 interest code만 반환
- 알 수 없는 입력 처리

## Place Mock Provider
- 알려진 query
- 없는 query → 빈 목록
- deterministic order
- 필수 필드 검증

## Plan Mock Provider
- 동일 입력 동일 plan
- day/sequence 구조 검증
- 실제 DB write 없음

## Safety
- 실제 API Key 불필요
- 실제 network call 없음

전체 테스트:

```bash
pytest --basetemp=tmp/pytest-task06
```

기존 131개 + 신규 테스트 전부 통과해야 한다.

---

# 19. 기존 기능 보호

Task 01~05 구현을 깨뜨리지 마라.

특히:
- Auth
- User
- Companion
- Trip
- Alembic 001/002
- 실제 MySQL Schema

를 변경할 필요가 없어야 한다.

이번 Task에서 DB Migration 생성 금지.

---

# 20. Git 규칙

현재 Git worktree이며 Task 05까지 push 완료 상태다.

금지:
- `git reset --hard`
- `git clean -fd`
- 기존 commit 수정
- 사용자 변경사항 삭제

Task 06 완료 후
Codex가 자동 commit/push하지 마라.

사용자가 검토 후 직접 commit한다.

---

# 21. Secret 보호

절대 출력/저장 금지:

- `.env` 내용
- MYSQL_PASSWORD
- JWT_SECRET_KEY
- YouTube API Key
- Kakao/Naver Secret
- Gemini Key
- EXAONE Key
- 기타 실제 Secret

`.env` 수정 금지.

Mock JSON에 실제 Secret을 넣지 마라.

---

# 22. 완료 보고 형식

```text
[Task 06 작업 결과]

1. 생성한 파일
- ...

2. 수정한 파일
- ...

3. Mock Data
- 생성/사용 파일:
- 데이터 구조:
- 기존 데이터 보존 여부:

4. Mock Provider
- YouTube/Content:
- Preference Analysis:
- Place:
- Plan:

5. Provider Interface / DI
- ...

6. 실제 외부 API 호출 여부
- YouTube:
- Kakao:
- EXAONE:
- 기타:

7. DB 변경 여부
- Migration:
- DB write:

8. 테스트
- 기존 테스트:
- 신규 테스트:
- 총 collected:
- passed:
- failed:

9. 발견된 문제
- ...

10. 문서와 구현 충돌
- ...

11. Task 06 완료 여부
- ...

12. 다음 Task
- Task 07 YouTube Source + Preference Analysis API
```

---

# 23. 완료 조건

- [ ] 실제 외부 API 호출 없음
- [ ] Mock YouTube Provider 준비
- [ ] Mock Preference Analysis Provider 준비
- [ ] Mock Place Provider 준비
- [ ] Mock Plan Provider 준비
- [ ] Provider Interface 분리
- [ ] Mock/Real 교체 가능한 구조
- [ ] deterministic Mock Data
- [ ] 실제 Secret 없음
- [ ] 네트워크 호출 없음
- [ ] DB Migration 없음
- [ ] 기존 001/002 수정 없음
- [ ] Task 01~05 테스트 유지
- [ ] 전체 pytest 통과
- [ ] Task 07 API 구현 시작하지 않음
- [ ] 자동 Git commit/push 없음

**지금은 Task 06만 진행해라.**
