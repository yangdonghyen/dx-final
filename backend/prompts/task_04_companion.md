# Codex Task 04 — Companion API

Task 01~03은 완료되었다.

현재 상태:
- FastAPI Backend skeleton 완료
- MySQL 연결 완료
- SQLAlchemy Model 22개 완료
- Alembic 001_initial_schema 적용 완료
- Alembic 002_seed_interest_codes 적용 완료
- Auth/User/JWT/Refresh/Preferences 완료
- pytest 105 passed
- GitHub backend repository 연결 완료

이번 Task에서는 Companion 기능만 구현한다.

## 1. 구현 전 문서
1. docs/01_planning/01_core_features.md
2. docs/02_api/02_api_spec.md
3. docs/03_database/03_db_schema.md
4. docs/05_architecture/05_project_structure.md
5. docs/07_implementation/07_implementation_plan.md

Source of Truth:
- API: docs/02_api/02_api_spec.md
- DB: docs/03_database/03_db_schema.md
- 구조: docs/05_architecture/05_project_structure.md

## 2. 이번 Task 범위
구현 API:
- GET /api/v1/companions
- POST /api/v1/companions
- PATCH /api/v1/companions/{companion_id}
- DELETE /api/v1/companions/{companion_id}

사용 Table:
- companions
- companion_preferences
- companion_interests
- interest_codes

구조:
Router → Service → Repository → MySQL

## 3. 범위 제한
이번 Task에서 구현 금지:
- Trip CRUD
- YouTube
- Place
- Plan
- EXAONE
- Gemini
- Kakao/Naver 실제 로그인
- TourAPI
- Weather
- Routing
- Smart Docent
- Frontend 연동

## 4. 인증/소유권
모든 Companion API는 기존 get_current_user()를 사용한다.
클라이언트가 전달하는 user_id를 신뢰하지 마라.

소유권:
companion.user_id == current_user.id

다른 사용자의 Companion 조회/수정/삭제 금지.

## 5. GET /companions
현재 로그인 사용자의 Companion 목록 조회.
기본적으로 ARCHIVED 제외.

필요 시 함께 반환:
- 기본 정보
- companion_preferences
- companion_interests

N+1 Query 주의.

## 6. POST /companions
문서에 정의된 필드만 받는다.

생성 흐름:
1. 현재 사용자 확인
2. Companion 생성
3. Companion Preference 생성
4. Interest Code 검증
5. Companion Interest 저장
6. Transaction Commit

중간 실패 시 불완전 데이터가 남지 않도록 Transaction 처리.

## 7. PATCH /companions/{companion_id}
현재 로그인 사용자가 소유한 Companion만 수정 가능.
PATCH이므로 전달되지 않은 값 유지.

수정 가능:
- Companion 기본 정보
- Preferences
- Interests

수정 금지:
- companion_id
- user_id
- 생성일
- 소유권 관련 값

interests 배열이 전달되면 문서 규칙을 따른다.
명시가 없으면 전달된 배열을 최종 interest 집합으로 처리하되 문서와 충돌하지 마라.

## 8. DELETE /companions/{companion_id}
실제 DELETE 금지.
Soft Delete:
status = ARCHIVED

금지:
- companion row 실제 삭제
- companion_preferences 삭제
- companion_interests 삭제

## 9. Companion Preferences
Companion당 1개만 유지.

문서 기준 필드:
- walking_tolerance
- rest_frequency
- avoid_stairs
- avoid_hills
- taxi_allowed

정확한 이름/Enum/default/nullable은 DB 문서 우선.

## 10. Companion Interests
interest_codes DB Master Table로 검증.

허용 Seed:
FOOD
CAFE
NATURE
CULTURE
HISTORY
SHOPPING
EXHIBITION
ACTIVITY

없는 code는 validation error.
문서 밖 code 생성 금지.

## 11. Repository
최소:
- CompanionRepository
- CompanionPreferenceRepository
- CompanionInterestRepository

기존 InterestCodeRepository 재사용 가능.

Router에서 직접 SQLAlchemy Query 금지.

## 12. Service
최소:
- CompanionService

책임:
- 소유권 검증
- 생성/수정
- Soft Delete
- Preferences
- Interests 검증/갱신
- Transaction

## 13. Schema
Companion 전용 Pydantic Schema 생성.

예:
- CompanionCreate
- CompanionUpdate
- CompanionResponse
- CompanionPreferenceInput

PATCH 필드는 optional.
request에 user_id 넣지 마라.

## 14. Error Handling
기존 공통 Exception 구조 재사용.

최소:
- UNAUTHORIZED
- COMPANION_NOT_FOUND
- FORBIDDEN 또는 기존 소유권 실패 코드
- INVALID_INTEREST_CODE
- VALIDATION_ERROR

## 15. 테스트
최소 다음을 검증한다.

인증:
- 인증 없이 GET /companions → 401
- 인증 없이 POST /companions → 401

생성:
- 정상 생성
- preference 포함
- interests 포함
- 없는 interest code 거부
- 실패 시 부분 데이터 잔존 없음

조회:
- 자기 Companion만 조회
- ARCHIVED 제외
- 다른 사용자 Companion 노출 없음

수정:
- 기본 정보 부분 수정
- preference 수정
- interests 수정
- 전달되지 않은 값 유지
- 다른 사용자 Companion 수정 불가
- 존재하지 않는 Companion 처리

삭제:
- DELETE 시 ARCHIVED
- ARCHIVED 후 목록 제외
- preference/interests 보존
- 다른 사용자 Companion 삭제 불가

제약:
- Companion당 preference 1개
- duplicate interest relationship 방지

## 16. DB 보호
기존 001/002 Migration 수정 금지.
이번 Task에서 Schema 변경은 원칙적으로 필요하지 않아야 한다.

Schema 변경 필요 시:
1. 문서와 현재 Schema 비교
2. 이유 보고
3. 별도 Migration 필요성 제시
4. 임의 적용 금지

DROP/DELETE/TRUNCATE 금지.

## 17. 기존 기능 보호
전체 테스트:
pytest --basetemp=tmp/pytest-task04

기존 105 tests 유지 + 신규 테스트 모두 통과해야 완료.

## 18. Git 규칙
현재 Git worktree다.

금지:
- git reset --hard
- git clean -fd
- 과거 commit 강제 덮어쓰기
- 사용자 변경사항 임의 삭제

Task 04 완료 후 자동 commit/push 금지.
사용자가 직접 검토 후 commit한다.

## 19. Secret 보호
출력 금지:
- .env 내용
- MYSQL_PASSWORD
- JWT_SECRET_KEY
- Provider Secret
- API Key
- Raw JWT/Refresh Token

.env 수정 금지.

## 20. 완료 보고 형식

[Task 04 작업 결과]

1. 생성한 파일
2. 수정한 파일
3. 구현 API
4. Companion 구현
   - 기본 정보
   - Preferences
   - Interests
   - Soft Delete
   - Ownership
5. DB 변경 여부
6. 테스트
   - 기존 테스트
   - 신규 테스트
   - 총 collected
   - passed
   - failed
7. 발견된 버그
8. 문서와 구현 충돌
9. Task 04 완료 여부
10. 다음 Task

## 21. 완료 조건
- GET /companions 구현
- POST /companions 구현
- PATCH /companions/{companion_id} 구현
- DELETE /companions/{companion_id} 구현
- JWT current user 기준 동작
- 다른 사용자 Companion 접근 차단
- Preferences 1:1 유지
- Interest Code DB 검증
- DELETE = ARCHIVED
- preference/interests 실제 삭제 없음
- Router에서 직접 Query 없음
- Service/Repository 분리
- Transaction 일관성
- 기존 001/002 migration 수정 없음
- 전체 pytest 통과
- 실제 외부 API 호출 없음
- Task 05 이상 범위 구현 없음

지금은 Task 04만 진행해라.
