# Codex Task 05 — Trip CRUD & Snapshot

Task 01~04는 완료되었다.

현재 상태:
- FastAPI Backend skeleton 완료
- MySQL 연결 완료
- SQLAlchemy Model 22개 완료
- Alembic 001_initial_schema 적용 완료
- Alembic 002_seed_interest_codes 적용 완료
- Auth/User/JWT/Refresh/Preferences 완료
- Companion API 완료
- pytest 117 passed
- GitHub backend repository 연결 및 Task 04 push 완료

이번 Task에서는 **Trip CRUD와 여행 생성 시점 Snapshot 처리만 구현**한다.

---

# 1. 구현 전 반드시 읽을 문서

다음 문서를 다시 읽고 작업해라.

1. `docs/01_planning/01_core_features.md`
2. `docs/02_api/02_api_spec.md`
3. `docs/03_database/03_db_schema.md`
4. `docs/05_architecture/05_project_structure.md`
5. `docs/07_implementation/07_implementation_plan.md`

이번 Task의 Source of Truth:
- API: `docs/02_api/02_api_spec.md`
- DB: `docs/03_database/03_db_schema.md`
- 구조: `docs/05_architecture/05_project_structure.md`

문서와 이 프롬프트가 충돌하면 문서를 우선하고 충돌 내용을 결과에 보고해라.

---

# 2. 이번 Task 범위

구현 API:

- `POST /api/v1/trips`
- `GET /api/v1/trips`
- `GET /api/v1/trips/{trip_id}`
- `PATCH /api/v1/trips/{trip_id}`
- `DELETE /api/v1/trips/{trip_id}`

주요 Table:

- `trips`
- `trip_preferences`
- `trip_companions`
- `trip_interests`

참조 Table:

- `users`
- `user_preferences`
- `user_interests`
- `companions`
- `companion_preferences`
- `companion_interests`
- `interest_codes`

구조:

```text
Router
→ Service
→ Repository
→ MySQL
```

---

# 3. 이번 Task에서 구현하지 말 것

아직 다음 기능은 구현하지 마라.

- YouTube source 등록
- 취향 AI 분석
- Place 검색
- Plan 생성
- Plan 수정/재생성
- EXAONE
- Gemini
- Kakao/Naver 실제 로그인
- Kakao Local
- TourAPI
- Weather
- Routing
- Smart Docent
- Frontend 연동

이번 Task는 **Trip CRUD + Snapshot**에만 집중한다.

---

# 4. 인증 / 소유권

모든 Trip API는 기존 `get_current_user()`를 사용한다.

클라이언트가 body/query/path로 넘기는 임의의 `user_id`를 신뢰하지 마라.

Trip 소유권은 반드시 현재 로그인 사용자 기준으로 검증한다.

다른 사용자의 Trip:
- 조회 금지
- 수정 금지
- 삭제 금지

---

# 5. POST /trips

여행 생성 시 API 문서에서 허용하는 Trip 입력값만 받는다.

예시 개념:
- title
- destination
- start_date
- end_date
- budget_krw
- transport / travel style 관련 문서 정의 필드
- companion_ids
- trip preference override
- interest 관련 입력

정확한 필드명, nullable, Enum, 기본값은 API/DB 문서를 따른다.

---

# 6. 여행 생성 시 Snapshot 원칙

이번 Task의 핵심이다.

여행 생성 시점의 사용자/동행자 조건을 저장하여,
나중에 원본 Profile 또는 Companion이 수정되어도
이미 만들어진 여행의 조건이 자동으로 바뀌지 않도록 한다.

## 6-1. trip_preferences

기본적으로 현재 사용자의 `user_preferences`를 여행 생성 시점에 Snapshot한다.

문서/API에서 Trip 생성 요청으로 override 가능한 필드가 있다면:

```text
user default
→ request override
→ trip_preferences snapshot
```

순서로 적용한다.

`trip_preferences`는 Trip당 1개만 유지한다.

## 6-2. trip_companions

선택된 Companion은 반드시 현재 사용자가 소유한 활성 Companion이어야 한다.

여행 생성 시 원본 Companion 정보를 Snapshot한다.

특히 기존 DB 설계의 Snapshot Column과
`interests_snapshot` JSON을 사용한다.

원본 `companions`, `companion_preferences`, `companion_interests`가 이후 변경되어도
기존 `trip_companions` Snapshot을 자동 갱신하지 마라.

`companion_id`는 원본 참조 용도이며,
Snapshot 값이 여행 당시 조건의 기준이다.

## 6-3. trip_interests

여행 관심사는 DB 문서의 `source_type`을 정확히 사용한다.

허용 값:

```text
PROFILE
CONTENT_AI
USER
```

이번 Task에서는 AI 분석을 하지 않으므로
`CONTENT_AI`를 임의 생성하지 마라.

Profile에서 가져온 관심사는 필요 시 `PROFILE`,
사용자가 Trip 생성/수정에서 명시한 관심사는 `USER`
로 처리하되, 정확한 우선순위/중복 규칙은 API/DB 문서를 따른다.

문서에 없는 임의 interest code 생성 금지.

---

# 7. Companion 검증

Trip 생성/수정에서 Companion ID를 받는 경우:

1. 해당 Companion 존재 여부
2. 현재 사용자 소유 여부
3. ARCHIVED 여부

를 검증한다.

다른 사용자 Companion을 Trip에 추가할 수 없어야 한다.

ARCHIVED Companion을 새 Trip에 추가하지 마라.

---

# 8. GET /trips

현재 로그인 사용자의 Trip 목록만 반환한다.

기본적으로 ARCHIVED Trip은 목록에서 제외한다.

정렬 기준은 API 문서를 따른다.
문서가 없다면 임의로 복잡한 pagination/sorting을 추가하지 마라.

목록 응답에 포함할 필드는 API 문서 기준으로 제한한다.

---

# 9. GET /trips/{trip_id}

현재 사용자 소유 Trip만 상세 조회한다.

필요 시 문서에 따라 함께 반환:
- trip 기본 정보
- trip_preferences
- trip_companions snapshot
- trip_interests

다른 사용자 Trip에 대해 소유권 정보가 노출되지 않도록
기존 Error Handling 규칙을 따른다.

---

# 10. PATCH /trips/{trip_id}

PATCH이므로 전달되지 않은 값은 유지한다.

수정 가능 필드는 API 문서를 따른다.

중요:
- `user_id`, `trip_id`, 생성일 등 내부 식별 필드 수정 금지
- 날짜 변경 시 DB CHECK 및 API validation 유지
- budget 등 숫자 제약 유지
- destination nullable 규칙 유지

## Snapshot 수정 주의

Trip의 동행자/선호/관심사를 명시적으로 수정하는 API 규칙이 문서에 있다면
그 경우에만 해당 Snapshot을 갱신한다.

사용자 Profile이나 Companion 원본이 바뀌었다는 이유만으로
Trip Snapshot을 자동 동기화하지 마라.

Companion 목록을 수정할 때 새로 추가된 Companion은
그 시점의 Snapshot을 생성한다.

기존에 남아 있는 Companion Snapshot은
문서에서 refresh를 요구하지 않는 한 임의 재생성하지 마라.

---

# 11. DELETE /trips/{trip_id}

실제 DELETE SQL로 Trip을 삭제하지 마라.

Soft Delete:

```text
status = ARCHIVED
```

정확한 상태 Enum은 DB 문서를 따른다.

연관 데이터:
- trip_preferences
- trip_companions
- trip_interests

를 실제 삭제하지 마라.

이미 ARCHIVED 상태인 Trip 처리 방식은 API 문서를 따른다.

---

# 12. Repository

최소 다음 책임을 분리한다.

```text
TripRepository
TripPreferenceRepository
TripCompanionRepository
TripInterestRepository
```

기존 Repository 재사용 가능:
- UserPreferenceRepository
- UserInterestRepository
- CompanionRepository
- InterestCodeRepository

Router에서 직접 SQLAlchemy Query를 작성하지 마라.

---

# 13. Service

최소:

```text
TripService
```

책임:
- 현재 사용자 소유권 검증
- Trip 생성/조회/수정/Soft Delete
- User preference snapshot
- Companion snapshot
- Trip interest 생성/검증
- Transaction 관리

---

# 14. Schema

Trip 전용 Pydantic Schema를 만든다.

예:
- TripCreate
- TripUpdate
- TripListItemResponse
- TripDetailResponse
- TripPreferenceInput/Response
- TripCompanionResponse

정확한 이름은 기존 프로젝트 스타일에 맞춘다.

규칙:
- Request/Response 분리
- PATCH 필드 optional
- user_id request 금지
- 내부 상태/식별 필드 무단 수정 금지

---

# 15. Validation

문서와 DB 제약을 모두 반영한다.

최소 확인:
- start_date / end_date 관계
- budget_krw 제약
- Enum 값
- interest code 존재
- companion ownership
- companion status
- trip ownership

Validation 실패 시 부분 데이터가 남지 않아야 한다.

---

# 16. Transaction

Trip 생성은 최소 다음을 하나의 논리적 Transaction으로 처리한다.

```text
trips
+
trip_preferences
+
trip_companions
+
trip_interests
```

중간 실패 시 불완전 Trip이 남지 않도록 Rollback한다.

Trip 수정에서 연관 Snapshot이 함께 변경될 때도
부분 성공이 남지 않도록 처리한다.

---

# 17. 테스트

최소 다음 테스트를 추가한다.

## 인증
- 인증 없이 GET /trips → 401
- 인증 없이 POST /trips → 401

## 생성
- 정상 Trip 생성
- user_preferences snapshot 생성
- companion snapshot 생성
- companion interests_snapshot 저장
- user profile interest → trip_interests 반영
- 사용자 지정 interest 처리
- 없는 interest code 거부
- 다른 사용자 Companion 거부
- ARCHIVED Companion 거부
- 생성 중 실패 시 부분 데이터 없음

## Snapshot 독립성
- Trip 생성 후 user_preferences 원본 변경
  → 기존 trip_preferences 값은 유지
- Trip 생성 후 companion 원본 정보 변경
  → 기존 trip_companions snapshot 값은 유지
- Companion interest 변경
  → 기존 interests_snapshot 값은 유지

## 조회
- 현재 사용자 Trip만 목록 반환
- ARCHIVED Trip 목록 제외
- 상세 조회 정상
- 다른 사용자 Trip 노출 금지

## 수정
- 기본 필드 partial update
- 날짜 validation
- preference 명시 수정
- companion 목록 변경 시 신규 Snapshot
- 다른 사용자 Trip 수정 금지

## 삭제
- 실제 row 삭제가 아니라 ARCHIVED
- ARCHIVED 후 목록 제외
- trip_preferences / trip_companions / trip_interests 보존
- 다른 사용자 Trip 삭제 금지

## DB 제약
- trip_preferences는 Trip당 1개
- trip_interests duplicate 방지
- trip_companions unique 규칙 유지

---

# 18. DB 보호

기존:
- `001_initial_schema`
- `002_seed_interest_codes`

Migration을 수정하지 마라.

이번 Task에서 Schema 변경은 원칙적으로 필요하지 않아야 한다.

Schema 변경이 필요하다고 판단되면:
1. 문서와 현재 Schema 비교
2. 이유 보고
3. 별도 Migration 필요성을 제시
4. 사용자 확인 없이 임의 적용하지 마라

DROP / TRUNCATE / 기존 데이터 일괄 DELETE 금지.

---

# 19. 기존 기능 보호

Task 01~04 기능이 깨지면 Task 05 완료가 아니다.

현재 기준:

```text
117 passed
```

전체 테스트:

```bash
pytest --basetemp=tmp/pytest-task05
```

기존 117개 + 신규 Task 05 테스트가 모두 통과해야 한다.

---

# 20. Git 규칙

현재 Git worktree이며 Task 04까지 remote에 push되어 있다.

금지:
- `git reset --hard`
- `git clean -fd`
- 과거 commit 강제 변경
- 사용자 작업 임의 삭제

Task 05 완료 후 자동 commit/push하지 마라.
사용자가 결과를 확인한 후 직접 commit한다.

---

# 21. Secret 보호

절대 출력 금지:
- `.env`
- MYSQL_PASSWORD
- JWT_SECRET_KEY
- Provider Secret
- API Key
- Raw JWT / Refresh Token

`.env` 수정 금지.

---

# 22. 완료 보고 형식

```text
[Task 05 작업 결과]

1. 생성한 파일
- ...

2. 수정한 파일
- ...

3. 구현 API
- POST /trips
- GET /trips
- GET /trips/{trip_id}
- PATCH /trips/{trip_id}
- DELETE /trips/{trip_id}

4. Trip 구현
- 기본 CRUD:
- User Preference Snapshot:
- Companion Snapshot:
- Interests:
- Soft Delete:
- Ownership:

5. DB 변경 여부
- Migration:
- 이유:

6. 테스트
- 기존 테스트:
- 신규 테스트:
- 총 collected:
- passed:
- failed:

7. Snapshot 독립성 검증
- User Preference:
- Companion:
- Companion Interests:

8. 발견된 버그
- ...

9. 문서와 구현 충돌
- ...

10. Task 05 완료 여부
- ...

11. 다음 Task
- Task 06 Mock External Provider
```

---

# 23. 완료 조건

- [ ] POST /trips 구현
- [ ] GET /trips 구현
- [ ] GET /trips/{trip_id} 구현
- [ ] PATCH /trips/{trip_id} 구현
- [ ] DELETE /trips/{trip_id} 구현
- [ ] JWT current user 기준 동작
- [ ] 다른 사용자 Trip 접근 차단
- [ ] trip_preferences Snapshot
- [ ] trip_companions Snapshot
- [ ] interests_snapshot JSON 유지
- [ ] trip_interests source_type 규칙 유지
- [ ] 원본 User/Companion 변경 후 기존 Snapshot 불변 검증
- [ ] DELETE = ARCHIVED Soft Delete
- [ ] 연관 Snapshot 실제 삭제 없음
- [ ] Router / Service / Repository 분리
- [ ] Transaction 일관성
- [ ] 기존 001/002 migration 수정 없음
- [ ] 전체 pytest 통과
- [ ] Task 06 이상 범위 구현 없음
- [ ] 자동 Git commit/push 없음

**지금은 Task 05만 진행해라.**
