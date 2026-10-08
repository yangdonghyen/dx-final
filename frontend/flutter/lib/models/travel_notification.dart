/// 알림 목록 한 건에 표시할 아이콘, 제목, 내용, 읽음 상태 데이터입니다.
class TravelNotification {
  const TravelNotification(
    this.emoji,
    this.title,
    this.body,
    this.time, {
    this.unread = false,
  });
  final String emoji, title, body, time;
  final bool unread;
}
