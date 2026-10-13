import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

import '../../core/theme/app_theme.dart';
import '../../services/active_trip_service.dart';
import '../../services/plan_service.dart';
import '../../widgets/itinerary_route_map.dart';
import '../../widgets/app_bottom_navigation.dart';
import '../trip/itinerary_screen.dart';

/// One stop of a day of the saved AI plan, as [TodayTravelScreen] shows it.
class TodayScheduleEntry {
  const TodayScheduleEntry({
    required this.time,
    required this.emoji,
    required this.place,
    required this.description,
    this.position,
    this.travel,
    this.travelMode,
  });

  final String time;
  final String emoji;
  final String place;
  final String description;

  /// Null when the stop has no verified coordinates; it stays off the map.
  final LatLng? position;

  /// Travel into this stop from the previous one, as the server sent it
  /// (see [planTravelLabel]). Null means nothing is shown.
  final String? travel;
  final String? travelMode;
}

/// Shows one day of the trip's saved AI plan.
///
/// With [itinerary] it shows that day as given (from the full itinerary).
/// Without it, it loads the active trip's saved plan and shows only the day
/// whose date is today. It never shows sample stops: with no trip, no plan or
/// no stop today it says so instead.
class TodayTravelScreen extends StatefulWidget {
  const TodayTravelScreen({
    super.key,
    this.itinerary,
    this.title,
    this.planService,
    this.today,
  });

  final List<TodayScheduleEntry>? itinerary;

  /// Heading for [itinerary], e.g. "DAY 2 · 10월 30일 일정".
  final String? title;
  final PlanService? planService;

  /// Defaults to the device date; tests pass a fixed date.
  final DateTime? today;

  @override
  State<TodayTravelScreen> createState() => _TodayTravelScreenState();
}

enum _LoadState { loading, ready, noTrip, noPlan, generating, notToday, failed }

class _TodayTravelScreenState extends State<TodayTravelScreen> {
  late final PlanService _planService = widget.planService ?? PlanService();
  _LoadState _state = _LoadState.loading;
  List<TodayScheduleEntry> _schedule = const [];
  String _title = '오늘 일정';
  String? _message;

  DateTime get _today => DateUtils.dateOnly(widget.today ?? DateTime.now());

  @override
  void initState() {
    super.initState();
    final given = widget.itinerary;
    if (given != null) {
      _schedule = given;
      _title = widget.title ?? '선택한 날 일정';
      _state = given.isEmpty ? _LoadState.noPlan : _LoadState.ready;
    } else {
      _load();
    }
  }

  Future<void> _load() async {
    final planId = ActiveTripService.planId;
    final tripId = ActiveTripService.tripId;
    if (planId == null && tripId == null) {
      setState(() => _state = _LoadState.noTrip);
      return;
    }
    setState(() => _state = _LoadState.loading);
    try {
      GeneratedPlan? plan;
      if (planId != null) {
        plan = await _planService.get(planId);
      } else {
        final lookup = await _planService.findForTrip(tripId!);
        if (lookup.state == TripPlanState.generating) {
          if (!mounted) return;
          setState(() => _state = _LoadState.generating);
          return;
        }
        plan = lookup.plan;
      }
      if (!mounted) return;
      if (plan == null || plan.days.isEmpty) {
        setState(() => _state = _LoadState.noPlan);
        return;
      }
      final today = _today;
      final day = plan.days
          .where(
            (day) =>
                day.visitDate != null &&
                DateUtils.isSameDay(day.visitDate, today),
          )
          .firstOrNull;
      setState(() {
        if (day == null) {
          _state = _LoadState.notToday;
          _message = _tripRangeMessage(plan!);
        } else {
          _schedule = todayEntriesForPlanDay(day);
          _title = '오늘 일정 · ${today.month}월 ${today.day}일';
          _state = _schedule.isEmpty ? _LoadState.notToday : _LoadState.ready;
        }
      });
    } catch (error) {
      debugPrint('[Today] plan load failed: $error');
      if (!mounted) return;
      setState(() {
        _state = _LoadState.failed;
        _message = planErrorMessage(error);
      });
    }
  }

  static String? _tripRangeMessage(GeneratedPlan plan) {
    final dates = [
      for (final day in plan.days)
        if (day.visitDate != null) day.visitDate!,
    ]..sort();
    if (dates.isEmpty) return null;
    String label(DateTime date) => '${date.month}월 ${date.day}일';
    final first = label(dates.first);
    final last = label(dates.last);
    return first == last
        ? '이 여행은 $first 일정이에요.'
        : '이 여행은 $first ~ $last 일정이에요.';
  }

  @override
  Widget build(BuildContext context) {
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
      body: _state == _LoadState.ready ? _scheduleBody() : _statusBody(),
      bottomNavigationBar: const AppBottomNavigation(selectedIndex: 0),
    );
  }

  Widget _statusBody() {
    if (_state == _LoadState.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    final (title, detail) = switch (_state) {
      _LoadState.noTrip => ('진행 중인 여행이 없어요', '여행을 만들면 AI가 짠 일정이 여기에 표시돼요.'),
      _LoadState.generating => ('일정을 아직 만들고 있어요', '잠시 후 다시 확인해주세요.'),
      _LoadState.notToday => (
        '오늘은 여행 일정이 없어요',
        _message ?? '전체 일정에서 날짜별 일정을 확인해주세요.',
      ),
      _LoadState.failed => ('일정을 불러오지 못했어요', _message ?? ''),
      _ => ('아직 만들어진 일정이 없어요', '여행 만들기에서 AI 일정을 생성해주세요.'),
    };
    final canRetry =
        _state == _LoadState.failed || _state == _LoadState.generating;
    final hasTrip =
        ActiveTripService.planId != null || ActiveTripService.tripId != null;
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 8),
            Text(
              detail,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Color(0xFF4B5563)),
            ),
            if (canRetry && widget.itinerary == null) ...[
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _load,
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  minimumSize: const Size.fromHeight(52),
                ),
                child: const Text('다시 확인'),
              ),
            ],
            if (_state == _LoadState.notToday && hasTrip) ...[
              const SizedBox(height: 20),
              OutlinedButton(
                onPressed: () => Navigator.of(context).pushReplacement(
                  MaterialPageRoute(
                    builder: (_) => ItineraryScreen(
                      tripDates: ActiveTripService.dates,
                      transport: ActiveTripService.transport,
                      places: ActiveTripService.places,
                    ),
                  ),
                ),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(52),
                ),
                child: const Text('전체 일정 보기'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _scheduleBody() {
    final schedule = _schedule;
    final mapped = [
      for (final (index, item) in schedule.indexed)
        if (item.position != null) (index, item),
    ];
    return Column(
      children: [
        if (mapped.isNotEmpty)
          ItineraryRouteMap(
            points: [
              for (final (_, item) in mapped)
                ItineraryMapPoint(item.place, item.position!),
            ],
            satellite: false,
            height: 192,
            label: '$_title 이동 경로',
            onMarkerTap: (index) =>
                _showScheduleDetail(context, mapped[index].$2),
          ),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 13),
          color: AppColors.soft,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _title,
                style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
              ),
              const SizedBox(height: 3),
              Text(
                '${schedule.first.emoji}  ${schedule.first.place}',
                style: const TextStyle(
                  fontSize: 19,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                schedule.first.time,
                style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280)),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 14, 20, 24),
            children: [
              Text(
                _title,
                style: const TextStyle(
                  fontSize: 21,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'AI가 만든 일정을 그대로 보여드려요.',
                style: TextStyle(color: Color(0xFF6B7280)),
              ),
              const SizedBox(height: 12),
              for (final (index, item) in schedule.indexed)
                _ScheduleCard(
                  number: index + 1,
                  item: item,
                  // The first stop has nothing to travel from.
                  travel: index == 0 ? null : item.travel,
                  onTap: () => _showScheduleDetail(context, item),
                ),
            ],
          ),
        ),
      ],
    );
  }

  void _showScheduleDetail(BuildContext context, TodayScheduleEntry item) {
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
        child: Padding(
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
                  if (item.travel != null) ...[
                    Expanded(
                      child: _DetailBox(label: '이동', value: item.travel!),
                    ),
                    const SizedBox(width: 12),
                  ],
                  const Expanded(
                    child: _DetailBox(label: '예상 비용', value: '비용 정보 없음'),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Text(
                item.description,
                style: const TextStyle(fontSize: 15, color: Color(0xFF4B5563)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ScheduleCard extends StatelessWidget {
  const _ScheduleCard({
    required this.number,
    required this.item,
    required this.travel,
    required this.onTap,
  });
  final int number;
  final TodayScheduleEntry item;
  final String? travel;
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
        child: Text(
          [
            travel == null ? item.time : '${item.time} · $travel',
            item.description,
          ].join('\n'),
        ),
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
