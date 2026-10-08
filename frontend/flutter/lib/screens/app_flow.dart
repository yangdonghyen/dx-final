import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';

/// 초기 화면 흐름을 한 파일에 모아 둔 시제품입니다. 현재 앱 시작점에서는 사용하지 않습니다.
class TravelMateFlow extends StatefulWidget {
  const TravelMateFlow({super.key});
  @override
  State<TravelMateFlow> createState() => _TravelMateFlowState();
}

class _TravelMateFlowState extends State<TravelMateFlow> {
  String page = 'login';
  final history = <String>[];
  final selectedPlaces = <String>{'안목해변'};
  final transport = <String>{'기차'};
  bool senior = true;
  int people = 2;
  int tab = 0;

  static const places = <PlaceData>[
    PlaceData('안목해변', '강원 강릉시', '🌊', ['바다', '카페', '산책']),
    PlaceData('황리단길', '경북 경주시', '🏛️', ['맛집', '전통', '카페']),
    PlaceData('월정리 해안도로', '제주 제주시', '🚗', ['바다', '드라이브', '휴식']),
    PlaceData('광안리해수욕장', '부산 수영구', '🌃', ['바다', '야경', '맛집']),
    PlaceData('전주 한옥마을', '전북 전주시', '🏘️', ['전통문화', '맛집', '체험']),
  ];

  void go(String value, {bool replace = false}) {
    setState(() {
      if (!replace) history.add(page);
      page = value;
    });
  }

  void back() =>
      setState(() => page = history.isEmpty ? 'home' : history.removeLast());

  @override
  Widget build(BuildContext context) {
    final screens = <String, Widget>{
      'login': login(),
      'register': formPage(
        '회원가입',
        '보고가고에 오신 것을 환영해요',
        ['이름', '이메일', '비밀번호', '비밀번호 확인'],
        '가입 완료',
        'setup',
      ),
      'setup': setup(),
      'home': home(),
      'search-text': search(false),
      'search-voice': search(true),
      'camera': camera(),
      'analyzing': loading('사진 속 장소를 분석하고 있어요', 'place-result'),
      'place-result': placesPage('검색 결과', '추천 여행지', '검색한 조건과 취향을 반영했어요'),
      'youtube-saved': placesPage(
        '저장한 여행지',
        'YouTube 저장 여행지',
        '저장한 여행 콘텐츠 12개',
        footer: 'AI 취향 분석하기',
        next: 'ai-analysis',
      ),
      'place-detail': detail(),
      'map': map(),
      'ai-analysis': insight(
        'AI 취향 분석',
        '민우님의 여행 취향',
        '🌊 바다 · 🍜 맛집 · 💆 휴식',
        '바다를 보며 쉬는 카페 여행\n걷기 좋은 전통마을 여행\n맛집 중심의 1박 2일 여행',
        '취향 확인하고 저장하기',
        'taste-confirm',
      ),
      'taste-confirm': taste(),
      'trip-places': selectPlaces(),
      'trip-date': date(),
      'trip-people': peoplePage(),
      'trip-transport': transportPage(),
      'trip-budget': selectPage('예산', '여행 만들기 5/6', '예산은 어느 정도인가요?', [
        '💚 10만원 이하',
        '💛 10~30만원',
        '🧡 30~50만원',
        '❤️ 50만원 이상',
      ], 'trip-companions'),
      'trip-companions': selectPage('동행자 조건', '여행 만들기 6/6', '동행자 정보를 알려주세요', [
        '👤 아빠 · 60대 · 걷기 30분 정도',
        '🚕 택시 적극 이용',
        '🏠 실내 선호',
        '🚫 등산 피하기',
      ], 'trip-confirm'),
      'trip-confirm': confirm(),
      'ai-loading': loading('AI가 여행 일정을 만들고 있어요', 'itinerary'),
      'itinerary': itinerary(false),
      'past-itinerary': itinerary(true),
      'weather': weather(),
      'today-travel': today(),
      'directions': simple(
        '길찾기',
        '오죽헌까지 안내',
        '택시 약 12분 · 4.2km',
        [
          '현재 위치에서 출발',
          '강릉 커피거리 앞에서 택시를 호출하세요',
          '오죽헌 입구에서 하차하세요',
          '도착 예정 12:32',
        ],
        '안내 시작',
        null,
      ),
      'rest-search': simple(
        '근처 쉴 곳',
        '잠시 쉬어가세요',
        '현재 위치에서 가까운 장소를 추천해요',
        ['☕ 편안한 카페 · 2분', '🪑 해변 쉼터 · 5분', '🚻 공용 화장실 · 3분'],
        null,
        null,
      ),
      'accommodation': simple(
        '숙소',
        '숙소를 찾아보세요',
        '여행 동선에 맞춰 추천해요',
        [
          '🏨 강릉 바다뷰 호텔 · 1박 12만원부터',
          '🏨 경포대 스테이 · 여행지까지 10분',
          '🏨 안목 게스트하우스 · 카페거리 3분',
        ],
        null,
        null,
      ),
      'pre-departure': simple(
        '출발 전 체크',
        '여행 전 준비를 확인하세요',
        '',
        [
          '✓ 기차표를 확인했어요',
          '✓ 숙소 예약을 확인했어요',
          '✓ 비 예보에 맞는 우산을 챙겼어요',
          '□ 동행자에게 일정을 공유했어요',
        ],
        '일정 보기',
        'itinerary',
      ),
      'comfort-travel': comfort(),
      'past-trips': simple(
        '지난 여행',
        '여행 기록',
        '다시 보고 싶은 추억을 꺼내보세요',
        [
          '강릉 여행 · 2026.08.20 ~ 08.22',
          '부산 여행 · 2026.07.10 ~ 07.12',
          '제주 여행 · 2026.06.02 ~ 06.05',
        ],
        '지난 일정 보기',
        'past-itinerary',
      ),
      'notifications': simple(
        '알림',
        '새로운 알림',
        '',
        [
          '🧳 여행 D-1 · 강릉 여행이 내일 시작돼요.',
          '🌧️ 오늘 비 예보 · 계획 2를 확인해보세요.',
        ],
        '날씨 일정 확인',
        'weather',
      ),
      'profile': profile(),
    };
    final hasNav = {'home', 'map', 'youtube-saved', 'profile'}.contains(page);
    return MediaQuery(
      data: MediaQuery.of(
        context,
      ).copyWith(textScaler: TextScaler.linear(senior ? 1.08 : 1)),
      child: Scaffold(
        body: SafeArea(child: screens[page] ?? home()),
        bottomNavigationBar: hasNav ? bottom() : null,
      ),
    );
  }

  Widget shell(String title, Widget body) => Column(
    children: [
      Container(
        color: Colors.white,
        child: Row(
          children: [
            IconButton(
              onPressed: back,
              icon: const Icon(Icons.chevron_left_rounded),
            ),
            Expanded(
              child: Text(
                title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
            const SizedBox(width: 48),
          ],
        ),
      ),
      Expanded(child: body),
    ],
  );
  Widget scroll(List<Widget> children) => ListView(
    padding: const EdgeInsets.fromLTRB(20, 18, 20, 28),
    children: children,
  );
  Widget heading(String title, String sub) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(fontSize: 23, fontWeight: FontWeight.w900),
        ),
        if (sub.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(sub, style: const TextStyle(color: Color(0xFF8B92A5))),
          ),
      ],
    ),
  );
  Widget card(Widget child, {Color color = Colors.white}) => Container(
    margin: const EdgeInsets.only(bottom: 13),
    padding: const EdgeInsets.all(15),
    decoration: BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(20),
      boxShadow: const [BoxShadow(color: Color(0x10000000), blurRadius: 10)],
    ),
    child: child,
  );
  Widget button(
    String text,
    VoidCallback tap, {
    bool soft = false,
    IconData? icon,
  }) => SizedBox(
    width: double.infinity,
    height: senior ? 60 : 54,
    child: FilledButton.icon(
      onPressed: tap,
      icon: icon == null ? const SizedBox() : Icon(icon),
      label: Text(text, style: const TextStyle(fontWeight: FontWeight.w900)),
      style: FilledButton.styleFrom(
        backgroundColor: soft ? AppColors.soft : AppColors.primary,
        foregroundColor: soft ? AppColors.primary : Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
    ),
  );
  Widget chip(String text, bool on, VoidCallback tap) => Padding(
    padding: const EdgeInsets.only(right: 7, bottom: 7),
    child: ChoiceChip(
      label: Text(text),
      selected: on,
      onSelected: (_) => tap(),
      selectedColor: AppColors.soft,
    ),
  );

  Widget login() => Container(
    color: Colors.white,
    child: scroll([
      const SizedBox(height: 28),
      Center(
        child: Container(
          width: 80,
          height: 80,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: AppColors.primary,
            borderRadius: BorderRadius.circular(25),
          ),
          child: const Text('✈️', style: TextStyle(fontSize: 40)),
        ),
      ),
      const SizedBox(height: 18),
      const Text(
        '보고가고',
        textAlign: TextAlign.center,
        style: TextStyle(fontSize: 30, fontWeight: FontWeight.w900),
      ),
      const SizedBox(height: 7),
      const Text(
        '나에게 맞는 여행을 시작해볼까요?',
        textAlign: TextAlign.center,
        style: TextStyle(color: Color(0xFF8B92A5)),
      ),
      const SizedBox(height: 32),
      const TextField(decoration: InputDecoration(hintText: '아이디 또는 이메일')),
      const SizedBox(height: 12),
      const TextField(
        obscureText: true,
        decoration: InputDecoration(hintText: '비밀번호'),
      ),
      const SizedBox(height: 20),
      button('로그인하기', () => go('setup', replace: true)),
      TextButton(
        onPressed: () => go('register'),
        child: const Text('아직 계정이 없으신가요? 회원가입'),
      ),
      const Divider(height: 32),
      button('카카오로 로그인하기', () => go('setup', replace: true), soft: true),
      const SizedBox(height: 10),
      button('네이버로 로그인하기', () => go('setup', replace: true), soft: true),
    ]),
  );
  Widget formPage(
    String app,
    String title,
    List<String> fields,
    String label,
    String next,
  ) => shell(
    app,
    scroll([
      heading(title, ''),
      ...fields.map(
        (x) => Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: TextField(
            obscureText: x.contains('비밀번호'),
            decoration: InputDecoration(hintText: x),
          ),
        ),
      ),
      const SizedBox(height: 12),
      button(label, () => go(next, replace: true)),
    ]),
  );
  Widget setup() => shell(
    '여행 취향 설정',
    scroll([
      heading('어떤 여행을 좋아하세요?', 'AI가 맞춤 여행을 만들어드릴게요'),
      const Text(
        '관심사 (여러 개 선택)',
        style: TextStyle(fontWeight: FontWeight.w900),
      ),
      const SizedBox(height: 8),
      Wrap(
        children: [
          '🌊 바다',
          '🍜 맛집',
          '☕ 카페',
          '🌲 자연',
          '🏛 전통문화',
          '💆 휴식',
        ].map((x) => chip(x, true, () {})).toList(),
      ),
      const SizedBox(height: 14),
      const Text('화면 모드', style: TextStyle(fontWeight: FontWeight.w900)),
      Row(
        children: [
          Expanded(
            child: chip(
              '📱 기본 모드',
              !senior,
              () => setState(() => senior = false),
            ),
          ),
          Expanded(
            child: chip(
              '🔎 편한 모드',
              senior,
              () => setState(() => senior = true),
            ),
          ),
        ],
      ),
      const SizedBox(height: 25),
      button('저장하기', () => go('home', replace: true)),
    ]),
  );
  Widget home() {
    final menu = senior
        ? [
            ('📝', '전체 일정', 'itinerary'),
            ('📅', '오늘의 일정', 'today-travel'),
            ('🧳', '여행 만들기', 'trip-places'),
            ('☀️', '오늘 날씨', 'weather'),
          ]
        : [
            ('🔎', '여행지 검색', 'search-text'),
            ('📷', '사진으로 찾기', 'camera'),
            ('🧳', '여행 계획하기', 'trip-places'),
            ('🌿', '편안한 여행', 'comfort-travel'),
          ];
    return scroll([
      heading('안녕하세요, 민우님', '보고가고 ✈️'),
      ...menu.map(
        (x) => card(
          ListTile(
            leading: Text(x.$1, style: const TextStyle(fontSize: 28)),
            title: Text(
              x.$2,
              style: const TextStyle(fontWeight: FontWeight.w900),
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => go(x.$3),
          ),
        ),
      ),
      heading('예정된 여행', ''),
      card(
        ListTile(
          title: const Text(
            '강릉 여행',
            style: TextStyle(fontWeight: FontWeight.w900),
          ),
          subtitle: const Text('9월 24일 ~ 9월 26일 · 2명 · D-1'),
          onTap: () => go('itinerary'),
        ),
      ),
      heading('저장한 여행지', ''),
      ...places.take(2).map(placeCard),
      button('지난 여행 다시 보기', () => go('past-trips'), soft: true),
    ]);
  }

  Widget bottom() => NavigationBar(
    selectedIndex: tab,
    onDestinationSelected: (value) {
      setState(() => tab = value);
      go(['home', 'map', 'youtube-saved', 'profile'][value]);
    },
    destinations: const [
      NavigationDestination(icon: Icon(Icons.home_outlined), label: '홈'),
      NavigationDestination(icon: Icon(Icons.map_outlined), label: '탐색'),
      NavigationDestination(icon: Icon(Icons.favorite_outline), label: '저장'),
      NavigationDestination(icon: Icon(Icons.person_outline), label: '마이'),
    ],
  );
  Widget search(bool voice) => shell(
    voice ? '음성으로 찾기' : '여행지 검색',
    scroll([
      heading(
        voice ? '찾고 싶은 여행지를 말해보세요' : '어디로 떠나고 싶으세요?',
        voice ? '마이크 버튼을 누르고 편하게 말씀하세요.' : '여행지, 카페, 맛집을 검색할 수 있어요',
      ),
      if (voice)
        Center(
          child: Container(
            width: 150,
            height: 150,
            alignment: Alignment.center,
            decoration: const BoxDecoration(
              color: AppColors.soft,
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.mic, size: 72, color: AppColors.primary),
          ),
        )
      else
        const TextField(
          decoration: InputDecoration(
            prefixIcon: Icon(Icons.search),
            hintText: '예: 강릉 바다 근처 카페',
          ),
        ),
      const SizedBox(height: 32),
      button(
        voice ? '음성 검색 시작' : '검색하기',
        () => go('place-result'),
        icon: voice ? Icons.mic : Icons.search,
      ),
    ]),
  );
  Widget camera() => shell(
    '사진으로 찾기',
    scroll([
      heading('사진 속 장소를 찾아드릴게요', '여행 사진을 선택하면 AI가 장소를 분석해요.'),
      Container(
        height: 280,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: const Color(0xFFE9EEF8),
          borderRadius: BorderRadius.circular(24),
        ),
        child: const Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.camera_alt_outlined, size: 72, color: AppColors.primary),
            SizedBox(height: 12),
            Text('사진을 촬영하거나 앨범에서 선택하세요'),
          ],
        ),
      ),
      const SizedBox(height: 24),
      button(
        '사진 선택하기',
        () => go('analyzing'),
        icon: Icons.photo_library_outlined,
      ),
    ]),
  );
  Widget loading(String text, String next) {
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => Future.delayed(const Duration(milliseconds: 1200), () {
        // `build` prepares the available screens.  Only the visible loading
        // screen may advance the flow; inactive screens must not redirect.
        final isVisibleLoadingScreen =
            (page == 'analyzing' && next == 'place-result') ||
            (page == 'ai-loading' && next == 'itinerary');
        if (mounted && isVisibleLoadingScreen) {
          go(next, replace: true);
        }
      }),
    );
    return Container(
      alignment: Alignment.center,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFFF0F4FF), Color(0xFFF7F0FF)],
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 24),
          const Text('🤖', style: TextStyle(fontSize: 42)),
          Text(
            text,
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 8),
          const Text('이동 거리 · 취향 · 휴식 시간을 함께 고려해요'),
        ],
      ),
    );
  }

  Widget placesPage(
    String app,
    String title,
    String sub, {
    String? footer,
    String? next,
  }) => shell(
    app,
    scroll([
      heading(title, sub),
      ...places.map(placeCard),
      if (footer != null) button(footer, () => go(next!)),
    ]),
  );
  Widget placeCard(PlaceData p) => InkWell(
    onTap: () => go('place-detail'),
    child: card(
      Row(
        children: [
          Container(
            width: 80,
            height: 80,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppColors.soft,
              borderRadius: BorderRadius.circular(15),
            ),
            child: Text(p.emoji, style: const TextStyle(fontSize: 35)),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(left: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    p.name,
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  Text(
                    p.region,
                    style: const TextStyle(color: Color(0xFF8B92A5)),
                  ),
                  Text(
                    p.tags.take(2).join(' · '),
                    style: const TextStyle(color: AppColors.primary),
                  ),
                ],
              ),
            ),
          ),
          const Icon(Icons.chevron_right),
        ],
      ),
    ),
  );
  Widget detail() => shell(
    '안목해변',
    scroll([
      Container(
        height: 220,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColors.soft,
          borderRadius: BorderRadius.circular(24),
        ),
        child: const Text('🌊', style: TextStyle(fontSize: 100)),
      ),
      const SizedBox(height: 18),
      heading('안목해변', '강원 강릉시 · 바다와 커피 향이 만나는 곳'),
      card(
        const Text(
          '바다 산책 후 카페거리를 함께 둘러보세요. 여유로운 오후 코스로 좋아요.',
          style: TextStyle(height: 1.5),
        ),
      ),
      button('여행 계획에 추가하기', () => go('trip-places')),
      const SizedBox(height: 10),
      button('지도에서 보기', () => go('map'), soft: true),
    ]),
  );
  Widget map() => shell(
    '지도 탐색',
    Stack(
      children: [
        Container(
          color: const Color(0xFFE7F0E8),
          alignment: Alignment.center,
          child: const Icon(
            Icons.map_outlined,
            size: 180,
            color: Color(0xFF6B9B79),
          ),
        ),
        Positioned(
          left: 20,
          right: 20,
          top: 18,
          child: TextField(
            readOnly: true,
            onTap: () => go('search-text'),
            decoration: const InputDecoration(
              fillColor: Colors.white,
              hintText: '장소를 검색해보세요',
              prefixIcon: Icon(Icons.search),
            ),
          ),
        ),
        const Positioned(
          left: 80,
          top: 220,
          child: Chip(label: Text('📍 안목해변')),
        ),
        const Positioned(
          right: 35,
          top: 350,
          child: Chip(label: Text('☕ 카페거리')),
        ),
      ],
    ),
  );
  Widget insight(
    String app,
    String title,
    String result,
    String suggestions,
    String label,
    String next,
  ) => shell(
    app,
    scroll([
      heading(title, '저장한 여행지와 콘텐츠를 분석했어요'),
      card(
        Text(
          result,
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
        ),
        color: AppColors.soft,
      ),
      card(
        Text(
          suggestions,
          style: const TextStyle(height: 2, fontWeight: FontWeight.w700),
        ),
      ),
      button(label, () => go(next)),
    ]),
  );
  Widget taste() => shell(
    '취향 확인',
    scroll([
      heading('이 취향이 맞나요?', '언제든지 다시 바꿀 수 있어요'),
      Wrap(
        children: [
          '🌊 바다',
          '🍜 맛집',
          '💆 휴식',
          '☕ 카페',
          '🌲 자연',
        ].map((x) => chip(x, true, () {})).toList(),
      ),
      const SizedBox(height: 25),
      button('저장하기', () => go('home', replace: true)),
    ]),
  );
  Widget selectPlaces() => shell(
    '장소 선택',
    scroll([
      heading('여행 만들기 1/6', '가보고 싶은 여행지를 선택해주세요'),
      ...places.map(
        (p) => InkWell(
          onTap: () => setState(
            () => selectedPlaces.contains(p.name)
                ? selectedPlaces.remove(p.name)
                : selectedPlaces.add(p.name),
          ),
          child: card(
            Row(
              children: [
                Text(p.emoji, style: const TextStyle(fontSize: 28)),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    p.name,
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                ),
                Icon(
                  selectedPlaces.contains(p.name)
                      ? Icons.check_circle
                      : Icons.circle_outlined,
                  color: AppColors.primary,
                ),
              ],
            ),
            color: selectedPlaces.contains(p.name)
                ? AppColors.soft
                : Colors.white,
          ),
        ),
      ),
      button('선택 완료 (${selectedPlaces.length}곳)', () => go('trip-date')),
    ]),
  );
  Widget date() => shell(
    '날짜 선택',
    scroll([
      heading('여행 만들기 2/6', '여행 기간을 선택해주세요'),
      card(
        CalendarDatePicker(
          initialDate: DateTime(2026, 9, 24),
          firstDate: DateTime(2026),
          lastDate: DateTime(2027),
          onDateChanged: (_) {},
        ),
      ),
      const Text(
        '9월 24일 → 9월 26일 · 3일',
        textAlign: TextAlign.center,
        style: TextStyle(fontWeight: FontWeight.w900),
      ),
      const SizedBox(height: 20),
      button('다음', () => go('trip-people')),
    ]),
  );
  Widget peoplePage() => shell(
    '인원 선택',
    scroll([
      heading('여행 만들기 3/6', '몇 명이 함께 가나요?'),
      card(
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            IconButton(
              onPressed: people > 1 ? () => setState(() => people--) : null,
              icon: const Icon(Icons.remove_circle_outline, size: 35),
            ),
            Text(
              '$people명',
              style: const TextStyle(fontSize: 34, fontWeight: FontWeight.w900),
            ),
            IconButton(
              onPressed: () => setState(() => people++),
              icon: const Icon(
                Icons.add_circle,
                size: 35,
                color: AppColors.primary,
              ),
            ),
          ],
        ),
      ),
      button('다음', () => go('trip-transport')),
    ]),
  );
  Widget transportPage() => selectPage('이동수단', '여행 만들기 4/6', '어떻게 이동하시나요?', [
    '🚗 자동차',
    '🚆 기차',
    '🚌 대중교통',
    '🚕 택시',
    '🚶 도보 중심',
  ], 'trip-budget');
  Widget selectPage(
    String app,
    String step,
    String title,
    List<String> items,
    String next,
  ) => shell(
    app,
    scroll([
      heading(step, title),
      ...items.map(
        (x) =>
            card(Text(x, style: const TextStyle(fontWeight: FontWeight.w900))),
      ),
      button('다음', () => go(next)),
    ]),
  );
  Widget confirm() => shell(
    '일정 확인',
    scroll([
      heading('이 조건으로 여행을 만들어드릴게요', '조건을 확인해주세요'),
      card(
        Text(
          '📍 ${selectedPlaces.join(', ')}\n📅 9/24 ~ 9/26 · 3일\n👥 $people명\n🚗 ${transport.join(" + ")}\n💰 30~50만원',
          style: const TextStyle(height: 2, fontWeight: FontWeight.w800),
        ),
      ),
      card(
        const Text(
          'AI가 이동 거리, 취향, 동행자 조건과 휴식 시간을 고려해 DAY별 일정을 자동으로 만들어요.',
          style: TextStyle(color: AppColors.primary),
        ),
        color: AppColors.soft,
      ),
      button('🤖 AI 일정 만들기', () => go('ai-loading')),
    ]),
  );
  Widget itinerary(bool past) => shell(
    past ? '지난 여행 일정' : '강릉 여행 일정',
    scroll([
      heading(
        past ? '강릉 여행 · 2026년 8월' : '9월 24일 ~ 9월 26일',
        '$people명 · ${transport.join(" + ")}',
      ),
      _map(),
      ...[
        ['10:30', '🚆', '강릉 도착', '기차역 → 안목해변'],
        ['11:20', '🌊', '안목해변', '산책 · 사진 · 휴식'],
        ['12:10', '☕', '강릉 커피거리', '30분 휴식'],
        ['13:30', '🍲', '중앙시장', '점심 식사'],
        ['16:30', '🏨', '숙소 체크인', '여유롭게 휴식'],
      ].map(
        (x) => card(
          Text(
            '${x[0]}  ${x[1]}  ${x[2]}\n${x[3]}',
            style: const TextStyle(height: 1.6, fontWeight: FontWeight.w700),
          ),
        ),
      ),
      if (!past) button('오늘의 여행 보기', () => go('today-travel')),
    ]),
  );
  Widget _map() => InkWell(
    onTap: () => go('map'),
    child: Container(
      height: 120,
      margin: const EdgeInsets.only(bottom: 15),
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: const Color(0xFFE7F0E8),
        borderRadius: BorderRadius.circular(20),
      ),
      child: const Text(
        '🗺️ 일정 경로 지도 보기',
        style: TextStyle(fontWeight: FontWeight.w900),
      ),
    ),
  );
  Widget weather() => shell(
    '오늘 날씨',
    scroll([
      card(
        const Text(
          '강릉 · 현재 날씨\n🌧️  19° 비\n강수확률 70% · 습도 86% · 바람 3.4m/s',
          style: TextStyle(
            height: 1.8,
            color: Colors.white,
            fontSize: 17,
            fontWeight: FontWeight.w900,
          ),
        ),
        color: Color(0xFF173B76),
      ),
      heading('날씨별 오늘 일정', '현재 비 예보에는 계획 2를 추천해요.'),
      card(
        const Text(
          '🌧️ 계획 2 · 오죽헌 → 강릉시립미술관 → 실내 카페',
          style: TextStyle(height: 1.7, fontWeight: FontWeight.w900),
        ),
        color: AppColors.soft,
      ),
      button('이 일정으로 여행 보기', () => go('today-travel')),
    ]),
  );
  Widget today() => shell(
    '오늘의 여행',
    scroll([
      heading('오늘의 일정', '강릉 여행 · DAY 2 · 비 오는 날 계획 2'),
      button('길찾기 시작', () => go('directions'), icon: Icons.navigation),
      const SizedBox(height: 15),
      ...[
        '☕ 실내 카페 휴식 · 다음 장소까지 택시 12분',
        '🏛 오죽헌 · 관람 60분',
        '🎨 강릉시립미술관 · 실내 관람',
        '🍲 중앙시장 · 저녁 식사',
      ].map(
        (x) =>
            card(Text(x, style: const TextStyle(fontWeight: FontWeight.w900))),
      ),
      button('근처 쉴 곳 찾기', () => go('rest-search'), soft: true),
    ]),
  );
  Widget simple(
    String app,
    String title,
    String sub,
    List<String> items,
    String? label,
    String? next,
  ) => shell(
    app,
    scroll([
      heading(title, sub),
      ...items.map(
        (x) =>
            card(Text(x, style: const TextStyle(fontWeight: FontWeight.w800))),
      ),
      if (label != null) button(label, () => go(next!)),
    ]),
  );
  Widget comfort() => shell(
    '편안한 여행',
    scroll([
      heading('지금 어디로 가시나요?', '큰 글씨와 간단한 안내로 도와드릴게요'),
      card(
        const Text(
          '다음 일정\n오죽헌\n13:00 · 택시로 12분',
          style: TextStyle(
            fontSize: 20,
            height: 1.7,
            fontWeight: FontWeight.w900,
          ),
        ),
        color: AppColors.soft,
      ),
      button('길찾기 시작', () => go('directions'), icon: Icons.navigation),
      const SizedBox(height: 12),
      button('오늘 일정 모두 보기', () => go('today-travel'), soft: true),
      const SizedBox(height: 12),
      button('쉴 곳 찾기', () => go('rest-search'), soft: true),
    ]),
  );
  Widget profile() => shell(
    '마이페이지',
    scroll([
      card(
        const Row(
          children: [
            CircleAvatar(
              radius: 28,
              backgroundColor: AppColors.primary,
              child: Text(
                '민',
                style: TextStyle(color: Colors.white, fontSize: 23),
              ),
            ),
            SizedBox(width: 14),
            Text(
              '민우\n여유롭게 여행하는 탐험가',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900),
            ),
          ],
        ),
      ),
      ...[
        ['✈️ 지난 여행', 'past-trips'],
        ['🧳 출발 전 체크', 'pre-departure'],
        ['🏨 숙소 찾기', 'accommodation'],
        ['🔔 알림', 'notifications'],
        ['⚙️ 여행 취향 설정', 'setup'],
      ].map(
        (x) => InkWell(
          onTap: () => go(x[1]),
          child: card(
            Row(
              children: [
                Text(x[0], style: const TextStyle(fontWeight: FontWeight.w900)),
                const Spacer(),
                const Icon(Icons.chevron_right),
              ],
            ),
          ),
        ),
      ),
    ]),
  );
}

class PlaceData {
  const PlaceData(this.name, this.region, this.emoji, this.tags);
  final String name;
  final String region;
  final String emoji;
  final List<String> tags;
}
