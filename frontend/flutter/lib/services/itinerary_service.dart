import '../models/trip.dart';

/// 여행 조건을 받아 날짜별 일정 초안을 만드는 서비스입니다.
class ItineraryService {
  static List<DayPlan> build(DateTime s, DateTime e) {
    final count = e.difference(s).inDays + 1;
    const template = <ScheduleItem>[
      ScheduleItem('10:30', '강릉 도착', '🚆'),
      ScheduleItem('11:20', '안목해변', '🌊', note: '산책 · 사진 · 휴식'),
      ScheduleItem('12:10', '카페거리', '☕', note: '30분 휴식'),
      ScheduleItem('13:30', '중앙시장', '🍲'),
      ScheduleItem('16:30', '숙소 체크인', '🏨'),
    ];
    return List.generate(
      count,
      (i) => DayPlan(i + 1, s.add(Duration(days: i)), template),
    );
  }
}
