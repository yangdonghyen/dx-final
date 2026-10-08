# 02. Backend API Specification — Draft Final

## 1. 기본 규칙

Base URL:

`/api/v1`

인증이 필요한 API는 Header에 우리 서비스 JWT를 전달한다.

```http
Authorization: Bearer {OUR_ACCESS_TOKEN}
```

### API 기본 원칙

- 로그인 이후 현재 사용자는 JWT로 식별한다.
- Request Body에서 user_id를 받아 현재 사용자를 판단하지 않는다.
- 다른 사용자의 데이터 접근을 차단한다.
- 외부 API 원본 응답은 그대로 Flutter에 전달하지 않는다.
- Backend 내부 표준 Schema로 변환해 반환한다.
- 생성/수정된 일정은 자동 저장한다.
- 일정 생성/수정/재구성 후 Validation Service를 반드시 실행한다.
- API Key와 Secret은 `.env`로 관리한다.
- 확인할 수 없는 정보는 AI가 추측하지 않는다.

---

# 2. 공통 API

## 2-1. Health Check

### Endpoint

`GET /health`

### Response

```json
{
  "status": "ok"
}
```

### 목적

- Backend 서버 실행 확인
- 배포 상태 확인
- Codex 및 테스트 환경에서 서버 상태 확인

---

# 3. 인증 API

지원 Provider:

- KAKAO
- NAVER

---

## 3-1. 소셜 로그인

### Endpoint

`POST /auth/social-login`

### Request

Kakao:

```json
{
  "provider": "KAKAO",
  "access_token": "provider_access_token"
}
```

Naver:

```json
{
  "provider": "NAVER",
  "access_token": "provider_access_token"
}
```

### Backend 처리

1. provider 값 확인
2. provider access token 검증
3. Kakao 또는 Naver 사용자 정보 API 호출
4. provider_user_id 확보
5. USER_AUTH 조회
6. 신규 사용자면 USER 및 USER_AUTH 생성
7. 기존 사용자면 해당 USER 조회
8. 우리 서비스 Access Token / Refresh Token 생성

### Response

```json
{
  "access_token": "our_access_token",
  "refresh_token": "our_refresh_token",
  "token_type": "bearer",
  "is_new_user": true,
  "user": {
    "user_id": 1,
    "nickname": null,
    "profile_completed": false
  }
}
```

### 보안 규칙

- provider access_token을 장기 저장하지 않는다.
- 클라이언트가 제공하는 provider_user_id를 신뢰하지 않는다.
- provider_user_id는 Backend가 Kakao/Naver API를 통해 직접 확인한다.
- 같은 이메일이라는 이유만으로 KAKAO와 NAVER 계정을 자동 통합하지 않는다.

---

## 3-2. Access Token 갱신

### Endpoint

`POST /auth/refresh`

### Request

```json
{
  "refresh_token": "our_refresh_token"
}
```

### Response

```json
{
  "access_token": "new_access_token",
  "refresh_token": "new_refresh_token",
  "token_type": "bearer"
}
```

---

## 3-3. 로그아웃

### Endpoint

`POST /auth/logout`

### Request

```json
{
  "refresh_token": "our_refresh_token"
}
```

### Response

```json
{
  "message": "logout_success"
}
```

---

# 4. 사용자 API

## 4-1. 내 정보 조회

### Endpoint

`GET /users/me`

### Response

```json
{
  "user_id": 1,
  "nickname": "동현",
  "age_group": "20S",
  "profile_completed": true,
  "preferences": {
    "interests": [
      "FOOD",
      "CAFE",
      "CULTURE"
    ],
    "walking_tolerance": "LOW",
    "rest_frequency": "HIGH",
    "avoid_stairs": true,
    "avoid_hills": false,
    "taxi_allowed": true
  }
}
```

---

## 4-2. 기본 프로필 수정

### Endpoint

`PATCH /users/me`

### 규칙

소셜 최초 로그인 직후에는 `nickname`과 `age_group`이 비어 있을 수 있다.
초기 프로필 설정 완료 전까지 `profile_completed = false`를 유지한다.
`age_group`은 `UNDER_20`, `20S`, `30S`, `40S`, `50S`, `60S`, `70S_PLUS` 중 하나를 사용한다.

### Request

```json
{
  "nickname": "동현",
  "age_group": "20S"
}
```

### Response

```json
{
  "user_id": 1,
  "nickname": "동현",
  "age_group": "20S",
  "profile_completed": true
}
```

---

## 4-3. 여행 성향 수정

### Endpoint

`PATCH /users/me/preferences`

### Request

```json
{
  "interests": [
    "FOOD",
    "CAFE",
    "NATURE"
  ],
  "walking_tolerance": "LOW",
  "rest_frequency": "HIGH",
  "avoid_stairs": true,
  "avoid_hills": false,
  "taxi_allowed": true
}
```

---

# 5. 동행자 API

## 5-1. 동행자 등록

### Endpoint

`POST /companions`

### Request

```json
{
  "name": "어머니",
  "relation": "MOTHER",
  "age_group": "60S",
  "preferences": {
    "interests": [
      "NATURE",
      "FOOD"
    ],
    "walking_tolerance": "LOW",
    "rest_frequency": "HIGH",
    "avoid_stairs": true,
    "avoid_hills": true,
    "taxi_allowed": true
  }
}
```

### Response

```json
{
  "companion_id": 3,
  "name": "어머니"
}
```

---

## 5-2. 동행자 목록 조회

### Endpoint

`GET /companions`

### Response

```json
{
  "companions": [
    {
      "companion_id": 2,
      "name": "아버지",
      "relation": "FATHER",
      "age_group": "60S"
    },
    {
      "companion_id": 3,
      "name": "어머니",
      "relation": "MOTHER",
      "age_group": "60S"
    }
  ]
}
```

---

## 5-3. 동행자 수정

### Endpoint

`PATCH /companions/{companion_id}`

Backend는 현재 로그인 사용자가 해당 동행자의 소유자인지 확인한다.

---

## 5-4. 동행자 삭제

### Endpoint

`DELETE /companions/{companion_id}`

### 처리 규칙

물리 삭제하지 않고 `companions.status = ARCHIVED`로 처리한다.
과거 여행의 동행자 Snapshot은 유지한다.

---

# 6. 여행 API

## 6-1. 새로운 여행 생성

### Endpoint

`POST /trips`

### Request

```json
{
  "title": "대전 2박 3일",
  "departure": "광주",
  "destination": "대전",
  "start_date": "2026-10-10",
  "end_date": "2026-10-12",
  "budget_krw": 300000,
  "transport_mode": "PUBLIC_TRANSIT",
  "companion_ids": [3],
  "trip_preferences": {
    "walking_tolerance": "LOW",
    "rest_frequency": "HIGH"
  }
}
```

`destination`은 콘텐츠 분석 이후 정해질 수도 있으므로 NULL 허용 가능.

### Response

```json
{
  "trip_id": 15,
  "status": "DRAFT"
}
```

---

## 6-2. 내 여행 목록 조회

### Endpoint

`GET /trips`

---

## 6-3. 여행 상세 조회

### Endpoint

`GET /trips/{trip_id}`

반환 대상:

- 여행 기본정보
- 선택된 동행자
- 연결된 YouTube Source
- 분석된 여행 취향
- 현재 Plan ID
- 현재 상태

---

## 6-4. 여행 조건 수정

### Endpoint

`PATCH /trips/{trip_id}`

### Request 예시

```json
{
  "budget_krw": 400000,
  "transport_mode": "CAR"
}
```

---

## 6-5. 여행 삭제

### Endpoint

`DELETE /trips/{trip_id}`

### 처리 규칙

물리 삭제하지 않고 `trips.status = ARCHIVED`로 처리한다.

---

## 6-6. 여행 공유 / 초대 링크 생성

### Endpoint

`POST /trips/{trip_id}/share-links` (소유자만)

### Request

```json
{ "link_type": "VIEW" }
```

`link_type`: `VIEW`(보기 전용, 만료 없음) 또는 `INVITE`(동행자 초대, 7일 후 만료)

### Response `201`

```json
{
  "link_type": "VIEW",
  "url": "http://<host>/api/v1/shared-trips/<token>",
  "expires_at": null
}
```

- token 원문은 응답에만 포함, DB에는 SHA-256 hash만 저장 (`trip_share_links`)
- URL origin은 `PUBLIC_SHARE_BASE_URL`, 비어 있으면 요청 origin

## 6-7. 공유된 여행 조회

`GET /shared-trips/{token}` (인증 불필요)

- `Accept: text/html`이면 카카오톡·브라우저용 간단한 HTML 페이지
  - `INVITE` 링크 페이지에는 앱을 여는 `bogogago://invite?token=<token>` 버튼("보고가고 앱에서 참여하기")이 있음
- 그 외에는 JSON: `link_type, title, destination, start_date, end_date, owner_nickname, companions[{name, relation}], selected_places[]`
- 없거나 회수된 링크 `404 SHARE_LINK_NOT_FOUND`, 만료 `410 SHARE_LINK_EXPIRED`

## 6-8. 초대 링크로 여행 참여

`POST /shared-trips/{token}/join` (로그인 사용자)

- `INVITE` 링크만 가능, 소유자는 참여 불가
- `trip_companions`에 `member_user_id`, `relation_snapshot = FRIEND`로 1회만 추가
- Response: `{ "trip_id": 1, "already_joined": false }`

---

# 7. YouTube 콘텐츠 및 취향 분석 API

## 7-1. YouTube 콘텐츠 추가

### Endpoint

`POST /trips/{trip_id}/sources/youtube`

### Request

```json
{
  "youtube_url": "https://youtube.com/watch?v=..."
}
```

### Backend 처리

YouTube URL
→ videoId 추출
→ YouTube Data API 호출
→ title / description / tags 등 저장

### Response

```json
{
  "source_id": 21,
  "type": "YOUTUBE",
  "video_id": "abc123",
  "title": "강릉 꼭 가봐야 할 여행지",
  "description": "...",
  "tags": [
    "강릉",
    "경포대",
    "안목해변"
  ]
}
```

---

## 7-2. YouTube 콘텐츠 제거

### Endpoint

`DELETE /trips/{trip_id}/sources/{source_id}`

### 처리 규칙

분석 출처 이력을 보존하기 위해 물리 삭제하지 않고
`trip_sources.is_active = false`로 처리한다.

---

## 7-3. 이번 여행 취향 분석

### Endpoint

`POST /trips/{trip_id}/analyze-preferences`

### 분석 입력

- 사용자 기본 취향
- 선택된 동행자 취향
- YouTube Metadata
- 사용자 여행 조건

### Response

```json
{
  "inferred_preferences": [
    "NATURE",
    "CAFE",
    "FOOD"
  ],
  "destination_candidates": [
    "강릉"
  ],
  "evidence": [
    {
      "source": "YOUTUBE",
      "text": "안목해변과 강릉 카페거리 관련 콘텐츠"
    }
  ]
}
```

분석 결과는 사용자가 수정할 수 있어야 한다.

AI가 반환하는 관심사 코드는 DB의 `interest_codes`에 존재하는 값만 허용한다.
임의의 신규 코드(예: `SEA`, `LOCAL_FOOD`)를 바로 저장하지 않는다.

확정된 결과는 `trip_interests`에 반영한다.

---

# 8. 장소 API

## 8-1. 장소 검색

### Endpoint

`GET /places/search?query=경복궁&region=서울`

### 사용 목적

- 여행지 직접 입력
- 일정의 장소 교체
- AI가 제안하지 않은 장소 추가
- 스마트 도슨트 후보 검증

### Backend 처리

Kakao Map / TourAPI 등 외부 API
→ 장소 검색
→ 기존 `places` 조회
→ 없으면 `places`에 Upsert
→ 내부 `place_id` 확보
→ 내부 Place Schema로 변환
→ Flutter 반환

API가 반환하는 `place_id`는 외부 API ID가 아니라 우리 MySQL의 `places.place_id`다.

### Response

```json
{
  "places": [
    {
      "place_id": 101,
      "name": "경복궁",
      "region": "서울",
      "address": "서울특별시 종로구 ...",
      "latitude": 37.0,
      "longitude": 126.0
    }
  ]
}
```

---

# 9. AI 여행 일정 API

## 9-1. 일정 생성

### Endpoint

`POST /trips/{trip_id}/plans/generate`

### Backend 처리

사용자 조건
+ 동행자 조건
+ YouTube 기반 취향
+ 관광지 데이터
+ 날씨
+ 이동정보
→ EXAONE
→ 일정 초안
→ Validation Service
→ DB 저장

### Response

```json
{
  "plan_id": 30,
  "status": "DRAFT",
  "days": [
    {
      "day": 1,
      "visit_date": "2026-10-10",
      "items": [
        {
          "item_id": 1001,
          "place_id": 101,
          "name": "경복궁",
          "start_time": "10:00",
          "end_time": "12:00",
          "validation_status": "VALID"
        }
      ]
    }
  ],
  "warnings": []
}
```

---

### 검증 응답 규칙

`plan_items.validation_status`는 `VALID`, `WARNING`, `UNKNOWN` 중 하나를 반환한다.
세부 검증 문제는 Backend의 `plan_validation_issues`를 바탕으로 `warnings`에 정규화해 반환한다.

---

## 9-2. 일정 조회

### Endpoint

`GET /plans/{plan_id}`

---

## 9-3. 일정 직접 수정

### Endpoint

`POST /plans/{plan_id}/edit`

### 장소 삭제

```json
{
  "operation": "DELETE_PLACE",
  "item_id": 1001
}
```

### 장소 교체

```json
{
  "operation": "REPLACE_PLACE",
  "item_id": 1001,
  "new_place_id": 105
}
```

### 휴식 추가

```json
{
  "operation": "ADD_REST",
  "day": 1,
  "after_item_id": 1001,
  "duration_minutes": 30
}
```

### 순서 변경

```json
{
  "operation": "REORDER",
  "day": 1,
  "item_ids": [
    1003,
    1001,
    1002
  ]
}
```

수정 완료 후 Validation Service를 자동 실행한다.

---

## 9-4. AI 일정 재구성

### Endpoint

`POST /plans/{plan_id}/regenerate`

### 사용자 피로

```json
{
  "reason": "USER_FATIGUE",
  "instruction": "많이 걸어서 힘들어요."
}
```

### 날씨 변화

```json
{
  "reason": "WEATHER_CHANGE",
  "instruction": "비가 와서 실내 일정 위주로 바꿔주세요."
}
```

### Backend 처리

현재 일정
+ 변경조건
→ EXAONE
→ 새 일정
→ Validation Service
→ PLAN_REVISION 저장
→ 수정된 일정 저장

---

## 9-5. 일정 최종 확정

### Endpoint

`POST /plans/{plan_id}/confirm`

### Response

```json
{
  "plan_id": 30,
  "status": "CONFIRMED"
}
```

별도의 SAVE API를 만들지 않는다.

일정 생성 및 수정은 자동 저장하며,
`confirm`은 사용자가 최종 일정으로 확정했다는 상태 변경만 수행한다.

---

# 10. 일정 검증

일정 검증은 별도의 Flutter 공개 API로 만들지 않는다.

아래 상황에서 Backend 내부 Validation Service를 자동 실행한다.

- 최초 일정 생성
- 장소 삭제
- 장소 교체
- 순서 변경
- 휴식 추가
- AI 일정 재구성

### 검증 항목

- 실제 장소 존재 여부
- 좌표
- 이동 가능성
- 이동시간
- 운영시간
- 날짜
- 일정 충돌
- 날씨
- 사용자 이동 제약
- 동행자 이동 제약

### 규칙

- AI가 검증 결과를 생성하지 않는다.
- 검증할 수 없는 정보는 `UNKNOWN` 또는 Warning으로 반환한다.
- 외부 API 장애 시 AI가 값을 추측해 채우지 않는다.

---

# 11. 스마트 도슨트 API

스마트 도슨트는 여행계획 기능과 별도의 현장 기능으로 취급한다.

---

## 11-1. 사진 장소 추정

### Endpoint

`POST /docent/identify`

### Content-Type

`multipart/form-data`

### Request

- image: 사용자 사진
- trip_id: Optional

### Backend 처리

사진
→ Gemini
→ 장소 후보 추정
→ Kakao/TourAPI 등으로 후보 검증
→ 후보 반환

### Response

```json
{
  "analysis_id": 500,
  "message": "사진을 분석한 결과 아래 장소일 가능성이 있습니다.",
  "candidates": [
    {
      "candidate_id": 1,
      "place_id": 101,
      "name": "경복궁",
      "region": "서울",
      "rank": 1,
      "verification_status": "VERIFIED"
    },
    {
      "candidate_id": 2,
      "place_id": 102,
      "name": "창덕궁",
      "region": "서울",
      "rank": 2,
      "verification_status": "VERIFIED"
    }
  ]
}
```

### 표현 규칙

허용:

- "경복궁일 가능성이 있습니다."
- "경복궁이 아닐까요?"
- "아래 장소 중 하나로 보입니다."

금지:

- "여기는 경복궁입니다."

모델이 임의로 생성한 숫자 확률을 사용자에게 제공하지 않는다.

장소를 특정하기 어려운 경우:

```json
{
  "analysis_id": 501,
  "candidates": [],
  "message": "사진만으로 정확한 장소를 특정하기 어렵습니다."
}
```

사진 원본은 기본적으로 분석 완료 후 영구 보관하지 않는다.

---

## 11-2. 스마트 도슨트 설명

### Endpoint

`POST /docent/explain`

### Request

```json
{
  "analysis_id": 500,
  "candidate_id": 1
}
```

### Backend 처리

사용자가 선택한 장소
→ 검증된 장소정보 확보
→ EXAONE
→ 사용자 친화적 설명

### Response

```json
{
  "place_id": 101,
  "name": "경복궁",
  "description": "경복궁은 ...",
  "highlights": [
    "...",
    "..."
  ]
}
```

### 규칙

- 사용자가 장소 후보를 선택한 이후 설명을 생성한다.
- EXAONE에게 검증된 장소 데이터를 함께 전달한다.
- 검증되지 않은 사실을 생성하지 않도록 한다.

---

# 12. 공통 Error Response

모든 API는 같은 오류 구조를 사용한다.

```json
{
  "error": {
    "code": "TRIP_NOT_FOUND",
    "message": "여행 정보를 찾을 수 없습니다."
  }
}
```

### HTTP Status

- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- 409 Conflict
- 422 Unprocessable Entity
- 429 Too Many Requests
- 502 Bad Gateway

---

# 13. Backend 내부 Service

Flutter에서 직접 호출하지 않고 FastAPI 내부에서 사용한다.

```text
services/

auth/
├── kakao_service
└── naver_service

youtube_service
kakao_map_service
tour_service
weather_service

gemini_service
exaone_service

plan_generation_service
plan_validation_service
docent_service
```

### 역할

| Service | 역할 |
|---|---|
| kakao_service | Kakao 로그인 인증 |
| naver_service | Naver 로그인 인증 |
| youtube_service | YouTube 메타데이터 수집 |
| kakao_map_service | 장소 검색, 주소, 좌표 |
| tour_service | 관광정보 |
| weather_service | 날씨정보 |
| gemini_service | 스마트 도슨트 이미지 장소 후보 추정 |
| exaone_service | 조건 해석, 일정 생성, 재구성, 도슨트 설명 |
| plan_generation_service | 여행 일정 생성 전체 흐름 |
| plan_validation_service | 실제 일정 검증 |
| docent_service | 스마트 도슨트 전체 흐름 |

---

# 14. 최종 공개 Endpoint 목록

```text
COMMON
GET     /health

AUTH
POST    /auth/social-login
POST    /auth/refresh
POST    /auth/logout

USER
GET     /users/me
PATCH   /users/me
PATCH   /users/me/preferences

COMPANION
GET     /companions
POST    /companions
PATCH   /companions/{companion_id}
DELETE  /companions/{companion_id}

TRIP
POST    /trips
GET     /trips
GET     /trips/{trip_id}
PATCH   /trips/{trip_id}
DELETE  /trips/{trip_id}

YOUTUBE / PREFERENCE
POST    /trips/{trip_id}/sources/youtube
DELETE  /trips/{trip_id}/sources/{source_id}
POST    /trips/{trip_id}/analyze-preferences

PLACE
GET     /places/search

PLAN
POST    /trips/{trip_id}/plans/generate
GET     /plans/{plan_id}
POST    /plans/{plan_id}/edit
POST    /plans/{plan_id}/regenerate
POST    /plans/{plan_id}/confirm

SMART DOCENT
POST    /docent/identify
POST    /docent/explain
```

총 27개 Endpoint.

---

# 15. Codex 구현 고정 규칙

1. API Base URL은 `/api/v1`을 사용한다.
2. 로그인 이후 현재 사용자는 JWT로 식별한다.
3. user_id를 Request Body로 받아 현재 사용자를 판단하지 않는다.
4. 다른 사용자의 Trip, Plan, Companion 접근을 차단한다.
5. YouTube Metadata는 여행계획의 Source로 취급한다.
6. Gemini의 장소 추정 결과를 확정 정보처럼 표현하지 않는다.
7. 스마트 도슨트 설명은 사용자가 후보 장소를 선택한 후 생성한다.
8. EXAONE은 일정 초안을 생성하지만 실제 장소·시간·날씨를 확정하지 않는다.
9. 외부 API 원본 Response를 Flutter에 그대로 반환하지 않는다.
10. Backend 표준 Schema로 변환해 반환한다.
11. API Key와 Secret은 `.env`로 관리하며 Git에 Commit하지 않는다.
12. 생성 및 수정된 일정은 자동 저장한다.
13. 일정 생성/수정/재구성 후 Validation Service를 실행한다.
14. 외부 API 장애 시 AI가 실제 정보를 추측해 채우지 않는다.
15. 확인할 수 없는 정보는 `UNKNOWN` 또는 Warning으로 반환한다.
16. Kakao와 Naver 계정을 이메일만으로 자동 통합하지 않는다.
