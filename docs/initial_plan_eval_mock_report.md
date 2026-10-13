# 초기 일정 생성 평가 스크립트: Mock 검증 결과 (2026-10-11)

## 추가한 파일
- `backend/scripts/run_initial_plan_eval_isolated_mysql.ps1`: 격리 MySQL 실행기. task74c 스크립트와 구조가 같습니다.
- `backend/scripts/evaluate_initial_plan_generation.py`: 시드, 생성, 채점, 저장을 맡습니다.
- `.gitignore`: `.initial_plan_eval_mysql/` 추가

서비스 코드와 프롬프트는 바꾸지 않았습니다.

## 격리 보장
- 실행 전에 MySQL80 서비스의 my.ini를 읽기 전용으로 확인합니다. 포트가 3306이거나 운영 포트와 같으면, 또는 datadir가 운영 datadir 안에 있으면 중단합니다.
- 실행할 때마다 `.initial_plan_eval_mysql\<UUID>`에 새 mysqld를 띄웁니다. 127.0.0.1에서 34000~34999 포트만 씁니다.
- 연결 뒤에는 `@@port`, `@@datadir`, `DATABASE()`, `CURRENT_USER()`를 확인합니다. Python 쪽에서도 URL, datadir 경로, 앱 MYSQL_* 설정, 실제 서버 값을 다시 확인하고, 하나라도 다르면 종료 코드 3으로 끝냅니다. 실행기 없이 직접 실행했을 때 중단되는 것도 확인했습니다.
- 정리할 때는 자기 pid-file에 적힌 mysqld만 종료하고, 자기 UUID 폴더만 삭제합니다.
- Kakao 장소 검색은 끕니다(place_provider=None). route_provider는 unavailable입니다.

## Mock 실행 결과
| 대상 | 결과 | 생성시간 | 자동 점수 | 경고 | Critical | 기존 일정 자동 점수 |
|---|---|---|---|---|---|---|
| 제주 67 | 성공 | 42ms | 65.0 | 4 | 0 | 57.7 (수동 47) |
| 부산 68 | 성공 | 39ms | 80.5 | 5 | 0 | 67.0 (수동 54) |

Mock 점수는 결정적 초안으로 계산한 값이라 품질 판단에 쓰지 않습니다. 현재 규칙으로 기존 67을 다시 계산하면 경고가 11건이고, 사용자 보고와 같습니다.

결과 파일: `docs/initial_plan_eval/<시각>_<trip>_<mode>/result.json`, `result.md`

## 한계
1. export에는 기존 일정에 쓰인 장소(제주 9곳, 부산 8곳)만 있습니다. 당시 전체 후보 목록이 없어서 후보 풀이 기존과 같지 않습니다.
2. 자동 점수는 리뷰 6.3 기준의 근사치입니다. 기존 일정에서 수동 점수보다 약 10~13점 높게 나왔으므로, 80점 판정은 수동으로 다시 확인해야 합니다.
3. 장소 실존, 영업시간, 이동시간은 검증 불가로 감점합니다. 정상으로 처리하지 않습니다.
4. Real 모드의 Ollama 통계 기록은 가짜 응답으로만 확인했고, 실제 호출은 하지 않았습니다.
5. 이 PC에는 2026-10-09에 시작된 `.task71_mysql` mysqld 2개가 아직 떠 있습니다. 이번 작업과는 무관하며 건드리지 않았습니다.

## 실제 실행 (사용자가 직접)
```powershell
cd C:\dev\dx-all\backend
.\scripts\run_initial_plan_eval_isolated_mysql.ps1 -Trip Jeju -Provider Real -AiTimeoutSeconds 300
```
부산은 `-Trip Busan`으로 실행합니다. 기본 timeout은 .env 값(180초)을 씁니다. 3일 일정은 180초를 넘을 수 있어서 300초를 권장합니다.
