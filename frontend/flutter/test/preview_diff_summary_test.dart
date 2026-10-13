import 'package:flutter_test/flutter_test.dart';
import 'package:travel_mate/services/preview_diff_summary.dart';

void main() {
  test('describes the actually removed place, not an AI explanation', () {
    final summary = previewDiffSummary({
      'change_type': 'REMOVED',
      'before': {'place_id': 3, 'item_type': 'PLACE', 'title': '감천문화마을'},
      'after': null,
      'reason': '광안리 해변을 제거했습니다.',
    });

    expect(summary, '장소 감천문화마을: 일정에서 제외했습니다.');
    expect(summary, isNot(contains('광안리 해변')));
  });

  test('does not claim a removal when the diff has no removed place', () {
    final summary = previewDiffSummary({
      'change_type': 'UNCHANGED',
      'before': {'place_id': 2, 'item_type': 'PLACE', 'title': '광안리 해변'},
      'after': {'place_id': 2, 'item_type': 'PLACE', 'title': '광안리 해변'},
    });

    expect(summary, '장소 광안리 해변: 유지합니다.');
    expect(summary, isNot(contains('제외')));
  });

  test('shows verified meal, rest, and time before and after values', () {
    expect(
      previewDiffSummary({
        'change_type': 'RESCHEDULED',
        'before': {
          'item_type': 'MEAL',
          'title': '국밥집',
          'visit_date': '2026-10-10',
          'start_time': '12:00',
          'end_time': '13:00',
        },
        'after': {
          'item_type': 'MEAL',
          'title': '국밥집',
          'visit_date': '2026-10-10',
          'start_time': '13:00',
          'end_time': '14:00',
        },
      }),
      '식사 국밥집의 시간을 2026-10-10 12:00~13:00에서 2026-10-10 13:00~14:00(으)로 변경했습니다.',
    );
    expect(
      previewDiffSummary({
        'change_type': 'REST_CHANGED',
        'before': {
          'item_type': 'REST',
          'title': '휴식',
          'visit_date': '2026-10-10',
          'start_time': '15:00',
          'end_time': '15:30',
        },
        'after': {
          'item_type': 'REST',
          'title': '휴식',
          'visit_date': '2026-10-10',
          'start_time': '15:00',
          'end_time': '16:00',
        },
      }),
      contains('2026-10-10 15:00~15:30에서 2026-10-10 15:00~16:00'),
    );
  });
}
