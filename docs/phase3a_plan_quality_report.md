# Phase 3A 결과 보고서: 중복 장소 보정과 일정 품질 검증 (2026-10-11)

Ollama와 Kakao는 실제로 호출하지 않았습니다. MySQL80과 사용자 여행 데이터도 건드리지 않았습니다. 프롬프트와 AI 출력 구조(스키마)는 바꾸지 않았습니다.

## 1. 문제 발생 위치 (조사 결과)
| 문제 | 위치 | 원인 |
|---|---|---|
| 중복 place_id → 재시도 약 66초 | `ExaonePlanGenerationProvider._parse` | 중복이 하나만 있어도 즉시 검증 실패가 나서 AI를 다시 호출했습니다. 서비스의 `_prepare_draft`에는 중복 처리 코드가 있지만, provider가 먼저 거절해서 실행될 일이 없었습니다. |
| 1일차 점심 누락 | `PlanGenerationService._repair_meal_slots` | 시간대가 틀린 식당만 바로잡고, 점심이 없는 날은 보정하지 않았습니다. 12:30 사진관 같은 관광지가 점심 자리에 그대로 남았습니다. |
| 관광 과밀, 연속 관광, 날짜 간 불균형 | `plan_quality_rules.review_day/review_plan` | 이 세 가지를 검사하는 규칙이 없었습니다. |
| 후보 부족, 한 권역 집중 | `_log_activity_shortage` | 후보 개수만 셌고, 유형이나 지역 분포는 보지 않았습니다. |
| 점수 과대평가 | `scripts/evaluate_initial_plan_generation.py` v1 | 서버가 어차피 맞춰 주는 항목(이름·유형)에 점수를 줬습니다. 관심사는 장소 이름으로도 인정했고, FREE_TIME을 휴식으로 쳤습니다. |

## 2. 적용한 개선
1. **중복 장소의 결정적 보정**: `exaone_plan_provider.py` `_repair_duplicates`, `_replacement_fits`
   - 첫 방문은 그대로 둡니다. Anchor도 첫 방문은 보존됩니다.
   - 두 번째 이후 방문은 같은 시간 칸에 아직 안 쓴 후보로 바꿉니다. 후보는 item_type과 activity_kind가 같아야 하고, 안 쓴 Anchor를 먼저 고른 뒤 후보 순서대로 고릅니다.
   - 시간은 그대로 두므로 시간 충돌이 생기지 않습니다.
   - 날짜가 있는 행사, 그리고 검증된 영업시간이 그 칸과 맞지 않는 장소는 대체 후보에서 뺍니다. 영업시간 정보가 없으면 정상이라고 가정하지 않고 UNKNOWN으로 둡니다.
   - 바꿀 후보가 하나라도 없으면 아무것도 바꾸지 않습니다. 기존처럼 `duplicate_place_id:...` 사유로 AI를 재시도하며, 재시도 프롬프트도 기존과 같습니다.
   - 보정 내역은 로그(`EXAONE duplicate place repaired`)와 `call_diagnostics[].repairs`에 남습니다.
2. **점심 누락 보정**: `plan_generation_service.py` `_repair_missing_lunch`
   - 대상은 일정이 점심 시간대(11:00~14:00) 전체에 걸쳐 있는데 점심이 없는 날입니다.
   - 아직 안 쓴 식당을 점심 시간대에 시작하는 칸에 넣습니다. 칸 길이는 120분 이하여야 합니다.
   - 빈 칸(REST/FREE_TIME)을 먼저 쓰고, 빈 칸이 없으면 Anchor가 아닌 관광지 칸을 씁니다. 관광지 칸은 그날 관광지가 2곳 이상일 때만 쓰고, 밀려난 관광지는 다시 미사용 후보로 돌아갑니다.
   - 영업시간이 맞지 않는 식당과 행사는 쓰지 않습니다. 쓸 식당이 없으면 그대로 두고 MISSING_LUNCH 경고가 남습니다.
3. **새 품질 경고**: `plan_quality_rules.py`
   - `CONSECUTIVE_SIGHTS`: 식사·카페·휴식 없이 관광지가 4곳 이상 이어지는 경우입니다.
   - `CROWDED_DAY`: 하루 관광 시간이 360분을 넘는 경우입니다.
   - `UNEVEN_DAYS`: 일정 길이가 6시간 이상인 날끼리 비교해 관광 시간이 180분 이상 차이 나는 경우입니다. 도착일·출발일처럼 짧은 날은 비교하지 않습니다.
   - 저장되는 이슈 유형은 기존 enum의 `OTHER`를 그대로 씁니다.
4. **후보 공급 진단**: `plan_quality_rules.candidate_supply`
   - 비음식 후보 수, 관광 유형 수, 권역 수(반경 2km 묶음), 문제 코드를 계산합니다. 문제 코드는 `SIGHTS_FEWER_THAN_DAYS`, `SIGHTS_BELOW_TWO_PER_DAY`, `SINGLE_AREA`, `SIGHTS_WITHOUT_COORDINATES`입니다.
   - 서비스 로그 `plan_candidate_supply`와 평가 보고서에 표시합니다.
   - 근거는 카테고리와 좌표뿐입니다. 장소의 성격이나 접근성은 추정하지 않습니다.
5. **평가기 v2**
   - v1 점수(`score`)는 그대로 두고 `score_v2`를 따로 계산합니다. 80점 판정은 v2 기준이고, v1 판정은 `passes_80_v1`에 남깁니다.
   - 과거 일정도 v1과 v2로 모두 다시 계산합니다.

## 3. 과거 일정 재계산 (같은 export, 같은 채점기)
| trip | 수동 점수(리뷰) | v1 | v2 | 경고(이전 규칙) | 경고(Phase 3A 규칙) |
|---|---|---|---|---|---|
| 제주 67 | 47 | 57.7 | **50.4** | 11 | 12 (UNEVEN_DAYS 추가) |
| 부산 68 | 54 | 67.0 | **58.0** | 5 | 6 (CROWDED_DAY 추가) |

v1은 수동 점수보다 10~13점 높았습니다. v2는 3~4점 높아서 차이가 줄었지만, 여전히 수동 점수보다 약간 높습니다.

## 4. 수정 전후 Mock 결과 (격리 MySQL, 가짜 Ollama)
Mock의 1차 응답은 일부러 같은 장소를 반복하도록 만들었습니다.

| 대상 | 수정 전 | 수정 후 |
|---|---|---|
| 제주 | 호출 2회 (1차 invalid → 재시도) | 호출 2회. 같은 종류의 미사용 관광지가 없어서 보정할 수 없었고, 기존 방식대로 재시도했습니다(의도한 동작). 진단 결과: 비음식 1곳, 권역 1개 → `SIGHTS_FEWER_THAN_DAYS`, `SINGLE_AREA`. v2 61.7 / v1 65.0 |
| 부산 | 호출 2회 (1차 duplicate_place_id:163 → 재시도) | **호출 1회**. 163번 중복을 306번(해파랑길)으로 보정했습니다. 진단 결과: 비음식 6곳, 유형 6개, 권역 1개 → `SINGLE_AREA`. v2 66.0 / v1 80.5 |

Mock 점수는 가짜 응답으로 계산한 값이라 품질 판단에 쓰지 않습니다. 결과 파일은 `docs/initial_plan_eval/20261011_201033_jeju_mock`, `20261011_201042_busan_mock`에 있습니다.

## 5. 회귀 테스트
- 백엔드 단위 테스트: `tests/unit` 556개 통과. Phase 3A 새 테스트 13개가 포함됩니다.
- 백엔드 전체 테스트(MySQL 통합 제외): 584개 통과.
- 격리 MySQL 통합 테스트 12개 통과: Preview·Approve·Revision·Anchor·롤백·Flutter HTTP 계약. 실행 스크립트는 `run_task74c_isolated_mysql.ps1 -SkipUnit`입니다.
- 새 테스트(`tests/unit/test_phase3a_plan_quality.py`)가 확인하는 내용:
  - 중복 보정 성공(호출 1회)
  - 보정 불가 시 재시도, 그리고 두 응답 모두 보정 불가면 거절
  - Anchor 첫 방문 보존과 안 쓴 Anchor 우선 선택
  - 영업시간이 맞지 않거나 날짜가 있는 후보 제외
  - 같은 날 중복 시 시간 유지
  - 점심 보정 성공, 쓸 식당이 없을 때 유지, Anchor와 영업시간 불일치 식당 미사용, 빈 칸 우선 사용
  - 연속 관광, 날짜 간 불균형, 도착일 예외
  - 후보 부족과 단일 권역 진단
- Flutter 코드는 바꾸지 않았고, API 응답 스키마도 같습니다. 바뀐 것은 경고 문구가 늘어날 수 있다는 점뿐입니다. Flutter 테스트는 이번에 다시 돌리지 않았습니다.

## 6. 여전히 검증이 필요한 사항
- 실제 EXAONE에서 중복이 얼마나 자주, 어떤 종류의 장소로 생기는지에 따라 보정 성공률이 달라집니다. 제주처럼 관광 후보가 1곳뿐이면 보정이 불가능하고 재시도가 그대로 일어납니다.
- 점심 보정 때문에 관광지가 하나 빠질 수 있습니다. 실제 일정에서 체감이 어떤지 확인해야 합니다.
- 이동시간은 route_provider가 unavailable이라 여전히 전부 UNKNOWN입니다. 직선 5.8km, 9.9km 구간도 경고만 남습니다.
- 장소의 실존 여부와 영업시간은 검증할 수 없어서 점수에서 보류했습니다.
- v2 기준과 연속 관광·과밀 기준값(4곳, 360분, 180분)은 시니어 사용자 기준으로 임의로 정한 초기값입니다. 사용자 취향 값(rest_frequency, walking_tolerance)에 따라 다르게 적용하는 것은 아직 하지 않았습니다.

## 7. 다음 단계로 분리
- 후보 보충: 권역과 유형 다양성을 기준으로 Kakao에서 추가 검색하는 기능
- AI 출력 구조와 프롬프트 변경
- 취향(휴식 빈도·보행 허용)에 따른 품질 기준 조정
- 실제 경로 이동시간 연동

## 8. 실제 EXAONE 재테스트 명령어 (사용자 실행)
```powershell
cd C:\dev\dx-all\backend
.\scripts\run_initial_plan_eval_isolated_mysql.ps1 -Trip Busan -Provider Real -AiTimeoutSeconds 300
.\scripts\run_initial_plan_eval_isolated_mysql.ps1 -Trip Jeju -Provider Real -AiTimeoutSeconds 300
```

## 9. 변경 파일
- `backend/app/services/external/ai/exaone_plan_provider.py`
- `backend/app/services/plan_generation_service.py`
- `backend/app/services/plan_quality_rules.py`
- `backend/scripts/evaluate_initial_plan_generation.py`
- `backend/tests/unit/test_phase3a_plan_quality.py` (신규)
- `backend/tests/unit/test_plan_quality_rules.py` (부산 기대값에 CROWDED_DAY 추가)
