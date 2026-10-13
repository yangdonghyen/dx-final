# Travel Mate 프로젝트 핸드오프

최종 업데이트: 2026-09-29

## 한눈에 보는 현재 상태

Travel Mate는 여행 계획·장소 탐색·일정 확인·지난 여행 기록을 제공하는 앱이다. React 웹 구현을 기준으로 Flutter 모바일 앱을 Android Studio에서 개발하고 있다.

- 저장소: https://github.com/yangdonghyen/Dx-.git
- 브랜치: 로컬 `master`, 게시 대상 `origin/main`
- 최근 병합 커밋: `f0dee74` — 로컬 Flutter 개선(`89fbde2`, `41acfcc`, `f2c8dea`)과 원격 여행 만들기·날씨 개선(`f789de9`)을 통합했다.
- Git 상태: 이 핸드오프 업데이트를 포함한 작업을 `origin/main`에 푸시했다. 로컬에만 남은 `flutter/lib/app.dart`의 공백 변경과 미추적 `incoming-dx/`는 업로드에서 제외했다.
- Android Studio 프로젝트: `C:\Users\smhrd\Desktop\project\code\flutter`

## 다음 작업을 바로 시작하려면

1. 위 `flutter/` 폴더를 Android Studio에서 연다. `src/App.tsx`는 화면 동작을 비교할 때 참고하는 React 목업이다.
2. Windows 개발자 모드를 켜고 `flutter pub get`을 다시 실행한다. 이전 실행은 `speech_to_text` 다운로드와 잠금 파일 갱신까지 진행했지만 플러그인 심볼릭 링크 생성에서 중단됐다.
3. Android 에뮬레이터나 실제 기기에서 여행 만들기 → 날짜 범위별 전체 일정 → 대안 일정 선택 → 홈 왕복, 오늘의 일정 상세 → 휴식 장소 추가, 말로 찾기 → 검색 결과, 지난 여행 뒤로가기를 차례로 확인한다. 이 흐름들은 Dart 정적 분석은 통과했지만 기기 동작은 아직 확인하지 않았다.
4. 다른 개발 환경의 Android 빌드에서는 Flutter SDK Gradle 캐시 잠금으로 컴파일 전에 멈춘 기록이 있다. 같은 오류가 재발하면 Gradle 프로세스와 SDK 캐시 잠금을 확인한다.

현재 일정·여행지·추천 데이터는 목업이다. 오늘의 일정에 추가한 휴식 장소는 앱을 완전히 재시작하면 초기화된다. 이후 작업에서 실제 데이터 연결과 영구 저장을 결정해야 한다.

## 2026-09-29 작업 업데이트

### 전체 일정의 불편 사유별 편의 일정 재생성

- 목업 `src/App.tsx`와 `src/lib/comfort.ts`의 `일정이 힘들어요` 흐름을 Flutter 전체 일정 화면에 반영했다.
- 걷기, 장소 수, 이동시간, 휴식 부족 중 하나 이상을 선택해 일정 재생성을 요청할 수 있다.
- 걷기 사유는 관광 일정에 택시·차량 이용 권장을 표시하고, 장소 수와 이동시간 사유는 관광 일정을 줄이며, 휴식 부족 사유는 관광 후 휴식 일정을 추가한다.
- 재생성 뒤 `일정에 이렇게 반영했어요` 안내에 적용된 변경과 횟수를 표시한다.
- 사유 선택 버튼은 높이가 고정된 2×2 배치로 바꿔 선택 상태 변경에 따라 영역이 늘어나지 않게 했다.
- 다른 추천 일정을 고르면 이전의 편의 일정 결과와 안내를 초기화한다.
- 수정 파일: `flutter/lib/screens/trip/itinerary_screen.dart`

### 확인 상태

- `git diff --check` 통과.
- 이전 커밋 당시 Flutter 분석과 에뮬레이터 실행은 확인하지 않았다.
- 이전 커밋 `89fbde2`에는 위 Flutter 화면과 `Handoff.md`만 포함했고, 기존 `flutter/lib/app.dart` 수정 및 미추적 `incoming-dx/`는 제외했다.

### 전체 일정의 대안 선택과 홈 왕복 상태 유지

- 목업의 `다른 일정 보기`에 맞춰 자연 중심 코스와 맛집 집중 코스를 선택하면 일정 목록과 지도 경로에 선택한 장소를 반영한다.
- 대안 선택 영역은 항상 두 카드로 유지한다. 선택한 카드 자리에는 직전에 보던 일정이 들어가므로 처음 추천한 일정도 다시 선택할 수 있다.
- 처음 추천한 일정이 대안 카드로 이동하면 위치에 따라 `✨ 다른 일정 1 · 추천 일정` 또는 `✨ 다른 일정 2 · 추천 일정`으로 표시한다.
- 카드 제목과 설명은 왼쪽, `선택하기 →`는 오른쪽 영역 가운데에 배치했다. 대안을 선택하면 변경된 첫 장소가 보이도록 일정 목록을 스크롤한다.
- 홈 화면이 `ItinerarySession`을 보관한다. 전체 일정 화면을 닫았다가 다시 열어도 선택한 코스, 대안 카드 배치, DAY, 지도 종류와 변경 안내가 유지된다.
- 수정 파일: `flutter/lib/screens/trip/itinerary_screen.dart`, `flutter/lib/screens/home/home_screen.dart`
- 확인: 두 파일의 Dart 정적 분석에서 `No issues found!`, `git diff --check` 통과. Android 에뮬레이터 실행 확인은 아직 하지 않았다.
- 이번 커밋에서도 기존 `flutter/lib/app.dart` 수정과 미추적 `incoming-dx/`는 제외한다.

### 오늘의 일정 상세와 휴식 장소 반영

- 오늘의 일정 카드의 `상세`와 지도 마커를 누르면 일정별 시간, 장소, 이동, 특징과 주변 휴식 장소 찾기 버튼을 보여준다. `상세` 글자는 17pt로 조정했다.
- 휴식 장소 화면의 `이곳에서 휴식하기`는 선택한 장소를 오늘의 일정으로 돌려준다. 선택한 일정 바로 뒤에 휴식 일정을 추가하고, 이후 일정을 30분씩 늦추며 목록과 지도에 반영한다.
- 계획별로 추가된 휴식 일정은 앱 실행 중 화면을 나갔다 돌아와도 유지된다. 앱을 완전히 재시작한 뒤의 영구 저장은 아직 없다.
- 수정 파일: `flutter/lib/screens/travel/today_travel_screen.dart`, `flutter/lib/screens/travel/rest_search_screen.dart`

### 지난 여행 헤더

- 지난 여행 목록 화면의 왼쪽 상단에 배경 없는 큰 뒤로가기 아이콘을 추가했다. 제목은 아이콘과 같은 높이에 두고, 제목과 설명을 화면 가운데 정렬했다.
- 수정 파일: `flutter/lib/screens/my/past_trips_screen.dart`

### 말로 여행지 찾기

- 목업의 음성 검색 흐름을 참고해 마이크와 `말하기`/`다시 말하기`/`음성 입력 중지` 버튼을 누를 수 있게 연결했다. 음성이 인식되면 해당 검색어로 결과 화면을 연다.
- 음성 화면의 직접 입력 검색창과 `찾기` 버튼은 제거했다. `직접 입력으로 전환` 버튼은 별도로 남겼고, 음성 버튼과 화면 가운데에 맞췄다.
- `speech_to_text` 의존성 및 Android·iOS 마이크/음성 인식 권한 설정을 추가했다. 한국어 음성 인식이 가능하면 한국어 로캘을 사용하고, 권한이나 인식 문제가 있으면 안내 문구를 표시한다.
- 텍스트 검색 화면은 음성 인식 검색어를 초기값으로 받아 결과를 보여주며, 문장 안에 장소명이나 지역명이 포함된 경우도 검색한다.
- 수정 파일: `flutter/lib/screens/search/voice_search_screen.dart`, `flutter/lib/screens/search/text_search_screen.dart`, `flutter/pubspec.yaml`, `flutter/pubspec.lock`, `flutter/android/app/src/main/AndroidManifest.xml`, `flutter/ios/Runner/Info.plist`

### 이번 작업 확인 상태

- 관련 Flutter 화면의 Dart 정적 분석에서 `No issues found!`를 확인했다. `git diff --check`를 통과했다.
- `flutter pub get`은 패키지를 다운로드하고 잠금 파일을 갱신했지만, Windows 개발자 모드가 꺼져 있어 플러그인 심볼릭 링크 생성 단계에서 종료됐다.
- Android 에뮬레이터나 실제 기기에서 음성 인식 및 화면 흐름은 아직 실행 확인하지 않았다. 실행 환경에서 개발자 모드를 켠 뒤 `flutter pub get`과 기기 동작을 확인해야 한다.

## 프로젝트 구조

- `src/App.tsx`: React 기반의 참고 구현 화면과 흐름
- `flutter/`: Android Studio에서 실행하는 Flutter 모바일 앱
- `flutter/lib/screens/`: 로그인, 홈, 탐색, 일정, 마이페이지 등 기능별 화면
- `flutter/lib/widgets/itinerary_route_map.dart`: FlutterMap 기반의 공통 일정 경로 지도
- `DESIGN_SPEC.md`: 디자인 참고 문서

## 누적 작업 이력

### 1. Flutter 앱 기반 구성

- 기존 React 화면 흐름을 참고해 Flutter 프로젝트를 저장소의 `flutter/` 폴더에 구성했다.
- Android, iOS, Web, Windows, macOS, Linux 실행 대상과 Flutter 의존성을 포함했다.
- 공통 테마, 버튼, 화면 헤더, 일정 지도 등 재사용 UI를 구성했다.
- 로그인, 취향 설정, 홈, 탐색 지도, 일정, 마이페이지, 알림, AI 취향 재분석 흐름을 Flutter 화면으로 이관·보완했다.

### 2. 지도·GPS·일정 기능

- 탐색 지도에서 GPS 권한을 요청하고, 위치를 얻지 못하면 기본 좌표를 사용하도록 처리했다.
- 일반 지도와 위성 지도 전환을 제공한다.
- OpenStreetMap 타일을 사용하며, 일정 지도에서는 이동 경로와 순서 마커를 표시한다.
- 오늘 여행과 전체 일정 화면에서 일정별 경로·마커·날짜 또는 계획 선택 UI를 제공한다.

### 3. 접근성과 화면 용어 정리

- 큰 글자와 간결한 조작을 지원하는 모드를 기존 `시니어 모드`에서 사용자 노출 명칭 `편한 모드`로 변경했다.
- 취향 설정 화면에서 기본 모드와 편한 모드를 카드 형태로 선택하도록 정리했다.
- 화면별 안내 문구와 터치 영역을 모바일 사용에 맞게 보완했다.

### 4. 이번 최신 기능 개선

#### 홈과 알림

- 홈 화면에 비 예보 알림을 추가했다.
- 알림은 5초 후 자동으로 닫히며, 누르면 비 오는 날 일정인 계획 2로 이동한다.
- 홈의 알림 버튼을 알림 화면으로 연결했다.
- 알림 화면의 날씨 알림도 계획 2로 바로 이동한다.

#### 날씨와 오늘 여행

- 날씨 화면에서 계획 1·2·3을 선택할 수 있다.
- 선택한 계획에 맞는 오늘 여행 일정과 이동 경로 지도를 표시한다.
- 계획 2는 비 오는 날을 위한 실내 중심 일정이며, 계획 3은 더위를 고려한 일정이다.

#### 장소 탐색과 저장 장소

- 장소 상세 화면을 이미지, 태그, 편의시설, 추천 문구, 저장 상태 전환, 여행 만들기 버튼을 포함하도록 개편했다.
- 저장 장소 화면과 텍스트 검색 화면을 확장했다.

#### 지난 여행

- 전주·부산·제주 지난 여행 카드를 추가했다.
- 각 여행의 기록을 읽기 전용 타임라인으로 볼 수 있도록 추가했다.
- 지난 여행 상세 화면에서 뒤로가기가 가능하다.

## 최신 변경 파일

- `flutter/lib/screens/home/home_screen.dart`
- `flutter/lib/screens/travel/weather_screen.dart`
- `flutter/lib/screens/travel/today_travel_screen.dart`
- `flutter/lib/screens/discovery/place_detail_screen.dart`
- `flutter/lib/screens/my/past_trips_screen.dart`
- `flutter/lib/screens/my/past_itinerary_screen.dart`
- `flutter/lib/screens/my/notifications_screen.dart`
- `flutter/lib/screens/my/profile_screen.dart`
- `flutter/lib/screens/preference/youtube_saved_screen.dart`
- `flutter/lib/screens/search/text_search_screen.dart`
- `flutter/lib/screens/auth/setup_screen.dart`
- `flutter/lib/screens/app_flow.dart`
- `flutter/lib/screens/trip/itinerary_screen.dart`
- `flutter/lib/README.md`
- `src/App.tsx`

## 검증 상태

- 최신 기능 커밋 전 `git diff --check`를 통과했다.
- 이번 최신 변경 묶음은 아직 에뮬레이터 또는 실제 기기에서 실행 검증하지 않았다.
- 출시 전 `flutter/` 폴더에서 아래 명령을 실행한다.

```bash
flutter pub get
flutter analyze
flutter run
```

## 알려진 제약과 다음 작업 우선순위

1. 에뮬레이터 또는 실제 Android 기기에서 화면 전환, 날씨 계획 선택, 지도 로딩을 확인한다.
2. Android의 GPS 권한 처리와 OpenStreetMap 타일 로딩을 확인한다.
3. 현재 목업인 여행·날씨·검색·추천 데이터를 실제 API, 로딩 상태, 오류 처리로 교체한다.
4. 배포 전 Android 애플리케이션 ID `com.example.travel_mate`를 실제 패키지명으로 변경한다.
5. 대규모 배포 전 OpenStreetMap 타일 사용 정책을 검토하고 필요하면 적절한 타일 제공자로 교체한다.

## 2026-09-29 통합 작업 기록

## Session update - 2026-09-29 (travel creator and weather)

- `flutter/lib/screens/trip/trip_places_screen.dart`: rebuilt the travel-creation flow into six steps using saved places, a single large calendar date-range picker, larger senior-friendly people/transport/budget controls, and a larger confirmation view. Transport uses walking instead of train.
- The date step shows the selected range and number of nights/days. Budget custom entry is inline with the custom-budget card and formats typed amounts with thousands separators.
- The companion step now follows the mockup flow: select a registered companion, edit their age, walking tolerance, and avoided activities, and add another companion. The selected companion is shown in the confirmation summary.
- `flutter/lib/screens/trip/itinerary_screen.dart`: receives the selected travel dates and generates the DAY selector and displayed dates for the full inclusive date range, instead of a fixed three-day schedule. Long date ranges can be horizontally scrolled.
- `flutter/lib/screens/travel/weather_screen.dart`: enlarged the current-weather content and recommendation view. Replaced the uneven plan chips with fixed button cards and changed precipitation, humidity, and wind into high-contrast icon metric cards.
- Verification passed: `flutter analyze lib/screens/trip/trip_places_screen.dart`, `flutter analyze lib/screens/trip/itinerary_screen.dart`, and `flutter analyze lib/screens/travel/weather_screen.dart` all completed with no issues.
- Android emulator build note: Android Studio's run failed before app compilation because Flutter SDK Gradle could not delete `C:\flutter\packages\flutter_tools\gradle\build\kotlin\compileKotlin\cacheable\caches-jvm`; this is an SDK cache/Gradle process lock, not an app-code analysis error. Stop Gradle processes and recreate that cache before running again.
- Local state: all work is saved to disk only and intentionally not committed to Git.
## 2026-09-29 오늘 작업 누적 요약 (최신)

### 작업 환경 및 저장소

- Android Studio 프로젝트 경로: `C:\Users\user\dev\travel_mate\flutter`
- 기준 목업: `C:\Users\user\dev\travel_mate\src\App.tsx`
- 오늘 변경은 커밋 `f789de9` (`Improve trip creation and weather screens`)으로 저장되었고, GitHub 원격 저장소 `origin/main`에 푸시 완료되었습니다.

### 완료한 화면 개선

- 지난 여행: 상단 뒤로가기 버튼을 추가하고, 중복된 `지난 여행` 제목을 제거했습니다.
- 마이페이지: 빠른 메뉴와 AI 바로가기 아이콘·터치 영역을 키웠습니다.
- 오늘 여행: 상단의 `계획 1 / 2 / 3` 표기를 제거했습니다.
- 여행 만들기:
  - 저장한 장소를 선택하도록 변경했고, 특정 지역이 고정되지 않게 했습니다.
  - 날짜는 큰 단일 달력에서 기간을 선택하며, 선택한 날짜와 `n박 n일`을 표시합니다.
  - 인원 빠른 선택, 확대된 인원 조절, 도보 이동수단, 목업 기반 예산 카드를 적용했습니다.
  - 직접 입력 예산은 같은 카드 안에서 입력하며 금액에 천 단위 쉼표를 적용합니다.
  - 동행자는 등록된 동행자에서 선택하고 연령대·걷기 정도·피하고 싶은 활동을 조정할 수 있습니다.
  - 여행 확인 카드와 글자를 크게 조정했습니다.
- AI 일정: 선택한 시작일~종료일의 전체 기간만큼 DAY 목록과 날짜를 동적으로 만들며, 긴 기간은 가로 스크롤로 선택합니다.
- 오늘 날씨: 현재 날씨, 세부 지표, 추천 일정의 크기를 키웠고, 계획 1·2·3은 고정 비율 버튼 카드로 정리했습니다. 강수확률·습도·바람은 아이콘과 높은 대비의 개별 카드로 표시합니다.

### 검증 및 알려진 상태

- `trip_places_screen.dart`, `itinerary_screen.dart`, `weather_screen.dart` 대상 `flutter analyze`는 모두 오류 없이 통과했습니다.
- Android 에뮬레이터 실행은 Flutter SDK Gradle 캐시 잠금으로 중단된 이력이 있습니다. `C:\flutter\packages\flutter_tools\gradle\build\kotlin\compileKotlin\cacheable\caches-jvm` 캐시를 삭제하기 전에 Gradle 프로세스를 중지해야 합니다.
- 오늘 변경과 핸드오프는 커밋 `694067b`로 로컬 저장했으며, 원격 최신 변경과 병합했습니다.

### 원격 작업 기록

- 원격 `main`의 `f789de9`를 가져왔다. 여행 만들기 화면은 저장 장소 선택부터 날짜, 동행인, 이동, 예산, 확인까지 여섯 단계로 확장됐다. 날짜 범위와 숙박 일수, 동행인 설정, 사용자 지정 예산 입력을 다룬다.
- 전체 일정 화면은 선택한 여행 날짜 범위의 DAY와 날짜를 가로 스크롤로 보여준다. 병합하면서 기존의 대안 일정 선택과 홈 왕복 상태 유지 기능도 함께 보존했다.
- 날씨 화면의 계획 선택 및 기상 지표 카드와 프로필 바로가기 아이콘이 커졌다.
- 지난 여행 화면은 기존의 왼쪽 뒤로가기 아이콘과 가운데 정렬 제목·설명을 유지했다. 오늘의 일정은 기존 상세 화면과 휴식 장소 추가 기능을 유지했다.
- 원격 작업 기록에는 여행 만들기, 전체 일정, 날씨 화면의 Dart 분석 통과가 기록돼 있다. Android 에뮬레이터 빌드는 Flutter SDK의 Gradle 캐시 잠금 문제로 앱 컴파일 전 중단됐다고 기록돼 있다.
- 이번 병합에서 `Handoff.md`, 지난 여행, 오늘의 일정, 전체 일정 화면에 충돌이 발생했고 양쪽 기능을 반영해 해결했다. 기존 `flutter/lib/app.dart`의 공백 변경과 미추적 `incoming-dx/`는 병합 범위에서 제외했다.
- 병합 후 관련 Flutter 화면 7개의 Dart 정적 분석에서 `No issues found!`를 확인했다. 에뮬레이터나 실제 기기 실행은 이번 병합 과정에서 확인하지 않았다.

## 2026-10-12 긴 사용자명 표시 안정화

### 완료
- 홈 화면과 마이페이지에서 긴 사용자명을 말줄임표로 생략하지 않고 전체 표시하도록 변경했습니다.
- 홈 헤더는 사용자명 영역과 알림 버튼 영역을 분리해, 긴 이름이 여러 줄이 되어도 알림 버튼과 겹치지 않게 했습니다.
- 기본/편한 모드 마이페이지의 사용자명은 프로필 카드 안의 가변 폭 영역에서 줄바꿈되며, 카드 바깥으로 넘치지 않게 했습니다.

### 변경 파일
- `flutter/lib/screens/home/home_screen.dart`
- `flutter/lib/screens/my/profile_screen.dart`

### 확인
- `git diff --check` 통과.
- 실기기에서는 앱 완전 종료 후 재실행 또는 새 APK 설치 후 긴 사용자명 표시를 확인합니다.

## 2026-10-12 AI 초안·저장 목록 반응형 보완

### 완료
- AI 코스 초안의 DAY 1을 확정 일정과 같은 흐름으로 통일했습니다. 초안은 이제 `10:00 숙소 체크인 · 짐 보관 → 11:00 선택 장소 → 13:00 점심 식사 · 지역 맛집 → 14:30 다음 장소/산책 → 18:30 숙소 복귀 · 휴식` 순서와 설명을 표시합니다.
- 편한 모드 저장 장소 카드에서 지역·태그·삭제 버튼이 좁은 기기에서 가로로 충돌하던 구성을 줄바꿈 가능한 레이아웃으로 변경했고, 카드 높이를 늘려 내용이 잘리지 않도록 조정했습니다.

### 변경 파일
- `flutter/lib/screens/trip/trip_places_screen.dart`
- `flutter/lib/screens/preference/youtube_saved_screen.dart`
- `flutter/lib/core/layout/app_responsive.dart`

### 확인
- `dart format flutter/lib/screens/trip/trip_places_screen.dart` 완료.
- `git diff --check` 통과.
- 실제 Android 기기에서는 Hot Restart 후 AI 초안과 확정 DAY 1, 편한 모드 저장 카드의 긴 지역명·태그·삭제 버튼 줄바꿈을 확인합니다.

### dx-all 반영 메모 (2026-10-12)
- 백엔드 연동판에서는 AI 코스 초안이 실제 일정 생성으로 대체돼 있어 목업 초안(`_draftStep`) 변경은 반영하지 않았습니다. 목업 이동시간(예: 도보 10분 · 700m)도 들어오지 않습니다.
- 저장 장소 화면은 서버 저장 목록 버전을 유지하고, 카드 높이(`savedPlaceExtent` 248/260)만 반영했습니다.
