# Phase 3B 1차분: 후보 장소 공급·품질 개선 (2026-10-11)

이번 작업에서 Ollama·Kakao를 실제로 호출하지 않았고 MySQL80에도 접근하지 않았습니다. 프롬프트, Flutter API 응답 스키마, Preview/Approve, Revision 코드는 그대로입니다.

## 1. 현재 흐름 (`PlanGenerationService._input` → `_candidate_places`)
1. Anchor 주변 DB 캐시를 모으고, 이어서 목적지 전체 DB 캐시를 place_id 순서로 붙입니다(`_database_candidates`).
2. 날짜가 맞지 않는 행사를 제외합니다.
3. 후보가 `desired_count = max(2, 일수×2)`보다 적을 때만 Kakao 주변 검색과 도시 전체 검색("관광지·문화시설·맛집·카페")을 합니다.
4. 비음식 후보가 일수×2보다 적으면 관광지 검색으로 보충합니다(`_activity_backfill`).
5. 같은 위치의 중복을 제거하고, 경로 정보가 있으면 이동 제약으로 거릅니다(`_mobility_candidates`). 현재 route_provider가 unavailable이라 이 단계는 사실상 아무것도 거르지 않습니다.
6. `_balanced_candidate_pool`에서 최대 15곳을 고릅니다. 관광지를 먼저 예약하고, 그다음 식당·카페, 남은 관광지 순서입니다.
7. `_rank_for_interests`로 관심사 카테고리가 일치하는 후보를 앞으로 보냅니다(안정 정렬).
8. EXAONE은 후보 목록 안에서만 고르고, 중복이 나오면 provider가 보정하거나 재시도합니다(Phase 3A).

## 2. 확인된 문제
| # | 문제 | 부산 68에 미친 영향 |
|---|---|---|
| A | 보충 검색 조건이 후보 개수뿐 | 2일 일정이면 목표가 4곳이라 DB 8곳으로 이미 충족되어 Kakao 검색을 하지 않았습니다. |
| B | 권역과 유형을 보지 않음 | 비음식 6곳이 모두 광안리 반경 2km 안에 있어도 "충분"으로 판정했습니다. |
| C | 식당 목표가 없음 | 점심·저녁 4끼에 식당이 2곳뿐이었고, 그 결과 1일차 점심이 누락됐습니다. |
| D | 예약 순서가 place_id 순 | 관광지 예약분이 한 권역에서 먼저 채워졌습니다. |
| E | 취향 미반영 | travel_style과 rest_frequency가 후보 수에 영향을 주지 않았습니다. |
| F | 중복 대체 시 거리 미확인(3A) | 첫 미사용 후보로 바꾸기 때문에 먼 장소가 들어갈 수 있었습니다. 10.0km 구간이 여기서 생겼을 가능성이 있습니다(추정). |
| G | 후보 부족이어도 정상 생성 | 생성은 되고 경고만 남아서, 평가에서 품질 문제와 공급 문제를 구분할 수 없었습니다. |

## 3. 1차분 구현
| 개선 | 위치 |
|---|---|
| 목표 수 계산: 관광지는 일수×2(STANDARD는 ×3, 휴식 많음이면 ×2), 식당은 일수×2(FOOD_FOCUSED는 ×3), 권역은 2일 이상이면 2개 | `PlanGenerationService._candidate_targets` |
| 관광지 보충 조건에 권역 수 추가. 개수가 충분해도 권역이 모자라면 기존 검색어로 검색합니다 | `_activity_backfill(…, areas_needed)` |
| 식당 보충: 식당이 끼니 수보다 적으면 기존 공급자의 `search("맛집"/"음식점")`을 씁니다. 실제 검색 결과 중 식당이면서 목적지·사용 가능 조건과 날짜를 통과한 곳만 넣습니다 | `_meal_backfill` |
| 권역별 교차 배치: 반경 2km로 권역을 묶은 뒤 번갈아 예약합니다. 식당은 끼니 수만큼 카페보다 먼저 예약합니다 | `_interleave_by_area`, `_balanced_candidate_pool` |
| 공급 진단: 목표, 부족분(관광지·식당·권역), 문제 코드(`RESTAURANTS_FEWER_THAN_MEALS` 추가) | `plan_quality_rules.candidate_supply`, 로그 `plan_candidate_supply … shortfall=` |
| 중복 대체 보수화: 앞뒤 일정과의 직선거리가 5km(보행 LOW 2km, VERY_LOW 1km) 이내이거나 원래 장소보다 멀지 않은 후보만 씁니다. 그중 가장 가까운 곳을 고르고, 좌표가 없는 후보는 제외합니다. 맞는 후보가 없으면 AI 재시도로 넘어갑니다 | `ExaonePlanGenerationProvider._repair_duplicates` |
| 평가기 후보 모드: `export`(과거 장소만), `fixture`(합성 데이터로 보충, Mock 전용), `kakao`(실제 Kakao로 보충, 사용자 실행). 후보가 부족하면 80점 판정을 하지 않습니다(`supply_ok`) | `evaluate_initial_plan_generation.py`, `.ps1 -Candidates` |

- 장소, 영업시간, 이동시간은 어디서도 만들어 내지 않습니다. 거리는 저장된 좌표의 직선거리일 뿐이며, 이동시간으로 환산하지 않습니다.
- 후보가 부족해도 API는 기존처럼 일정을 만들고 경고를 냅니다. Flutter 계약을 지키기 위해서입니다. 대신 부족 원인과 부족분은 로그와 평가 보고서에 남기고, 평가에서는 합격 처리하지 않습니다.

## 4. Mock 결과 (격리 MySQL, 가짜 Ollama, 1차 응답에 일부러 중복 포함)
| 대상 / 후보 모드 | 모델에 전달 | 관광 / 식당 / 권역 | 공급 판정 | 중복 처리 | v2 |
|---|---|---|---|---|---|
| 부산 export | 8 | 6 / 2 / 1 | 부족(한 권역, 식당 2<4) | 1회 호출로 보정(가장 가까운 310) | 66.0 |
| 부산 fixture | 15 | 10 / 5 / 4 | 충분 | 1회 호출로 보정 | 72.0 |
| 제주 export | 8 | 1 / 6 / 1 | 부족(관광 1<3, 한 권역) | 보정 불가 → 재시도 | 61.7 |
| 제주 fixture | 14 | 7 / 6 / 7 | 충분 | 5km 안에 대체 후보가 없어 재시도(보수 규칙대로 동작) | 68.0 |

fixture 장소는 이름에 [가상]이 붙은 합성 데이터이고, 점수는 Mock 응답에 대한 값입니다. 따라서 위 점수는 품질 결과가 아닙니다. 결과 파일은 `docs/initial_plan_eval/20261011_2037*_mock_*`에 있습니다.

## 5. 테스트
- 백엔드 테스트 593개 통과(MySQL 통합 제외). Phase 3B 새 테스트 9개가 포함됩니다(`tests/unit/test_phase3b_candidate_supply.py`).
  - 취향별 목표 수
  - 권역 교차 배치
  - 끼니 수만큼 식당 예약
  - 한 권역일 때 추가 검색
  - 식당 부족 시에만 검색
  - 공급자 없을 때 부족분 보고
  - 가장 가까운 대체 후보 선택
  - 먼 후보만 있으면 재시도
  - 보행 허용에 따른 반경 축소
- 격리 MySQL 통합 테스트 12개 통과: Preview·Approve·Revision·Anchor·롤백·Flutter HTTP 계약.

## 6. 남은 사항 (다음 단계)
- 실제 Kakao 검색 결과가 다른 권역의 장소를 얼마나 돌려주는지 확인해야 합니다. 검색어는 아직 목적지 전체 단위입니다. 권역(구·읍면)을 지정한 검색은 다음 단계에서 합니다.
- 운영 환경에서는 Kakao 검색 호출이 늘어납니다. 권역 부족일 때 관광지 검색이 최대 4회, 식당 부족일 때 식당 검색이 최대 2회 추가됩니다.
- 후보 부족을 사용자 화면에 경고로 보여주는 기능은 API 응답 문구가 바뀌므로 별도로 결정해야 합니다.
- 휴식 선호와 보행 허용을 품질 경고 기준값(연속 관광 수 등)에 반영하는 작업이 남았습니다.
- 실제 이동시간 연동이 필요합니다. 현재는 UNKNOWN을 유지합니다.

## 7. 실행 명령 (PowerShell)
```powershell
cd C:\dev\dx-all\backend
python -B -m pytest tests -q -p no:cacheprovider -m "not mysql_integration"
.\scripts\run_task74c_isolated_mysql.ps1 -SkipUnit
.\scripts\run_initial_plan_eval_isolated_mysql.ps1 -Trip Busan -Provider Mock -Candidates Export
.\scripts\run_initial_plan_eval_isolated_mysql.ps1 -Trip Busan -Provider Mock -Candidates Fixture
# 실제 EXAONE (사용자 실행)
.\scripts\run_initial_plan_eval_isolated_mysql.ps1 -Trip Busan -Provider Real -Candidates Export -AiTimeoutSeconds 300
.\scripts\run_initial_plan_eval_isolated_mysql.ps1 -Trip Busan -Provider Real -Candidates Kakao -AiTimeoutSeconds 300
```
`-Candidates Kakao`는 실제 Kakao 검색을 호출합니다. 로컬 `.env`의 Kakao 키를 사용하고, 검색 결과는 격리 DB에만 저장됩니다.

## 8. 변경 파일
- `backend/app/services/plan_generation_service.py`
- `backend/app/services/plan_quality_rules.py`
- `backend/app/services/external/ai/exaone_plan_provider.py`
- `backend/scripts/evaluate_initial_plan_generation.py`
- `backend/scripts/run_initial_plan_eval_isolated_mysql.ps1`
- `backend/scripts/fixtures/phase3b_synthetic_places.json` (신규, 합성 데이터)
- `backend/tests/unit/test_phase3b_candidate_supply.py` (신규)
- `backend/tests/unit/test_phase3a_plan_quality.py` (공급 진단 기대값 갱신)
