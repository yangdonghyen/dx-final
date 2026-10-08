import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

import '../../core/theme/app_theme.dart';
import '../../services/active_trip_service.dart';
import '../../widgets/itinerary_route_map.dart';
import 'rest_search_screen.dart';
import '../../widgets/app_bottom_navigation.dart';

/// 오늘 진행할 여행 일정을 시간 순서대로 보여주고 다음 행동을 안내하는 화면입니다.
class TodayScheduleEntry {
  const TodayScheduleEntry({
    required this.time,
    required this.emoji,
    required this.place,
    required this.description,
    required this.position,
    this.travel = '도보 10분',
  });

  final String time;
  final String emoji;
  final String place;
  final String description;
  final LatLng position;
  final String travel;
}
class TodayTravelScreen extends StatefulWidget {
  const TodayTravelScreen({
    super.key,
    this.plan = 1,
    this.transport = const {},
    this.places = const [],
    this.itinerary,
  });
  final int plan;
  final Set<String> transport;
  final List<String> places;
  final List<TodayScheduleEntry>? itinerary;

  static const _plan1 = <_Schedule>[
    _Schedule(
      '08:00',
      '🥣',
      '아침 식사 · 안목 로컬 식당',
      '도보 5분',
      '아침 식사 · 휴식',
      LatLng(37.7712, 128.9455),
    ),
    _Schedule(
      '09:30',
      '🌊',
      '안목해변 산책',
      '도보 10분',
      '산책 · 바다',
      LatLng(37.7718, 128.9465),
    ),
    _Schedule(
      '11:00',
      '☕',
      '강릉 커피거리',
      '도보 8분',
      '카페 · 휴식',
      LatLng(37.7704, 128.9440),
    ),
    _Schedule(
      '12:30',
      '🍽️',
      '점심 식사 · 강릉 중앙시장',
      '택시 15분',
      '점심 식사 · 시장',
      LatLng(37.7554, 128.8962),
    ),
    _Schedule(
      '14:00',
      '🌊',
      '경포호 산책로',
      '택시 8분',
      '산책 · 벤치',
      LatLng(37.7955, 128.8965),
    ),
    _Schedule(
      '15:30',
      '🏨',
      '숙소에서 휴식',
      '택시 12분',
      '숙소 · 휴식',
      LatLng(37.7529, 128.8902),
    ),
  ];
  static const _plan2 = <_Schedule>[
    _Schedule(
      '08:00',
      '🥣',
      '아침 식사 · 숙소 조식',
      '도보 2분',
      '아침 식사 · 실내',
      LatLng(37.7529, 128.8902),
    ),
    _Schedule(
      '09:30',
      '🏛️',
      '오죽헌',
      '택시 12분',
      '문화 · 관람',
      LatLng(37.7795, 128.8760),
    ),
    _Schedule(
      '11:20',
      '🖼️',
      '강릉시립미술관',
      '택시 12분',
      '실내 관람 · 휴식',
      LatLng(37.7660, 128.9029),
    ),
    _Schedule(
      '13:00',
      '🍽️',
      '점심 식사 · 중앙시장',
      '도보 8분',
      '점심 식사 · 실내',
      LatLng(37.7554, 128.8962),
    ),
    _Schedule(
      '14:30',
      '☕',
      '실내 카페 휴식',
      '택시 9분',
      '실내 · 휴식',
      LatLng(37.7704, 128.9440),
    ),
    _Schedule(
      '16:00',
      '🏨',
      '숙소에서 휴식',
      '택시 12분',
      '숙소 · 휴식',
      LatLng(37.7529, 128.8902),
    ),
  ];
  static const _plan3 = <_Schedule>[
    _Schedule(
      '07:00',
      '🥣',
      '아침 식사 · 숙소 조식',
      '도보 2분',
      '아침 식사 · 실내',
      LatLng(37.7529, 128.8902),
    ),
    _Schedule(
      '08:00',
      '🌅',
      '이른 안목해변 산책',
      '택시 15분',
      '이른 산책 · 바다',
      LatLng(37.7718, 128.9465),
    ),
    _Schedule(
      '10:30',
      '🎨',
      '강릉 아르떼뮤지엄',
      '택시 20분',
      '실내 전시 · 시원함',
      LatLng(37.6928, 128.8171),
    ),
    _Schedule(
      '12:30',
      '🍽️',
      '점심 식사 · 실내 식당',
      '택시 15분',
      '점심 식사 · 실내',
      LatLng(37.7040, 128.8360),
    ),
    _Schedule(
      '14:00',
      '☕',
      '그늘 카페 휴식',
      '택시 10분',
      '그늘 · 휴식',
      LatLng(37.7704, 128.9440),
    ),
    _Schedule(
      '15:30',
      '🏨',
      '숙소에서 휴식',
      '택시 12분',
      '숙소 · 휴식',
      LatLng(37.7529, 128.8902),
    ),
  ];

  @override
  State<TodayTravelScreen> createState() => _TodayTravelScreenState();
}

class _TodayTravelScreenState extends State<TodayTravelScreen> {
  static final Map<int, List<_Schedule>> _savedSchedules = {};

  late List<_Schedule> _schedule;
  int? _latestRestIndex;
  final GlobalKey _latestRestKey = GlobalKey();

  @override
  void initState() {
    super.initState();
    _schedule = _scheduleForPlan(widget.plan);
  }

  @override
  void didUpdateWidget(covariant TodayTravelScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.plan != widget.plan || oldWidget.itinerary != widget.itinerary) {
      _schedule = _scheduleForPlan(widget.plan);
      _latestRestIndex = null;
    }
  }

  List<_Schedule> _scheduleForPlan(int plan) {
    final itinerary = widget.itinerary ?? const <TodayScheduleEntry>[];
    if (itinerary.isNotEmpty) {
      return itinerary
          .map(
            (item) => _Schedule(
              item.time,
              item.emoji,
              item.place,
              item.travel,
              item.description,
              item.position,
            ),
          )
          .toList();
    }
    return _applyConfirmedPlaces(
      List<_Schedule>.of(
        _savedSchedules[plan] ??
            (plan == 2
                ? TodayTravelScreen._plan2
                : plan == 3
                ? TodayTravelScreen._plan3
                : TodayTravelScreen._plan1),
      ),
      plan,
    );
  }
  List<_Schedule> _applyConfirmedPlaces(List<_Schedule> schedule, int plan) {
    if (widget.places.isEmpty) return schedule;
    final primary = widget.places.first;
    final secondary = widget.places.length > 1 ? widget.places[1] : '$primary 주변 산책';
    final positions = List<LatLng>.generate(
      5,
      (index) => schedule[index % schedule.length].position,
    );
    final weatherStops = switch (plan) {
      2 => <(String, String, String, String)>[
        ('🏨', '숙소 체크인 · 짐 보관', '일정 시작', '체크인 · 짐 보관 후 비를 피해 출발'),
        ('📍', '$primary 실내·휴식 우선 방문', '도보 10분', '날씨를 고려해 실내 또는 짧은 동선으로 관람'),
        ('🍽️', '점심 식사 · 지역 맛집', '도보 10분', '실내 식사 60분'),
        ('☕', '$secondary 주변 카페 · 실내 휴식', '도보 10분', '비를 피하는 휴식 80분'),
        ('🛏️', '숙소 복귀 · 휴식', '도보 10분', '숙소로 돌아와 휴식'),
      ],
      3 => <(String, String, String, String)>[
        ('🏨', '숙소 체크인 · 짐 보관', '일정 시작', '체크인 · 짐 보관 후 이른 시간에 출발'),
        ('🌤️', '$primary 이른 방문', '도보 10분', '더위를 피해 오전에 대표 명소 관람'),
        ('🍽️', '점심 식사 · 지역 맛집', '도보 10분', '점심 식사 60분'),
        ('☕', '$secondary 주변 그늘 · 실내 휴식', '도보 10분', '가장 더운 시간은 카페 또는 실내에서 휴식'),
        ('🛏️', '숙소 복귀 · 휴식', '도보 10분', '해가 약해지기 전 숙소로 복귀'),
      ],
      _ => <(String, String, String, String)>[
        ('🏨', '숙소 체크인 · 짐 보관', '일정 시작', '체크인 · 짐 보관 후 가볍게 출발'),
        ('📍', primary, '도보 10분', '대표 명소 · 관람 90분'),
        ('🍽️', '점심 식사 · 지역 맛집', '도보 10분', '점심 식사 60분'),
        ('🚶', secondary, '도보 10분', '지역 산책 · 체험 90분'),
        ('🛏️', '숙소 복귀 · 휴식', '도보 10분', '숙소로 돌아와 짐 정리 · 휴식'),
      ],
    };
    return List<_Schedule>.generate(
      weatherStops.length,
      (index) => _Schedule(
        index == 0 ? '10:00' : index == 1 ? '11:00' : index == 2 ? '13:00' : index == 3 ? '14:30' : '18:30',
        weatherStops[index].$1,
        weatherStops[index].$2,
        weatherStops[index].$3,
        weatherStops[index].$4,
        positions[index],
      ),
    );
  }

  String _travelFor(int index, String defaultTravel) {
    if (index == 0) return defaultTravel;
    if (widget.transport.contains('자동차')) return '자차 8분 · 3.2km';
    if (widget.transport.contains('대중교통')) return '대중교통 16분 · 3.2km';
    if (widget.transport.contains('택시')) return '택시 12분 · 3.2km';
    return defaultTravel;
  }

  @override
  Widget build(BuildContext context) {
    final plan = widget.plan;
    final schedule = _schedule;
    final itinerary = widget.itinerary ?? const <TodayScheduleEntry>[];
    final title = itinerary.isNotEmpty
        ? '확정한 오늘 일정'
        : plan == 2
        ? '비 오는 날 계획 2'
        : plan == 3
        ? '더운 날 계획 3'
        : '오늘 일정';
    final subtitle = itinerary.isNotEmpty
        ? '전체 일정에서 확인한 오늘의 코스를 그대로 보여드려요.'
        : '확정한 여행 코스와 이동수단을 반영한 일정이에요.';
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        leading: IconButton(
          onPressed: () => Navigator.of(context).maybePop(),
          icon: const Icon(Icons.chevron_left_rounded),
          tooltip: '뒤로가기',
        ),
        title: const Text('오늘 일정'),
        backgroundColor: Colors.white,
      ),
      body: Column(
        children: [
          ItineraryRouteMap(
            points: schedule
                .map((item) => ItineraryMapPoint(item.place, item.position))
                .toList(),
            satellite: false,
            height: 192,
            label: '$title 이동 경로',
            onMarkerTap: (index) => _showScheduleDetail(
              context,
              schedule[index],
              _travelFor(index, schedule[index].travel),
            ),
          ),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 13),
            color: AppColors.soft,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                const SizedBox(height: 3),
                Text(
                  '${schedule.first.emoji}  ${schedule.first.place}',
                  style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 2),
                Text(schedule.first.time, style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 14, 20, 24),
              children: [
                Text(title, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w900)),
                const SizedBox(height: 6),
                Text(subtitle, style: const TextStyle(color: Color(0xFF6B7280))),
                const SizedBox(height: 12),
                ...schedule.asMap().entries.map(
                  (entry) => _ScheduleCard(
                    key: entry.key == _latestRestIndex ? _latestRestKey : null,
                    number: entry.key + 1,
                    item: entry.value,
                    travel: _travelFor(entry.key, entry.value.travel),
                    onTap: () => _showScheduleDetail(
                      context,
                      entry.value,
                      _travelFor(entry.key, entry.value.travel),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: const AppBottomNavigation(selectedIndex: 0),
    );
  }
  void _showScheduleDetail(
    BuildContext context,
    _Schedule item, [
    String? travel,
  ]) {
    final features = item.tags.split('·').map((tag) => tag.trim()).toList();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => SafeArea(
        top: false,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(sheetContext).height * 0.78,
          ),
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${item.time} 일정',
                            style: const TextStyle(
                              color: AppColors.primary,
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '${item.emoji} ${item.place}',
                            style: const TextStyle(
                              fontSize: 23,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      onPressed: () => Navigator.of(sheetContext).pop(),
                      tooltip: '일정 상세 닫기',
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: _DetailBox(
                        label: '이동',
                        value: travel ?? item.travel,
                      ),
                    ),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: _DetailBox(label: '예상 비용', value: '비용 정보 없음'),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                const Text(
                  '이 일정의 특징',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 9),
                Wrap(
                  spacing: 7,
                  runSpacing: 7,
                  children: features
                      .map(
                        (feature) => Chip(
                          label: Text(feature),
                          labelStyle: const TextStyle(
                            color: Color(0xFF2749A5),
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                          ),
                          backgroundColor: AppColors.soft,
                          side: BorderSide.none,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(20),
                          ),
                        ),
                      )
                      .toList(),
                ),
                if (features.contains('휴식')) ...[
                  const SizedBox(height: 15),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(13),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF0FDF4),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Text(
                      '휴식하기 좋은 일정이에요.',
                      style: TextStyle(
                        color: Color(0xFF15803D),
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: () => _findRestPlace(sheetContext, item),
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(54),
                    backgroundColor: AppColors.primary,
                  ),
                  child: Text(
                    '${item.place} 주변 휴식 장소 찾기',
                    textAlign: TextAlign.center,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _findRestPlace(
    BuildContext sheetContext,
    _Schedule target,
  ) async {
    Navigator.of(sheetContext).pop();
    final selected = await Navigator.of(context).push<RestPlaceSelection>(
      MaterialPageRoute(
        builder: (_) => RestSearchScreen(targetPlace: target.place),
      ),
    );
    if (!mounted || selected == null) return;

    final targetIndex = _schedule.indexOf(target);
    if (targetIndex < 0) return;
    final restStop = _Schedule(
      _shiftTime(target.time, 30),
      selected.icon,
      selected.name,
      selected.travel,
      'AI 추천 · 휴식',
      LatLng(
        target.position.latitude + 0.0003,
        target.position.longitude + 0.0003,
      ),
    );

    setState(() {
      _schedule = [
        ..._schedule.take(targetIndex + 1),
        restStop,
        ..._schedule
            .skip(targetIndex + 1)
            .map((stop) => stop.copyWith(time: _shiftTime(stop.time, 30))),
      ];
      _latestRestIndex = targetIndex + 1;
      _savedSchedules[widget.plan] = List<_Schedule>.of(_schedule);
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final restContext = _latestRestKey.currentContext;
      if (restContext != null) {
        Scrollable.ensureVisible(
          restContext,
          duration: const Duration(milliseconds: 350),
          alignment: 0.2,
        );
      }
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('${selected.name}을(를) 오늘의 일정에 추가했어요.')),
    );
  }

  String _shiftTime(String time, int minutesToAdd) {
    final parts = time.split(':').map(int.parse).toList();
    final totalMinutes = parts[0] * 60 + parts[1] + minutesToAdd;
    return '${(totalMinutes ~/ 60).toString().padLeft(2, '0')}:${(totalMinutes % 60).toString().padLeft(2, '0')}';
  }
}

class _ScheduleCard extends StatelessWidget {
  const _ScheduleCard({
    super.key,
    required this.number,
    required this.item,
    required this.travel,
    required this.onTap,
  });
  final int number;
  final _Schedule item;
  final String travel;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 10),
    elevation: 0,
    color: number == 1 ? const Color(0xFFF0FBF2) : Colors.white,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(18),
      side: BorderSide(
        color: number == 1 ? const Color(0xFF86D19C) : const Color(0xFFEDEFF4),
      ),
    ),
    child: ListTile(
      onTap: onTap,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      leading: CircleAvatar(
        backgroundColor: number == 1
            ? const Color(0xFF16A34A)
            : AppColors.primary,
        child: Text(
          '$number',
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w900,
          ),
        ),
      ),
      title: Text(
        '${item.emoji}  ${item.place}',
        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 5),
        child: Text('${item.time} · $travel\n${item.tags}'),
      ),
      trailing: const Text(
        '상세',
        style: TextStyle(
          fontSize: 17,
          color: AppColors.primary,
          fontWeight: FontWeight.bold,
        ),
      ),
    ),
  );
}

class _DetailBox extends StatelessWidget {
  const _DetailBox({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(
      color: const Color(0xFFF7F9FF),
      borderRadius: BorderRadius.circular(16),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
        ),
        const SizedBox(height: 5),
        Text(
          value,
          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
        ),
      ],
    ),
  );
}

class _Schedule {
  const _Schedule(
    this.time,
    this.emoji,
    this.place,
    this.travel,
    this.tags,
    this.position,
  );
  final String time;
  final String emoji;
  final String place;
  final String travel;
  final String tags;
  final LatLng position;

  _Schedule copyWith({String? time, String? place}) => _Schedule(
    time ?? this.time,
    emoji,
    place ?? this.place,
    travel,
    tags,
    position,
  );
}
