# Task 11-A — Kakao Real Place Provider 구현 프롬프트

작업 경로:

`C:\dev\프로젝트백엔드`

현재 상태:

- Task 10 완료
- Provider mode 설정 추가 완료
- 기본값은 모두 `mock`
- Factory는 현재 Mock Provider를 반환
- `real` mode는 허용하지만 Real Provider가 없어 `REAL_PROVIDER_NOT_IMPLEMENTED(501)` 반환
- 서비스 계층은 Provider protocol에 의존하며 Mock 구현체에 직접 결합되어 있지 않음
- `.env.example`에 provider mode 설정 존재
- 현재 전체 테스트 기준: `190 passed, 0 failed, 0 errors`
- 실제 Kakao REST API Key는 로컬 `.env`의 `KAKAO_REST_API_KEY`에 저장되어 있음
- Kakao Local API 실제 호출 테스트 성공
- Kakao Map/Local 사용 설정 ON 완료

이번 세션에서는 **Kakao Place Real Provider만 구현**하세요.

다음은 하지 마세요.

- Naver Real Provider 구현
- YouTube Real Provider 구현
- EXAONE/Plan Real Provider 구현
- Preference Real Provider 구현
- Task 11의 다른 Real Provider 구현
- commit
- push
- migration

---

# 1. 기존 구조 우선 확인

코드를 수정하기 전에 다음을 확인하세요.

- `app/services/external/factory.py`
- `app/services/external/place/provider.py`
- `app/services/external/place/mock_provider.py`
- `app/services/place_search_service.py`
- `app/repositories/place_repository.py`
- `app/core/config.py`
- `.env.example`
- Place 관련 schema/model
- Task 08 Place Search 테스트
- 현재 provider mode 테스트

기존 Provider protocol과 DTO contract를 그대로 재사용하세요.

Service interface를 불필요하게 변경하지 마세요.

---

# 2. Kakao Real Provider 구현

기존 Place Provider protocol을 만족하는 실제 구현체를 추가하세요.

권장 파일명 예시:

`app/services/external/place/kakao_provider.py`

단, 프로젝트 convention에 더 적절한 위치/이름이 있으면 기존 구조를 우선하세요.

Kakao keyword 장소 검색 API를 사용합니다.

기본 endpoint:

`GET https://dapi.kakao.com/v2/local/search/keyword.json`

인증:

`Authorization: KakaoAK {KAKAO_REST_API_KEY}`

API Key를 코드에 하드코딩하지 마세요.

기존 Settings의 `kakao_rest_api_key`를 사용하세요.

---

# 3. Kakao 응답 → 기존 Provider DTO 매핑

기존 Place Provider DTO에 맞춰 다음 개념을 매핑하세요.

- `id` → `external_id`
- provider → `"KAKAO"`
- `place_name` → `name`
- `category_name` → `category`
- `address_name` → `address`
- `x` → longitude
- `y` → latitude
- `phone` → phone
- `place_url` → source_url

DTO field 이름은 실제 기존 protocol/schema를 확인해서 맞추세요.

프로젝트 외부 contract를 임의 변경하지 마세요.

---

# 4. Region 처리 원칙

이번 구현의 핵심은 `region` 처리입니다.

`region` 문자열을 단순히 `query`에 합치는 방식만 사용하지 마세요.

예:

`query="광주 카페"`

만으로 지역을 판단하면 현재 주소 체계에서 광주 외 지역이 섞일 수 있습니다.

실제 테스트에서 다음과 같은 결과가 확인되었습니다.

- 담양
- 화순
- 목포
- 순천

등이 `광주` 텍스트 검색에 함께 노출될 수 있음.

따라서 RegionResolver 또는 동일 책임을 가진 별도 컴포넌트를 두세요.

권장 파일 예시:

`app/services/region_resolver.py`

또는 기존 architecture에 맞는 위치.

---

# 5. 광주 특수 처리

현재 `region=광주`는 **2025-06-30 기준 구 광주광역시 행정경계**를 기준으로 처리합니다.

프로젝트에 다음 파일이 존재해야 합니다.

`data/regions/legacy_gwangju_2025.geojson`

이 GeoJSON은 SGIS 2025-06-30 시도 경계 데이터에서:

- `SIDO_CD = 24`
- `SIDO_NM = 광주광역시`

를 추출한 것입니다.

광주 Polygon bounding box는 검증 결과 대략:

- min longitude: `126.644703`
- min latitude: `35.050895`
- max longitude: `127.022275`
- max latitude: `35.258704`

단, 가능하면 GeoJSON geometry에서 bounds를 계산하거나 설정 객체로 관리하고,
서비스 여러 곳에 숫자를 중복 하드코딩하지 마세요.

---

# 6. 광주 검색 방식

`region=광주`일 때:

1. 광주 GeoJSON 로드
2. 광주 전체 bounding box 계산
3. bounding box를 `3 × 3 grid`로 분할
4. 각 grid에서 Kakao keyword 검색
5. Kakao `place id` 기준 중복 제거
6. 각 장소 좌표를 광주 Polygon과 비교
7. Polygon 내부 장소만 유지
8. 기존 Provider DTO로 변환
9. 결과 반환

실제 사전 테스트에서:

- 담양 장소 → Polygon 밖 → 제거
- 화순 장소 → Polygon 밖 → 제거
- 광주 동구/서구/남구/북구/광산구 장소 → 유지

가 정상 동작함을 확인했습니다.

---

# 7. Polygon 판정

현재 프로젝트 가상환경에는 `geopandas`가 없습니다.

이번 Task 때문에 `geopandas` 같은 무거운 dependency를 추가하지 마세요.

다음 중 하나를 선택하세요.

1. 이미 프로젝트에 `shapely`가 있다면 재사용
2. 없다면 표준 Python + GeoJSON으로 Point-in-Polygon 구현
3. 기존 dependency 정책에 맞는 더 가벼운 방식

새 dependency 추가가 꼭 필요하지 않다면 추가하지 마세요.

Polygon / MultiPolygon 둘 다 안전하게 처리할 수 있게 구현하세요.

---

# 8. 광주 외 지역 처리

서울·부산 등 모든 지역에 Polygon 방식을 강제하지 마세요.

현재 정책:

### 광주
특수 처리:

- 2025 legacy Gwangju Polygon
- 3×3 grid search
- place id dedupe
- polygon filter

### 목포
일반 검색 후 주소 기준:

`목포시`

가 포함된 결과만 유지할 수 있도록 처리

### 순천
주소 기준:

`순천시`

### 여수
주소 기준:

`여수시`

### 기타 지역
기존 Kakao 검색 결과를 기본으로 사용하되,
현재 구조에서 안전하게 적용 가능한 일반 region 처리 방식을 사용하세요.

중요:

`if "광주" in address`

같은 단순 문자열 판정은 금지합니다.

현재 주소 예:

`전남광주통합특별시 목포시 ...`

에도 `"광주"` 문자열이 포함될 수 있기 때문입니다.

---

# 9. RegionResolver 설계

서비스 곳곳에 다음과 같은 분기를 흩뿌리지 마세요.

```python
if region == "광주":
    ...
```

지역 정책은 한 곳에서 관리하세요.

개념적으로 다음과 같은 구조를 권장합니다.

```text
RegionResolver
  ├─ 광주 → LEGACY_POLYGON
  ├─ 목포 → ADDRESS_FILTER("목포시")
  ├─ 순천 → ADDRESS_FILTER("순천시")
  ├─ 여수 → ADDRESS_FILTER("여수시")
  └─ 기타 → DEFAULT
```

실제 class/enum 구조는 기존 프로젝트 convention에 맞게 최소 설계하세요.

---

# 10. Factory 연결

현재 Factory는 provider mode 설정을 읽을 수 있는 상태입니다.

`PLACE_PROVIDER=mock`

→ `MockPlaceProvider`

`PLACE_PROVIDER=real`

→ `KakaoPlaceProvider`

가 되도록 연결하세요.

다른 provider의 factory 동작은 건드리지 마세요.

기본값은 계속 `mock`이어야 합니다.

테스트 환경에서도 명시하지 않으면 Mock을 사용해야 합니다.

---

# 11. PlaceSearchService의 KAKAO 하드코딩

현재 `PlaceSearchService`가:

`external_provider == "KAKAO"`

를 요구하는 것으로 확인되어 있습니다.

이번 Task는 Kakao Real Provider만 구현하므로 당장 기능상 문제는 없습니다.

다만 불필요한 변경은 하지 말고:

- 현재 Kakao Real Provider와 충돌하지 않는지 확인
- 이후 Naver Place Provider 추가 시 provider-agnostic 구조로 개선이 필요한 부분은 결과 보고에 기록

정도로 처리하세요.

Task 11-A 범위를 벗어난 대규모 리팩토링은 금지합니다.

---

# 12. Kakao API 오류 처리

다음 상황을 기존 프로젝트 exception convention에 맞춰 처리하세요.

- Kakao API key 누락
- 401 / 403
- 429 rate limit
- timeout
- network error
- 5xx
- malformed JSON
- 예상 필드 누락

실제 secret 값은 로그에 출력하지 마세요.

외부 API 응답 전체를 민감정보 포함 상태로 그대로 로그에 남기지 마세요.

---

# 13. HTTP client

프로젝트에 이미 사용하는 HTTP client가 있다면 재사용하세요.

새 라이브러리를 무작정 추가하지 마세요.

timeout을 반드시 설정하세요.

테스트에서 실제 Kakao API를 호출하지 않도록 HTTP layer를 mock/stub 가능하게 구성하세요.

---

# 14. 테스트

자동 테스트에서는 실제 Kakao API를 호출하지 마세요.

HTTP 응답을 Mock하여 다음을 검증하세요.

## Factory

- `PLACE_PROVIDER=mock` → MockPlaceProvider
- `PLACE_PROVIDER=real` → KakaoPlaceProvider

## Kakao DTO mapping

- id
- name
- category
- address
- longitude
- latitude
- phone
- source_url
- external_provider = KAKAO

## 광주

- 광주 내부 좌표 유지
- 담양 좌표 제거
- 화순 좌표 제거
- 중복 Kakao place id 제거
- 3×3 grid 검색 수행
- Polygon / MultiPolygon 처리

## 목포

- `목포시` 주소 유지
- 순천시 주소 제거

## 순천

- `순천시` 주소 유지
- 목포시 주소 제거

## 여수

- `여수시` 주소 유지
- 타 지역 제거

## Error

- API key 누락
- Kakao 401/403
- Kakao 429
- timeout
- malformed response

기존 테스트를 삭제하거나 완화하지 마세요.

---

# 15. 기존 Place Search API 유지

기존 API:

`GET /api/v1/places/search?query=...&region=...`

contract를 유지하세요.

Service / Repository / DB upsert 동작도 유지하세요.

Real Provider 추가 때문에 API response schema를 불필요하게 변경하지 마세요.

---

# 16. DB 변경

이번 Task는 Provider 교체 작업입니다.

- migration 생성 금지
- DB schema 변경 금지

현재 Place model의 `kakao_place_id` 구조를 그대로 사용하세요.

다만 Naver 추가 시 provider-agnostic external identity 구조가 필요할 수 있다는 점은 결과 보고에 남기세요.

---

# 17. 실제 API Smoke Test

자동 테스트 전체 통과 후에만,
로컬 `.env`의 실제 `KAKAO_REST_API_KEY`를 사용한 수동 smoke test를 해도 됩니다.

단:

- API key 값을 출력하지 말 것
- 테스트 로그에 secret을 출력하지 말 것
- 테스트 자동화에 실제 Kakao 호출을 넣지 말 것

수동 확인 예:

`GET /api/v1/places/search?query=카페&region=광주`

이때:

- 담양/화순 결과가 최종 응답에 포함되지 않는지
- 광주 내부 결과가 반환되는지

확인하세요.

가능하면 추가로:

- `region=목포`
- `region=순천`

도 1회씩 smoke test 하세요.

---

# 18. 전체 Regression

현재 기준:

`190 passed`

작업 완료 후 반드시:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=".pytest_tmp"
```

를 실행하세요.

목표:

- 기존 190개 유지
- 신규 테스트 모두 통과
- failed = 0
- errors = 0

warnings는 개수만 보고하세요.

---

# 19. 토큰 / 컨텍스트 관리

이번 세션에서는 **Kakao Place Real Provider 하나만 완성**하세요.

우선순위:

1. RegionResolver
2. KakaoPlaceProvider
3. Factory 연결
4. unit tests
5. integration regression
6. optional manual smoke test

컨텍스트가 부족할 것 같으면,
깨진 상태로 종료하지 말고 완성된 단위에서 중단하세요.

---

# 20. 금지사항

- Naver Real Provider 구현 금지
- YouTube Real Provider 구현 금지
- EXAONE Real Provider 구현 금지
- Preference Real Provider 구현 금지
- migration 금지
- DB schema 변경 금지
- commit 금지
- push 금지
- API key 하드코딩 금지
- secret 출력 금지
- 기존 테스트 삭제/skip 금지
- 테스트 expectation 완화 금지
- Task 범위 밖 대규모 리팩토링 금지

---

# 완료 보고 형식

## [Task 11-A Kakao Real Provider 작업 결과]

### 생성 파일
- ...

### 수정 파일
- ...

### Kakao Real Provider
- endpoint:
- HTTP client:
- timeout:
- DTO mapping:

### RegionResolver

#### 광주
- filter type:
- GeoJSON:
- grid:
- dedupe:
- polygon filter:

#### 목포
- ...

#### 순천
- ...

#### 여수
- ...

#### 기타
- ...

### Factory
- mock:
- real:

### PlaceSearchService
- 변경 여부:
- KAKAO 하드코딩 상태:

### 오류 처리
- API key:
- 401/403:
- 429:
- timeout:
- 5xx:
- malformed response:

### DB 변경
- Migration:
- Schema:

### 테스트
- 기존 기준: 190
- 신규 테스트:
- 총 collected:
- passed:
- failed:
- errors:
- warnings:

### 실제 Kakao Smoke Test
- 수행 여부:
- 광주:
- 목포:
- 순천:
- secret 노출 여부:

### 발견 이슈
- ...

### Task 11-A 완료 여부
- 완료 / 미완료

### 다음 단계
- Naver/YouTube 등은 시작하지 말고 다음 Task 후보만 보고

Task 11-A까지만 수행하세요.
