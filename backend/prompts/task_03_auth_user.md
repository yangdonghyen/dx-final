# Codex Task 03 — Auth & User

Task 01과 Task 02는 완료되었다.

현재 상태:
- FastAPI Backend skeleton 완료
- 실제 MySQL 연결 완료
- SQLAlchemy Model 22개 완료
- Alembic initial migration 적용 완료
- 서비스 테이블 22개 + alembic_version 존재
- pytest 90 passed

이번 Task에서는 **Auth + User 기능만 구현**한다.

## 구현 전 문서
1. docs/01_planning/01_core_features.md
2. docs/02_api/02_api_spec.md
3. docs/03_database/03_db_schema.md
4. docs/04_external_api/04_external_apis.md
5. docs/05_architecture/05_project_structure.md
6. docs/07_implementation/07_implementation_plan.md

Source of Truth:
- API: docs/02_api/02_api_spec.md
- DB: docs/03_database/03_db_schema.md
- 구조: docs/05_architecture/05_project_structure.md

## 이번 Task 범위

AUTH
- POST /api/v1/auth/social-login
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout

USER
- GET /api/v1/users/me
- PATCH /api/v1/users/me
- PATCH /api/v1/users/me/preferences

구조:
Router → Service → Repository → MySQL

소셜 Provider 검증:
AuthService → SocialAuthProvider interface/adapter

## 중요 범위 제한

이번 Task에서 실제 Kakao/Naver 외부 API 연동은 하지 마라.
실제 Provider HTTP 연동은 후속 Task에서 진행한다.

이번 Task:
- Provider adapter interface
- Test/Fake provider
- Auth service flow
- JWT
- Refresh Token
- User/Profile API

구현 금지:
- 실제 Kakao/Naver HTTP 호출
- Companion
- Trip
- YouTube
- Kakao Local
- TourAPI
- Weather
- EXAONE
- Gemini
- Plan
- Smart Docent

## Social Login 입력 원칙

요청 개념:
{
  "provider": "KAKAO",
  "access_token": "provider-access-token"
}

지원 provider:
KAKAO, NAVER

클라이언트가 user_id/provider_user_id/email/nickname을 신뢰 가능한 식별자로 보내도록 만들지 마라.
이 값은 Provider 검증 결과에서 얻는다.

## Social Login 처리 흐름

1. provider + provider access_token 수신
2. provider adapter가 access_token 검증
3. provider_user_id 획득
4. user_auths에서 (provider, provider_user_id) 조회
5-A. 기존 사용자이면 해당 User 사용
5-B. 최초 로그인이라면 users + user_auths 생성
6. Backend Access JWT 발급
7. Backend Refresh Token 발급
8. Raw Refresh Token은 응답으로만 전달
9. DB에는 Refresh Token hash만 저장
10. 사용자 정보 + Backend Token 반환

원칙:
- Provider Access Token 장기 저장 금지
- Client가 전달한 사용자 식별자 신뢰 금지
- 이메일만으로 서로 다른 Provider 계정을 자동 연결하지 마라
- (provider, provider_user_id)를 식별 기준으로 사용

## 최초 로그인

별도 회원가입 API를 만들지 마라.
최초 Social Login 성공 시 자동 회원 생성.

users.nickname은 NULL 가능.
Social Login 직후 nickname=NULL, profile_completed=false 상태 가능.

## JWT

.env의 기존 설정을 사용:
- JWT_SECRET_KEY
- JWT_ACCESS_EXPIRE_MINUTES
- JWT_REFRESH_EXPIRE_DAYS

Secret 출력 금지.

Access Token payload 최소:
- sub = user_id
- type = access

Refresh Token은 access token과 구분 가능해야 함.

검증:
- signature
- expiration
- token type

## Refresh Token 저장

refresh_tokens 테이블 사용.
- Raw Token DB 저장 금지
- token_hash UNIQUE
- user_id 연결
- expires_at 저장
- 폐기/만료 토큰 재사용 금지

## POST /auth/refresh

1. Refresh Token 수신
2. JWT 형식/서명/만료/type 검증
3. Raw Token hash
4. DB에서 조회
5. 만료/폐기 확인
6. User 상태 확인
7. 새 Access Token 발급

문서가 rotation을 요구하면 문서를 따른다.
명시가 없으면 임의 복잡한 정책을 추가하지 마라.

## POST /auth/logout

현재 Refresh Token을 폐기.
Access JWT blacklist는 이번 Task에서 만들지 마라.

## 인증 Dependency

get_current_user() 구현.

Authorization: Bearer <access-token>
→ JWT 검증
→ sub user_id
→ User 조회
→ User 상태 확인
→ current user 반환

401/403 구분은 기존 API 문서와 예외 구조를 따른다.

## GET /users/me

JWT의 user_id 기준으로 현재 사용자 조회.
Body/Query/Header의 임의 user_id를 사용하지 마라.

## PATCH /users/me

부분 수정.
- 전달되지 않은 값 유지
- nickname duplicate 허용
- nickname UNIQUE 검증 금지
- age_group은 문서 Enum
- status/user_id/provider 정보 수정 금지

## PATCH /users/me/preferences

사용자 선호:
- walking tolerance
- rest frequency
- avoid stairs
- avoid hills
- taxi allowed
- interests

정확한 필드명/타입은 문서를 따른다.

user_preferences는 User당 1개.
필요 시 upsert.

## Interests

Master codes:
FOOD
CAFE
NATURE
CULTURE
HISTORY
SHOPPING
EXHIBITION
ACTIVITY

문서 밖 코드 생성 금지.

DB에 Seed가 없다면 현재 Task 동작에 필요한 최소 Seed 방법을 먼저 검토.
기존 001 migration은 수정하지 마라.

## Repository

최소:
- UserRepository
- UserAuthRepository
- RefreshTokenRepository
- UserPreferenceRepository
- UserInterestRepository
- InterestCodeRepository

Router에서 직접 SQLAlchemy query 작성 금지.

## Service

최소:
- AuthService
- UserService

## Provider Adapter

실제 Provider 호출 금지.
추상 인터페이스 + Fake/Test provider 구현.

반환 개념:
- provider
- provider_user_id
- email optional
- nickname optional

실제 Kakao/Naver adapter는 후속 Task에서 교체 가능해야 함.

## Error Handling

기존 Task 01 공통 Exception 구조 재사용.

최소:
- INVALID_TOKEN
- TOKEN_EXPIRED
- UNSUPPORTED_PROVIDER
- INVALID_PROVIDER_TOKEN
- UNAUTHORIZED
- USER_NOT_FOUND
- USER_INACTIVE
- INVALID_INTEREST_CODE
- VALIDATION_ERROR

정확한 응답 포맷은 API 문서 우선.

## Transaction

최초 로그인:
users 생성 + user_auths 생성 + refresh token 저장

중간 오류 시 불완전 데이터가 남지 않도록 transaction 고려.

## 테스트

Social Login:
- 신규/기존 KAKAO
- 신규/기존 NAVER
- unsupported provider
- provider token 검증 실패
- 재로그인 user 중복 생성 방지
- 동일 이메일 다른 provider 자동 연결 금지

JWT:
- 정상 access
- 만료
- 잘못된 signature
- refresh를 access API에 사용
- 잘못된 token type

Refresh:
- 정상
- 만료
- 폐기
- DB에 없는 token

Logout:
- 정상
- logout 후 refresh 재사용 불가

User:
- GET /users/me
- 인증 없이 401
- PATCH /users/me
- partial update
- nickname duplicate 허용

Preferences:
- 생성
- 수정
- interest validation
- 없는 interest code 거부
- user당 preferences 1개 유지

## DB 규칙

기존 Table 구조를 임의 변경하지 마라.
Schema 변경이 정말 필요하면:
- 문서/현재 Schema 비교
- 별도 Alembic revision
- 기존 001_initial_schema 수정 금지

## 기존 테스트 보호

전체 테스트:
pytest --basetemp=tmp/pytest

이전 temp ACL 문제가 있었으므로 repository 내부 tmp 사용 가능.

Task 01/02 테스트가 깨지면 완료가 아니다.

## Secret 보호

출력 금지:
- MYSQL_PASSWORD
- JWT_SECRET_KEY
- Provider Client Secret
- API Key
- Raw Refresh Token 로그

.env 수정 금지.

## 완료 보고 형식

[Task 03 작업 결과]

1. 생성한 파일
2. 수정한 파일
3. 구현 API
4. Auth 구현
5. User 구현
6. DB 변경 여부
7. 테스트 결과
8. 발견된 문제
9. 문서와 구현 충돌
10. 실제 외부 API 연동 여부
11. Task 03 완료 여부
12. 다음 Task

## 완료 조건

- Social Login API 구현
- Provider Adapter 분리
- 실제 Kakao/Naver API 호출 없음
- 최초 로그인 자동 User 생성
- 기존 User 중복 생성 방지
- 이메일만으로 Provider 자동 연결하지 않음
- Backend JWT 발급
- Refresh Token hash 저장
- Refresh API 구현
- Logout 구현
- get_current_user 구현
- GET /users/me 구현
- PATCH /users/me 구현
- PATCH /users/me/preferences 구현
- Interest Code 검증
- 기존 001 migration 수정 없음
- 전체 pytest 통과
- Secret 로그 없음
- Task 04 이상 범위 구현 없음

지금은 Task 03만 진행해라.
