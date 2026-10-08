# MySQL Connection Check — Before Codex Task 02

프로젝트 루트의 `.env` 파일에 실제 MySQL 접속정보와 JWT Secret을 입력해두었다.

Codex Task 02를 시작하기 전에,
현재 구현된 설정 및 SQLAlchemy 연결 코드를 사용해서
**MySQL 연결 상태만 비파괴적으로 확인**해라.

## 중요 규칙

이번 작업에서는 DB를 절대 변경하지 마라.

다음 작업은 금지한다.

- CREATE DATABASE
- DROP DATABASE
- CREATE TABLE
- ALTER TABLE
- DROP TABLE
- INSERT
- UPDATE
- DELETE
- Alembic Migration 적용
- 기존 데이터 변경
- 사용자/권한 변경

오직 연결 및 조회만 수행한다.

## Secret 보호

`.env`에 있는 다음 실제 값을 출력하지 마라.

- MYSQL_PASSWORD
- JWT_SECRET_KEY
- API Key
- Client Secret

접속 URL을 출력할 경우에도 Password는 반드시 마스킹해라.

## 확인할 항목

현재 프로젝트의 `app/core/config.py`,
`app/db/session.py` 등 Task 01에서 구현한 기존 코드를 우선 사용해라.

확인:

1. `.env`가 정상적으로 로딩되는가
2. MySQL 서버에 연결되는가
3. 현재 선택된 Database 이름
4. MySQL Version
5. 현재 Database에 존재하는 Table 목록
6. 현재 계정으로 SELECT가 가능한가
7. Task 02에서 Alembic Migration을 진행할 수 있을 것으로 보이는가

가능하면 다음과 같은 읽기 전용 쿼리만 사용해라.

```sql
SELECT DATABASE();
SELECT VERSION();
SHOW TABLES;
```

DB에 기존 Table이 있으면 이름만 보고하고,
내용을 임의 조회하거나 변경하지 마라.

## 연결 실패 시

연결에 실패하면:

1. Secret 값은 출력하지 말 것
2. 에러 종류만 설명할 것
3. HOST / PORT / DATABASE / USER 중 어떤 설정을 확인해야 하는지 알려줄 것
4. 설정을 임의 수정하지 말 것
5. Task 02를 시작하지 말 것

## 연결 성공 시

연결에 성공하더라도
**이번 작업에서는 Task 02를 시작하지 마라.**

Model 생성이나 Migration은 하지 말고 결과만 보고해라.

## 결과 보고 형식

```text
[MySQL 연결 확인]

- .env 로딩:
- 연결 성공 여부:
- Database:
- MySQL Version:
- 기존 Table:
- SELECT 가능 여부:
- 발견된 문제:
- Task 02 진행 가능 여부:
```

이번 작업은 MySQL 연결 확인만 수행하고 종료해라.
