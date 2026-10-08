# Codex Task 01 — Backend Project Skeleton

이 프로젝트의 Backend 구현을 시작한다.

현재 Frontend는 별도의 Flutter GitHub Repository에서 개발 중이며,
현재 Repository는 FastAPI Backend 전용이다.
Frontend 파일을 생성하거나 수정하지 마라.

## 1. 구현 전 반드시 읽을 문서

아래 문서를 순서대로 읽고 프로젝트 전체 구조를 이해한 뒤 작업해라.

1. `docs/01_planning/01_core_features.md`
2. `docs/02_api/02_api_spec.md`
3. `docs/03_database/03_db_schema.md`
4. `docs/04_external_api/04_external_apis.md`
5. `docs/05_architecture/05_project_structure.md`
6. `docs/06_mock/06_mock_data.md`
7. `docs/07_implementation/07_implementation_plan.md`

`mock_data/` 폴더가 있으면 내용도 확인하되,
이번 Task에서는 Mock 기능을 구현하지 않는다.

문서 간 충돌이나 현재 Repository와의 충돌을 발견하면
임의로 판단하지 말고 작업 결과에 보고해라.

---

## 2. 이번 작업 범위

이번에는 **Task 01 / Phase 0만 구현**한다.

목표:

1. FastAPI 프로젝트 Skeleton
2. 문서에 정의된 Backend 폴더 구조
3. FastAPI Application 진입점
4. `/api/v1` Router 기본 구조
5. `GET /api/v1/health`
6. 환경변수 설정 구조
7. 사용자가 준비한 기존 MySQL 연결 구조
8. SQLAlchemy Base / Session
9. Alembic 기본 설정
10. CORS
11. 공통 Exception
12. `security.py` 기본 구조
13. `.env.example`
14. `.gitignore`
15. `requirements.txt`
16. 기본 `README.md`
17. Phase 0 최소 테스트

---

## 3. 이번 Task에서 구현하지 말 것

아직 다음 기능은 구현하지 마라.

- 실제 Kakao / Naver 로그인
- User CRUD
- Companion CRUD
- Trip CRUD
- YouTube API
- Kakao Local / Routing
- TourAPI
- 기상청 API
- EXAONE
- Gemini
- 여행 일정 생성/수정/재구성
- Smart Docent
- 전체 22개 SQLAlchemy Model
- 전체 DB Migration
- Mock Provider

작업 범위를 임의로 확장하지 마라.

---

## 4. Architecture 규칙

기본 흐름:

```text
Router
→ Service
→ Repository
→ MySQL
```

외부 API가 필요한 경우 향후:

```text
Router
→ Business Service
→ External Adapter
→ External API
```

규칙:

- Router에 SQL 직접 작성 금지
- Router에서 외부 API 직접 호출 금지
- Router에 복잡한 Business Logic 작성 금지
- SQLAlchemy Model과 Pydantic Schema 분리
- 기존 API Endpoint 임의 변경 금지

---

## 5. Frontend / Backend 분리

Frontend는 별도 Repository다.

```text
travel-ai-frontend/
└── Flutter
```

현재 Repository는 Backend 전용이다.

Backend와 Frontend의 계약은:

```text
docs/02_api/02_api_spec.md
```

를 기준으로 한다.

Frontend 코드나 Flutter 파일을 생성/수정하지 마라.

---

## 6. MySQL 규칙

MySQL Database는 사용자가 직접 준비한다.
Backend는 **이미 존재하는 MySQL Database에 연결만 한다.**

절대 하지 말 것:

- `CREATE DATABASE`
- `DROP DATABASE`
- `CREATE USER`
- `DROP USER`
- `GRANT` 권한 임의 변경
- 운영 DB 초기화
- 기존 Table 임의 삭제

Schema/Table 변경은 향후 Alembic Migration으로만 관리한다.

환경변수:

```env
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_DATABASE=
MYSQL_USER=
MYSQL_PASSWORD=
```

필요하면 내부적으로 `MYSQL_URL`을 조합할 수 있다.

실제 MySQL 접속정보가 없으면 임의 값을 만들어 접속하지 마라.
실제 접속정보가 필요한 시점에는 작업을 멈추고
사용자에게 필요한 항목만 알려줘라.

실제 비밀번호/Secret을 코드, Markdown, Git에 남기지 마라.

---

## 7. CORS

Frontend가 별도 Origin에서 실행되므로:

```env
CORS_ALLOWED_ORIGINS=
```

를 사용한다.

쉼표로 여러 Origin을 받을 수 있게 한다.

운영환경에서:

```python
allow_origins=["*"]
```

를 사용하지 마라.

---

## 8. Health API

구현:

```http
GET /api/v1/health
```

정상 응답:

```json
{
  "status": "ok"
}
```

MySQL 접속정보가 없어도 FastAPI Application 자체는 실행 가능해야 한다.

---

## 9. `.env.example`

최소 다음 항목을 넣는다.

```env
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_DATABASE=
MYSQL_USER=
MYSQL_PASSWORD=

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

`.env`는 Git에 포함하지 않는다.

---

## 10. 최소 프로젝트 구조

`docs/05_architecture/05_project_structure.md`를 우선 기준으로 한다.

Task 01에서는 최소 다음 구조를 준비한다.

```text
app/
├── main.py
├── dependencies.py
├── api/
│   └── v1/
│       ├── router.py
│       ├── auth.py
│       ├── users.py
│       ├── companions.py
│       ├── trips.py
│       ├── places.py
│       ├── plans.py
│       └── docent.py
├── core/
│   ├── config.py
│   ├── security.py
│   ├── exceptions.py
│   └── logging.py
├── db/
│   ├── base.py
│   └── session.py
├── models/
├── schemas/
├── repositories/
├── services/
├── validators/
└── utils/

alembic/
tests/
docs/
mock_data/
prompts/
```

필요하면 빈 폴더 유지를 위해 `.gitkeep`을 사용할 수 있다.

---

## 11. Alembic

Task 01에서는:

- Alembic 기본 설정
- SQLAlchemy Metadata 연결 구조
- 향후 Migration 가능 상태

까지만 준비한다.

전체 22개 Table Migration은 아직 만들지 마라.

Database 자체 생성/삭제 Logic도 만들지 마라.

---

## 12. `security.py`

이번 Task에서는 실제 Auth Logic을 구현하지 않는다.

향후 JWT 구현이 가능하도록 최소 구조만 준비한다.

- JWT 설정값 읽기
- Access Token 생성 함수 자리
- Token 검증 구조
- Refresh Token Hash 지원 준비

과도한 Auth 구현은 하지 마라.

---

## 13. 테스트

최소 다음 테스트를 작성하고 실행한다.

```text
GET /api/v1/health
→ 200
→ {"status": "ok"}
```

가능하면 다음도 확인한다.

- Application Import
- Config Loading
- CORS Origin Parsing

실제 MySQL 계정정보가 없다면 DB 연결 테스트를 억지로 성공시키지 마라.

---

## 14. 작업 방식

1. `docs/` 문서를 순서대로 읽는다.
2. 현재 Repository 구조를 확인한다.
3. 기존 파일을 함부로 삭제/덮어쓰지 않는다.
4. Task 01에 필요한 파일만 생성/수정한다.
5. 최소 테스트를 작성한다.
6. 테스트를 직접 실행한다.
7. FastAPI Application 실행/Import 가능 여부를 확인한다.
8. Task 01 범위 안에서 오류를 해결한다.
9. 작업 결과를 보고한다.

---

## 15. 완료 후 보고 형식

```text
[작업 결과]

1. 생성한 파일
- ...

2. 수정한 파일
- ...

3. 구현한 기능
- ...

4. 실행한 테스트와 결과
- ...

5. 아직 실행하지 못한 항목
- ...

6. 사용자에게 필요한 다음 정보
- ...

7. 발견한 문서/구현 충돌
- 없음 / 상세내용

8. 다음 Codex Task에서 해야 할 내용
- ...
```

문서와 구현 사이에 충돌이 있으면 임의 수정하지 말고 보고해라.

---

## 16. Task 01 완료조건

- [ ] FastAPI Application 정상 실행/Import
- [ ] `/api/v1/health` 200
- [ ] `/docs` 접근 가능
- [ ] Backend 폴더 구조 준비
- [ ] `.env.example` 준비
- [ ] `.env` Git Ignore
- [ ] MySQL Config 구조 준비
- [ ] 기존 MySQL 연결 구조 준비
- [ ] Database 생성/삭제 Logic 없음
- [ ] SQLAlchemy Base / Session 준비
- [ ] Alembic 기본 설정
- [ ] CORS 환경변수 처리
- [ ] 공통 Exception 구조
- [ ] Security 기본 구조
- [ ] 최소 Test 작성/통과
- [ ] Frontend 파일 생성/수정 없음
- [ ] Task 01 범위 밖 기능 구현 없음

**지금은 Task 01만 진행해라.**
