# Task 13 — TV 화면 촬영 이미지 업로드 연결

## 목표

사용자가 Flutter 앱에서 휴대폰 카메라로 TV 화면을 촬영하고,
촬영한 이미지를 현재 로그인 세션의 JWT와 함께 FastAPI 백엔드로 전송할 수 있게 한다.

이번 Task의 범위는 **촬영 + 백엔드 전송 + 수신 검증**까지만이다.

아직 아래 기능은 구현하지 않는다.

- Vision 모델 분석
- OCR
- 장소 후보 추출
- Kakao 장소 검증
- 여행 일정 생성 연결

이 기능들은 다음 Task에서 이어서 구현한다.

---

## 작업 위치 / Git 안전 규칙

실제 작업 저장소:

```text
C:\dev\dx-all
```

백엔드:

```text
C:\dev\dx-all\backend
```

Flutter:

```text
C:\dev\dx-all\frontend\flutter
```

반드시 지킬 것:

1. `C:\dev\dx-all` 내부만 수정한다.
2. 기존 `C:\dev\프로젝트백엔드`, `C:\dev\DX-front`는 참고/비교가 필요하면 읽을 수 있지만 수정하지 않는다.
3. `DXback`, `Dx-` 원격 저장소는 절대 수정하지 않는다.
4. `git commit`, `git push`, `git pull`은 하지 않는다.
5. 작업 완료 후 변경 파일 목록과 테스트 결과만 보고한다.
6. 기존 로그인 / Setup / Plan / Kakao / YouTube / EXAONE 기능을 깨뜨리지 않는다.

---

## 가장 먼저 할 일

코드를 바로 만들지 말고 기존 구조부터 확인한다.

특히 아래를 먼저 찾아본다.

- Flutter에 기존 `camera_screen.dart` 또는 유사한 화면이 있는지
- 기존 이미지 선택/촬영 코드가 있는지
- `pubspec.yaml`에 `image_picker` 또는 `camera` 패키지가 이미 있는지
- 기존 API 호출 공통 클래스 (`ApiClient`) 구조
- `AuthSession.accessToken` 사용 방식
- FastAPI router/service/schema 구조
- 기존 인증 의존성으로 현재 로그인 사용자를 받는 방식
- 기존 multipart 업로드 endpoint가 이미 있는지

이미 있는 구조를 우선 재사용하고 중복 구현하지 않는다.

---

# 1. Flutter 요구사항

## 사용자 흐름

목표 UX:

```text
장소 발견 화면
→ [TV 화면 촬영하기]
→ 휴대폰 카메라 실행
→ 사진 촬영
→ 촬영 이미지 미리보기
→ [이 사진 사용하기]
→ 백엔드 업로드
→ 업로드 성공 표시
```

현재 화면 구조상 더 자연스러운 기존 화면이 있으면
새 화면을 무조건 만들지 말고 기존 화면에 최소 변경으로 연결한다.

---

## 카메라

단순 사진 촬영 목적이므로 기존 의존성이 없다면
`image_picker`의 `ImageSource.camera`를 우선 검토한다.

단, 이미 프로젝트에서 `camera` 패키지 또는 별도 카메라 구조를 사용 중이라면
기존 방식을 유지한다.

Android 카메라 권한 및 필요한 설정도 확인한다.

---

## 이미지 미리보기

촬영 성공 후:

- 촬영 이미지를 화면에 표시
- 다시 촬영 가능
- 사용자가 확인 후 업로드할 수 있도록 구성

촬영 취소 시 앱이 오류 나지 않아야 한다.

---

## 백엔드 전송

기존 `ApiClient` 또는 서비스 계층 구조를 따른다.

가능하면 새 서비스는 다음과 같이 기능별로 분리한다.

예:

```text
lib/services/scene_image_service.dart
```

단, 기존 프로젝트 네이밍/디렉터리 규칙이 다르면 기존 규칙을 우선한다.

요청 방식:

```http
POST /api/v1/discovery/scene-image
Authorization: Bearer <service JWT>
Content-Type: multipart/form-data
```

multipart field:

```text
file
```

Flutter는 현재 로그인한 사용자의 `AuthSession.accessToken`을 사용한다.

토큰이 없으면 요청하지 않고 사용자에게 오류를 표시한다.

---

# 2. Backend 요구사항

## Endpoint

새 endpoint:

```http
POST /api/v1/discovery/scene-image
```

역할:

1. 인증된 사용자만 접근
2. multipart 이미지 수신
3. 이미지 기본 검증
4. 수신 성공 응답

이번 Task에서는 Vision 분석을 하지 않는다.

---

## 인증

기존 프로젝트의 JWT 인증 방식을 그대로 재사용한다.

새로운 별도 인증 방식을 만들지 않는다.

현재 로그인 사용자를 확인할 수 있어야 한다.

---

## 파일 검증

최소 검증:

허용 MIME type:

```text
image/jpeg
image/png
image/webp
```

최대 파일 크기:

```text
10 MB
```

잘못된 파일은 기존 프로젝트의 오류 응답 형식을 따라 4xx로 반환한다.

빈 파일도 거부한다.

---

## 이미지 저장 정책

이번 Task에서는 영구 저장을 만들지 않는다.

DB에 이미지 binary를 저장하지 않는다.

GridFS, S3, 로컬 영구 업로드 폴더 등을 새로 만들지 않는다.

Task 14 Vision 분석에서 동일 요청의 image bytes를 바로 분석할 수 있도록
서비스 계층이 bytes를 받을 수 있는 구조로 만든다.

Task 13에서는 수신 및 검증 후 메타데이터만 응답한다.

예상 응답 개념:

```json
{
  "received": true,
  "filename": "tv_scene.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 123456
}
```

실제 응답 Schema/필드명은 기존 프로젝트 스타일을 우선한다.

보안상 로컬 파일 경로나 서버 내부 경로는 응답하지 않는다.

---

# 3. 구조 원칙

가능하면 다음 계층을 유지한다.

```text
Router
   ↓
Service
   ↓
향후 Vision Provider
```

이번 Task:

```text
Scene Image Router
        ↓
Scene Image Service
        ↓
이미지 validation
        ↓
수신 결과
```

다음 Task 14에서는:

```text
Scene Image Service
        ↓
Vision / OCR Provider
        ↓
장소 후보
```

로 자연스럽게 확장할 수 있어야 한다.

Router 안에 이미지 분석 로직을 넣지 않는다.

---

# 4. 향후 기능을 고려한 설계

최종 서비스 흐름은 다음이다.

```text
TV 프로그램 / YouTube 시청
        ↓
휴대폰으로 TV 화면 촬영
        ↓
[현재 Task 13]
이미지 → Backend
        ↓
[Task 14]
Vision / OCR
        ↓
[Task 15]
장소 후보 추출
        ↓
[Task 16]
Kakao 실제 장소 검증
        ↓
[Task 17]
사용자가 장소 확인
        ↓
[Task 18]
기존 Plan 생성으로 전달
```

따라서 Task 13에서 불필요하게 장소 분석 코드를 섞지 않는다.

---

# 5. UI 상태 처리

최소한 다음 상태를 처리한다.

```text
촬영 전
촬영 완료
업로드 중
업로드 성공
업로드 실패
```

업로드 중에는 중복 요청을 막는다.

백엔드 오류가 나도 앱이 crash하지 않아야 한다.

오류 메시지는 사용자가 이해하기 쉬운 한국어로 표시한다.

예:

```text
이미지를 전송하지 못했습니다. 다시 시도해 주세요.
```

---

# 6. 테스트

## Backend

다음을 테스트한다.

1. 정상 JPEG 업로드 → 성공
2. 정상 PNG 업로드 → 성공
3. 인증 없음 → 401
4. 이미지가 아닌 파일 → 4xx
5. 빈 파일 → 4xx
6. 10MB 초과 → 4xx

기존 pytest 전체 테스트가 깨지지 않아야 한다.

---

## Flutter

가능한 범위에서 service 단위 테스트를 추가한다.

최소 확인:

- multipart 요청 생성
- Authorization Bearer token 포함
- endpoint 정확성
- 서버 오류 처리

그리고 실행:

```text
flutter test
flutter analyze
```

기존에 이미 존재하던 info warning과
이번 변경으로 새로 생긴 warning/error를 구분해서 보고한다.

---

# 7. 완료 조건

다음이 모두 충족되면 Task 13 완료다.

```text
Flutter 카메라 실행
→ TV 화면 촬영
→ 이미지 미리보기
→ 사용자가 업로드 실행
→ JWT 포함 multipart 요청
→ FastAPI 이미지 수신
→ 파일 검증
→ 200 계열 응답
→ Flutter 성공 상태 표시
```

아직 장소를 맞추지 않아도 된다.

이번 Task의 성공 기준은:

> **"휴대폰에서 촬영한 TV 화면 이미지가 인증된 사용자 요청으로 백엔드까지 정상 전달된다."**

이다.

---

# 8. 작업 후 보고

작업이 끝나면 아래 형식으로만 정리해서 보고한다.

## 구현 내용
- ...

## 수정/추가 파일
- ...

## Backend 테스트 결과
- ...

## Flutter 테스트 결과
- ...

## 수동 E2E 테스트 방법
- ...

## 다음 Task 14에서 연결할 지점
- ...

## Git 상태
- commit/push/pull 하지 않았는지 확인
