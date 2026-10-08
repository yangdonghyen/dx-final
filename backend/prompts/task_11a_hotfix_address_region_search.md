# Task 11-A Hotfix — 목포/순천/여수 지역 검색 힌트 수정

작업 경로:

`C:\dev\프로젝트백엔드`

현재 상태:

- Kakao Real Provider 구현 완료
- 전체 테스트: 201 passed
- `PLACE_PROVIDER=real`
- 실제 Kakao API Key 로딩 정상
- `region=광주` 실제 API smoke test 성공
- 광주는 2025 legacy Gwangju Polygon + 3x3 grid + polygon filter로 정상 동작

현재 발견된 문제:

```text
GET /api/v1/places/search?query=카페&region=목포
→ {"places":[]}
```

하지만 Kakao Local API 직접 호출:

```text
query="목포 카페"
```

에서는 다음처럼 실제 목포시 결과가 정상적으로 반환됨:

- 커피창고로
- 석산
- 대반동201
- 스타벅스 목포해안로점
- 스타벅스 목포북항DT점
- 기타 목포시 카페

모든 결과의 `address_name`은:

```text
전남광주통합특별시 목포시 ...
```

형태로 확인됨.

따라서 현재 백엔드 문제는,
목포/순천/여수 ADDRESS_FILTER 지역에서 Kakao 검색 시 `query=카페`만 보내고
검색 후 주소 필터만 적용하기 때문에 후보 자체에 해당 도시가 없어서 빈 배열이 되는 것으로 추정됩니다.

---

# 수정 목표

광주는 기존 로직을 절대 변경하지 마세요.

광주:

```text
query=카페
→ 3x3 grid
→ Kakao place id dedupe
→ legacy Gwangju polygon filter
```

그대로 유지합니다.

목포/순천/여수 같은 ADDRESS_FILTER 지역에서는:

```text
사용자 query = "카페"
region = "목포"

Kakao 실제 검색 query = "목포 카페"
→ 검색 결과 수신
→ address_name에 정확한 target city token "목포시"가 포함된 결과만 유지
```

형태로 변경하세요.

즉:

```text
목포 → "목포 {query}" 검색 → "목포시" 주소 필터
순천 → "순천 {query}" 검색 → "순천시" 주소 필터
여수 → "여수 {query}" 검색 → "여수시" 주소 필터
```

검색 힌트와 최종 주소 검증을 둘 다 사용합니다.

---

# 구현 원칙

1. RegionResolver의 기존 책임을 유지하세요.
2. 지역별 문자열 로직을 KakaoProvider 곳곳에 하드코딩하지 마세요.
3. 가능하면 RegionResolver 결과에:
   - search hint
   - address filter token
   을 함께 표현하도록 최소 변경하세요.
4. 광주 special polygon 로직은 손대지 마세요.
5. 기타 DEFAULT 지역 동작도 불필요하게 변경하지 마세요.
6. API response contract 변경 금지.
7. DB schema/migration 변경 금지.
8. commit/push 금지.

---

# 테스트 추가/수정

실제 Kakao API는 unit test에서 호출하지 마세요.

다음을 검증하세요.

### 목포
입력:

```text
query="카페"
region="목포"
```

Kakao HTTP request에 실제 검색어가:

```text
목포 카페
```

로 전달되는지 검증.

그리고 응답 후보 중:

```text
전남광주통합특별시 목포시 ...
```

는 유지하고,

```text
전남광주통합특별시 순천시 ...
```

는 제거.

### 순천

Kakao request query:

```text
순천 카페
```

최종 주소:

```text
순천시
```

만 유지.

### 여수

Kakao request query:

```text
여수 카페
```

최종 주소:

```text
여수시
```

만 유지.

### 광주 Regression

`region=광주`에서 검색어를:

```text
광주 카페
```

로 바꾸면 안 됩니다.

기존처럼 query 자체는 `카페`를 사용하고
grid/polygon 방식이 그대로 동작하는지 기존 테스트로 확인하세요.

---

# 전체 테스트

현재 기준:

```text
201 passed
```

수정 후:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=".pytest_tmp"
```

실행.

목표:

- 기존 201개 유지
- 신규 regression test 통과
- failed = 0
- errors = 0

---

# 완료 후 실제 Smoke Test 안내

코드 수정 및 전체 테스트 통과 후,
실제 서버에서 다음 URL을 다시 확인할 예정입니다.

```text
GET /api/v1/places/search?query=카페&region=목포
GET /api/v1/places/search?query=카페&region=순천
GET /api/v1/places/search?query=카페&region=여수
```

각 결과는 해당 도시 주소만 포함해야 합니다.

---

# 완료 보고 형식

## [Task 11-A Hotfix 결과]

### 원인
- ...

### 수정 파일
- ...

### ADDRESS_FILTER 검색 방식
- 목포:
- 순천:
- 여수:

### 광주 Regression
- 기존 3x3 grid 유지:
- polygon filter 유지:
- `"광주 {query}"` 사용 여부:

### 테스트
- 기존 기준: 201
- 신규 테스트:
- 총 collected:
- passed:
- failed:
- errors:
- warnings:

### DB 변경
- Migration:
- Schema:

### 완료 여부
- 완료 / 미완료

이 Hotfix만 수행하고 Naver/YouTube/EXAONE 작업은 시작하지 마세요.
