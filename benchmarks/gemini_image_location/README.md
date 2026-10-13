# Gemini Image Location Accuracy Benchmark

## 목적

여행지 사진만을 입력으로 하여 Gemini가 실제 촬영 장소를 얼마나 정확히 식별하는지 측정하는 독립 실험입니다. 서비스 backend, frontend, DB를 사용하거나 변경하지 않습니다.

## 데이터 준비

`images/`에 평가 이미지를 넣고 `ground_truth.csv`에 한 이미지당 한 행을 작성합니다.

```csv
image_id,image_path,true_country,true_region,true_city,true_place,difficulty
001,images/001.jpg,대한민국,부산광역시,부산,해운대해수욕장,landmark
002,images/002.jpg,대한민국,서울특별시,서울,경복궁,landmark
```

필수 열은 `image_id,image_path,true_country,true_region,true_city,true_place,difficulty`입니다. `difficulty`는 `landmark`, `general`, `hard` 중 하나여야 합니다. `image_path`는 이 폴더 기준 상대 경로이며 JPG, PNG, WEBP 이미지를 지원합니다.

이미지 파일명에는 장소명을 넣지 마세요. 파일명은 모델에 보내지 않지만, 사람이 결과를 검토하거나 실험 코드를 변경할 때 정답 누출의 단서가 될 수 있습니다. 예를 들어 `001.jpg`처럼 중립적인 이름을 사용합니다.

## 실행

기존 프로젝트와 동일한 `GEMINI_API_KEY` 및 `GEMINI_MODEL` 설정을 사용합니다. 현재 셸에 값이 없으면 프로젝트의 `backend/.env`에서 같은 환경변수 이름을 읽습니다. 키 값은 출력하거나 결과 파일에 기록하지 않습니다.

```powershell
cd C:\dev\dx-all\benchmarks\gemini_image_location
python run_benchmark.py
```

`results.csv`가 있으면 이미 `success` 또는 `failure`로 처리된 `image_id`는 기본적으로 건너뜁니다. 실패 항목을 다시 요청하려면 `--retry-failed`를 사용하고, 모두 다시 실행하려면 `--force`를 사용합니다.

## 평가 지표

- Country / Region / City Accuracy: 성공 응답 가운데 해당 필드가 정답과 일치한 비율입니다.
- Exact Place Accuracy는 Gemini가 사진만 보고 실제 장소명을 정확히 식별한 비율이다.
- 문자열 비교는 앞뒤/내부 공백, 영문 대소문자, 기본 괄호·구두점만 제거합니다. 의미 기반 보정, fuzzy matching, LLM 판정은 하지 않습니다.
- difficulty별 Exact Place Accuracy도 성공 응답만을 분모로 별도 계산합니다.

API 실패는 정확도 분모에서 제외하며 전체·성공·실패 수를 함께 출력합니다. 따라서 API 실패가 많을 때 정확도만으로 모델 성능을 과대해석하면 안 됩니다. 작은 데이터셋, 정답 라벨의 표현 차이, 촬영 각도와 가시성도 결과에 영향을 줍니다.

YouTube 메타데이터 장소 단서 발견률 72.6%와는 서로 다른 실험이며 직접 비교하면 안 된다.
