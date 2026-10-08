import 'place.dart';
import 'companion.dart';

/// 일정표 한 줄에 표시할 시간, 장소, 아이콘, 메모입니다.
class ScheduleItem {
  const ScheduleItem(this.time, this.title, this.emoji, {this.note = ''});
  final String time, title, emoji, note;
}

/// 여행의 하루와 그날의 일정 항목 목록입니다.
class DayPlan {
  const DayPlan(this.day, this.date, this.items);
  final int day;
  final DateTime date;
  final List<ScheduleItem> items;
}

/// 여행 만들기 단계에서 입력한 날짜·인원·예산 등의 임시 값입니다.
class TripDraft {
  DateTime start = DateTime(2026, 9, 24), end = DateTime(2026, 9, 28);
  int travelers = 2;
  List<String> transport = ['기차'];
  String budget = '30~50만원';
  List<Place> places = [];
  List<Companion> companions = [];
}
