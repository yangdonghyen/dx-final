# Codex Task 02 — Database Models & Initial Alembic Migration

Task 01은 완료되었고, 실제 MySQL 연결도 확인되었다.

현재 확인된 상태:

```text
.env 로딩: 정상
MySQL 연결: 성공
Database: campus_26K_LGDX19_p3_1
MySQL Version: 8.0.26
현재 Table: 없음
SELECT: 가능
```

이번 Task에서는 **Database Model과 초기 Alembic Migration만 구현**한다.

Frontend는 별도 Flutter Repository이며,
현재 Repository는 FastAPI Backend 전용이다.

---

# 1. 구현 전 반드시 읽을 문서

아래 문서를 순서대로 다시 읽고 작업해라.

1. `docs/01_planning/01_core_features.md`
2. `docs/02_api/02_api_spec.md`
3. `docs/03_database/03_db_schema.md`
4. `docs/04_external_api/04_external_apis.md`
5. `docs/05_architecture/05_project_structure.md`
6. `docs/06_mock/06_mock_data.md`
7. `docs/07_implementation/07_implementation_plan.md`

특히 이번 Task의 Source of Truth는:

```text
docs/03_database/03_db_schema.md
```

이다.

DB Schema 문서와 다른 Table/Column을 임의로 추가하거나 삭제하지 마라.

---

# 2. 이번 Task 범위

이번에는 다음만 구현한다.

1. 22개 SQLAlchemy Model
2. Enum / FK / UNIQUE / CHECK / NULL 규칙 반영
3. Relationship 최소 구성
4. Alembic Metadata 연결
5. Initial Migration 생성
6. Migration SQL 검토
7. 실제 MySQL에 `alembic upgrade head`
8. 실제 Table 생성 확인
9. Schema 구조 확인
10. Model / Migration 관련 테스트

---

# 3. 이번 Task에서 구현하지 말 것

아직 다음 기능은 구현하지 마라.

- Kakao 실제 로그인
- Naver 실제 로그인
- Auth API
- User CRUD
- Companion CRUD
- Trip CRUD
- YouTube API
- Kakao Local API
- TourAPI
- Weather API
- EXAONE
- Gemini
- Plan 생성 Business Logic
- Smart Docent Business Logic
- Mock Provider
- Repository Business Query 구현
- Service Business Logic

이번 Task는 **DB Model + Migration**에 집중한다.

---

# 4. MySQL 안전 규칙

현재 Database는 이미 존재한다.

절대 다음 작업을 하지 마라.

```text
CREATE DATABASE
DROP DATABASE
CREATE USER
DROP USER
GRANT 권한 변경
Database 전체 초기화
```

허용:

```text
CREATE TABLE
ALTER TABLE
CREATE INDEX
CREATE CONSTRAINT
```

단, 반드시 **Alembic Migration을 통해서만** 수행한다.

수동 SQL로 Table을 직접 만들지 마라.

---

# 5. Migration 적용 전 확인

Migration을 실제 적용하기 전에 다음 순서로 진행해라.

1. 현재 DB가 빈 상태인지 다시 확인
2. `SHOW TABLES` 결과 확인
3. 가능하면 `SHOW GRANTS FOR CURRENT_USER()` 또는 동등한 읽기 전용 방법으로
   DDL 권한 존재 여부를 확인
4. Initial Migration 파일 생성
5. Migration 내용을 직접 검토
6. 문서의 22개 Table과 일치하는지 비교
7. 위험한 SQL이 없는지 확인
8. 그 후 `alembic upgrade head` 실행

금지되는 SQL이 Migration 안에 있으면 적용하지 마라.

특히 다음 SQL이 있으면 중단해라.

```text
DROP DATABASE
DROP TABLE
DROP USER
DELETE FROM
TRUNCATE
```

현재 DB가 비어 있다고 해도,
문서에 없는 기존 Table이 발견되면 Migration을 바로 적용하지 말고 보고해라.

---

# 6. 구현해야 할 22개 Table

정확한 Column/Constraint는 `03_db_schema.md`를 기준으로 한다.

## 인증 / 사용자

1. `users`
2. `user_auths`
3. `refresh_tokens`
4. `user_preferences`
5. `interest_codes`
6. `user_interests`

## 동행자

7. `companions`
8. `companion_preferences`
9. `companion_interests`

## 여행

10. `trips`
11. `trip_preferences`
12. `trip_companions`
13. `trip_interests`

## 콘텐츠 / 장소

14. `trip_sources`
15. `places`
16. `source_places`

## 일정

17. `travel_plans`
18. `plan_items`
19. `plan_revisions`
20. `plan_validation_issues`

## 스마트 도슨트

21. `docent_analyses`
22. `docent_candidates`

Table 수가 22개가 아니면 Migration을 적용하지 말고 원인을 확인해라.

---

# 7. Model 파일 배치

`docs/05_architecture/05_project_structure.md`를 기준으로 다음 도메인 단위로 묶어라.

```text
app/models/

auth.py
user.py
companion.py
trip.py
place.py
plan.py
docent.py
```

권장 매핑:

```text
auth.py
- user_auths
- refresh_tokens

user.py
- users
- user_preferences
- interest_codes
- user_interests

companion.py
- companions
- companion_preferences
- companion_interests

trip.py
- trips
- trip_preferences
- trip_companions
- trip_interests
- trip_sources

place.py
- places
- source_places

plan.py
- travel_plans
- plan_items
- plan_revisions
- plan_validation_issues

docent.py
- docent_analyses
- docent_candidates
```

Table 하나당 Python 파일 하나를 만들지 마라.

---

# 8. SQLAlchemy Model 규칙

## 기본 규칙

- SQLAlchemy 2.x 스타일을 우선 사용
- MySQL 8.x 기준
- PK는 `BIGINT AUTO_INCREMENT`
- DateTime Default 반영
- Boolean Default 반영
- Nullable 정확히 반영
- Unique Constraint 정확히 반영
- Foreign Key 정확히 반영
- Check Constraint 정확히 반영
- Enum 값 정확히 반영
- JSON Column 정확히 반영
- `ondelete` 정책 정확히 반영

문서에 없는 Constraint를 임의로 추가하지 마라.

---

# 9. Enum 규칙

문서에 정의된 Enum 값을 그대로 사용한다.

예:

```text
UserStatus
ACTIVE
WITHDRAWN
SUSPENDED
```

```text
AgeGroup
UNDER_20
20S
30S
40S
50S
60S
70S_PLUS
```

```text
WalkingTolerance
VERY_LOW
LOW
NORMAL
HIGH
```

```text
RestFrequency
LOW
NORMAL
HIGH
```

같은 Enum이 여러 Table에서 반복되면
Python Enum을 공통 모듈로 분리할 수 있다.

예:

```text
app/models/enums.py
```

단, **DB에 저장되는 실제 Enum 문자열은 문서와 동일해야 한다.**

---

# 10. 중요한 DB 규칙

다음 규칙을 반드시 반영한다.

## users

- `nickname`은 Social Login 직후 NULL 가능
- Profile 완료 시 Application Logic에서 필수
- nickname UNIQUE 금지

## user_auths

```text
UNIQUE(provider, provider_user_id)
UNIQUE(user_id, provider)
```

## refresh_tokens

- Raw Token 저장 금지
- `token_hash` UNIQUE

## user_preferences

- User 1:1
- `user_id` UNIQUE

## interest_codes

- PK = `interest_code`
- Master Code Table

## user_interests

```text
UNIQUE(user_id, interest_code)
```

---

## companions

DELETE Business Logic은 향후:

```text
status = ARCHIVED
```

로 처리하므로
이번 Model에서는 status Enum을 정확히 반영한다.

---

## companion_preferences

```text
UNIQUE(companion_id)
```

## companion_interests

```text
UNIQUE(companion_id, interest_code)
```

---

## trips

- `destination` NULL 허용
- Date CHECK 반영
- `budget_krw` unsigned/0 이상 규칙 반영
- Soft Delete는 status로 관리

---

## trip_preferences

```text
UNIQUE(trip_id)
```

---

## trip_companions

- Snapshot Column 유지
- `companion_id` NULL 가능
- Companion 삭제 시 `SET NULL`
- `interests_snapshot` JSON

```text
UNIQUE(trip_id, companion_id)
```

---

## trip_interests

```text
source_type:
PROFILE
CONTENT_AI
USER
```

```text
UNIQUE(trip_id, interest_code)
```

---

## trip_sources

- tags = JSON
- `is_active` 존재
- YouTube Source만 현재 지원

```text
UNIQUE(trip_id, source_type, external_id)
```

---

## places

- `name` UNIQUE 금지
- `kakao_place_id` UNIQUE
- `tour_content_id` UNIQUE
- 여러 NULL 허용
- latitude / longitude CHECK
- opening_hours JSON
- `verification_status` Enum

---

## source_places

- `place_id` NULL 가능
- numeric confidence 저장 금지
- `rank_no` 사용

```text
UNIQUE(source_id, rank_no)
```

---

## travel_plans

MVP에서는 Trip당 Plan 1개.

```text
UNIQUE(trip_id)
```

---

## plan_items

- `place_id` NULL 가능
- REST / FREE_TIME 허용
- visit_date / sequence_no 사용

```text
UNIQUE(plan_id, visit_date, sequence_no)
```

Time CHECK도 반영한다.

---

## plan_revisions

- Snapshot = JSON
- `revision_no` 사용

```text
UNIQUE(plan_id, revision_no)
```

---

## plan_validation_issues

- resolved Boolean 없음
- `resolved_at IS NULL` = 미해결
- `item_id` NULL 가능

---

## docent_analyses

- 이미지 원본 Column 만들지 마라
- `trip_id` NULL 가능
- `selected_place_id` NULL 가능

---

## docent_candidates

- numeric confidence Column 만들지 마라
- `place_id` NULL 가능

```text
UNIQUE(analysis_id, rank_no)
```

---

# 11. Relationship 규칙

SQLAlchemy Relationship은 최소한으로 구성한다.

목표:

- 기본 Join 가능
- 불필요한 Circular Import 방지
- Cascade 오작동 방지

Relationship 때문에 DB Schema와 다른 Cascade를 생성하지 마라.

DB Foreign Key의 `ON DELETE`가 Source of Truth다.

---

# 12. Alembic Metadata

Alembic이 모든 Model을 인식해야 한다.

다음 구조를 점검해라.

```text
app/db/base.py
→ Base Metadata
→ 모든 Model Import
→ alembic/env.py target_metadata
```

`alembic revision --autogenerate`가 22개 Table을 모두 감지해야 한다.

---

# 13. Initial Migration

Migration 이름 권장:

```text
001_initial_schema
```

또는 Alembic 기본 Revision ID + 명확한 Message.

예:

```bash
alembic revision --autogenerate -m "initial schema"
```

Migration을 생성한 후 바로 적용하지 말고 먼저 내용을 검토한다.

확인:

```text
Create Table = 22
Drop Table = 0
Database 생성 = 0
Database 삭제 = 0
```

---

# 14. Migration 적용

검토가 끝났고 문제가 없으면:

```bash
alembic upgrade head
```

를 실행한다.

실패하면:

- 임의 수동 SQL로 우회하지 마라
- DB Secret 출력 금지
- Error 원인만 분석
- 부분 적용된 Table이 있는지 확인
- 임의 DROP으로 복구하지 마라
- 결과를 사용자에게 보고

---

# 15. Migration 적용 후 검증

최소 다음을 확인한다.

```sql
SELECT DATABASE();
SHOW TABLES;
```

Expected:

```text
22개 Service Table
+
alembic_version
```

즉 총 조회 Table 수는 Alembic Version Table 포함 시 23개가 될 수 있다.

이 차이를 오류로 판단하지 마라.

---

# 16. Schema 검증

중요 Table은 `SHOW CREATE TABLE` 또는 SQLAlchemy Inspector로 검증한다.

최소 확인:

```text
users
user_auths
trips
trip_companions
places
travel_plans
plan_items
docent_analyses
```

검증 항목:

- PK
- FK
- UNIQUE
- NULL
- Enum
- JSON
- Check Constraint
- ondelete

---

# 17. interest_codes Seed

이번 Task에서는 **Table 구조까지만 구현**한다.

`interest_codes` 초기 데이터는 아직 자동 INSERT하지 마라.

향후 Phase 1 또는 별도 Seed Task에서:

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

를 입력한다.

이번 Migration에 Master Data INSERT를 억지로 포함하지 마라.

---

# 18. 테스트

최소 다음 테스트를 추가한다.

## Metadata Test

- Model Table 수 = 22
- 각 주요 Table 존재
- 주요 Column 존재

## Constraint Test

최소:

```text
users.nickname UNIQUE 아님
user_auths provider+provider_user_id UNIQUE
trip_preferences trip_id UNIQUE
travel_plans trip_id UNIQUE
places name UNIQUE 아님
places kakao_place_id UNIQUE
plan_items order UNIQUE
```

## Enum Test

중요 Enum 값이 문서와 동일한지 검증한다.

## Alembic Test

- Migration Import 가능
- Upgrade SQL 생성 가능
- Dangerous Drop 없음

실제 MySQL Migration을 성공 적용한 경우:
- 실제 DB에 Table 존재 확인

---

# 19. 기존 Task 01 테스트

Task 02 작업 후에도 기존 테스트를 모두 실행한다.

```bash
pytest
```

Task 01에서 통과했던 테스트가 깨지면 Task 02 완료가 아니다.

---

# 20. 기존 파일 보호

다음 폴더/파일은 함부로 변경하지 마라.

```text
docs/
mock_data/
prompts/
```

문서 수정이 필요하다고 판단해도 이번 Task에서는 수정하지 말고 보고한다.

`.env` 내용 출력/수정 금지.

`.env.example`은 Model 구현에 꼭 필요한 변화가 없다면 수정하지 마라.

---

# 21. 완료 후 보고 형식

작업 완료 후 아래 형식으로 보고해라.

```text
[Task 02 작업 결과]

1. 생성한 파일
- ...

2. 수정한 파일
- ...

3. 구현한 SQLAlchemy Model
- 총 Model/Table 수:
- 목록:

4. 생성한 Alembic Migration
- Revision:
- Create Table 수:
- Drop Table 수:

5. 실제 MySQL 적용 결과
- 연결:
- Migration:
- 생성된 Table 수:
- alembic_version:
- 실패 여부:

6. Schema 검증 결과
- FK:
- UNIQUE:
- CHECK:
- ENUM:
- JSON:
- ON DELETE:

7. 실행한 테스트
- pytest:
- 추가 테스트:
- 결과:

8. 발견된 문제
- ...

9. 문서와 구현 충돌
- 없음 / 상세내용

10. 사용자에게 필요한 정보
- ...

11. 다음 Task에서 해야 할 내용
- ...
```

---

# 22. Task 02 완료조건

아래를 모두 만족해야 완료다.

- [ ] SQLAlchemy Service Table = 22개
- [ ] DB Schema 문서와 Column 일치
- [ ] PK/FK/UNIQUE/CHECK 반영
- [ ] Enum 값 일치
- [ ] JSON Column 반영
- [ ] ON DELETE 정책 반영
- [ ] Model Import 정상
- [ ] Alembic Metadata가 모든 Model 감지
- [ ] Initial Migration 생성
- [ ] Migration 검토 완료
- [ ] 위험한 DROP 없음
- [ ] 실제 MySQL `alembic upgrade head` 성공
- [ ] 실제 DB에 22개 Service Table 생성 확인
- [ ] `alembic_version` 확인
- [ ] 주요 Schema 검증
- [ ] Task 01 테스트 포함 전체 테스트 통과
- [ ] docs/mock_data/prompts 수정 없음
- [ ] Database 자체 생성/삭제 없음
- [ ] Task 02 범위 밖 Business Logic 구현 없음

**지금은 Task 02만 진행해라.**
