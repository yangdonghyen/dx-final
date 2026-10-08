import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

/// 지난 여행의 날짜별 일정과 방문 기록을 다시 확인하는 화면입니다.
class PastItineraryScreen extends StatefulWidget {
  const PastItineraryScreen({super.key, required this.trip});
  final dynamic trip;

  @override
  State<PastItineraryScreen> createState() => _PastItineraryScreenState();
}

class _PastItineraryScreenState extends State<PastItineraryScreen> {
  int _selectedDay = 0;
  dynamic get trip => widget.trip;
@override
  Widget build(BuildContext context) {
    final places = List<String>.from(trip.places as List<String>);
    final startDate = _startDate(trip.startDate as String);
    final endDate = _endDate(startDate, trip.endDate as String);
    final dayCount = endDate.difference(startDate).inDays + 1;
    final selectedDay = _selectedDay.clamp(0, dayCount - 1);
    final selectedDate = startDate.add(Duration(days: selectedDay));
    final selectedRecords = _recordsForDay(selectedDay, dayCount, places);

    return Scaffold(
      backgroundColor: const Color(0xFFF7F8FF),
      appBar: AppBar(
        leading: IconButton(
          onPressed: () => Navigator.of(context).maybePop(),
          icon: const Icon(Icons.chevron_left_rounded),
          tooltip: '지난 여행으로 돌아가기',
        ),
        title: const Text('여행 기록'),
        backgroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 18, 20, 24),
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(trip.title as String, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w800)),
                const SizedBox(height: 5),
                Text('${trip.startDate} ~ ${trip.endDate} · ${trip.travelers}명', style: const TextStyle(color: Color(0xFF6B7280))),
                const SizedBox(height: 10),
                Text('총 $dayCount일 여행 기록', style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.w800)),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 46,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: dayCount,
              separatorBuilder: (_, _) => const SizedBox(width: 8),
              itemBuilder: (context, index) => ChoiceChip(
                label: Text('DAY ${index + 1}'),
                selected: selectedDay == index,
                onSelected: (_) => setState(() => _selectedDay = index),
                selectedColor: AppColors.primary,
                labelStyle: TextStyle(
                  color: selectedDay == index ? Colors.white : AppColors.ink,
                  fontWeight: FontWeight.w800,
                ),
                side: BorderSide(
                  color: selectedDay == index ? AppColors.primary : const Color(0xFFE5E7EB),
                ),
              ),
            ),
          ),
          const SizedBox(height: 18),
          _DayHeader(date: selectedDate),
          const SizedBox(height: 8),
          ...selectedRecords.asMap().entries.map((entry) {
            final item = entry.value;
            return _RecordCard(
              number: entry.key + 1,
              time: item.$1,
              emoji: item.$2,
              title: item.$3,
              detail: item.$4,
            );
          }),        ],
      ),
    );
  }

  DateTime _startDate(String startText) {
    final parts = startText.split('.');
    return DateTime(int.parse(parts[0]), int.parse(parts[1]), int.parse(parts[2]));
  }
  DateTime _endDate(DateTime start, String endText) {
    final parts = endText.split('.');
    return DateTime(start.year, int.parse(parts[0]), int.parse(parts[1]));
  }

  List<(String, String, String, String)> _recordsForDay(
    int dayIndex,
    int dayCount,
    List<String> places,
  ) {
    final firstPlace = places[(dayIndex * 2) % places.length];
    final secondPlace = places[(dayIndex * 2 + 1) % places.length];
    final isFirstDay = dayIndex == 0;
    final isLastDay = dayIndex == dayCount - 1;
    final morning = isFirstDay
        ? ('09:30', '🏨', '숙소 체크인', '짐을 맡기고 여행을 시작할 준비를 했어요.')
        : isLastDay
        ? ('09:30', '🧳', '숙소 체크아웃', '숙소를 정리하고 마지막 일정을 시작했어요.')
        : ('09:30', '🥐', '아침 준비', '오늘 일정을 위해 여유롭게 준비했어요.');
    final endOfDay = isLastDay
        ? ('17:00', '🚆', '귀가', '여행을 마치고 안전하게 돌아갔어요.')
        : ('18:00', '🏨', '숙소에서 휴식', '하루 여행을 마무리했어요.');

    return [
      morning,
      (
        '10:30',
        trip.emoji as String,
        isFirstDay ? '여행 시작 · $firstPlace' : firstPlace,
        isFirstDay ? '체크인 후 첫 여행지로 이동했어요.' : '여행 기록으로 남긴 방문 장소예요.',
      ),
      ('13:00', '🍽️', '점심 식사', '현지 맛집에서 여유롭게 식사했어요.'),
      ('15:00', '📍', secondPlace, '사진과 함께 남긴 여행지예요.'),
      endOfDay,
    ];
  }}

class _DayHeader extends StatelessWidget {
  const _DayHeader({required this.date});
  final DateTime date;

  @override
  Widget build(BuildContext context) => Text(
    '${date.month}월 ${date.day}일',
    style: const TextStyle(
      fontSize: 18,
      fontWeight: FontWeight.w900,
      color: AppColors.ink,
    ),
  );
}
class _RecordCard extends StatelessWidget {
  const _RecordCard({required this.number, required this.time, required this.emoji, required this.title, required this.detail});
  final int number; final String time; final String emoji; final String title; final String detail;
  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: const BorderSide(color: Color(0xFFE5E7EB))),
      child: ListTile(
        contentPadding: const EdgeInsets.all(14),
        leading: CircleAvatar(backgroundColor: number == 1 ? const Color(0xFF16A34A) : AppColors.primary, child: Text('$number', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800))),
        title: Text('$emoji  $title', style: const TextStyle(fontWeight: FontWeight.w800)),
        subtitle: Padding(padding: const EdgeInsets.only(top: 5), child: Text('$time · $detail')),
      ),
    );
  }}
