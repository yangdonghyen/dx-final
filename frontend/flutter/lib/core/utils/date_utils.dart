/// 여행 날짜의 표시 형식과 여행 기간을 계산하는 공용 함수입니다.
String shortDate(DateTime d) => '${d.month}/${d.day}';
int tripDays(DateTime s, DateTime e) => e.difference(s).inDays + 1;
