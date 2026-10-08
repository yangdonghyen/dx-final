# 보고가고 Flutter 빠른 안내

이 폴더는 Android Studio에서 실행하는 Flutter 앱입니다. 화면을 찾을 때는 아래 **빠른 찾기**부터 확인하세요.

## 빠른 찾기

| 하고 싶은 일 | 먼저 열 파일 |
| --- | --- |
| 앱 시작 화면·테마 변경 | `main.dart` → `app.dart` → `core/theme/app_theme.dart` |
| 로그인·회원가입·초기 설정 | `screens/auth/` |
| 홈 메뉴·하단 탭 | `screens/home/home_screen.dart` |
| 여행 만들기 전체 흐름 | `screens/trip/trip_places_screen.dart` |
| AI가 만든 전체 일정 | `screens/trip/itinerary_screen.dart` |
| 오늘 일정·날씨·길찾기 | `screens/travel/` |
| 지난 여행·알림·마이페이지 | `screens/my/` |
| 장소 검색·지도·카메라 분석 | `screens/search/`, `screens/discovery/` |
| 저장 장소·취향 분석 | `screens/preference/` |
| 공통 버튼·카드·헤더 | `widgets/` |
| 화면에 보이는 예시 데이터 | `data/mock_data.dart` |

## 실행 흐름

```text
main.dart
  └─ app.dart (TravelMateApp, 테마, 첫 화면)
       └─ screens/auth/login_screen.dart
            └─ screens/auth/setup_screen.dart
                 └─ screens/home/home_screen.dart
```

현재 화면 이동은 대부분 각 화면의 `Navigator.push`로 연결합니다. `core/routes/app_routes.dart`는 경로 이름을 모아 둔 참고 파일입니다.

## 화면별 위치

### 여행 만들기와 일정

- `screens/trip/trip_places_screen.dart` — 실제 여행 만들기 통합 화면. 장소, 날짜, 인원, 이동수단, 예산, 동행자, 확인 단계를 모두 관리합니다.
- `screens/trip/itinerary_screen.dart` — 생성된 DAY별 전체 일정과 경로 지도입니다.
- `screens/trip/ai_loading_screen.dart` — AI 일정 생성 중 화면입니다.
- `screens/trip/trip_*_screen.dart` — 단계별 분리 화면의 이전/참고 구현입니다. 새 기능은 우선 `trip_places_screen.dart`에 반영합니다.

### 여행 중 사용하는 화면

- `screens/travel/today_travel_screen.dart` — 오늘의 여행 일정입니다.
- `screens/travel/weather_screen.dart` — 오늘 날씨와 날씨별 계획 선택입니다.
- `screens/travel/directions_screen.dart` — 길찾기입니다.
- `screens/travel/rest_search_screen.dart` — 휴식 장소 검색입니다.
- `screens/travel/accommodation_screen.dart`, `pre_departure_screen.dart` — 숙소와 출발 전 확인입니다.

### 장소 찾기와 취향

- `screens/search/` — 텍스트·음성 검색입니다.
- `screens/discovery/` — 지도, 카메라 분석, 장소 결과·상세입니다.
- `screens/preference/` — 저장 장소, AI 취향 분석, 취향 확인입니다.

### 내 정보와 기록

- `screens/my/profile_screen.dart` — 마이페이지입니다.
- `screens/my/past_trips_screen.dart`, `past_itinerary_screen.dart` — 지난 여행과 상세 일정입니다.
- `screens/my/notifications_screen.dart` — 알림입니다.

## 공통 코드 위치

| 종류 | 위치 | 예시 |
| --- | --- | --- |
| 색상·테마 | `core/theme/app_theme.dart` | `AppColors.primary`, 버튼·텍스트 스타일 |
| 공통 위젯 | `widgets/` | `app_header.dart`, `primary_button.dart`, `place_card.dart` |
| 예시 데이터 | `data/mock_data.dart` | 저장 장소, 알림 |
| 데이터 형태 | `models/` | 장소, 여행, 동행자, 일정 |
| 화면용 로직 | `services/` | 편안한 여행, 일정 생성 |
| 날짜 도우미 | `core/utils/date_utils.dart` | 날짜 계산·표시 |

## 수정할 때 참고

1. 화면 문구·배치만 바꿀 때는 해당 `screens/...` 파일을 수정합니다.
2. 여러 화면에서 같은 색상·여백·버튼을 바꿀 때는 `core/theme/` 또는 `widgets/`를 먼저 확인합니다.
3. 화면의 샘플 장소·여행·알림은 `data/mock_data.dart`에서 찾습니다.
4. `screens/app_flow.dart`는 초기 프로토타입 참고용이며, 현재 앱의 실제 시작 흐름에는 사용하지 않습니다.

## 자주 쓰는 명령

`flutter/` 폴더에서 실행합니다.

```bash
flutter pub get
flutter analyze
flutter run
```
