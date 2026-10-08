# 06. Mock Data — Draft Final

## 1. 목적

외부 API와 AI가 아직 연결되지 않은 상태에서도 Backend API, DB, Flutter 연동을 개발할 수 있도록
일관된 Mock 데이터 세트를 제공한다.

이번 Mock의 기준 시나리오는 다음과 같다.

```text
사용자: 60대 테스트 사용자
동행자: 30대 자녀
여행: 광주 → 서울 / 1박 2일
관심사: CULTURE / FOOD / CAFE
조건: 걷기 LOW / 휴식 HIGH / 계단·언덕 회피
콘텐츠: 서울 궁궐·카페 YouTube Mock
일정: 경복궁 → 휴식 → 미술관 → 카페
검증: 둘째 날 비 예보 + 일부 이동시간 UNKNOWN
스마트 도슨트: 경복궁/창덕궁 후보
```

모든 데이터는 테스트 전용이며 실제 운영정보를 의미하지 않는다.

---

# 2. 파일 구성

```text
mock_data/
├── users.json
├── companions.json
├── trips.json
├── youtube.json
├── places.json
├── plans.json
└── docent.json
```

---

# 3. ID 연결 규칙

```text
user_id       = 1
companion_id  = 3
trip_id       = 15
source_id     = 21
plan_id       = 30

places:
101 경복궁
102 국립현대미술관 서울
103 서울공예박물관
104 안국 테스트 카페
105 북촌한옥마을
106 창덕궁

plan_items:
1001~1006

docent:
analysis_id 500 / 501
```

Mock 파일 간 ID를 임의로 바꾸지 않는다.

---

# 4. users.json

테스트 대상:

```text
GET /users/me
PATCH /users/me
PATCH /users/me/preferences
```

포함 데이터:

- 사용자 기본 프로필
- 기본 여행 성향
- 관심사
- Social Auth Fixture

---

# 5. companions.json

테스트 대상:

```text
POST /companions
GET /companions
PATCH /companions/{id}
DELETE /companions/{id}
```

ACTIVE 동행자와 ARCHIVED 예시를 포함한다.

---

# 6. trips.json

테스트 대상:

```text
POST /trips
GET /trips
GET /trips/{id}
PATCH /trips/{id}
DELETE /trips/{id}
```

포함:

- 여행 기본정보
- 여행별 Preference
- Companion Snapshot
- Trip Interest
- create Request / Response

---

# 7. youtube.json

실제 YouTube API 연결 전 아래 흐름을 Mock한다.

```text
YouTube URL
→ Metadata
→ AI Preference 분석
```

포함:

- `trip_sources` 대응 Source
- 정규화된 YouTube Provider Response
- 취향 분석 Response
- URL 오류 / 영상 접근 불가 실패 예시

AI 관심사는 반드시 `interest_codes`에 존재하는 코드만 사용한다.

---

# 8. places.json

Kakao / TourAPI / Routing / Weather의 정규화 결과를 하나의 Fixture에 모았다.

포함:

- Place 6개
- `/places/search` Response 예시
- Route Mock
- Weather Mock

주의:

`안국 테스트 카페`는 실제 매장이 아닌 Mock 전용 장소다.

`kakao_place_id`, `tour_content_id`의 `mock-*` 값도 실제 외부 ID가 아니다.

---

# 9. plans.json

테스트 대상:

```text
POST /trips/{trip_id}/plans/generate
GET /plans/{plan_id}
POST /plans/{plan_id}/edit
POST /plans/{plan_id}/regenerate
POST /plans/{plan_id}/confirm
```

Happy Path와 Warning을 함께 넣었다.

검증 Issue:

```text
WEATHER_WARNING
TRAVEL_TIME_UNKNOWN
```

이 때문에 일부 Item의 `validation_status = WARNING`이다.

직접 수정 예:

```text
DELETE_PLACE
REPLACE_PLACE
ADD_REST
REORDER
```

재구성 예:

```text
USER_FATIGUE
WEATHER_CHANGE
```

---

# 10. docent.json

테스트 대상:

```text
POST /docent/identify
POST /docent/explain
```

포함:

- 장소 후보가 있는 성공 케이스
- 장소를 특정할 수 없는 정상 케이스
- Explain Request/Response
- Gemini 내부 정규화 Response

`identify_no_match`는 Error가 아니라 정상 응답이다.

---

# 11. Mock 사용 원칙

## 외부 API Adapter 개발 전

Service에서 Fixture를 읽어 반환할 수 있다.

예:

```text
USE_MOCK_EXTERNAL_APIS=true
```

개발 환경에서만 사용하는 옵션으로 둔다.

## 실제 API 연결 후

같은 내부 DTO를 반환해야 한다.

```text
Mock Provider
      ↓
Internal DTO

Real Provider
      ↓
Internal DTO
```

Business Service는 Mock인지 실제 API인지 몰라도 동작해야 한다.

---

# 12. 권장 환경변수

`.env.example`에 개발용으로 추가 가능:

```env
USE_MOCK_EXTERNAL_APIS=true
MOCK_DATA_DIR=mock_data
```

Production에서는 반드시:

```env
USE_MOCK_EXTERNAL_APIS=false
```

---

# 13. Codex 규칙

1. Mock 데이터를 운영 DB의 사실 데이터로 간주하지 않는다.
2. Mock 전용 외부 ID(`mock-*`)를 실제 Provider 요청에 사용하지 않는다.
3. Mock Adapter와 Real Adapter가 동일한 내부 DTO를 반환하도록 한다.
4. 테스트에서 고정 ID가 필요한 경우 이 문서의 ID를 사용한다.
5. `interest_codes` 밖의 Interest를 추가하지 않는다.
6. Plan Item이 참조하는 `place_id`는 `places.json`에 존재해야 한다.
7. Smart Docent의 `place_id`도 `places.json`과 연결되어야 한다.
8. Warning Mock을 제거하지 않는다. Validation 테스트에 사용한다.
9. no-match Smart Docent 응답을 실패로 처리하지 않는다.
10. 실제 외부 API 연동이 완료되더라도 Mock Fixture는 테스트용으로 유지한다.

---

# 14. 5단계 완료 기준

- [x] User Mock
- [x] Companion Mock
- [x] Trip Mock
- [x] YouTube Mock
- [x] Place Mock
- [x] Routing Mock
- [x] Weather Mock
- [x] Plan Mock
- [x] Validation Warning Mock
- [x] Smart Docent Mock
- [x] 공통 ID 연결 확인
- [x] Happy Path 준비
- [x] 실패/경고 케이스 준비

다음 단계는 `6. 구현 우선순위와 완료조건 정의`다.
