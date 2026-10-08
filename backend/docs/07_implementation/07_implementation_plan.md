# 07. Implementation Priority & Definition of Done — Draft Final (Separate Frontend / Existing MySQL)

## 1. 목적

이 문서는 Codex가 Backend를 구현할 때 따라야 할 **구현 우선순위**와
각 단계가 완료되었다고 판단할 수 있는 **Definition of Done(완료조건)** 을 정의한다.

현재 프로젝트 전제:

```text
Frontend = 별도 Flutter GitHub Repository
Backend = 별도 FastAPI GitHub Repository
Database = 사용자가 준비한 MySQL Database
DB 접속정보 = 사용자가 제공, Backend `.env`로 관리
```

기본 원칙:

```text
구조부터 만들고
→ Mock으로 End-to-End 흐름 확인
→ 실제 외부 API 연결
→ AI 연결
→ Validation 강화
→ Smart Docent
```

외부 API나 AI 연결이 늦어져도 Backend 전체 개발이 멈추지 않도록 한다.

---

# 2. 전체 구현 순서

```text
Phase 0. 프로젝트 기반 세팅
Phase 1. 인증 / 사용자 / 동행자
Phase 2. 여행 CRUD + Mock 기반 핵심 흐름
Phase 3. 장소 / YouTube 실제 외부 API 연결
Phase 4. EXAONE 여행계획 생성
Phase 5. 일정 검증 / 수정 / 재구성
Phase 6. TourAPI / Weather / Routing 연결 강화
Phase 7. Smart Docent
Phase 8. 통합 테스트 / 안정화
```

---

# 3. Phase 0 — 프로젝트 기반 세팅

## 구현 항목

```text
FastAPI 프로젝트 생성
폴더 구조 생성
config.py
.env.example
사용자 MySQL 연결
DB Session
SQLAlchemy Base
Alembic
CORS 설정
공통 Exception
공통 Response/Error 형태
JWT Utility
Health API
```

## 우선 구현 파일

```text
app/main.py
app/core/config.py
app/core/security.py
app/core/exceptions.py
app/db/base.py
app/db/session.py
app/api/v1/router.py
```

## 최소 API

```http
GET /api/v1/health
```

예상 Response:

```json
{
  "status": "ok"
}
```

## 완료조건

- [ ] FastAPI 서버가 실행된다.
- [ ] `/docs` Swagger가 열린다.
- [ ] `/api/v1/health`가 200을 반환한다.
- [ ] `.env`를 통해 사용자가 제공한 MySQL 접속정보를 읽는다.
- [ ] 기존 MySQL Database Connection이 정상이다.
- [ ] Backend가 `CREATE DATABASE` / `DROP DATABASE`를 수행하지 않는다.
- [ ] Alembic이 기존 Database에 Migration을 적용할 수 있다.
- [ ] CORS 허용 Origin을 환경변수로 읽는다.
- [ ] `.env`가 Git Ignore 대상이다.
- [ ] 공통 Error Response 구조가 정의되어 있다.

### Phase 0 완료 판정

```text
API 서버 + 사용자의 MySQL 연결 + Migration 기반이 정상 동작
```

## MySQL 작업 규칙

사용자가 제공할 정보:

```text
HOST
PORT
DATABASE
USER
PASSWORD
```

이 값은 `.env`에만 저장한다.

Codex/Backend가 하지 않는 작업:

```text
CREATE DATABASE
DROP DATABASE
CREATE USER
DROP USER
GRANT 권한 임의 변경
운영 DB 초기화
```

Schema/Table 변경은 Alembic으로만 수행한다.

---

# 4. Phase 1 — 인증 / 사용자 / 동행자

## 구현 순서

### 1-1. User / Auth Model

```text
users
user_auths
refresh_tokens
user_preferences
interest_codes
user_interests
```

### 1-2. Companion Model

```text
companions
companion_preferences
companion_interests
```

### 1-3. Seed

```text
interest_codes
```

초기 코드:

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

## API

```http
POST /auth/social-login
POST /auth/refresh
POST /auth/logout

GET /users/me
PATCH /users/me
PATCH /users/me/preferences

GET /companions
POST /companions
PATCH /companions/{companion_id}
DELETE /companions/{companion_id}
```

## 개발 초기 Social Login 처리

실제 Kakao/Naver 연결 전에는 Mock Provider를 사용할 수 있다.

```text
Mock Provider Token
→ Mock provider_user_id
→ User 생성
→ JWT 발급
```

실제 Provider 연결 시 동일한 `auth_service` 흐름을 유지한다.

## 완료조건

- [ ] 신규 Social Login Mock으로 User가 생성된다.
- [ ] 기존 사용자는 재로그인 시 중복 생성되지 않는다.
- [ ] Access Token / Refresh Token이 발급된다.
- [ ] Refresh Token 원문이 DB에 저장되지 않는다.
- [ ] `/users/me`가 JWT 사용자를 반환한다.
- [ ] User Preference 수정 가능하다.
- [ ] User Interest 저장 가능하다.
- [ ] Companion CRUD가 동작한다.
- [ ] Companion DELETE는 실제 삭제가 아니라 `ARCHIVED`다.
- [ ] 다른 사용자의 Companion에 접근할 수 없다.

### Phase 1 완료 판정

```text
로그인 → 사용자 프로필 → 동행자 관리가 Mock 상태에서 정상 동작
```

---

# 5. Phase 2 — 여행 CRUD + Mock 기반 핵심 흐름

이 단계가 첫 번째 **핵심 MVP Vertical Slice**다.

## 구현 Model

```text
trips
trip_preferences
trip_companions
trip_interests
trip_sources

places
source_places

travel_plans
plan_items
plan_revisions
plan_validation_issues
```

## API

```http
POST /trips
GET /trips
GET /trips/{trip_id}
PATCH /trips/{trip_id}
DELETE /trips/{trip_id}

POST /trips/{trip_id}/sources/youtube
DELETE /trips/{trip_id}/sources/{source_id}

POST /trips/{trip_id}/analyze-preferences

GET /places/search

POST /trips/{trip_id}/plans/generate
GET /plans/{plan_id}
POST /plans/{plan_id}/confirm
```

## 이 단계에서는

실제 외부 API를 반드시 붙이지 않아도 된다.

`mock_data/`를 사용하여:

```text
YouTube Mock
Place Mock
EXAONE Mock
Weather Mock
Routing Mock
```

으로 전체 흐름을 먼저 완성한다.

## 핵심 End-to-End 시나리오

```text
로그인
↓
사용자/동행자 설정
↓
Trip 생성
↓
YouTube Source 추가
↓
Mock 취향 분석
↓
Mock Place 조회
↓
Mock Plan 생성
↓
Plan 조회
↓
Plan Confirm
```

## 완료조건

- [ ] Trip 생성 가능
- [ ] User Preference가 Trip Preference로 복사된다.
- [ ] Companion Snapshot이 `trip_companions`에 저장된다.
- [ ] Trip Interest를 저장할 수 있다.
- [ ] Trip DELETE는 `ARCHIVED`다.
- [ ] YouTube Source가 Trip과 연결된다.
- [ ] Source DELETE는 `is_active = FALSE`다.
- [ ] Mock Place를 검색할 수 있다.
- [ ] Mock Plan 생성이 가능하다.
- [ ] Plan Item이 실제 `place_id`를 참조한다.
- [ ] Plan 조회 API가 DB/API 명세와 맞는다.
- [ ] Plan Confirm이 동작한다.

### Phase 2 완료 판정

```text
외부 API 없이도 핵심 여행 흐름이 처음부터 끝까지 동작
```

이 단계가 매우 중요하다.

---

# 6. Phase 3 — 실제 Kakao / Naver / YouTube / Place 연결

Mock으로 전체 흐름이 검증된 뒤 Provider를 연결한다.

## 구현 순서

### 3-1. Kakao Login

```text
Kakao Access Token
→ /v2/user/me
→ provider_user_id
```

### 3-2. Naver Login

```text
Naver Access Token
→ /v1/nid/me
→ provider_user_id
```

### 3-3. YouTube

```text
URL
→ videoId
→ videos.list
→ Metadata
```

### 3-4. Kakao Local

```text
장소명
→ Keyword Search
→ places Upsert
→ 내부 place_id
```

## 완료조건

- [ ] Kakao 실제 로그인 성공
- [ ] Naver 실제 로그인 성공
- [ ] 잘못된 Social Token이 정상 Error 처리된다.
- [ ] YouTube URL에서 videoId 추출 가능
- [ ] YouTube Metadata 조회 가능
- [ ] 비공개/없는 영상 실패 처리 가능
- [ ] Kakao 장소 검색 가능
- [ ] Kakao Place ID로 중복 장소 생성 방지
- [ ] 외부 Place ID와 내부 place_id가 분리된다.
- [ ] Provider 장애 시 내부 Error Code로 변환된다.

### Phase 3 완료 판정

```text
Mock 대신 실제 인증/콘텐츠/장소 Provider를 연결해도 기존 Business Flow가 유지
```

---

# 7. Phase 4 — EXAONE 여행계획 생성

여기서 처음 실제 AI 여행계획을 연결한다.

## 구현 항목

```text
YouTube Metadata 기반 취향 분석
Trip 데이터 정리
User Preference
Companion Snapshot
Trip Interest
Place 후보
EXAONE Prompt
EXAONE Response Schema Validation
Plan 저장
```

## 반드시 먼저 준비할 것

EXAONE에게 전달하는 Place는:

```json
{
  "place_id": 101,
  "name": "..."
}
```

처럼 Backend가 검증한 장소만 전달한다.

AI가 임의 장소 ID를 생성하면 안 된다.

## API

```http
POST /trips/{trip_id}/analyze-preferences
POST /trips/{trip_id}/plans/generate
```

## 완료조건

- [ ] EXAONE Adapter가 Business Service와 분리되어 있다.
- [ ] Base URL / Model / Key가 환경변수다.
- [ ] AI Request가 실제 Trip 조건을 포함한다.
- [ ] AI Response가 JSON Schema/Pydantic 검증을 통과해야만 저장된다.
- [ ] 허용되지 않은 Interest Code는 저장되지 않는다.
- [ ] 존재하지 않는 place_id는 저장되지 않는다.
- [ ] AI Timeout이 전체 DB Transaction을 깨뜨리지 않는다.
- [ ] AI 실패 시 기존 Plan 데이터가 보존된다.

### Phase 4 완료 판정

```text
실제 Trip 데이터를 기반으로 EXAONE이 일정 초안을 생성하고 DB에 안전하게 저장
```

---

# 8. Phase 5 — 일정 검증 / 수정 / 재구성

AI 생성 이후 가장 중요한 Backend 기능이다.

## 구현 API

```http
POST /plans/{plan_id}/edit
POST /plans/{plan_id}/regenerate
POST /plans/{plan_id}/confirm
```

## Edit Operation

```text
DELETE_PLACE
REPLACE_PLACE
ADD_REST
REORDER
```

## Validation

우선 Mock/내부 규칙부터 구현:

```text
Trip 날짜 범위
시간 겹침
sequence
place_id 존재
휴식 조건
```

그리고 Provider 정보가 연결되면:

```text
운영시간
이동시간
날씨
접근성 Warning
```

추가.

## Revision

수정/재구성 전:

```text
현재 일정
→ plan_revisions Snapshot
→ 수정
→ Validation
→ Version 증가
```

## 완료조건

- [ ] DELETE_PLACE가 정상 동작
- [ ] REPLACE_PLACE가 정상 동작
- [ ] ADD_REST가 정상 동작
- [ ] REORDER가 정상 동작
- [ ] 수정 전 Revision Snapshot이 남는다.
- [ ] `current_version`이 증가한다.
- [ ] USER_FATIGUE 재구성이 가능하다.
- [ ] WEATHER_CHANGE 재구성이 가능하다.
- [ ] 검증 Issue가 `plan_validation_issues`에 저장된다.
- [ ] Warning이 있어도 Plan 조회 가능
- [ ] Critical Issue가 있을 경우 Confirm 정책이 적용된다.

### 초기 Confirm 정책

```text
CRITICAL 미해결 존재
→ Confirm 불가

WARNING만 존재
→ 사용자 확인 후 Confirm 가능
```

### Phase 5 완료 판정

```text
AI가 만든 일정이 사용자 상태/환경 변화에 따라 안전하게 수정되고 검증됨
```

---

# 9. Phase 6 — TourAPI / Routing / Weather 강화

일정 Validation의 실제 데이터 품질을 높인다.

## 6-1. TourAPI

사용:

```text
관광 상세정보
소개
운영정보
이미지
```

## 6-2. Routing

사용:

```text
도보
대중교통
자동차
```

정규화:

```json
{
  "mode": "WALK",
  "duration_minutes": 18,
  "distance_meters": 1300,
  "available": true
}
```

## 6-3. 기상청

사용:

```text
여행일이 단기예보 범위에 있을 때
```

## 완료조건

- [ ] TourAPI 정보가 Place에 보강된다.
- [ ] TourAPI 결과 없음이 장소 미존재로 처리되지 않는다.
- [ ] 이동시간/거리가 Plan Item에 반영된다.
- [ ] Routing 실패는 `TRAVEL_TIME_UNKNOWN`으로 처리된다.
- [ ] Weather가 단기예보 범위 밖이면 확정값을 생성하지 않는다.
- [ ] Weather 실패가 Plan 전체 실패로 이어지지 않는다.
- [ ] 비/악천후 Warning을 생성할 수 있다.

### Phase 6 완료 판정

```text
일정 Validation이 실제 관광/이동/날씨 데이터를 사용
```

---

# 10. Phase 7 — Smart Docent

여행계획 이후 별도 기능으로 개발한다.

## API

```http
POST /docent/identify
POST /docent/explain
```

## Identify Flow

```text
Flutter Image
↓
Image Validation
↓
Gemini
↓
후보 최대 3개
↓
Kakao/TourAPI 검증
↓
docent_analyses
docent_candidates
↓
Flutter
```

## Explain Flow

```text
사용자가 candidate 선택
↓
검증된 places 데이터
↓
EXAONE
↓
설명 생성
```

## 완료조건

- [ ] multipart 이미지 업로드 가능
- [ ] 파일 크기/MIME 검증
- [ ] 이미지 원본 DB 저장 안 함
- [ ] Gemini 장소 후보 최대 3개
- [ ] 장소 식별 실패는 Error가 아닌 빈 배열
- [ ] Gemini 숫자 confidence를 사용하지 않음
- [ ] Kakao/TourAPI로 후보 검증
- [ ] 사용자가 후보를 선택한 뒤에만 Explain 가능
- [ ] EXAONE 설명이 검증된 Place Context를 사용
- [ ] Trip 없이도 Docent를 사용할 수 있음

### Phase 7 완료 판정

```text
사진 → 후보 → 사용자 선택 → 장소 설명의 전체 흐름이 동작
```

---

# 11. Phase 8 — 통합 테스트 / 안정화

최종 Codex 구현 마무리 단계.

## API Test

최소:

```text
Auth
Users
Companions
Trips
YouTube
Places
Plans
Docent
```

## 필수 시나리오

### Happy Path

```text
로그인
→ 프로필
→ 동행자
→ Trip
→ YouTube
→ 관심사
→ 장소
→ Plan
→ Validation
→ Confirm
```

### Fatigue

```text
Plan
→ "힘들어요"
→ Revision
→ REST 추가/일정 축소
→ Validation
```

### Weather

```text
Plan
→ 비 예보
→ WEATHER_WARNING
→ Regenerate
→ 실내 중심 일정
```

### External Failure

```text
TourAPI 실패
Weather 실패
YouTube 실패
AI Timeout
```

각 실패가 전체 서비스에 어떤 영향을 주는지 테스트한다.

### Smart Docent

```text
사진
→ 후보
→ 선택
→ 설명
```

그리고:

```text
사진
→ 식별 불가
→ candidates=[]
```

도 테스트한다.

## 완료조건

- [ ] 주요 API Integration Test 통과
- [ ] 다른 사용자의 데이터 접근 차단
- [ ] Mock Test 통과
- [ ] 최소 핵심 External Test 통과
- [ ] AI Response Validation Test 통과
- [ ] DB Migration 재생성 가능
- [ ] 새 환경에서 README만 보고 실행 가능
- [ ] `.env.example` 완성
- [ ] Swagger와 실제 API 구조 일치
- [ ] 치명적인 TODO 없음

### Phase 8 완료 판정

```text
팀원이 새 PC에서 Repository를 받아 문서대로 실행하고 핵심 시나리오를 재현 가능
```

---

# 12. 기능 우선순위

## P0 — 반드시 구현

```text
Auth
User / Preference
Companion
Trip
YouTube Source
Place
Trip Interest
Plan Generate
Plan Validation
Plan Edit
Plan Regenerate
Plan Confirm
```

P0이 실제 프로젝트 핵심이다.

---

## P1 — 높은 우선순위

```text
TourAPI 상세정보
Routing
Weather Validation
Smart Docent
```

---

## P2 — 시간이 남으면

```text
고급 캐싱
복잡한 Provider Failover
운영 Monitoring 고도화
세밀한 성능 최적화
추가 추천 설명
```

P2 기능 때문에 P0 구현을 늦추지 않는다.

---

# 13. Codex 작업 단위 원칙

Codex에게 한 번에 전체 Backend를 만들라고 하지 않는다.

권장:

```text
Task 1
Phase 0만 구현

검토

Task 2
User/Auth Model + Migration

검토

Task 3
Auth API

검토

Task 4
Companion API

검토

...
```

한 Task 기준:

```text
관련 MD 읽기
→ 필요한 파일만 변경
→ 테스트 작성
→ 테스트 실행
→ 변경사항 요약
```

---

# 14. 각 Codex Task의 공통 완료조건

모든 Task는 다음을 만족해야 완료로 본다.

- [ ] API Spec과 URL 일치
- [ ] DB Schema와 Model 일치
- [ ] Folder Structure 준수
- [ ] Secret Hard Coding 없음
- [ ] Router에 SQL 직접 작성 없음
- [ ] Router에 External API 직접 호출 없음
- [ ] Error 처리 존재
- [ ] 최소 Test 존재
- [ ] 기존 Test가 깨지지 않음
- [ ] 불필요한 파일 생성 없음
- [ ] 문서와 다른 판단을 임의로 하지 않음
- [ ] Frontend Repository 파일을 생성/수정하지 않음
- [ ] API 계약을 임의 변경하지 않음
- [ ] Database 자체를 생성/삭제하지 않음
- [ ] MySQL 접속정보를 코드/문서/Git에 남기지 않음

---

# 15. 실제 Codex 투입 순서

```text
Codex Task 01
Backend Project Skeleton + Existing MySQL Connection + CORS

Codex Task 02
Database Models + Alembic

Codex Task 03
Auth / User

Codex Task 04
Companion

Codex Task 05
Trip

Codex Task 06
Mock External Provider

Codex Task 07
YouTube Source + Preference

Codex Task 08
Place

Codex Task 09
Mock Plan Generation

Codex Task 10
Plan Edit / Revision / Validation

Codex Task 11
Kakao / Naver / YouTube Real Provider

Codex Task 12
EXAONE

Codex Task 13
TourAPI / Routing / Weather

Codex Task 14
Smart Docent Gemini

Codex Task 15
Integration Test / Cleanup
```

---

# 16. MVP 첫 성공 지점

전체 기능을 다 만들기 전에 가장 먼저 달성해야 할 성공 지점:

```text
Mock Social Login
↓
User
↓
Companion
↓
Trip 생성
↓
Mock YouTube
↓
Mock Interest
↓
Mock Places
↓
Mock EXAONE Plan
↓
Plan 저장
↓
Plan 조회
```

이 흐름이 성공하면 Backend 기본 구조가 맞다는 뜻이다.

그 이후 실제 외부 API와 AI를 하나씩 교체한다.

---

# 17. 6단계 완료 기준

- [x] 구현 Phase 정의
- [x] 기능 우선순위 P0/P1/P2 정의
- [x] Phase별 완료조건 정의
- [x] Mock → Real Provider 순서 정의
- [x] Codex Task 단위 정의
- [x] 통합테스트 기준 정의
- [x] MVP 첫 성공 지점 정의

다음 단계는 **7. Codex 투입**이다.
