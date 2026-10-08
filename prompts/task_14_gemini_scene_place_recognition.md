# Task 14 — Gemini 기반 TV 화면 장소 인식

## 목표

Task 13에서 구현한 흐름:

```text
Flutter 카메라
→ TV 화면 촬영
→ 이미지 미리보기
→ JWT 포함 multipart 업로드
→ FastAPI `/api/v1/discovery/scene-image`
→ 200 OK
```

에 이어서, 업로드된 이미지를 **백엔드에서 Gemini의 이미지 이해 기능으로 분석하여 현재 화면에 나온 장소 후보를 식별**한다.

최종 목표 흐름:

```text
TV 프로그램 / YouTube 시청
        ↓
휴대폰으로 TV 화면 촬영
        ↓
Flutter → Backend 이미지 업로드
        ↓
Gemini 이미지 분석
        ↓
장소 후보 추출
        ↓
장소 정보 반환
        ↓
다음 Task에서 Kakao 실제 장소 검증
        ↓
검증된 장소 중심으로 여행계획 생성
```

이번 Task 14에서는 **Gemini로 이미지에서 장소 후보를 추출하여 Flutter까지 반환하는 것**까지 구현한다.

아직 이번 Task에서 하지 않을 것:

- Kakao 장소 검증
- 최종 장소 확정
- 자동 여행 일정 생성
- GPS 기반 일정
- `힘들어요` 기능

이 기능들은 이후 Task에서 연결한다.

---

## 작업 위치 / Git 안전 규칙

실제 작업 저장소:

```text
C:\dev\dx-all
```

Backend:

```text
C:\dev\dx-all\backend
```

Flutter:

```text
C:\dev\dx-all\frontend\flutter
```

반드시 지킬 것:

1. `C:\dev\dx-all` 내부만 수정한다.
2. `C:\dev\DX-front`, `C:\dev\프로젝트백엔드`는 필요한 경우 읽기/비교만 가능하며 수정하지 않는다.
3. `Dx-`, `DXback` 원격 저장소는 수정하지 않는다.
4. `git commit`, `git push`, `git pull` 하지 않는다.
5. 기존 로그인, Setup, Kakao, YouTube, EXAONE, Plan 기능을 깨뜨리지 않는다.
6. Task 13의 scene-image 업로드 구조를 최대한 재사용한다.
7. Gemini API Key를 Flutter 코드나 Git에 절대 하드코딩하지 않는다.

---

## 1. 먼저 기존 구조 확인

코드를 바로 만들지 말고 아래를 먼저 확인한다.

- `backend/app/api/v1/discovery.py`
- `backend/app/services/scene_image_service.py`
- `backend/app/schemas/scene_image.py`
- provider 구조와 factory 패턴
- 기존 EXAONE / Kakao / YouTube provider 구조
- config / `.env.example` 관리 방식
- 공통 AppError / error envelope
- Flutter `camera_screen.dart`
- Flutter `scene_image_service.dart`
- Task 13 테스트

기존 패턴과 최대한 일관되게 구현한다.

---

## 2. Gemini API Key 관리

Gemini API Key는 반드시 Backend 환경변수에서만 읽는다.

예:

```text
GEMINI_API_KEY=
GEMINI_MODEL=
```

`GEMINI_MODEL`은 코드에 특정 모델명을 강하게 하드코딩하지 말고 환경변수로 변경 가능하게 만든다.

`.env.example`에는 실제 비밀값이 아닌 빈 값 또는 예시값만 추가한다.

Flutter에는 Gemini API Key가 절대 들어가면 안 된다.

---

## 3. Backend Provider

기존 provider 패턴과 일치하도록 Gemini 이미지 분석 Provider를 만든다.

개념 예시:

```text
SceneImageService
        ↓
GeminiSceneProvider
        ↓
Gemini API
```

Provider 책임:

- 이미지 bytes 수신
- MIME type 수신
- Gemini 이미지 분석 요청
- 응답 파싱
- 장소 후보를 구조화된 결과로 반환
- API 오류 / timeout / 잘못된 응답 처리

Router 안에서 Gemini SDK를 직접 호출하지 않는다.

---

## 4. Gemini에 전달할 분석 목적

Gemini에게 단순히:

```text
이 사진 어디야?
```

라고 묻지 않는다.

TV 화면 촬영 이미지라는 점을 명시하고 아래 정보를 종합해서 장소를 추정하게 한다.

활용 가능한 단서:

```text
랜드마크
건물
자연 지형
거리 모습
간판
자막
표지판
상호명
언어
관광지 특징
방송 화면에 표시된 지명
```

이미지 안에 텍스트가 있으면 OCR 성격의 시각적 읽기도 함께 활용한다.

단, 이미지에서 확인할 수 없는 정보를 임의 생성하지 않도록 명확히 지시한다.

---

## 5. Gemini 출력 형식

자유로운 설명문보다 **구조화된 JSON 응답**을 우선한다.

개념적으로 다음 정보를 반환한다.

```json
{
  "recognized": true,
  "primary_candidate": {
    "place_name": "성산일출봉",
    "city": "서귀포시",
    "region": "제주특별자치도",
    "country": "대한민국",
    "category": "관광지"
  },
  "candidates": [
    {
      "place_name": "성산일출봉",
      "city": "서귀포시",
      "region": "제주특별자치도",
      "country": "대한민국",
      "category": "관광지"
    }
  ],
  "evidence": [
    "화산 분화구 형태의 지형",
    "화면 내 성산 관련 표기"
  ],
  "confidence": "HIGH",
  "needs_verification": true
}
```

주의:

- `confidence`는 모델의 자체 추정값이므로 실제 통계적 확률처럼 취급하지 않는다.
- `HIGH / MEDIUM / LOW` 같은 label 형태를 우선한다.
- Gemini가 확신하지 못하면 `recognized=false` 또는 `confidence=LOW`를 반환할 수 있어야 한다.
- 장소를 억지로 하나 선택하게 하지 않는다.
- 후보는 최대 3개 정도로 제한한다.
- 이후 Kakao 검증을 위해 `needs_verification=true`를 기본으로 둔다.

---

## 6. Gemini Prompt 원칙

프롬프트의 핵심 규칙:

```text
당신은 여행 장면 장소 식별기다.

입력 이미지는 사용자가 TV 프로그램 또는 YouTube를 시청하다가
휴대폰으로 촬영한 화면일 수 있다.

이미지에 실제로 보이는 시각적 단서만 사용한다.

랜드마크, 지형, 간판, 표지판, 자막, 건물명,
지역명 등을 종합하여 장소 후보를 추정한다.

확실하지 않으면 추측하여 확정하지 않는다.

정확한 장소를 특정할 수 없으면 recognized=false로 반환한다.

장소 후보가 여러 개라면 최대 3개만 반환한다.

응답은 지정된 JSON 구조만 반환한다.
```

Gemini가 응답 앞뒤에 Markdown code fence나 설명문을 붙이는 경우에도 안전하게 파싱할 수 있도록 처리한다.

가능하면 사용하는 SDK가 구조화 응답 / JSON schema를 공식 지원한다면 그 기능을 우선 검토한다.

---

## 7. 기존 scene-image endpoint 확장

현재:

```http
POST /api/v1/discovery/scene-image
```

Task 13에서는 이미지 수신 검증 후 메타데이터만 반환한다.

Task 14에서는 기존 endpoint를 자연스럽게 확장하거나,
현재 API 설계와 더 잘 맞는 별도 analyze endpoint를 추가할 수 있다.

단, 중복 업로드가 발생하지 않는 방향을 우선한다.

권장 UX는 한 번의 요청으로:

```text
이미지 수신
→ 이미지 검증
→ Gemini 분석
→ 장소 후보 반환
```

이 가능하도록 하는 것이다.

기존 Task 13 테스트가 깨지지 않아야 한다.

---

## 8. 실패 처리

### Gemini API Key 없음

서버 설정 오류로 명확하게 처리한다.

### Gemini timeout / API 장애

사용자에게는 내부 구현 세부사항을 노출하지 않고 공통 오류 응답을 사용한다.

예:

```text
장소를 분석하지 못했습니다. 다시 시도해 주세요.
```

### 장소 식별 실패

이 경우는 서버 오류가 아니다.

예:

```json
{
  "recognized": false,
  "primary_candidate": null,
  "candidates": [],
  "evidence": [],
  "confidence": "LOW",
  "needs_verification": true
}
```

Flutter에서는:

```text
장소를 정확히 찾지 못했어요.
TV 화면이 더 크게 나오도록 다시 촬영해 주세요.
```

같은 안내가 가능하게 한다.

---

## 9. Flutter 연결

Task 13의 카메라 촬영 화면을 재사용한다.

목표 UX:

```text
[TV 화면 촬영]
        ↓
사진 촬영
        ↓
미리보기
        ↓
[이 사진으로 장소 찾기]
        ↓
분석 중
        ↓
Gemini 결과
        ↓
"성산일출봉으로 보여요"
```

분석 중에는 중복 요청을 막는다.

Gemini 호출은 Flutter에서 직접 하지 않는다.

항상:

```text
Flutter
→ FastAPI Backend
→ Gemini
```

구조를 유지한다.

---

## 10. 결과 화면

기존 discovery 화면 / analyzing 화면 / place result 화면을 우선 재사용한다.

최소 표시 정보:

```text
추정 장소명
지역
신뢰 수준
판단 근거 일부
```

후보가 여러 개인 경우 1~3개를 보여줄 수 있다.

---

## 11. 다음 Task와 연결 가능하도록 설계

Task 14 결과는 다음 단계에서 바로 Kakao 장소검색으로 넘길 수 있어야 한다.

향후 흐름:

```text
Gemini
→ "성산일출봉"
        ↓
Kakao Places
→ 실제 장소 검색
        ↓
주소 / 좌표 / category 확보
        ↓
확정 장소
        ↓
기존 Plan 생성
```

Gemini 결과를 그대로 최종 사실처럼 DB에 저장하지 않는다.

---

## 12. 바로 여행계획으로 연결할 최종 구조

이번 Task에서는 아직 Plan 생성까지 호출하지 않지만 최종적으로 다음 UX를 목표로 한다.

```text
TV 화면 촬영
        ↓
Gemini 장소 인식
        ↓
Kakao 실제 장소 검증
        ↓
장소 확정
        ↓
사용자 preference 조회
        ↓
EXAONE Plan 생성
        ↓
"이 장소 중심으로 여행계획 만들기"
```

---

## 13. Backend 테스트

Gemini 실제 API를 모든 테스트에서 호출하지 않는다.

Provider를 mock/stub 할 수 있게 구조화한다.

최소 테스트:

1. 정상 이미지 + Gemini 성공 → 장소 후보 응답
2. Gemini가 장소를 특정하지 못함 → recognized=false
3. Gemini provider timeout → 기존 공통 오류 envelope
4. Gemini invalid JSON → 안전한 오류 처리
5. 인증 없음 → 401
6. 기존 Task 13 파일 검증 테스트 유지
7. Gemini API Key가 없을 때 적절한 오류 처리

전체 pytest가 통과해야 한다.

---

## 14. Flutter 테스트

최소 확인:

- scene-image 응답의 장소 분석 결과 파싱
- recognized=true
- recognized=false
- 서버 오류
- 인증 토큰 포함
- 분석 중 중복 요청 방지

실행:

```text
flutter test
flutter analyze
```

기존 info 메시지와 새로운 warning/error를 구분해서 보고한다.

---

## 15. 수동 E2E 성공 기준

실제 Android 에뮬레이터 또는 휴대폰에서:

```text
카카오 로그인
→ 카메라 화면
→ 여행지가 나오는 TV 화면 촬영
→ 이미지 미리보기
→ 장소 찾기
→ Backend 업로드
→ Gemini 분석
→ 장소 후보 반환
→ Flutter 화면에 장소 표시
```

백엔드 로그에는 scene-image 관련 2xx 응답이 확인되어야 한다.

---

## 16. 완료 조건

Task 14 완료 기준:

```text
사진 촬영 ✅
Backend 업로드 ✅
Gemini 이미지 분석 ✅
장소 후보 구조화 ✅
Flutter 결과 표시 ✅
```

아직 Kakao 실제 장소 검증이나 Plan 자동 생성은 하지 않는다.

다음 Task에서:

```text
Gemini 장소 후보
→ Kakao 검증
→ 검증 장소를 기존 여행계획 생성으로 전달
```

을 구현한다.

---

## 17. 작업 후 보고 형식

## 기존 구조 확인
- ...

## 구현 내용
- ...

## Gemini Provider
- ...

## API 변경
- ...

## Flutter 변경
- ...

## 수정/추가 파일
- ...

## Backend 테스트
- ...

## Flutter 테스트
- ...

## 실제 E2E 방법
- ...

## 다음 Task 연결 지점
- ...

## Git 상태
- commit/push/pull을 하지 않았는지 확인
