# 장소 이미지 인식 정확도 벤치마크

기존 백엔드의 **실제 HTTP 응답**을 평가합니다. 새 AI 판정이나 별도 Gemini/Kakao 호출은 하지 않습니다. Python 표준 라이브러리만 사용하므로 기존 backend Python/가상환경에서 추가 설치 없이 실행할 수 있습니다. 100장 이상을 순차 처리하며, 소량 점검도 가능합니다.

## 1차 평가 세트 원칙

1차 실험은 10개 관광지에서 각 12장, 총 120장으로 구성합니다. 각 관광지는 `landmark_full` 3장, `detail` 2장, `distant` 2장, `occluded`·`crowded`·`night` 각 1장, `tv_recapture` 2장입니다. `collection_plan.csv`는 이 수집 계획을 관리하는 파일이며, 실제 API 입력 파일인 `manifest.csv`와 구분합니다. 사진 수집 후 계획 행의 `image_path`, `source_note`, `collected`를 채우고, 실제로 확인된 `planned_place_id`를 바탕으로 manifest를 작성합니다.

Top-1과 Top-4를 평가합니다. 세부 장소 사진은 해당 세부 장소와 직접 상위 관광지까지만 정답이며, 같은 관광지의 형제 장소는 오답입니다. `tv_recapture`는 전체 결과와 별도로 촬영 유형별 결과에서 분석합니다.

`places.json`의 `accepted_names`는 **실험 전 고정한 정답 사전**입니다. 실행 결과가 기대와 다르다는 이유로 실행 후 alias를 추가해 정확도를 높이면 안 됩니다. 추가 alias가 필요한 근거가 발견되면 다음 실험을 위한 사전 변경으로 기록하고, 새 버전의 정답 사전으로 별도 실행하세요.

## 1. 이미지 넣기

이 폴더의 `images/`에 직접 확보한 사진을 넣습니다. JPEG(`.jpg`, `.jpeg`), PNG, WebP를 지원하며 파일당 **10 MiB 이하**, 빈 파일은 허용하지 않습니다. 하위 폴더도 사용할 수 있습니다. 파일 확장자에 맞는 실제 이미지여야 합니다. 벤치마크는 이미지를 변환하거나 내용의 유효성을 검사하지 않습니다.

포함된 manifest는 예시 3건이며 실제 사진은 포함하지 않습니다. 예시 이름에 맞는 사진을 넣거나, 실제 파일 이름과 정답에 맞게 manifest를 바꾸세요. 100장 평가라면 100개 이상의 행을 작성합니다. 같은 사진을 반복 등록하면 지표가 편향될 수 있습니다.

`images/`, `results/` 내부 파일은 이 폴더의 `.gitignore`에서 제외합니다(`.gitkeep` 제외). manifest, 정답 JSON, 문서, 스크립트, 테스트는 추적 가능합니다.

## 2. places.json 작성

`place_id`마다 세부 장소, 상위 장소와 **허용할 모든 이름**을 지정합니다.

```json
{
  "gyeongbokgung_geunjeongjeon": {
    "detail_name": "근정전",
    "parent_name": "경복궁",
    "accepted_names": ["근정전", "경복궁", "Geunjeongjeon", "Gyeongbokgung", "Gyeongbokgung Palace"]
  }
}
```

`detail_name`, `parent_name`은 표시용입니다. 자동으로 정답 목록에 추가되지 않으므로 인정할 이름은 반드시 `accepted_names`에 넣으세요. 독립 장소라면 두 표시 이름을 동일하게 적어도 됩니다. 상위 장소는 실제 계층상 올바른 경우에만 직접 등록합니다.

근정전 사진에서 `근정전`, `경복궁`, 등록한 영어 alias는 정답입니다. `경회루`, `창덕궁`은 오답입니다. 같은 관광지의 형제 장소를 자동 인정하지 않습니다. 영문/한글 번역, 부분 문자열, fuzzy matching을 사용하지 않습니다.

이름 비교와 후보 중복 제거는 양끝 공백 제거, `casefold()`, 공백과 다음 구분문자 제거만 수행합니다: `- ‐ ‑ – — _ . , · / \ : ; ( ) [ ] { } ' " ’`. 그 밖의 문자/숫자는 보존합니다. 예를 들어 `Gyeongbokgung-Palace`와 `gyeongbokgung palace`는 같지만 `경복궁역`과 `경복궁`은 다릅니다. 서로 다른 alias는 정답으로 인정할 수 있어도 정규화 결과가 다르면 별도 후보로 유지됩니다.

## 3. manifest.csv 작성

UTF-8 CSV를 사용합니다(Excel용 BOM도 허용). 첫 행은 다음과 같습니다.

```csv
image_id,image_path,place_id,capture_type,note
001,images/gyeongbokgung_001.jpg,gyeongbokgung_geunjeongjeon,landmark_full,근정전 전경
002,images/gyeongbokgung_002.png,gyeongbokgung_geunjeongjeon,tv_recapture,TV 화면 재촬영
003,images/gyeonghoeru_001.webp,gyeongbokgung_gyeonghoeru,night,경회루 야경
```

- `image_id`: 중복 없는 문자열. `001` 같은 앞자리 0을 보존합니다.
- `image_path`: **manifest 파일이 있는 폴더 기준** 상대 경로 또는 절대 경로.
- `place_id`: places.json에 등록한 키.
- `capture_type`: `landmark_full`, `detail`, `distant`, `occluded`, `night`, `crowded`, `tv_recapture` 등. 다른 이름도 허용하며 같은 값끼리 집계합니다.
- `note`: 선택 메모. 빈 값도 허용하지만 컬럼은 필요합니다. 쉼표가 있는 값은 CSV 규칙대로 큰따옴표로 감쌉니다.

실행 전에 전체 manifest와 파일을 검사합니다. 누락 파일, 빈/과대 파일, 중복 ID, 알 수 없는 정답 ID는 API 호출 전에 오류로 중단하여 잘못된 데이터셋으로 통계를 만들지 않습니다.

## 4. 백엔드 실행 및 인증

저장소에서 확인한 계약:

| 항목 | 실제 코드 기준 |
| --- | --- |
| HTTP API | `POST /api/v1/discovery/scene-image` |
| 업로드 필드 | multipart `file` |
| 분석 옵션 | multipart `analyze=true` (기본 false이므로 필수 전송) |
| 인증 | `Authorization: Bearer <access_token>` 필수 |
| 사용자 조건 | 유효한 JWT, DB에 존재하는 ACTIVE 사용자 |
| 후보 | `primary_candidate.place_name`, `candidates[].place_name` |
| 기타 결과 | `recognized`, `confidence`, `place_verified`, `verified_place` |
| 오류 형식 | `{"error":{"code":"...","message":"..."}}` |

근거 파일: `backend/app/main.py`, `backend/app/api/v1/discovery.py`, `backend/app/dependencies.py`, `backend/app/schemas/scene_image.py`, `backend/app/services/scene_image_service.py`, `backend/app/services/external/scene/gemini_provider.py`.

PowerShell에서 저장소 루트 기준으로 실행합니다. 아래 `.venv`는 예시이며 이미 사용하는 backend Python 경로가 다르면 그 경로로 바꾸세요. 새 환경이 필요한 경우에만 다음을 실행합니다.

```powershell
cd C:\dev\dx-all\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

백엔드 `backend/.env`에 기존 DB/JWT 설정을 유지하고 실제 provider 설정을 확인하세요. **기본 provider는 mock**이므로 실제 AI 정확도를 평가하려면 아래 real 설정이 필요합니다.

```dotenv
SCENE_RECOGNITION_PROVIDER=real
PLACE_PROVIDER=real
GEMINI_API_KEY=실제_키
GEMINI_MODEL=사용할_모델_ID
KAKAO_REST_API_KEY=실제_키
```

`GEMINI_FALLBACK_MODEL`은 기존 서비스가 지원하는 선택 설정입니다. MySQL 접속 설정과 `JWT_SECRET_KEY`, 기존 DB 준비도 필요합니다. 실제 비밀값을 manifest/정답/결과에 적지 마세요. 벤치마크는 서버의 provider 모드를 판별할 수 없으므로 실행자가 real 설정을 확인해야 합니다.

```powershell
# backend 디렉터리에서 기존 환경으로 서버 실행
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

다른 터미널에서 기존 앱 로그인 또는 `http://127.0.0.1:8000/docs`의 `POST /api/v1/auth/login`으로 기존 계정에 로그인하고 응답의 `access_token`을 준비하세요. 로그인 요청 필드는 `login_id`, `password`입니다. JWT는 만료되므로 긴 실행에서 401이 발생하면 새 토큰을 받아 다시 실행하세요. 도구는 자동 로그인/토큰 갱신을 하지 않습니다.

## 5. 벤치마크 실행

저장소 루트의 새 PowerShell 터미널에서:

```powershell
cd C:\dev\dx-all
$env:BENCHMARK_API_URL = "http://127.0.0.1:8000"
$env:BENCHMARK_ACCESS_TOKEN = "로그인에서_받은_access_token"

# 먼저 데이터셋 검사만 수행 (토큰/서버 불필요)
.\backend\.venv\Scripts\python.exe benchmarks/scene_place_accuracy/run_benchmark.py --validate-only

# 전체 평가
.\backend\.venv\Scripts\python.exe benchmarks/scene_place_accuracy/run_benchmark.py
```

`BENCHMARK_API_URL`은 호스트/기본 경로만 넣고 `/api/v1/discovery/scene-image`는 붙이지 않습니다. 미설정 기본값은 `http://127.0.0.1:8000`입니다. `BENCHMARK_ACCESS_TOKEN`에는 `Bearer ` 접두사 없이 토큰만 넣습니다. 환경변수는 실행한 터미널에 설정하세요. 스크립트 자체는 `.env`를 읽지 않습니다. 표준 Python만으로도 실행 가능합니다.

추가 옵션:

```powershell
python benchmarks/scene_place_accuracy/run_benchmark.py --manifest benchmarks/scene_place_accuracy/manifest.csv --places benchmarks/scene_place_accuracy/places.json --timeout 240 --retries 2 --retry-delay 2
```

`--results`로 출력 폴더를 바꿀 수 있습니다. 기본값은 스크립트 옆 `results/`이고 다른 위치를 지정하면 그 위치의 Git 제외 여부를 별도로 확인해야 합니다. `--manifest`, `--places`, `--results`의 상대 경로는 실행 디렉터리 기준입니다. 옵션을 생략하면 어디에서 실행해도 기본 예시 파일을 찾습니다.

429/503에만 기본 최대 2회 추가 재시도합니다(총 3회, `--retries 0`으로 비활성화, 최대 5회). 지연은 기본 2초, 4초 순으로 증가하며 30초 상한입니다. 다른 HTTP 오류, 네트워크 오류, 잘못된 JSON은 재시도하지 않습니다. `--timeout`은 소켓 타임아웃입니다. `elapsed_seconds`는 재시도/대기를 포함한 이미지 전체 시간입니다. 백엔드 내부 Gemini 재시도/fallback은 별개이며 API 응답에 내부 횟수가 없으므로 이 도구의 `retry_count`는 **HTTP 재호출 횟수만** 뜻합니다. 재시도는 추가 외부 API 호출/비용을 발생시킬 수 있습니다.

진행 예:

```text
[12/120] gyeongbokgung_012.jpg -> Top1 FAIL / Top4 PASS
[13/120] gyeongbokgung_013.jpg -> API FAIL (GEMINI_UNAVAILABLE) / accuracy excluded
```

## 6. 결과 해석

동일 UTC timestamp로 다음 파일을 만듭니다.

- `*_details.csv`: 이미지별 결과. Excel에서 한글이 보이도록 UTF-8 BOM 사용.
- `*_summary.json`: 전체/장소별/촬영 유형별 지표와 해당 실행의 정답 목록, manifest, 호출 옵션.
- `*_responses.jsonl`: HTTP 시도마다 이미지 ID, 시도 번호, HTTP 상태, 오류 코드, 응답 본문 문자열. 실패/재시도 응답도 보존. 요청 토큰/헤더/이미지 바이트는 저장하지 않습니다.

CSV의 `primary_candidate`는 API의 실제 primary 이름입니다. `ordered_candidates`는 primary 뒤에 candidates를 붙여 이름 정규화로 중복 제거한 뒤 앞의 최대 4개를 담은 JSON 배열입니다. `candidate_2`~`candidate_4`는 그 배열의 두 번째~네 번째 이름입니다. `verified_place`는 Kakao 검증 객체 전체를 JSON 문자열로 보존합니다. 원본 candidates와 evidence 등은 responses 파일에서 확인할 수 있습니다.

| 지표 | 계산 |
| --- | --- |
| API Success Rate | 유효한 분석 응답 수 / 전체 이미지 수 |
| Top-1 Accuracy | primary가 accepted_names에 속하는 수 / 유효한 분석 응답 수 |
| Top-4 Hit Rate | 최대 4개 고유 후보 중 정답이 있는 수 / 유효한 분석 응답 수 |
| Miss Rate | Top-4에 정답이 없는 수 / 유효한 분석 응답 수 |
| E2E Top-1/Top-4 | 해당 정답 수 / 전체 이미지 수 |

summary 비율 값은 0~1 범위이며 콘솔은 백분율입니다. 분모가 0이면 JSON `null`, 콘솔 `N/A`입니다. `by_place`, `by_capture_type`도 각 그룹 내부의 같은 분모 규칙을 사용하며 이미지 수, API 성공/실패, E2E 지표를 포함합니다. 전체 지표는 이미지 단위 집계입니다.

`recognized=false`는 정상 API 성공이지만 Top-1/Top-4 모두 오답입니다. 429/503/401 등 HTTP 오류와 네트워크 오류는 API 실패이고 정확도 분모에서 제외합니다(CSV 정답 칸은 빈 값). 2xx라도 JSON 오류, `recognized` 누락, 후보 형식 오류 같은 평가 불가능 응답은 `INVALID_RESPONSE`로 API 실패 처리합니다. 재시도 후 성공하면 해당 이미지는 API 성공 1건으로 셉니다.

Kakao `place_verified=false`만으로 오답 처리하지 않습니다. 백엔드는 Kakao 오류를 보조 검증 실패로 처리하여 Gemini 결과를 유지하므로 이 경우도 API 성공입니다. `verified_place`를 primary와 바꾸거나 정답 후보에 추가하지 않습니다. Gemini primary + 최대 3개 candidates 구조를 그대로 평가하며 중복이 있으면 실제 평가 후보가 4개 미만일 수 있습니다.

일부 API가 실패해도 나머지 이미지를 계속 평가하며 결과 생성 후 종료 코드 1을 반환합니다. 모두 API 성공이면 정확도와 무관하게 0, 입력 오류는 2입니다. 중간 강제 종료 시 이미 기록한 CSV/응답은 남지만 summary는 완료 시 생성합니다. 자동 이어하기는 제공하지 않습니다.

## 오프라인 테스트

```powershell
python -m unittest discover -s benchmarks/scene_place_accuracy -p "test_*.py" -v
```

외부 API, DB, 사진 없이 임시 바이트와 로컬 HTTP 모의 서버로 120행 처리, multipart 필드/MIME/인증 헤더, 재시도와 실패 분리, 후보 순서/중복/상한, 부모/alias/형제 판정, 그룹별 집계, 결과 저장을 검증합니다. 이 테스트는 실제 사진 인식 정확도나 실제 Gemini/Kakao 연결 성공을 보장하지 않습니다.
