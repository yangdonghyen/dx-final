/// 화면 파일 위치를 한눈에 보기 위한 라우트 이름 모음.
/// 실제 화면 이동은 각 화면의 Navigator.push로 연결하며, 이후 go_router로 교체하기 쉽도록 분리했다.
class AppRoutes {
  static const login = '/login',
      register = '/register',
      setup = '/setup',
      home = '/home',
      searchText = '/search/text',
      searchVoice = '/search/voice',
      camera = '/discovery/camera',
      map = '/discovery/map',
      youtubeSaved = '/preference/youtube-saved',
      itinerary = '/trip/itinerary',
      profile = '/my/profile';
}
