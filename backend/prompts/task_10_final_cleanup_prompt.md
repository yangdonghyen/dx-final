# Task 10 최종 마무리 프롬프트

작업 경로:
`C:\dev\프로젝트백엔드`

현재 파일시스템 문제는 해결되었습니다.

중요 현재 상태:

- 누락됐던 `app/schemas/plan.py` 복구 완료
- Plan schema import 정상
- pytest Windows temporary-directory 문제 해결
- 전체 테스트:
  - collected: 179
  - passed: 179
  - failed: 0
  - errors: 0
  - warnings: 9

전체 테스트 실행 명령:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=".pytest_tmp"
```

현재 테스트에 다음 파일이 존재하고 모두 통과합니다.

- `test_plan_generation_service.py`
- `test_plan_validation_service.py`
- `test_plan_edit_service.py`

따라서 이전 보고 내용을 그대로 믿지 말고
현재 실제 코드 기준으로 Task 10 상태를 다시 확인하세요.

이번 세션의 목표는:

> Task 10의 남은 기능을 정확히 식별하고 모두 구현하여 Task 10을 완전히 종료하는 것입니다.

Task 11 Real Provider는 절대 시작하지 마세요.

---

## 1. 먼저 현재 Task 10 실제 상태 확인

실제 코드를 확인하여 다음 기능별 상태를 판단하세요.

1. Plan Generation
2. 생성 직후 자동 Validation
3. Plan 조회
4. Plan Edit
   - DELETE_PLACE
   - REPLACE_PLACE
   - ADD_REST
   - REORDER
5. Plan Regenerate / Revision
6. Plan Confirm
7. current_version
8. plan_revisions snapshot
9. plan_validation_issues
10. transaction / rollback

특히 Plan Edit는:

- `app/services/plan_edit_service.py`
- `tests/unit/test_plan_edit_service.py`

가 현재 존재하고 9개 테스트가 통과하므로
이미 구현된 기능을 다시 만들지 마세요.

---

## 2. 문서 확인

다음 문서를 기준으로 남은 구현 범위를 확정하세요.

- `docs/07_implementation/07_implementation_plan.md`
- `docs/02_api/02_api_spec.md`
- `docs/03_database/03_db_schema.md`
- `docs/04_external_api/04_external_apis.md`
- `docs/05_architecture/05_project_structure.md`
- `docs/06_mock/06_mock_data.md`

문서에 없는 endpoint나 상태를 임의로 추가하지 마세요.

---

## 3. Plan 조회

문서에 Plan 조회 API가 정의되어 있고 아직 없다면 구현하세요.

반드시 확인:

- Plan 존재
- 사용자 소유권
- Trip 관계
- PlanItem 반환
- current_version
- plan status
- validation status / warning

기존 schema/repository를 재사용하세요.

---

## 4. Generation 후 Validation

현재 Plan 생성 흐름을 확인하세요.

Plan 생성 직후 `PlanValidationService`가 자동 실행되지 않는다면 연결하세요.

원하는 흐름:

```text
Plan 생성
→ PlanItem 저장
→ PlanValidationService 실행
→ validation issue 저장/해결
→ validation_status 갱신
→ commit
→ response
```

기존 `PlanValidationService`를 재사용하세요.

validation 로직을 중복 구현하지 마세요.

---

## 5. Regenerate / Revision

문서에 정의된 endpoint와 payload를 그대로 사용하세요.

지원 reason을 실제 문서에서 확인하세요.

기존 확인 결과에는:

- `USER_FATIGUE`
- `WEATHER_CHANGE`

가 있었습니다.

다음 항목을 구현/검증하세요.

- Plan 접근 검증
- Trip 소유권
- ARCHIVED Trip 차단
- 수정 전 Plan snapshot
- 기존 `plan_revisions` 사용
- 기존 Mock Provider 활용/확장
- Provider 결과 DTO 검증
- place_id 검증
- PlanItem 재구성
- 자동 validation
- 성공 시 `current_version` 증가
- 실패 시 rollback

새 DB table은 만들지 마세요.

---

## 6. Confirm

API spec에 정의된 Confirm endpoint를 구현하세요.

Confirm 전에 현재 validation 상태와 unresolved issue를 확인하세요.

문서 기준으로:

- blocking issue가 있으면 Confirm 차단
- warning만 존재할 때의 처리
- VALID 상태 처리

를 정확히 적용하세요.

성공 시 기존 Plan status enum을 사용하세요.

새 status를 임의로 추가하지 마세요.

---

## 7. Transaction

Generate/Edit/Regenerate/Confirm에서 부분 저장이 발생하지 않는지 확인하세요.

특히 Regenerate:

```text
snapshot
→ 변경
→ validation
→ version
→ commit
```

중간 실패:

```text
→ rollback
```

이 보장되어야 합니다.

---

## 8. 테스트

기존 179개 테스트를 유지하세요.

남은 기능에 대한 테스트를 추가하세요.

특히:

### Plan 조회
- 정상
- 없는 Plan
- 다른 사용자

### Generate + Validation
- 생성 직후 validation 수행
- validation_status 반영

### Regenerate
- 정상 USER_FATIGUE
- 정상 WEATHER_CHANGE
- snapshot 저장
- version 증가
- validation 실행
- 잘못된 place/provider 결과
- 다른 사용자
- ARCHIVED Trip

### Confirm
- 정상 confirm
- blocking issue confirm 차단
- warning-only 규칙
- 다른 사용자
- 없는 Plan

---

## 9. 전체 Regression

최종적으로 반드시 실행:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=".pytest_tmp"
```

현재 기준:

`179 passed`

최종 목표:

- 기존 179개 모두 유지
- 신규 테스트 모두 통과
- failed = 0
- errors = 0

warnings는 실패로 보지 않되 최종 보고에 개수를 적으세요.

현재 알려진 warning:

- `datetime.utcnow()` deprecation
- FastAPI/Starlette dependency deprecation

Task 10과 무관하면 이번 작업에서 억지로 수정하지 마세요.

---

## 10. Provider Factory는 아직 보류

이번 세션에서는 Task 10을 먼저 완전히 끝내세요.

Task 10 완료 전:

- Kakao Real Provider
- Naver Real Provider
- YouTube Real Provider
- 실제 API key
- Task 11 구현

을 시작하지 마세요.

Provider Factory도 Task 10 완료 후 별도 단계로 진행하세요.

---

## 11. 토큰 / 컨텍스트 관리

이번 작업의 최우선 목표는 Task 10 완료입니다.

컨텍스트가 부족해질 것 같다면:

1. 현재 남은 Task 10 기능
2. 테스트
3. 전체 regression

까지 안정적으로 끝낼 수 있는 범위만 구현하세요.

코드가 깨진 상태로 종료하지 마세요.

---

## 12. 금지사항

- Task 11 시작 금지
- 실제 외부 API 호출 금지
- 실제 API Key 입력 금지
- migration 금지
- commit 금지
- push 금지
- 테스트 삭제/skip 금지
- 테스트 expectation 완화 금지
- 대규모 unrelated refactoring 금지

---

# 완료 보고 형식

## [Task 10 최종 마무리 결과]

### 작업 시작 시 상태
- 기존 테스트: 179 passed

### Task 10 실제 구현 상태

#### Plan Generation
- ...

#### Generate 후 Validation
- ...

#### Plan 조회
- ...

#### Plan Edit
- DELETE_PLACE:
- REPLACE_PLACE:
- ADD_REST:
- REORDER:

#### Regenerate / Revision
- API:
- reason:
- snapshot:
- version:
- validation:

#### Confirm
- API:
- blocking 규칙:
- 상태 변경:

### 생성 파일
- ...

### 수정 파일
- ...

### Transaction
- ...

### DB 변경
- Migration:
- Schema:

### 테스트
- 기존 테스트: 179
- 신규 테스트:
- 총 collected:
- passed:
- failed:
- errors:
- warnings:

### 남은 Task 10 항목
- 없으면 `없음`

### Task 10 완료 여부
- 완료 / 미완료

### Task 11 시작 가능 여부
- 가능 / 불가능

Task 11은 시작하지 마세요.
