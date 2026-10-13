/// Creates the user-facing preview summary only from verified before/after
/// diff fields. In particular, it never uses a model-supplied explanation.
String previewDiffSummary(Map<String, dynamic> row) {
  final after = _item(row['after']);
  final before = _item(row['before']);
  final item = after.isNotEmpty ? after : before;
  final name = (item['title'] ?? '일정 항목').toString();
  final type = _typeLabel(item['item_type']?.toString());

  return switch (row['change_type']?.toString()) {
    'ADDED' => '$type $name: 추가했습니다.',
    'REMOVED' => '$type $name: 일정에서 제외했습니다.',
    'RESCHEDULED' || 'REST_CHANGED' =>
      '$type $name의 시간을 ${_schedule(before)}에서 ${_schedule(after)}(으)로 변경했습니다.',
    'UNCHANGED' => '$type $name: 유지합니다.',
    _ => '$type $name: 변경되었습니다.',
  };
}

Map<String, dynamic> _item(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : const <String, dynamic>{};

String _typeLabel(String? itemType) => switch (itemType) {
  'MEAL' => '식사',
  'REST' => '휴식',
  'FREE_TIME' => '자유 시간',
  _ => '장소',
};

String _schedule(Map<String, dynamic> item) {
  final date = item['visit_date']?.toString();
  final start = item['start_time']?.toString();
  final end = item['end_time']?.toString();
  final time = [start, end].where((value) => value != null).join('~');
  return [
    date,
    time,
  ].where((value) => value != null && value.isNotEmpty).join(' ');
}
