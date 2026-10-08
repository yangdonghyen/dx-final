# 2026-10-07 최신 작업 핸드오프

## 이번에 저장하는 변경

- 홈 `사진으로 찾기`는 검은 카메라 스타일의 안내 화면으로 정리했다. 상단 상태 아이콘, 큰 흰색 인식 프레임, 줌 표시, 하단의 흰 원형 셔터를 제공한다. 프레임과 셔터는 겹치지 않는다.
- 홈 촬영 화면의 셔터는 현재 목업 촬영 흐름으로 장소 분석 → 장소 결과 → 여행 코스 만들기로 이동한다. 실제 사진 기반 장소 인식 API는 아직 연결되지 않아 분석 결과 장소는 목업 데이터다.
- 직접 입력의 `이미지에서 장소 찾기`는 홈 촬영과 분리되어 있으며, 밝은 화면에서 앨범 이미지를 선택한 뒤 분석한다.
- 사진으로 찾기 결과에서 여행 코스를 시작하면 날짜 선택부터 진행하며, 여행 확인 화면 맨 위에 분석된 장소 카드를 표시한다.
- 여행 만들기 설문은 4단계다: 날짜 선택 → 이동수단 → 예산 선택(여유롭게/알뜰하게) → 동행자 정보. 여행 인원은 설문과 확인 화면에서 제거했다.
- 날짜 선택 화면은 달력과 선택 기간 안내가 하단 버튼에 가려지지 않도록 한 화면에 맞췄다.

## 검증 및 다음 확인

- 최근 검증: `flutter analyze lib/screens/discovery/camera_screen.dart`, `flutter analyze lib/screens/trip/trip_places_screen.dart` 모두 `No issues found!`.
- Android Studio에서 Hot Restart 후 홈 `사진으로 찾기`의 프레임·셔터 간격, 사진 결과 → 여행 만들기 → 확인 화면의 장소 카드 흐름을 수동 확인할 것.
- 실제 카메라 촬영 또는 사진 기반 장소 인식이 필요해지면 별도 카메라/비전 API 연동 범위를 결정해야 한다.

---
# 2026-10-06 추가 업데이트 — 사진 입력 방식 분리

- 홈의 `사진으로 찾기`는 카메라 촬영 전용으로 분리했다. 카메라 아이콘과 어두운 촬영 UI를 사용하며, 촬영 후 장소 분석으로 이동한다.
- 직접 입력의 `이미지에서 장소 찾기`는 `image_search_outlined` 아이콘을 사용한다. 밝은 앨범 선택 UI에서 이미지 파일만 불러오고 촬영 기능은 제공하지 않는다.
- 두 입력 경로는 각각 촬영·앨범 선택 뒤 동일하게 분석 결과와 여행 만들기로 이어진다.
- Android `CAMERA` 권한을 추가했다.
- 검증: `flutter analyze lib/screens/discovery/camera_screen.dart lib/screens/search/text_search_screen.dart lib/screens/home/home_screen.dart` → `No issues found!`

---
# 2026-10-06 추가 업데이트 — 공동 일정 알림 통합

- 전체 일정의 `공유하기` 시트에서 일정 변경 알림 카드·토글을 제거했다.
- 일정 카드의 연필 아이콘을 눌러 실제 수정을 시작하면 공용 알림함에 `민우님이 ○○ 일정을 수정 중이에요` 알림을 추가한다.
- 수정 저장 시 공용 알림함에 `민우님이 ○○ 일정을 수정했어요` 알림을 추가한다.
- 홈 상단 알림 배지와 알림함이 같은 `NotificationService` 상태를 관찰하므로 새 알림이 즉시 반영된다.
- 현재는 동일 앱 실행 세션의 목업 공용 상태다. 실제 상대방 휴대폰 알림은 서버·사용자 동기화·푸시 알림 연동이 필요하다.
- 검증: `flutter analyze lib/services/notification_service.dart lib/screens/trip/itinerary_screen.dart lib/screens/home/home_screen.dart lib/screens/my/notifications_screen.dart` → `No issues found!`

---
# 2026-10-06 최신 핸드오프

## 오늘 완료한 변경

- 이미지 장소 찾기: 촬영 기능 없이 앨범 사진만 선택한다. 사진 선택 → 미리보기 → 분석 → 장소 결과 → 여행 만들기 흐름으로 연결했다. `image_picker`를 추가했으며, 현재 장소 인식 결과는 기존 목업 데이터다.
- 저장 장소: `내가 발견한 여행지`와 `저장 장소 보기` 모두 삭제 전 재확인 창을 띄운다. 좋아요는 카드 우측 상단에 유지하고 삭제는 우측 하단의 빨간 `삭제` 텍스트 버튼으로 분리했다.
- 여행 만들기: 날짜 → 이동수단 → 동행자·예산의 3단계 흐름이다. 동행자의 걷기 정도·피하고 싶은 활동을 제거했고, 연령대를 고르기 전에는 `연령대 미선택`으로 표시한다. 예산은 `여유 있게 쓰기`·`알뜰하게 쓰기` 두 선택지다.
- 마이페이지: 회원 탈퇴는 사유 선택 후 최종 확인한다.
- 지난 여행: 기간에 맞는 DAY 수를 계산하고, 상단 `DAY 1`, `DAY 2` 버튼으로 한 날짜의 일정만 표시한다. 일정 헤더는 날짜만 보이며, 첫날은 숙소 체크인 후 여행 시작, 마지막 날은 숙소 체크아웃 후 귀가로 구성한다.

## 검증 및 유의점

- `camera_screen.dart`, `analyzing_screen.dart`, `place_result_screen.dart`, `profile_screen.dart`, `past_itinerary_screen.dart`, `youtube_saved_screen.dart`, `saved_photo_places_screen.dart`, `text_search_screen.dart`, `trip_places_screen.dart` 관련 `flutter analyze`를 실행해 모두 `No issues found!`를 확인했다.
- 동행자 모델의 필드를 제거했으므로 실행 중인 앱은 Hot Reload가 아닌 **Hot Restart**가 필요하다.
- Windows 데스크톱에서 새 `image_picker` 플러그인을 빌드하려면 Windows 개발자 모드의 심볼릭 링크 지원이 필요하다는 `flutter pub get` 안내가 있었다. Android 기기 수동 검증은 아직 필요하다.
- 실제 사진별 AI 장소 인식과 여행·저장 데이터의 영구 저장은 후속 API/저장소 연동이 필요하다.

---
# 보고가고 Flutter 핸드오프

## 현재 기준 및 다음 작업 시작점 (2026-10-02)

- GitHub `origin/main`의 `696eacf`까지 로컬 `master`에 반영했다. 이전에 새 커밋 8개를 가져왔고, 이번에는 알림 읽음 상태 통합 커밋 1개를 로컬 핸드오프 커밋과 병합했다. 핸드오프 내용 충돌은 두 기록을 모두 살려 해결했다. 로컬 병합 커밋은 아직 GitHub에 올리지 않았다.
- 새 작업의 중심 화면은 `lib/screens/trip/itinerary_screen.dart`다. 일정 공유 바텀시트, 고정 동행자 3명, 모드별 동행자 권한 표시, 일정 카드 아래 인라인 시간·장소·설명 편집이 추가됐다. 시간은 `HH:mm` 형식의 유효한 값만 저장한다.
- `lib/services/notification_service.dart`가 예시 알림과 앱 실행 중 읽음 상태를 관리한다. `lib/screens/my/notifications_screen.dart`의 항목 읽기·모두 읽음이 홈 알림 배지에 반영되고, 읽지 않은 알림이 없으면 배지가 사라진다.
- **다음 작업 전 확인:** `git status --short`로 작업 트리를 확인하고, `flutter` 폴더에서 `C:\flutter\bin\dart.bat analyze lib/screens/trip/itinerary_screen.dart lib/screens/my/notifications_screen.dart lib/screens/home/home_screen.dart lib/services/notification_service.dart`를 실행한다. 가져온 원격 변경은 이 환경에서 새로 전체 분석하거나 기기에서 재검증하지 않았다.
- **현재 구현 범위:** 공유·초대 링크, 동행자, 권한, 변경 알림, 일정 편집은 UI/목업 및 화면 내 상태다. 실제 동행자 계정·초대 수락·서버 권한 검사·일정 동기화·알림 저장은 연결되지 않았다. 후속 개발 시 이 연결과 편집 상태 유지가 핵심 작업이다.
- 기존 미커밋 변경 `lib/app.dart`(빈 줄), macOS/Windows 생성 플러그인 파일 3개, 루트의 미추적 `incoming-dx/`는 이번 동기화와 무관하다. 다음 커밋에 무심코 포함하지 않는다.

## 2026-10-02 홈 검색 후속 작업

- 홈의 인사말 아래 `어디로 떠나볼까요?` 문구를 제거했다.
- `말로 찾기`는 별도 화면 대신 홈 하단에 음성 인식 패널을 띄운다. 인식이 끝나면 해당 문구로 여행지 검색 화면을 연다. Android 에뮬레이터에서 마이크 권한과 패널 동작을 확인했다.
- `직접 입력` 화면에는 기본 `지역`과 두 번째 `링크` 선택지를 추가했다. 링크 검색은 URL의 경로·쿼리·프래그먼트에 포함된 장소명이나 지역명을 현재 등록된 장소 데이터와 비교한다. 단축 링크나 주소에 장소명이 없는 링크는 해석하지 못한다.
- 홈/직접 입력 변경은 `fd22ace`로 커밋했다. 직접 입력 화면 `dart analyze`와 `git diff --check`를 통과했다.
- 앞선 저장 장소 보기와 홈 버튼 배치 변경은 `083b783`, `3e1c18c`, `cf7d85a`에 커밋했다.
- 당시 `git merge origin/main` 결과는 `Already up to date`였다. 이후 홈 검색 관련 로컬 커밋은 GitHub에 올렸고, 이번 동기화에서 원격의 후속 커밋 8개까지 반영했다.
- 카메라 결과와 검색 결과는 여전히 샘플 장소 데이터에 기반하며, URL 페이지 내용을 읽거나 외부 지도 API를 호출하지 않는다.

## 2026-10-02 추가 작업

- 지난 여행 화면에 홈·탐색·저장·마이 하단 탭을 추가했다. 저장 탭에서 들어온 경우 저장 선택 상태를, 마이페이지에서 들어온 경우 마이 선택 상태를 유지한다.
- 편한 모드 홈의 `어디로 여행 갈까요?` 카드에 `사진으로 찾기` 버튼을 추가했다. 말로 찾기는 직접 입력과 같은 연한 색, 사진으로 찾기는 진한 기본 색이다. 기본·편한 모드의 알림 버튼은 약 20% 키웠다.
- 사진 결과 화면에 하단 탭과 `장소 저장`·`여행 만들기` 버튼을 추가했다. 현재 목업 결과인 안목해변을 저장하면 저장 탭에서 `사진 저장`으로 표시한다. 여행 만들기는 날짜 선택 단계부터 열린다.
- 관련 Dart 분석은 통과했다. 기기 실행은 아직 확인하지 않았다. 카메라 촬영·장소 인식은 목업이며 사진 저장 상태는 앱 실행 중에만 유지된다.
- 로컬 개선 `aeed615`를 커밋한 뒤 원격 `main`의 `b11139a`를 `a7f616d`로 병합했다. 충돌은 없었고 로그인·마이페이지와 수정 화면의 Dart 분석을 다시 통과했다.

## 이번 작업

### 일정 공동 수정 및 인라인 편집

- `lib/screens/trip/itinerary_screen.dart`에서 `코스 수정` 모드의 연필 버튼을 실제 편집 동작으로 연결했다.
  - 선택한 일정 카드 바로 아래에 시간·장소·설명 편집창이 열리고, 저장하면 해당 날짜의 화면 내 일정 데이터에 즉시 반영된다.
  - 현재는 API 연동 전 목업/로컬 상태(`_manualSchedules`)라 앱을 다시 시작하면 초기화된다.
- 수정 중 카드는 `민` 아이콘과 `수정 중`으로 표시한다.
  - 내 수정(마이페이지의 민우)은 파랑, 민지는 보라, 민우 표시는 분홍 계열로 구분한다.
  - `민` 아이콘을 탭하면 스낵바로 실제 사용자명(예: `민우님이 수정 중입니다`)을 확인할 수 있다.
- Flutter `ListTile`의 중간 배경색으로 발생하던 잉크 효과 오류를 피하기 위해 일정 난이도 카드의 중간 배경색 선언을 제거했다.


- 앱 표시명을 `여행메이트`에서 `보고가고`로 통일했습니다.
  - Flutter 앱 제목, Android/iOS/Web/Windows/macOS/Linux 표시명 및 프로젝트 안내 문서에 반영했습니다.
  - 패키지 ID와 프로젝트 폴더명인 `travel_mate`는 배포·외부 연동 영향 때문에 유지했습니다.
- 기본 모드 마이페이지를 편한 모드와 분리했습니다.
  - 기본 모드: 프로필 요약, 여행 통계, 여행 관리/앱 설정의 목록형 UI
  - 편한 모드: 기존 큰 카드·격자형 UI 유지
- 저장한 장소 화면을 모드별로 분리했습니다.
  - 기본 모드: 작은 이미지의 세로 목록 및 간결한 AI 분석 진입
  - 편한 모드: 기존 2열 큰 카드 유지
- 기본 모드 홈을 정리했습니다.
  - 여행 만들기 아래의 중복 음성 검색·직접 검색 버튼 제거
  - 검색창 아래에 오늘 날씨 카드 추가
- 날씨 화면에 7일 예보를 추가했습니다.
  - 기본 모드에 맞춘 작은 가로 예보 칩(요일·아이콘·최고/최저 기온)
  - 초기 구현은 샘플 예보 데이터이며 실시간 날씨 API 연동은 미구현입니다.

- Android Studio에서 구조를 쉽게 파악할 수 있도록 주요 화면·서비스·여행 생성 단계에 기능 설명 Dart 문서 주석(///)을 보강했습니다.

- 기본·편한 모드 마이페이지 하단에 로그아웃 버튼을 추가했습니다.
  - 확인 대화상자 후 앱의 인증 토큰을 지우고 로그인 화면으로 돌아갑니다.
  - 편한 모드에서는 버튼 높이·글자·아이콘을 키워 가독성을 높였습니다.
- 전체 일정 화면 상단에 여행 일정 공유 버튼을 추가했습니다.
  - 보기 전용 링크와 친구 초대 링크를 바텀시트에서 복사합니다.
  - 실제 초대 수락·동행자 공동 편집은 서버 멤버십 API 연동이 필요합니다.
  - 현재는 민지·준호·서연 3명의 고정 동행자 데이터와 링크 복사 상태를 표시해 UI 흐름을 미리 확인할 수 있습니다.

## 주요 변경 파일

- `lib/screens/home/home_screen.dart`
- `lib/screens/my/profile_screen.dart`
- `lib/screens/preference/youtube_saved_screen.dart`
- `lib/screens/travel/weather_screen.dart`
- `android/app/src/main/AndroidManifest.xml`
- `ios/Runner/Info.plist`
- `web/index.html`, `web/manifest.json`

## 검증

- `git diff --check` 통과
- 이 환경에서는 `dart`/`flutter` 분석 명령이 응답하지 않아 `flutter analyze`는 완료하지 못했습니다.

## 주의

- `macos/Flutter/GeneratedPluginRegistrant.swift`의 변경은 이번 작업 이전부터 존재하던 항목으로, 이번 커밋에 포함하지 않았습니다.

## 2026-10-01 작업 업데이트

### 편한 모드

- 일정 반영 및 코스 오류를 수정했다.
- 좋아요 저장 상태, 날씨 반영 코스, 저장한 여행지에서 바로 코스를 만드는 흐름을 추가했다.
- 홈 배너를 고정하고 이동 수단 표기를 보완했다.
- 로그아웃 기능을 추가했다.

### 기본 모드

- 일반 모드와 편한 모드 전환을 구현하고 기본 모드 페이지를 재구성했다.
- 중복 검색 흐름을 제거했다.
- 앱 이름을 `보고가고`로 변경했다.
- 날씨 카드와 주간 날씨를 추가했다.
- 로그아웃 기능을 추가했다.

## 2026-10-02 작업 업데이트

### 계정 기능

- 로그아웃 버튼, 회원탈퇴 버튼, 자동 로그인 버튼을 추가했다.

### 일정 공유·초대와 동행자 권한

- 링크 공유와 친구 초대 기능을 추가했다.
- 동행자 편집 권한 UI를 추가했다.
- 시니어(편한) 모드는 모든 권한을, 일반(기본) 모드는 부분 권한을 부여하도록 표시했다.

### 공동 일정 수정

- 누가 일정을 수정 중인지 보여 주고, 수정된 일정은 알림으로 확인할 수 있게 했다.
- `코스 수정` 모드에서 연필 아이콘을 누르면 해당 일정 카드 아래에 시간·장소·설명 수정창이 열린다.
- 저장하면 수정한 일정이 화면에 즉시 반영되도록 로컬 상태와 연결했다.
- 수정 중인 카드에 `민` 아이콘과 `수정 중` 상태를 표시한다.
- 내 카드(민우)는 파랑, 민지는 보라, 민우 표시는 분홍 계열로 구분한다.
- `민` 아이콘을 누르면 현재 수정 중인 사용자명을 안내한다.
- 시간 입력은 숫자 키보드와 `HH:mm` 자동 형식화를 사용하며 `00:00~23:59` 범위만 저장한다.

### 알림 읽음 처리

- 일정 변경 알림과 일반 알림을 함께 표시한다.
- 알림을 읽거나 `모두 읽음`을 누르면 빨간 미확인 표시가 사라진다.
- 미확인 알림이 0건이면 홈 알림 버튼의 빨간 배지를 표시하지 않는다.

### 검증·저장

- 일정·알림 관련 파일의 `flutter analyze`에서 `No issues found!`를 확인했다.
- GitHub `origin/main`에 다음 커밋을 푸시했다.
  - `fd27e1e` — 일정 시간 입력 검증
  - `3992ed2` — 모드별 동행자 권한 정책·핸드오프
  - `696eacf` — 통합 알림 읽음 상태
- `flutter/macos/Flutter/GeneratedPluginRegistrant.swift`의 기존 사용자 변경은 커밋에 포함하지 않았다.

## 다음 작업 우선순위

1. Android 에뮬레이터 또는 실기기에서 기본/편한 모드 전환, 계정 기능, 일정 공동 수정, 알림 읽음 상태를 수동 확인한다.
2. 동행자 권한과 알림 읽음 상태를 실제 로그인 사용자·서버 데이터 및 영구 저장소와 연결한다.
3. 목업 여행·경로·날씨 데이터를 실제 API와 오류·로딩 상태로 교체한다.

### 원격 main 최신 변경

- `lib/screens/trip/itinerary_screen.dart`
  - The inline itinerary time field uses a numeric keyboard, formats four digits as `HH:mm`, and accepts only valid clock values from `00:00` through `23:59`.
  - Saving revalidates the time so incomplete or invalid values are not persisted.
  - The companion permission policy is centralized with `_CompanionPermission`:
    - Comfort mode: every companion is shown `Edit itinerary · Add places · View`.
    - Basic mode: the mock companions are split into `Edit itinerary`, `Add places`, and `View only`.
- Validation: `flutter analyze lib/screens/trip/itinerary_screen.dart` passed.
- Important limitation: this is a local UI/mock policy only. The app has no authenticated member identity or server-side permission API yet, so permission enforcement for real shared trips remains to be implemented.
- Do not include `macos/Flutter/GeneratedPluginRegistrant.swift` in these commits; it is an unrelated pre-existing working-tree change.

## 2026-10-02: Unified notification read state

- Added `lib/services/notification_service.dart` as the shared source of mock itinerary-change and general notifications plus their in-memory read state.
- `lib/screens/my/notifications_screen.dart` now shows both notification types together. Opening an item marks it read; `모두 읽음` marks every item read.
- Both home-screen notification buttons observe the same unread state. Their red badge count updates after each read, and the entire red badge is hidden when the unread count reaches zero.
- Validation: `flutter analyze lib/screens/home/home_screen.dart lib/screens/my/notifications_screen.dart lib/services/notification_service.dart` passed.
- Scope: read state lasts while the app process is running. Persisting it across app restarts or receiving device push notifications still requires backend/local-storage integration.
