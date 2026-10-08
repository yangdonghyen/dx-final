import '../models/trip.dart';

/// 시니어·편안한 여행 화면에서 사용할 휴식 일정을 추가하는 서비스입니다.
class ComfortService {
  static List<ScheduleItem> rebuild(List<ScheduleItem> items) => [
    for (final x in items) ...[
      x,
      if (x.emoji != '☕' && x.emoji != '🏨')
        const ScheduleItem('', '휴식 시간', '🛋', note: '20~30분 쉬어가기'),
    ],
  ];
}
