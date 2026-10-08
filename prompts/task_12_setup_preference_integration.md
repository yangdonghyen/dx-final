# Task 12 — Flutter SetupScreen 사용자 취향 저장 연동

## 0. 작업 위치와 Git 안전 규칙 — 최우선

이 작업은 **통합 저장소만** 수정한다.

- 작업 루트: `C:\dev\dx-all`
- 백엔드: `C:\dev\dx-all\backend`
- 프론트: `C:\dev\dx-all\frontend\flutter`

다음 저장소/폴더는 **절대 수정하지 않는다.**

- `C:\dev\DX-front`
- `C:\dev\프로젝트백엔드`
- 기존 GitHub 프론트 저장소 `Dx-`
- 기존 GitHub 백엔드 저장소 `DXback`

### Git 관련 금지 사항

사용자가 별도로 지시하지 않는 한 아래 작업을 하지 않는다.

- `git push`
- `git pull`
- `git fetch`
- `git merge`
- `git rebase`
- `git reset`
- `git checkout` / `git switch`
- `git commit`
- remote 변경
- branch 생성/삭제
- 다른 저장소 파일 복사/덮어쓰기

특히 `Dx-` 프론트 저장소는 프론트 담당자 작업 공간이므로 **읽기/수정/커밋/푸시 대상이 아니다.**

작업 시작 시와 종료 시 `C:\dev\dx-all`에서만 `git status --short`를 확인한다.

---

## 1. 목표

현재 Flutter의 흐름은 대략 다음과 같다.

1. 실제 Kakao 로그인
2. 백엔드 `/api/v1/auth/social-login`
3. 서비스 JWT 저장
4. `SetupScreen`
5. 사용자가 여행 스타일/관심사/시니어 여부 등을 선택
6. 현재는 실제 백엔드 저장 없이 `HomeScreen`으로 이동

이번 작업의 목표는 다음과 같다.

> **SetupScreen에서 선택한 사용자 초기 여행 취향을 실제 FastAPI/MySQL에 저장하고, 저장 성공 후에만 HomeScreen으로 이동하도록 연결한다.**

---

## 2. 반드시 먼저 분석할 것

코드를 수정하기 전에 `dx-all` 내부의 현재 구현을 분석한다.

### Backend

다음을 확인한다.

- 사용자 관련 모델
- 사용자 관련 schema
- 사용자 관련 repository/service
- `/api/v1/users` 등 기존 사용자 API
- 인증된 현재 사용자를 얻는 dependency
- JWT 인증 방식
- 관심사/취향 관련 기존 테이블 또는 모델
- Alembic migration
- 이미 구현된 preference 관련 코드
- EXAONE preference 분석과 사용자 프로필 저장 기능의 역할 차이

### Frontend

다음을 확인한다.

- `lib/screens/auth/setup_screen.dart`
- `lib/services/auth_service.dart`
- `lib/data/api/api_client.dart`
- 현재 JWT 저장 위치
- `SetupScreen`의 실제 선택 변수
- `SetupScreen -> HomeScreen` 이동 코드
- 관련 model/service가 이미 있는지

### 중요한 원칙

**기존 기능이 있으면 재사용한다.**

비슷한 API/model/table/service가 있는데 새로 중복 구현하지 않는다.

분석 결과를 먼저 짧게 정리한 뒤 구현한다.

---

## 3. 프론트 UI 보호 원칙

프론트 담당자의 UI 변경과 충돌을 최소화해야 한다.

따라서:

- `SetupScreen`의 레이아웃/디자인을 가능한 한 유지한다.
- 색상, 간격, 버튼 디자인, 문구 등을 불필요하게 변경하지 않는다.
- API 통신 로직을 화면 파일에 길게 작성하지 않는다.
- 네트워크/DTO/저장 로직은 별도 service 또는 data 계층으로 분리한다.
- `SetupScreen`에는 가능한 한 아래 정도만 남긴다.
  - 현재 선택값 수집
  - 저장 함수 호출
  - loading/error UI
  - 저장 성공 시 화면 이동

목표 구조 예시:

```text
SetupScreen
    ↓
UserPreferenceService 또는 UserService
    ↓
ApiClient
    ↓
FastAPI
```

기존 프로젝트 구조와 더 잘 맞는 계층이 있으면 그 구조를 따른다.

---

## 4. 저장할 데이터

`setup_screen.dart`의 **실제 현재 변수와 선택지**를 기준으로 저장한다.

임의로 새로운 취향 항목을 만들어내지 않는다.

최소한 현재 화면에 존재하는 아래 성격의 값을 검토한다.

- 여행 스타일
- 관심사/선호 카테고리
- 시니어 모드 여부
- 화면에 실제 존재하는 기타 초기 설정

### 데이터 매핑 원칙

Frontend의 한글 표시 문자열을 DB에 그대로 넣기 전에 기존 Backend enum/code/schema가 있는지 확인한다.

예:

```text
"여유롭게" → SLOW
"맛집" → FOOD
```

같은 변환이 필요하다면 기존 정의를 우선 사용한다.

기존 정의가 없다면:
1. 최소한의 안정적인 code 값을 정의하고
2. UI 표시 문자열과 저장 code를 분리한다.

임의의 의미 변환을 하지 않는다.

---

## 5. Backend 구현 조건

가능하면 **로그인된 현재 사용자 기준**으로 저장한다.

### 금지

Flutter에서 다음처럼 user id를 하드코딩하지 않는다.

```text
user_id = 1
```

JWT에서 인증된 현재 사용자를 Backend가 식별해야 한다.

### API

기존 사용자 프로필/설정 API가 있으면 재사용한다.

없다면 현재 프로젝트 패턴에 맞는 최소 API를 추가한다.

예시일 뿐이며 기존 구조를 우선한다.

```http
PUT /api/v1/users/me/preferences
```

또는

```http
PATCH /api/v1/users/me
```

### 저장 방식

- 동일 사용자가 Setup을 다시 저장해도 중복 row가 무한히 생성되지 않도록 한다.
- update/upsert 성격을 고려한다.
- 관심사가 별도 관계 테이블이면 기존 스키마를 따른다.
- transaction 일관성을 유지한다.
- 잘못된 입력은 4xx로 처리한다.
- DB 오류를 성공으로 위장하지 않는다.

---

## 6. DB 스키마 변경

기존 테이블로 충분하면 **새 migration을 만들지 않는다.**

스키마 변경이 정말 필요할 때만 Alembic migration을 만든다.

스키마 변경 전에 반드시:

1. 기존 models
2. 기존 migrations
3. 실제 서비스 요구사항

을 검토한다.

DB를 삭제하거나 초기화하거나 기존 데이터를 임의로 변경하지 않는다.

다음 명령과 유사한 destructive 작업은 하지 않는다.

- DROP DATABASE
- DROP TABLE
- TRUNCATE
- 기존 migration history 재작성

---

## 7. Flutter 구현 조건

현재 카카오 로그인 및 AuthSession 구조를 깨뜨리지 않는다.

API 호출에는 현재 서비스 JWT를 사용한다.

예상 흐름:

```text
사용자 선택
→ "시작하기" 버튼
→ 중복 클릭 방지
→ 백엔드 저장 요청
→ 성공
→ HomeScreen

실패
→ HomeScreen으로 이동하지 않음
→ 사용자에게 이해 가능한 오류 표시
→ 재시도 가능
```

### Loading

저장 중에는 버튼 연타가 발생하지 않게 한다.

### Error

에러를 조용히 삼키지 않는다.

화면의 기존 스타일을 크게 변경하지 않는 선에서 실패 안내를 제공한다.

---

## 8. Kakao 로그인 코드 보호

현재 실제 Kakao 로그인 E2E가 성공한 상태다.

아래 기능을 불필요하게 변경하지 않는다.

- Kakao Flutter SDK 초기화
- Android redirect scheme
- `AuthService.loginWithKakao()`
- Kakao access token → FastAPI
- FastAPI Kakao token validation
- 서비스 JWT 발급/저장

이번 작업 때문에 인증 흐름을 재설계하지 않는다.

---

## 9. 외부 Provider 보호

이번 작업 범위가 아니므로 불필요하게 수정하지 않는다.

- Kakao Place Provider
- YouTube Provider
- EXAONE Provider
- Plan generation
- Region filtering
- Weather
- GPS

Setup 저장에 직접 필요하지 않은 코드는 건드리지 않는다.

---

## 10. 테스트

### Backend

관련 unit/integration test를 추가하거나 기존 테스트를 보강한다.

최소 검증:

1. 인증되지 않은 요청 거부
2. 인증된 사용자의 설정 저장 성공
3. 다시 저장하면 업데이트되는지
4. 관심사/스타일 값 검증
5. 다른 사용자의 데이터를 수정하지 않는지

가능한 기존 테스트 패턴을 따른다.

### Frontend

가능한 범위에서:

- `flutter analyze`
- 관련 테스트가 있으면 실행

최소한 compile/analyze 오류가 없어야 한다.

기존의 unrelated info warning은 새 오류로 간주하지 않는다.

---

## 11. 실행/환경 주의

실제 secret을 코드에 넣지 않는다.

특히 아래 값은 출력하거나 커밋하지 않는다.

- MySQL password
- JWT secret
- Kakao key
- YouTube key
- 기타 `.env` secret

`.env`를 수정해야 할 이유가 없다면 수정하지 않는다.

`.env.example`도 이번 기능에 새 환경변수가 필요할 때만 수정한다.

---

## 12. 완료 후 보고 형식

작업 완료 후 다음 순서로 보고한다.

### 1) 분석 결과
- 기존에 재사용한 코드/테이블/API
- 새로 추가할 필요가 있었던 부분

### 2) 변경 파일
각 파일별 변경 이유를 한 줄씩 설명한다.

### 3) 최종 API 흐름

```text
SetupScreen
→ Service
→ ApiClient
→ FastAPI
→ authenticated user
→ MySQL
→ success
→ HomeScreen
```

### 4) 테스트 결과
실행한 명령과 통과/실패 수를 보고한다.

### 5) Git 상태

`C:\dev\dx-all`에서:

```bash
git status --short
```

결과를 보고한다.

### 6) 절대 하지 말 것

작업 완료 후에도 자동으로:

- commit 하지 않는다.
- push 하지 않는다.
- pull 하지 않는다.

사용자가 검토한 후 별도로 지시한다.

---

## 13. 성공 조건

아래가 모두 만족되면 완료다.

- 실제 Kakao 로그인 기능 유지
- SetupScreen UI 최대한 유지
- 사용자가 선택한 초기 취향이 Backend에 저장
- JWT의 현재 사용자에게 저장
- 하드코딩 user id 없음
- 중복 저장 문제 없음
- 저장 실패 시 HomeScreen으로 넘어가지 않음
- Backend tests 통과
- Flutter analyze에 새 error 없음
- `Dx-`, `DXback` 저장소 수정 없음
- Git commit/push/pull 없음
- 모든 변경은 `C:\dev\dx-all` 내부에만 존재
