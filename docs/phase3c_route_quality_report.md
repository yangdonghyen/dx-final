# Phase 3C: 권역별 일정 묶기·식당 위치 최적화·시니어 휴식 (2026-10-12)

이번 작업에서는 Ollama와 Kakao를 호출하지 않았고 MySQL80에도 접근하지 않았습니다. 프롬프트와 AI 출력 구조는 그대로 두었습니다. 품질 v2 기준도 바꾸지 않았고, 새 점수 기준이 필요하지 않아 v3는 만들지 않았습니다.

## 1. 기존 흐름 확인 결과
| 단계 | 코드 | 확인 내용 |
|---|---|---|
| 후보 수집 | `_candidate_places` → DB 캐시, Kakao 주변·도시 검색, `_activity_backfill`, `_meal_backfill` | |
| 후보 선별 | `_balanced_candidate_pool`(15곳), `_rank_for_interests` | 3B의 권역 균형은 **후보 순서와 구성에만** 영향을 줍니다. |
| 일자·권역 배정 | **없음** | 어떤 장소를 며칠째에 넣을지는 EXAONE이 정하고, 서버는 날짜별 배정을 하지 않았습니다. |
| EXAONE 생성 | `ExaonePlanGenerationProvider` | 중복 장소 보정(3A·3B) |
| 후처리 | `_prepare_draft`(Anchor 보존, 식사 슬롯 보정, 점심 보충) | |
| 이동 검증 | `_adjust_route_timing`, `_validate_route_timing` | route_provider가 unavailable이라 모든 구간이 UNKNOWN입니다. |
| 저장 | `plans.create`, `items.create`, `validation.validate` | |

- **권역 수 계산:** `candidate_supply`의 권역 수는 **관광지만으로** 계산합니다. 식당은 포함하지 않습니다.
- **식당 선정:** 지금까지는 관광 동선과 관계없이 검색·DB 순서로 정해졌습니다. 그래서 부산 1일차 점심이 광안리에서 5.5km 떨어진 동구 신선식당이 됐습니다.
- **REST/FREE_TIME:** 모델이 넣은 값이 그대로 남습니다. 서버는 중복 장소나 장소 없는 PLACE만 FREE_TIME으로 바꿉니다. rest_frequency는 프롬프트와 후보 수(3B)에만 반영됐고, 일정 배치에는 쓰이지 않았습니다.

## 2. 구현 (첫 생성에만 적용, Preview/Revision 경로는 변경 없음)
| 개선 | 위치 | 동작 |
|---|---|---|
| 일자별 권역 묶기 | `plan_route_optimizer.optimize_routes` | 모델이 만든 칸끼리 장소를 맞바꿉니다(관광↔관광, 식당↔식당, 카페↔카페). 날짜가 달라도 바꿀 수 있습니다. 하루 직선 경로 합이 500m 이상 줄고, 가장 긴 구간이 길어지지 않을 때만 바꿉니다. 칸의 시간은 그대로이므로 식사시간, 하루 시작·끝 시각, 날짜는 바뀌지 않습니다. |
| 식당 위치 최적화 | 같은 모듈의 replace 이동, `_restaurants_by_area`, `_area_meal_backfill` | 식사 칸에 그날 관광지와 가까운 미사용 식당을 넣습니다. 후보 단계에서는 관광 권역마다 3km 안의 식당을 먼저 확보합니다. 근처에 식당이 없는 권역은 기존 공급자로 "<구> 맛집"을 검색합니다(최대 3개 권역). 그래도 없으면 바꾸지 않고 `far_meals`로 보고합니다. |
| 시니어 휴식 | `insert_rest_breaks`, `rest_policy` | 사용자가 정한 취향만 근거로 씁니다(rest_frequency, travel_style SLOW, walking_tolerance VERY_LOW/LOW). 긴 관광 방문(90분 또는 150분 이상)의 끝 30분을 휴식으로 바꿉니다. 하루 1회(HIGH는 2회)이고, 관광지 사이에 오는 칸을 우선합니다. 이미 REST가 있는 날, Anchor, 방문 시간이 60분 아래로 줄어드는 경우는 건드리지 않습니다. 휴식 시설 여부는 확인하지 않았다고 문구에 적습니다. FREE_TIME 칸의 이름만 REST로 바꾸는 일은 하지 않습니다. |
| 안전 검증 | `PlanGenerationService._optimize_routes`, `_checked` | 보정한 초안이 모델 초안과 같은 검증(초안·영업시간·행사 날짜·활동 다양성)을 통과해야 하고, 품질 경고가 늘지 않아야 채택합니다. 하나라도 어기면 원래 초안을 씁니다(`reverted` 기록). Anchor, 행사, 검증된 영업시간과 맞지 않는 칸은 처음부터 이동 대상에서 뺍니다. |
| 위험 표시 | 평가기 `route_risk` | 구간마다 직선 km, 일정 간격(분), 실측 여부를 표시합니다. 5km를 넘거나 간격에 비해 먼 구간은 "확인 필요"로 표시합니다. 직선거리는 순서를 정하는 데만 쓰며, 이동시간으로 환산해 저장하지 않습니다. |
| Replay 평가 | `-Provider Replay -ReplayResult <result.json>` | 저장된 실제 EXAONE 일정을 네트워크 없이 다시 입력해서, 후처리 전후를 실제 데이터로 비교합니다. |

## 3. 수정 전후 (부산 2일, Phase 3B 실제 EXAONE + Kakao 결과를 Replay)
후보 풀은 실제 실행과 같게 다시 계산됐습니다(15곳: 관광 7, 식당 8, 권역 7).

| 항목 | 수정 전 (실제 결과) | 수정 후 |
|---|---|---|
| 하루 직선 경로 합 | 57.1km | **21.2km** |
| 가장 긴 구간 | 19.8km | 8.7km |
| 5km 넘는 미검증 구간 | 4개 (5.5 / 9.3 / 13.4 / 19.8km) | 1개 (8.7km) |
| 품질 경고 | 5건 | 1건 (UNVERIFIED_LONG_LEG) |
| v2 점수 | 66.0 | **79.0** |
| v2 영역별 | 동선 12 → 16.5, 시니어·휴식 4 → 12.5 | |

일정 변화:
- **1일차:** 광안리 → ~~신선식당(동구)~~ **민락 국밥(1.4km)** → 해운대(2.3km). 광안리 방문 마지막 30분은 휴식입니다.
- **2일차:** 서쪽 권역(다대포·송도·감천)을 하루에 묶었습니다.
  - 이동 전: 송도 → 민락(동쪽, 13.4km) → 다대포(19.8km) → 감천 → 이재모피자
  - 이동 후: 다대포 → 이재모피자 점심 → 송도케이블카 → 감천 → 휴식 → 신발원 저녁
  - 민락 식당은 1일차로 옮겼습니다.
- **남은 감점:**
  - 다대포 → 점심 구간(직선 8.7km)이 남았습니다. 후보 15곳 중 다대포 3km 안에 식당이 없었기 때문입니다.
  - 모든 이동이 UNKNOWN이라, v2에서 이동시간 근거 점수는 9점 중 2점만 받습니다.
  - 영업시간을 확인할 수 없는 장소가 있습니다.

다른 회귀 데이터(3A 실제 부산, 광안리 한 권역만 있는 후보):
- 경로가 26.7km에서 25.7km로 조금 줄었고, v2는 58.5로 그대로입니다.
- 후보 자체가 한 권역이라 후처리로는 개선할 수 없습니다. 이 경우는 3B의 후보 보충이 필요합니다.

Mock fixture(합성 장소, 품질 결과 아님):
- 부산: 경로 32.2km → 28.7km, 권역 식당 검색 3회에서 2곳을 찾았습니다.
- 제주: 경로 242km → 139km. 3일 일정의 합성 장소가 제주 전역에 퍼져 있어 긴 구간이 남습니다.

## 4. 80점 목표에 대한 판단
- Replay에서 v2는 **79.0점으로 목표에 1점 모자랍니다.** 기준을 완화하거나 이동시간을 만들어 넣지 않았습니다.
- 다음 실제 실행에서는 새로 넣은 "권역 근처 식당 검색"이 후보 단계에서 작동합니다. 다대포·송도 근처 식당이 후보에 들어가면 남은 8.7km 구간이 줄 가능성이 있습니다(추정). Replay는 저장된 후보로만 돌기 때문에 이 효과를 보여줄 수 없습니다.
- 실측 이동시간(route provider) 없이는 동선 점수의 9점 중 7점을 받을 수 없습니다. 80점을 안정적으로 넘기려면 실제 경로 API 연동이 필요하다고 판단합니다.

## 5. 테스트
- 백엔드 테스트 **601개 통과**(MySQL 통합 제외). Phase 3C 새 테스트 8개가 포함됩니다(`tests/unit/test_phase3c_route_quality.py`).
  - 실제 부산 좌표에서 식당이 관광지 옆으로 이동하고 시간이 그대로인지
  - Anchor·행사·영업시간 불일치 칸을 옮기지 않는지
  - 근처 미사용 식당으로 바꾸는지
  - 먼 식당은 억지로 바꾸지 않고 보고하는지
  - 휴식이 취향에 따라 배치되는지 (LOW·Anchor·STANDARD 경우 포함)
  - 검증 실패 시 원래 초안으로 돌아가는지
  - 권역별 식당 순서가 맞는지
  - "<구> 맛집" 검색에서 먼 결과를 버리는지
- 격리 MySQL 통합 테스트 **12개 통과**: Preview·Approve·Revision·Anchor·롤백·Flutter HTTP 계약.
- 격리 MySQL Replay 2건과 Mock fixture 2건을 실행했고, 실행한 격리 인스턴스는 모두 정리했습니다.

## 6. 남은 위험
- **휴식 칸의 장소:** 휴식은 직전 장소에서 쉬는 것으로 배치했습니다. 그 장소에 쉴 곳이 있는지는 확인하지 않았습니다.
- **직선거리 기준:** 경로 최적화는 직선거리로만 판단합니다. 다리·터널·대중교통 노선 때문에 실제 이동은 다를 수 있습니다.
- **Kakao 호출 증가:** "<구> 맛집" 검색이 최대 3회 늘어납니다.
- **휴식으로 짧아지는 방문:** 긴 방문이 30분 짧아집니다. 사용자가 이를 원하지 않을 수 있습니다.
- **연속 관광 사이 휴식:** 이번에는 직접 넣지 않았습니다. 긴 방문의 끝 30분을 휴식으로 바꾸는 방식만 썼습니다.

## 7. 실행 명령 (PowerShell)
```powershell
cd C:\dev\dx-all\backend
python -B -m pytest tests -q -p no:cacheprovider -m "not mysql_integration"
.\scripts\run_task74c_isolated_mysql.ps1 -SkipUnit
# 실제 결과 재현 (네트워크 없음)
.\scripts\run_initial_plan_eval_isolated_mysql.ps1 -Trip Busan -Provider Replay -Candidates Export -ReplayResult C:\dev\dx-all\docs\initial_plan_eval\20261011_204539_busan_real_kakao\result.json
# 실제 EXAONE + Kakao 재평가 (사용자 실행)
.\scripts\run_initial_plan_eval_isolated_mysql.ps1 -Trip Busan -Provider Real -Candidates Kakao -AiTimeoutSeconds 300
```

## 8. 변경 파일
- `backend/app/services/plan_route_optimizer.py` (신규)
- `backend/app/services/plan_generation_service.py`
- `backend/scripts/evaluate_initial_plan_generation.py`
- `backend/scripts/run_initial_plan_eval_isolated_mysql.ps1`
- `backend/tests/unit/test_phase3c_route_quality.py` (신규)
