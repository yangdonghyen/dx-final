# 04. External APIs — Draft Final

## 1. 목적

이 문서는 AI 여행 서비스 Backend가 사용하는 외부 API의 역할과 입출력 규칙을 정의한다.

대상:

1. Kakao Login
2. Naver Login
3. YouTube Data API v3
4. Kakao Local / Routing API
5. Kakao Mobility Directions API
6. 한국관광공사 TourAPI
7. 기상청 단기예보 API
8. Gemini API
9. EXAONE API

실제 Endpoint/Model/Quota는 외부 서비스 정책에 따라 바뀔 수 있으므로,
Provider별 호출 코드는 Service/Adapter로 분리하고 Base URL과 Model은 환경변수로 관리한다.

---

# 2. 공통 설계 원칙

## Flutter 직접 호출 최소화

기본 구조:

```text
Flutter
→ FastAPI
→ External API
→ FastAPI에서 정규화/검증
→ Flutter
```

Flutter에 노출하지 않는 값:

- 외부 API Key
- Client Secret
- Service Key
- EXAONE/Gemini API Key
- 외부 API 원본 Response 전체

## Adapter 구조

```text
app/services/external/

auth/
├── kakao_auth_service.py
└── naver_auth_service.py

content/
└── youtube_service.py

place/
├── kakao_local_service.py
├── kakao_routing_service.py
├── kakao_mobility_service.py
└── tour_api_service.py

weather/
└── kma_weather_service.py

ai/
├── gemini_service.py
└── exaone_service.py
```

FastAPI Router가 외부 API를 직접 호출하지 않는다.

## Timeout / Retry

초기 권장:

```text
일반 REST API: 5~10초
AI API: 30~60초
```

Retry 대상:

- Timeout
- HTTP 429
- HTTP 5xx

최대 2회 재시도 + Exponential Backoff 사용을 기본으로 한다.

400/401/403/422는 자동 Retry하지 않는다.

---

# 3. Kakao Login

## 역할

```text
Flutter Kakao Login
→ Kakao Access Token
→ FastAPI
→ Kakao 사용자 정보 API
→ Kakao Service User ID 획득
→ user_auths 조회/생성
→ 우리 서비스 JWT 발급
```

## 외부 Endpoint

```http
GET https://kapi.kakao.com/v2/user/me
Authorization: Bearer {KAKAO_ACCESS_TOKEN}
```

## 사용할 외부 값

필수:

```json
{
  "id": 123456789
}
```

nickname/email은 동의 설정에 따라 없을 수 있으므로
우리 서비스 사용자 식별에는 사용하지 않는다.

## Backend 정규화

```json
{
  "provider": "KAKAO",
  "provider_user_id": "123456789"
}
```

## DB

```text
user_auths.provider = KAKAO
user_auths.provider_user_id = Kakao id
```

## 실패 처리

| 상황 | 내부 코드 |
|---|---|
| Access Token 잘못됨/만료 | `INVALID_SOCIAL_TOKEN` |
| Kakao 장애 | `SOCIAL_PROVIDER_UNAVAILABLE` |
| Kakao User ID 없음 | `SOCIAL_PROFILE_INVALID` |

## 환경변수

```env
KAKAO_REST_API_KEY=
KAKAO_CLIENT_SECRET=
```

---

# 4. Naver Login

## 역할

```text
Flutter Naver Login
→ Naver Access Token
→ FastAPI
→ Naver Profile API
→ Naver User ID 획득
→ user_auths 조회/생성
→ 우리 서비스 JWT 발급
```

## 외부 Endpoint

```http
GET https://openapi.naver.com/v1/nid/me
Authorization: Bearer {NAVER_ACCESS_TOKEN}
```

## 대표 외부 Response

```json
{
  "resultcode": "00",
  "message": "success",
  "response": {
    "id": "naver_user_unique_id"
  }
}
```

## Backend 정규화

```json
{
  "provider": "NAVER",
  "provider_user_id": "naver_user_unique_id"
}
```

## 실패 처리

| 상황 | 내부 코드 |
|---|---|
| 잘못된/만료 Token | `INVALID_SOCIAL_TOKEN` |
| 권한 설정 오류 | `SOCIAL_PERMISSION_DENIED` |
| Naver 장애 | `SOCIAL_PROVIDER_UNAVAILABLE` |

## 환경변수

```env
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
```

---

# 5. YouTube Data API v3

## 역할

YouTube 여행 콘텐츠의 메타데이터를 AI 여행계획 입력으로 사용한다.

스마트 도슨트와는 별개의 기능이다.

## 처리 흐름

```text
YouTube URL
→ Backend에서 videoId 추출
→ YouTube videos.list
→ snippet 추출
→ trip_sources 저장
→ 취향/장소 분석
```

## 외부 Endpoint

```http
GET https://www.googleapis.com/youtube/v3/videos
```

Query:

```text
part=snippet
id={VIDEO_ID}
key={YOUTUBE_API_KEY}
```

## 사용할 외부 필드

```text
items[].id
items[].snippet.title
items[].snippet.description
items[].snippet.tags
items[].snippet.channelId
items[].snippet.channelTitle
items[].snippet.categoryId
```

## Backend 정규화 DTO

```json
{
  "video_id": "abc123",
  "title": "강릉 2박 3일 여행",
  "description": "경포대와 안목해변...",
  "tags": [
    "강릉",
    "여행",
    "안목해변"
  ],
  "channel_id": "UC...",
  "channel_title": "여행채널"
}
```

## DB

```text
trip_sources
```

## 실패 처리

| 상황 | 내부 코드 |
|---|---|
| URL에서 videoId 추출 실패 | `INVALID_YOUTUBE_URL` |
| 영상 없음 | `YOUTUBE_VIDEO_NOT_FOUND` |
| 비공개/접근 불가 | `YOUTUBE_VIDEO_UNAVAILABLE` |
| Quota 초과 | `YOUTUBE_QUOTA_EXCEEDED` |
| Google API 장애 | `YOUTUBE_API_UNAVAILABLE` |

AI가 가져오지 못한 영상의 내용을 추측해서 저장하지 않는다.

## 환경변수

```env
YOUTUBE_API_KEY=
```

---

# 6. Kakao Local API

## 역할

AI 또는 사용자가 제시한 장소명을 실제 장소 데이터로 검증한다.

```text
"경복궁"
→ Kakao 장소 검색
→ Kakao Place ID / 주소 / 좌표
→ places Upsert
```

## 외부 Endpoint

```http
GET https://dapi.kakao.com/v2/local/search/keyword.json
Authorization: KakaoAK {KAKAO_REST_API_KEY}
```

필수 Query:

```text
query={장소명}
```

선택 Query:

```text
x={longitude}
y={latitude}
radius={meters}
page=
size=
sort=
```

## 사용할 외부 필드

```text
documents[].id
documents[].place_name
documents[].category_name
documents[].phone
documents[].address_name
documents[].road_address_name
documents[].x
documents[].y
documents[].place_url
```

주의:

```text
x = longitude
y = latitude
```

## Backend 정규화 DTO

```json
{
  "kakao_place_id": "123456",
  "name": "경복궁",
  "category": "관광명소",
  "address": "서울특별시 종로구 ...",
  "latitude": 37.5796,
  "longitude": 126.9770,
  "phone": null,
  "source_url": "..."
}
```

## DB 처리

```text
kakao_place_id로 places 조회
→ 있으면 Update
→ 없으면 Insert
→ 내부 places.place_id 반환
```

외부 `id`와 내부 `place_id`를 혼동하지 않는다.

## 실패 처리

| 상황 | 내부 코드 |
|---|---|
| 검색결과 0개 | `PLACE_NOT_FOUND` |
| 후보 다수/불명확 | `PLACE_AMBIGUOUS` |
| Kakao 장애 | `PLACE_PROVIDER_UNAVAILABLE` |
| 인증 실패 | `PLACE_PROVIDER_AUTH_ERROR` |

---

# 7. Kakao Routing API

## 역할

일정 검증 시 도보/대중교통 이동 가능성과 이동시간을 확인한다.

현재 Kakao REST Reference의 Routing 기능을 우선 검토한다.

## 내부 입력

```json
{
  "origin": {
    "latitude": 37.5796,
    "longitude": 126.9770
  },
  "destination": {
    "latitude": 37.5820,
    "longitude": 126.9900
  },
  "mode": "WALK"
}
```

또는:

```text
mode = PUBLIC_TRANSIT
```

## Backend 정규화 출력

```json
{
  "mode": "WALK",
  "duration_minutes": 18,
  "distance_meters": 1300,
  "available": true
}
```

## DB 반영

```text
plan_items.transport_mode_from_previous
plan_items.travel_minutes_from_previous
plan_items.travel_distance_meters_from_previous
```

## 실패 처리

경로를 구하지 못하면:

```json
{
  "available": false,
  "duration_minutes": null,
  "distance_meters": null
}
```

Validation Issue:

```text
TRAVEL_TIME_UNKNOWN
```

구현 직전 Kakao Developer Console에서 실제 권한/쿼터/응답 스키마를 다시 확인한다.

---

# 8. Kakao Mobility Directions API

## 역할

자동차 이동시간/거리를 검증한다.

`transport_mode = CAR` 또는 필요한 경우 `MIXED` 일정에서 사용한다.

## 외부 Endpoint

```http
GET https://apis-navi.kakaomobility.com/v1/directions
Authorization: KakaoAK {KAKAO_REST_API_KEY}
Content-Type: application/json
```

필수 Query:

```text
origin={longitude},{latitude}
destination={longitude},{latitude}
```

## Backend 정규화 결과

```json
{
  "mode": "CAR",
  "duration_minutes": 15,
  "distance_meters": 7200,
  "available": true
}
```

## 실패 처리

| 상황 | 내부 처리 |
|---|---|
| 경로 없음 | `TRAVEL_ROUTE_NOT_FOUND` |
| Provider 장애 | `ROUTING_PROVIDER_UNAVAILABLE` |
| 권한/쿼터 문제 | `ROUTING_PROVIDER_LIMIT` |

Kakao Mobility 상품/권한 조건은 별도 확인한다.
Provider 변경 가능성을 고려해 Adapter 뒤에 둔다.

---

# 9. 한국관광공사 TourAPI

## 역할

Kakao가 장소의 위치/좌표를 담당한다면 TourAPI는 관광 상세정보를 보강한다.

주요 사용 목적:

- 관광지
- 행사
- 숙박
- 상세 소개
- 이미지
- 관광정보

## 공통 입력

상세 Endpoint별 파라미터는 공식 Swagger를 최종 기준으로 한다.

대표 공통값:

```text
serviceKey
MobileOS
MobileApp
_type / dataType
pageNo
numOfRows
```

검색별 추가값 예:

```text
keyword
contentId
mapX
mapY
radius
areaCode
```

## Backend 정규화 DTO

```json
{
  "tour_content_id": "12345",
  "name": "경복궁",
  "address": "서울특별시 ...",
  "latitude": 37.5796,
  "longitude": 126.9770,
  "category": "관광지",
  "description": "조선 왕조의 법궁...",
  "image_url": "https://...",
  "phone": "..."
}
```

## DB

```text
places
```

필요 시:

```text
places.opening_hours
places.closed_days
places.parking_info
```

## 병합 규칙

```text
Kakao 장소
+
TourAPI 장소

→ 이름/좌표/주소 비교
→ 동일 장소면 하나의 places Row로 통합
```

불명확하면 억지로 자동 병합하지 않는다.

## 실패 처리

| 상황 | 내부 코드 |
|---|---|
| 검색 결과 없음 | `TOUR_INFO_NOT_FOUND` |
| 서비스키 오류 | `TOUR_API_AUTH_ERROR` |
| 요청량 제한 | `TOUR_API_LIMIT` |
| API 장애 | `TOUR_API_UNAVAILABLE` |

TourAPI 정보가 없다고 장소 자체가 존재하지 않는다고 판단하지 않는다.

## 환경변수

```env
TOUR_API_KEY=
TOUR_API_BASE_URL=
```

---

# 10. 기상청 단기예보 API

## 역할

여행 시점이 가까워졌을 때 날씨를 일정 검증/재구성 조건으로 사용한다.

## 중요한 제약

단기예보를 장기 여행 예측에 사용하지 않는다.

```text
여행까지 수주/수개월 남음
→ 실제 날씨 확정 금지

여행일이 단기예보 범위에 진입
→ 일정 검증에 활용
```

## Service URL

```text
https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0
```

단기예보는 해당 Service의 `getVilageFcst` 기능을 사용한다.

## 대표 Request

```text
ServiceKey={KMA_API_KEY}
pageNo=1
numOfRows=1000
dataType=JSON
base_date=YYYYMMDD
base_time=HHMM
nx={GRID_X}
ny={GRID_Y}
```

## 좌표 변환

```text
latitude / longitude
→ 기상청 nx / ny
```

변환 Utility를 Backend에 둔다.

## Backend 정규화

```json
{
  "forecast_at": "2026-10-10T15:00:00+09:00",
  "temperature_c": 22,
  "rain_probability": 70,
  "precipitation_type": "RAIN",
  "sky": "CLOUDY"
}
```

## 실패 처리

날씨를 가져오지 못해도 여행계획 전체를 실패시키지 않는다.

```text
Weather = UNKNOWN
```

그리고 Warning 생성:

```text
"날씨 정보를 확인하지 못했습니다."
```

## 환경변수

```env
KMA_API_KEY=
KMA_API_BASE_URL=https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0
```

---

# 11. Gemini API

## 역할

스마트 도슨트에서 사진을 분석해 장소 후보를 추정한다.

## 처리 흐름

```text
Flutter Image
→ FastAPI multipart/form-data
→ 이미지 Validation/Resize
→ Gemini
→ 장소 후보 0~3개
→ Kakao/TourAPI 검증
→ 사용자 후보 선택
```

## Prompt 핵심 규칙

```text
- 사진 속 장소를 확정하지 말 것
- 가능한 장소 후보 최대 3개
- 모르면 빈 배열 반환
- name / region만 구조화해 반환
- confidence 퍼센트 생성 금지
```

## 원하는 Output Schema

```json
{
  "candidates": [
    {
      "name": "경복궁",
      "region": "서울"
    },
    {
      "name": "창덕궁",
      "region": "서울"
    }
  ]
}
```

식별 불가:

```json
{
  "candidates": []
}
```

## Backend 후처리

```text
Gemini candidate
→ Kakao Local
→ 필요 시 TourAPI
→ places Upsert
→ docent_candidates
```

## 실패 처리

| 상황 | 내부 코드 |
|---|---|
| 지원하지 않는 이미지 | `INVALID_IMAGE` |
| 이미지 너무 큼 | `IMAGE_TOO_LARGE` |
| 장소 식별 불가 | 정상 + 빈 candidates |
| Gemini Timeout | `AI_PROVIDER_TIMEOUT` |
| Gemini 장애 | `AI_PROVIDER_UNAVAILABLE` |

장소 식별 불가는 Error가 아니다.

## 이미지 저장 정책

```text
요청 중 임시 처리
→ Gemini 분석
→ 폐기
```

MySQL에 원본 저장하지 않는다.

## 환경변수

```env
GEMINI_API_KEY=
GEMINI_MODEL=
```

Model은 Hard Coding하지 않는다.

---

# 12. EXAONE API

## 역할

텍스트 기반 AI 기능을 담당한다.

사용 기능:

1. 여행 조건 해석
2. YouTube 메타데이터 기반 관심사 분석
3. AI 여행 일정 초안 생성
4. 일정 재구성
5. 스마트 도슨트 설명

## Provider 구조

```text
ExaoneService Interface
        ↓
FriendliExaoneAdapter
```

향후 LG 공식 Endpoint, 사내 Endpoint 등으로 교체 가능하게 한다.

## 환경변수

```env
EXAONE_API_KEY=
EXAONE_BASE_URL=
EXAONE_MODEL=
```

Base URL과 Model 이름은 코드에 고정하지 않는다.

## 기본 Chat Request 개념

OpenAI-compatible Provider 사용 시:

```json
{
  "model": "${EXAONE_MODEL}",
  "messages": [
    {
      "role": "system",
      "content": "..."
    },
    {
      "role": "user",
      "content": "..."
    }
  ]
}
```

## 취향 분석 Input

```json
{
  "user_interests": [
    "CAFE",
    "NATURE"
  ],
  "youtube": {
    "title": "강릉 바다와 카페 여행",
    "description": "...",
    "tags": [
      "강릉",
      "카페"
    ]
  }
}
```

Output:

```json
{
  "interest_codes": [
    "CAFE",
    "NATURE"
  ],
  "destination_candidates": [
    "강릉"
  ]
}
```

`interest_codes`는 DB `interest_codes`에 존재하는 코드만 사용한다.

## 여행 일정 생성 Input

```json
{
  "trip": {
    "departure": "광주",
    "destination": "대전",
    "start_date": "2026-10-10",
    "end_date": "2026-10-12",
    "budget_krw": 300000,
    "transport_mode": "PUBLIC_TRANSIT"
  },
  "user_preferences": {
    "walking_tolerance": "LOW",
    "rest_frequency": "HIGH"
  },
  "companions": [],
  "interests": [
    "FOOD",
    "CULTURE"
  ],
  "places": []
}
```

Output:

```json
{
  "days": [
    {
      "visit_date": "2026-10-10",
      "items": [
        {
          "place_id": 101,
          "item_type": "PLACE",
          "title": "국립중앙과학관",
          "start_time": "10:00",
          "end_time": "12:00",
          "recommendation_reason": "..."
        }
      ]
    }
  ]
}
```

중요:

EXAONE에게 DB에 없는 임의 `place_id`를 생성하도록 하면 안 된다.
Backend가 전달한 후보 `place_id` 중 하나만 사용하도록 한다.

## 일정 재구성

Input:

```json
{
  "current_plan": {},
  "reason": "USER_FATIGUE",
  "instruction": "많이 걸어서 힘들어요.",
  "available_places": []
}
```

AI 결과 후 다시 Backend Validation을 수행한다.

## 스마트 도슨트 설명

Input:

```json
{
  "place": {
    "name": "경복궁",
    "description": "...",
    "category": "문화유산"
  },
  "audience": {
    "age_group": "60S"
  }
}
```

Output:

```json
{
  "description": "...",
  "highlights": [
    "...",
    "..."
  ]
}
```

검증된 `places`/TourAPI 데이터만 Grounding Context로 제공한다.

## 실패 처리

| 상황 | 내부 코드 |
|---|---|
| Timeout | `AI_PROVIDER_TIMEOUT` |
| 요청량 제한 | `AI_PROVIDER_RATE_LIMIT` |
| Provider 장애 | `AI_PROVIDER_UNAVAILABLE` |
| JSON Parsing 실패 | `AI_INVALID_RESPONSE` |
| Schema 불일치 | `AI_SCHEMA_VALIDATION_FAILED` |

AI Response는 반드시 Pydantic Schema Validation 후 사용한다.

---

# 13. 내부 표준 DTO

## Place

```json
{
  "external_provider": "KAKAO",
  "external_id": "12345",
  "name": "경복궁",
  "category": "...",
  "address": "...",
  "latitude": 37.0,
  "longitude": 126.0
}
```

## Route

```json
{
  "mode": "PUBLIC_TRANSIT",
  "duration_minutes": 35,
  "distance_meters": 12000,
  "available": true
}
```

## Weather

```json
{
  "forecast_at": "2026-10-10T15:00:00+09:00",
  "temperature_c": 22,
  "rain_probability": 70,
  "precipitation_type": "RAIN",
  "sky": "CLOUDY"
}
```

## AI Place Candidate

```json
{
  "name": "경복궁",
  "region": "서울",
  "rank_no": 1
}
```

---

# 14. 최종 환경변수 초안

```env
# MySQL
MYSQL_URL=

# JWT
JWT_SECRET_KEY=
JWT_ACCESS_EXPIRE_MINUTES=
JWT_REFRESH_EXPIRE_DAYS=

# Kakao
KAKAO_REST_API_KEY=
KAKAO_CLIENT_SECRET=

# Naver
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=

# YouTube
YOUTUBE_API_KEY=

# TourAPI
TOUR_API_KEY=
TOUR_API_BASE_URL=

# Weather
KMA_API_KEY=
KMA_API_BASE_URL=https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=

# EXAONE
EXAONE_API_KEY=
EXAONE_BASE_URL=
EXAONE_MODEL=

# Common
EXTERNAL_API_TIMEOUT_SECONDS=10
AI_API_TIMEOUT_SECONDS=60
```

`.env`는 Git Commit 금지.
Repository에는 `.env.example`만 올린다.

---

# 15. 외부 API 우선순위

## Phase 1

```text
1. Kakao Login
2. Naver Login
3. Kakao Local
4. YouTube Data API
```

목표:

```text
로그인
→ 사용자
→ 여행 생성
→ YouTube Metadata
→ 실제 장소 검색
```

## Phase 2

```text
5. TourAPI
6. EXAONE
7. Routing
8. 기상청
```

목표:

```text
실제 관광데이터
→ AI 일정
→ 이동/날씨 Validation
```

## Phase 3

```text
9. Gemini
```

목표:

```text
사진
→ 장소 후보
→ Kakao/TourAPI 검증
→ EXAONE 설명
```

---

# 16. Codex 고정 규칙

1. Router에서 외부 API를 직접 호출하지 않는다.
2. 외부 API별 Service/Adapter를 분리한다.
3. 모든 Secret/API Key는 환경변수로 관리한다.
4. Provider 원본 Response를 Flutter에 직접 반환하지 않는다.
5. Provider Response를 내부 DTO/Pydantic Schema로 변환한다.
6. 모든 외부 API 호출에 Timeout을 설정한다.
7. 400/401/403/422 오류를 무작정 Retry하지 않는다.
8. 429/5xx/Timeout은 제한적으로 Retry한다.
9. YouTube Metadata 실패 시 콘텐츠를 추측하지 않는다.
10. Kakao 외부 Place ID와 MySQL 내부 place_id를 구분한다.
11. TourAPI 정보가 없다고 장소 자체가 없다고 판단하지 않는다.
12. 단기예보 범위 밖 여행의 날씨를 확정하지 않는다.
13. Gemini 장소 분석 결과를 확정적으로 표현하지 않는다.
14. Gemini confidence 퍼센트를 임의 생성하지 않는다.
15. EXAONE Model/Base URL은 Hard Coding하지 않는다.
16. EXAONE 출력은 Pydantic Schema로 검증한다.
17. EXAONE은 전달받은 실제 place_id만 일정에 사용할 수 있다.
18. AI 결과 후 실제 정보 Validation을 수행한다.
19. 외부 API 실패 시 AI 추측값으로 대체하지 않는다.
20. `.env`는 Git Commit 금지, `.env.example`만 관리한다.

---

# 17. 공식 문서 참고

- Kakao Login REST API  
  https://developers.kakao.com/docs/ko/kakaologin/rest-api

- Naver Login Profile API  
  https://developers.naver.com/docs/login/profile/profile.md

- YouTube Data API videos.list  
  https://developers.google.com/youtube/v3/docs/videos/list

- Kakao Local REST API  
  https://developers.kakao.com/docs/ko/local/dev-guide

- Kakao REST API Reference  
  https://developers.kakao.com/docs/ko/rest-api/reference

- Kakao Mobility Directions  
  https://developers.kakaomobility.com/guide/navi-api/start

- 한국관광공사 국문 관광정보 서비스  
  https://www.data.go.kr/data/15101578/openapi.do

- 기상청 단기예보 조회서비스  
  https://www.data.go.kr/data/15084084/openapi.do

- Gemini Image Understanding  
  https://ai.google.dev/gemini-api/docs/image-understanding

- LG EXAONE 4.0 API 발표  
  https://www.lg.co.kr/media/release/29154

- K-EXAONE / FriendliAI  
  https://friendli.ai/blog/k-exaone-on-serverless

---

# 18. 3단계 완료 기준

- [x] 외부 API 목록 확정
- [x] 각 API 역할 확정
- [x] 호출 시점 확정
- [x] 필요한 Request 정의
- [x] 사용할 Response 필드/DTO 정의
- [x] DB 연결 위치 정의
- [x] 실패 처리 정의
- [x] 환경변수 이름 정의
- [x] AI Provider 역할 분리
- [x] Codex 구현 규칙 정의

실제 API Key 발급 및 Test Call은 구현 직전 또는 해당 Provider 구현 직전에 수행한다.
