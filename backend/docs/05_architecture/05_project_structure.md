# 05. Project Structure — Draft Final (Separate Frontend / Existing MySQL)

## 1. 목적

이 문서는 AI 여행 서비스 Backend의 FastAPI 프로젝트 폴더 구조와
각 디렉터리의 책임을 정의한다.

Codex는 이 구조를 기준으로 구현하며,
특별한 이유 없이 새로운 계층이나 중복 폴더를 임의로 추가하지 않는다.

---

# 2. 기술 스택

```text
Backend      FastAPI / Python
Database     MySQL 8.x
ORM          SQLAlchemy
Migration    Alembic
Validation   Pydantic
HTTP Client  httpx
Auth         JWT
Frontend     Flutter
```

외부 서비스:

```text
Kakao Login
Naver Login
YouTube Data API
Kakao Local / Routing
Kakao Mobility
TourAPI
기상청 API
Gemini
EXAONE
```

---

# 3. 전체 프로젝트 구조

Frontend와 Backend는 **별도 GitHub Repository**로 관리한다.

```text
travel-ai-frontend/
└── Flutter 프로젝트

travel-ai-backend/
│
├── app/
│   │
│   ├── main.py
│   │
│   ├── dependencies.py
│   │
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── router.py
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── companions.py
│   │       ├── trips.py
│   │       ├── places.py
│   │       ├── plans.py
│   │       └── docent.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   │
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── seed.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── companion.py
│   │   ├── trip.py
│   │   ├── place.py
│   │   ├── plan.py
│   │   └── docent.py
│   │
│   ├── schemas/
│   │   ├── common.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── companion.py
│   │   ├── trip.py
│   │   ├── place.py
│   │   ├── plan.py
│   │   └── docent.py
│   │
│   ├── repositories/
│   │   ├── user_repository.py
│   │   ├── auth_repository.py
│   │   ├── companion_repository.py
│   │   ├── trip_repository.py
│   │   ├── place_repository.py
│   │   ├── plan_repository.py
│   │   └── docent_repository.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── companion_service.py
│   │   ├── trip_service.py
│   │   ├── preference_service.py
│   │   ├── place_service.py
│   │   ├── plan_generation_service.py
│   │   ├── plan_validation_service.py
│   │   ├── plan_revision_service.py
│   │   ├── docent_service.py
│   │   │
│   │   └── external/
│   │       ├── auth/
│   │       │   ├── kakao_auth_service.py
│   │       │   └── naver_auth_service.py
│   │       │
│   │       ├── content/
│   │       │   └── youtube_service.py
│   │       │
│   │       ├── place/
│   │       │   ├── kakao_local_service.py
│   │       │   ├── kakao_routing_service.py
│   │       │   ├── kakao_mobility_service.py
│   │       │   └── tour_api_service.py
│   │       │
│   │       ├── weather/
│   │       │   └── kma_weather_service.py
│   │       │
│   │       └── ai/
│   │           ├── gemini_service.py
│   │           └── exaone_service.py
│   │
│   ├── validators/
│   │   ├── trip_validator.py
│   │   └── plan_validator.py
│   │
│   └── utils/
│       ├── youtube.py
│       ├── kma_grid.py
│       ├── image.py
│       └── datetime.py
│
├── alembic/
│   └── versions/
│
├── tests/
│   │
│   ├── unit/
│   │   ├── services/
│   │   ├── validators/
│   │   └── utils/
│   │
│   ├── integration/
│   │   ├── api/
│   │   ├── db/
│   │   └── external/
│   │
│   └── fixtures/
│
├── mock_data/
│   ├── users.json
│   ├── companions.json
│   ├── trips.json
│   ├── youtube.json
│   ├── places.json
│   ├── plans.json
│   └── docent.json
│
├── scripts/
│   └── seed_interest_codes.py
│
├── docs/
│   ├── 01_core_features.md
│   ├── 02_api_spec_draft_final.md
│   ├── 03_db_schema_draft_final.md
│   ├── 04_external_apis.md
│   └── 05_project_structure.md
│
├── .env
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```

---

# 4. 요청 처리 기본 흐름

기본적인 Backend 호출 흐름은 다음과 같다.

```text
Flutter
↓
API Router
↓
Service
↓
Repository
↓
MySQL
```

외부 API가 필요한 경우:

```text
Flutter
↓
API Router
↓
Business Service
↓
External Service / Adapter
↓
외부 API
↓
Business Service
↓
Repository
↓
MySQL
↓
Flutter Response
```

AI 여행 일정 생성 예:

```text
POST /api/v1/trips/{trip_id}/plans/generate

plans.py
↓
plan_generation_service.py
↓
trip_repository.py
place_repository.py
↓
exaone_service.py
↓
plan_validation_service.py
↓
Kakao / TourAPI / Weather / Routing
↓
plan_repository.py
↓
MySQL
↓
Response
```

---

# 5. Frontend / Backend Repository 분리

Frontend는 별도 Repository에서 개발한다.

```text
travel-ai-frontend/
└── Flutter
```

Backend Repository에는 Flutter 코드를 포함하지 않는다.

```text
travel-ai-backend/
├── app/
├── alembic/
├── tests/
├── mock_data/
├── scripts/
├── docs/
└── ...
```

Frontend와 Backend 사이의 계약은 다음 문서를 기준으로 한다.

```text
docs/02_api_spec_draft_final.md
```

Codex는 Frontend 구현 상태를 이유로 Backend Endpoint를 임의 변경하지 않는다.

---

# 6. CORS

Frontend와 Backend가 별도 Repository / 별도 Origin으로 동작할 수 있으므로
FastAPI에서 CORS 설정을 환경변수 기반으로 관리한다.

`.env.example` 예:

```env
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

Backend에서는 이 값을 List로 파싱해 `CORSMiddleware`에 전달한다.

운영환경에서는 다음처럼 전체 허용하지 않는다.

```python
allow_origins=["*"]
```

허용할 Frontend Origin만 명시한다.

---

# 7. app/main.py

FastAPI Application의 시작점.

책임:

```text
FastAPI App 생성
Router 등록
Exception Handler 등록
CORS 설정
Startup 설정
```

예상 구조:

```python
app = FastAPI()

app.include_router(
    api_router,
    prefix="/api/v1"
)
```

Business Logic을 `main.py`에 넣지 않는다.

---

# 8. api/v1

Flutter가 직접 호출하는 HTTP Endpoint를 정의한다.

```text
auth.py
users.py
companions.py
trips.py
places.py
plans.py
docent.py
```

Router 책임:

```text
Request 받기
Pydantic Validation
현재 로그인 사용자 확인
Service 호출
Response 반환
```

Router가 하면 안 되는 것:

```text
SQL 직접 실행
Gemini 직접 호출
EXAONE 직접 호출
Kakao API 직접 호출
복잡한 여행계획 로직 구현
```

---

# 9. core

## config.py

`.env` 환경변수를 읽는다.

예:

```text
MYSQL_URL
JWT_SECRET_KEY
KAKAO_REST_API_KEY
YOUTUBE_API_KEY
TOUR_API_KEY
KMA_API_KEY
GEMINI_API_KEY
EXAONE_API_KEY
```

Pydantic Settings 사용을 권장한다.

---

## security.py

책임:

```text
JWT 생성
JWT 검증
Access Token
Refresh Token
Refresh Token Hash
현재 사용자 확인
```

Kakao/Naver API 호출 코드는 넣지 않는다.

---

## exceptions.py

프로젝트 공통 Error를 정의한다.

예:

```text
TRIP_NOT_FOUND
PLACE_NOT_FOUND
INVALID_SOCIAL_TOKEN
AI_PROVIDER_TIMEOUT
```

모든 API Error Response를 통일한다.

---

# 10. db

## session.py

사용자가 별도로 준비한 MySQL Database에 연결한다.

```text
SQLAlchemy Engine
SessionLocal
get_db()
```

Backend는 **Database 자체를 생성하거나 삭제하지 않는다.**

사용자가 제공하는 MySQL 접속정보는 `.env`로 관리한다.

예:

```env
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_DATABASE=
MYSQL_USER=
MYSQL_PASSWORD=
```

또는 하나의 URL로 사용할 수 있다.

```env
MYSQL_URL=mysql+pymysql://USER:PASSWORD@HOST:3306/DATABASE
```

비밀번호를 Python 코드, Markdown, Git Repository에 직접 작성하지 않는다.

## base.py

모든 SQLAlchemy Model Base를 관리한다.

## seed.py

초기 Master Data를 입력한다.

대표적으로:

```text
interest_codes
```

---

# 11. models

`03_db_schema_draft_final.md`에 정의된 MySQL Table을
SQLAlchemy Model로 구현한다.

파일을 기능 도메인 단위로 묶는다.

예:

```text
user.py
→ users
→ user_preferences
→ user_interests
→ interest_codes

auth.py
→ user_auths
→ refresh_tokens

companion.py
→ companions
→ companion_preferences
→ companion_interests

trip.py
→ trips
→ trip_preferences
→ trip_companions
→ trip_interests
→ trip_sources

place.py
→ places
→ source_places

plan.py
→ travel_plans
→ plan_items
→ plan_revisions
→ plan_validation_issues

docent.py
→ docent_analyses
→ docent_candidates
```

테이블 하나당 Python 파일 하나를 만들 필요는 없다.

---

# 12. schemas

Pydantic Request / Response Model을 관리한다.

예:

```text
schemas/trip.py
```

내부:

```text
TripCreateRequest
TripUpdateRequest
TripResponse
TripListResponse
```

DB Model과 API Schema를 같은 클래스로 사용하지 않는다.

즉:

```text
SQLAlchemy Model
≠
Pydantic API Schema
```

---

# 13. repositories

Repository는 DB 접근 전용 계층이다.

예:

```text
trip_repository.py
```

책임:

```text
Trip 조회
Trip 생성
Trip 수정
Trip Soft Delete
Trip Companion 조회
Trip Interest 저장
```

Repository가 하면 안 되는 것:

```text
EXAONE 호출
Gemini 호출
여행 추천 판단
날씨 판단
HTTP Response 생성
```

---

# 14. services

서비스의 실제 Business Logic을 담당한다.

## auth_service.py

```text
Social Login 전체 흐름
신규 User 생성
기존 User 조회
JWT 발급
Refresh 처리
Logout
```

---

## preference_service.py

```text
User Preference
Companion Preference
YouTube 기반 관심사 분석
Trip Interest 확정
```

---

## plan_generation_service.py

핵심 서비스.

```text
Trip 조회
User 조건 조회
Companion 조건 조회
Interest 조회
Place 후보 수집
EXAONE 호출
AI Output Validation
Plan 저장
Plan Validation 실행
```

---

## plan_validation_service.py

```text
장소 존재
운영시간
이동시간
시간 충돌
날씨
이동 제약
```

등을 검증한다.

EXAONE에게 검증을 맡기지 않는다.

---

## plan_revision_service.py

```text
Plan Snapshot 저장
Revision 생성
Plan Version 증가
```

---

## docent_service.py

```text
사진 입력
Gemini 호출
장소 후보 추출
Kakao/TourAPI 검증
후보 DB 저장
사용자 선택
EXAONE 설명
```

---

# 15. external services

외부 Provider 연동 코드를 Business Logic과 분리한다.

예:

```text
gemini_service.py
```

책임:

```text
Gemini Request 생성
HTTP/API 호출
Response Parsing
Provider Error 변환
```

하지만 다음 작업은 하지 않는다.

```text
docent_candidates DB 저장
사용자에게 어떤 후보를 보여줄지 결정
여행계획 생성
```

이 작업은 `docent_service.py`가 담당한다.

---

# 16. validators

AI 또는 사용자가 만든 데이터에 대해
프로젝트 자체 규칙을 검사한다.

## trip_validator.py

예:

```text
start_date <= end_date
budget >= 0
여행 기간 검증
```

## plan_validator.py

예:

```text
Plan Item 날짜가 Trip 기간 안인가
시간이 겹치는가
sequence_no가 정상인가
```

외부 정보 검증은 `plan_validation_service.py`와 협력한다.

---

# 17. utils

Business Logic이 없는 공통 Utility만 둔다.

## youtube.py

```text
YouTube URL
→ videoId 추출
```

## kma_grid.py

```text
latitude / longitude
→ 기상청 nx / ny
```

## image.py

```text
이미지 MIME 검증
파일 크기 검증
Resize
```

## datetime.py

```text
날짜/시간 공통 Utility
```

`utils` 폴더에 Business Logic을 넣지 않는다.

---

# 18. Alembic

DB Schema 변경은 직접 수동으로 수정하지 않고
Alembic Migration으로 관리한다.

```text
alembic/
└── versions/
```

Backend/Codex가 하면 안 되는 작업:

```text
CREATE DATABASE
DROP DATABASE
CREATE USER
DROP USER
사용자 권한 임의 변경
운영 DB 전체 초기화
```

사용자가 준비한 Database에 Migration만 적용한다.

```bash
alembic upgrade head
```

예:

```text
001_create_users.py
002_create_companions.py
003_create_trips.py
```

초기 개발에서도 Schema 변경 이력을 남긴다.

---

# 19. tests

## unit

외부 API/DB 없이 단위 로직 테스트.

예:

```text
YouTube videoId parsing
날짜 검증
AI Output Schema 검증
일정 시간 충돌
기상청 Grid 변환
```

## integration

실제 FastAPI / Test DB 흐름 테스트.

예:

```text
로그인
Trip 생성
Companion 등록
Plan 생성
Smart Docent API
```

## external

외부 API Test는 실제 Key가 필요하므로
일반 Unit Test와 분리한다.

CI에서 항상 호출하지 않는다.

---

# 20. mock_data

5단계에서 사용할 Mock 데이터 위치.

```text
mock_data/

users.json
companions.json
trips.json
youtube.json
places.json
plans.json
docent.json
```

외부 API가 연결되지 않아도 Backend를 먼저 개발할 수 있도록 한다.

---

# 21. scripts

개발/초기화 전용 Script.

## seed_interest_codes.py

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

등 Master Data 입력.

---

# 22. docs

Codex가 구현 전 반드시 읽어야 하는 문서.

```text
docs/
├── 01_core_features.md
├── 02_api_spec_draft_final.md
├── 03_db_schema_draft_final.md
├── 04_external_apis.md
└── 05_project_structure.md
```

우선순위:

```text
1. Core Features
2. API Specification
3. DB Schema
4. External APIs
5. Project Structure
```

문서 간 충돌 시 Codex가 임의 판단하지 않고
작업을 중단하거나 TODO로 명시하도록 한다.

---

# 23. .env.example

Repository에 실제 `.env`는 올리지 않는다.

예:

```env
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_DATABASE=
MYSQL_USER=
MYSQL_PASSWORD=

# 또는 위 값을 조합한 MYSQL_URL 사용 가능
MYSQL_URL=

CORS_ALLOWED_ORIGINS=

JWT_SECRET_KEY=
JWT_ACCESS_EXPIRE_MINUTES=30
JWT_REFRESH_EXPIRE_DAYS=14

KAKAO_REST_API_KEY=
KAKAO_CLIENT_SECRET=

NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=

YOUTUBE_API_KEY=

TOUR_API_KEY=
TOUR_API_BASE_URL=

KMA_API_KEY=
KMA_API_BASE_URL=

GEMINI_API_KEY=
GEMINI_MODEL=

EXAONE_API_KEY=
EXAONE_BASE_URL=
EXAONE_MODEL=

EXTERNAL_API_TIMEOUT_SECONDS=10
AI_API_TIMEOUT_SECONDS=60
```

---

# 24. .gitignore

최소:

```gitignore
.env
.venv/
__pycache__/
*.pyc

.idea/
.vscode/

.pytest_cache/
.coverage

logs/
tmp/
```

실제 팀 개발환경에 따라 추가한다.

---

# 25. requirements.txt 초기 후보

```text
fastapi
uvicorn
sqlalchemy
pymysql
alembic
pydantic
pydantic-settings
python-jose
passlib
httpx
python-multipart
pytest
pytest-asyncio
```

AI Provider 공식 SDK를 사용할 경우:

```text
google-genai
```

등 필요한 Package를 실제 구현 시 추가한다.

버전은 구현 시작 시 호환성을 확인한 뒤 고정한다.

---

# 26. README.md

최소 다음 내용을 포함한다.

```text
프로젝트 소개
기술 스택
Python 버전
설치 방법
.env 설정 방법
MySQL 실행 방법
Alembic Migration 방법
FastAPI 실행 방법
테스트 실행 방법
API Docs 주소
docs 문서 구조
```

실행 예:

```bash
uvicorn app.main:app --reload
```

FastAPI Swagger:

```text
http://localhost:8000/docs
```

---

# 27. Codex 구현 규칙

1. `docs/`를 먼저 읽고 구현한다.
2. Router에 Business Logic을 작성하지 않는다.
3. Router에서 SQLAlchemy Query를 직접 작성하지 않는다.
4. Router에서 외부 API를 직접 호출하지 않는다.
5. DB 접근은 Repository에서 수행한다.
6. Business Logic은 Service에서 수행한다.
7. 외부 API는 `services/external`을 통해 호출한다.
8. API Request/Response는 Pydantic Schema를 사용한다.
9. SQLAlchemy Model과 Pydantic Schema를 분리한다.
10. Secret/API Key를 코드에 Hard Coding하지 않는다.
11. `.env`를 Git에 Commit하지 않는다.
12. Schema 변경은 Alembic Migration으로 관리한다.
13. AI Output을 그대로 신뢰하지 않고 Pydantic Validation한다.
14. 일정 생성/수정 후 Validation Service를 호출한다.
15. 기존 문서의 API URL을 임의 변경하지 않는다.
16. DB Table/Column을 임의 추가·삭제하지 않는다.
17. 새로운 구조가 필요하면 TODO와 이유를 먼저 남긴다.
18. 사용하지 않는 추상화/Factory/Interface를 과도하게 만들지 않는다.
19. MVP 구현을 우선한다.
20. 테스트 가능한 구조를 유지한다.
21. Frontend Repository 코드를 Backend Repository에 생성하지 않는다.
22. Frontend와의 계약은 API 명세를 기준으로 한다.
23. 사용자가 제공한 MySQL Database에 연결하며 Database 자체를 생성/삭제하지 않는다.
24. MySQL 접속정보는 `.env`로만 관리한다.
25. MySQL 비밀번호를 Markdown, Python 코드, Git에 남기지 않는다.
26. DB Schema 생성/변경은 Alembic Migration으로 수행한다.
27. 운영환경 CORS에 `allow_origins=["*"]`를 사용하지 않는다.

---

# 28. 구조를 한 줄로 요약

```text
Flutter
   ↓
FastAPI Router
   ↓
Business Service
   ├── Repository → MySQL
   └── External Adapter → Kakao / YouTube / TourAPI / Weather / Gemini / EXAONE
   ↓
Validation
   ↓
Flutter
```

---

# 29. 4단계 완료 기준

- [x] FastAPI Root 구조 확정
- [x] Router 구조 확정
- [x] Model / Schema 분리
- [x] Repository 계층 확정
- [x] Business Service 계층 확정
- [x] External API Adapter 구조 확정
- [x] Validation 구조 확정
- [x] Alembic 위치 확정
- [x] Test 구조 확정
- [x] Mock Data 위치 확정
- [x] 환경변수 파일 정책 확정
- [x] Codex 구현 규칙 확정

다음 단계는 `05. Mock 데이터 준비`다.
