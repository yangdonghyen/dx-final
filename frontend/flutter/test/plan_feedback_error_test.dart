import 'package:flutter_test/flutter_test.dart';

import 'package:travel_mate/data/api/api_client.dart';
import 'package:travel_mate/services/plan_service.dart';

ApiException feedbackError(String code) {
  return ApiException(422, {
    'error': {'code': code, 'message': 'Backend validation failed'},
  });
}

void main() {
  test('places/rest goal not met shows Korean guidance', () {
    final message = planErrorMessage(feedbackError('FEEDBACK_GOAL_NOT_MET'));

    expect(message, contains('수정안을 만들지 못했어요'));
    expect(message, contains('기존 일정은 그대로 유지됩니다'));
  });

  test('unachievable feedback explains the limitation', () {
    final message = planErrorMessage(
      feedbackError('FEEDBACK_GOAL_UNACHIEVABLE'),
    );

    expect(message, contains('선택 방문지'));
    expect(message, contains('기존 일정은 유지됩니다'));
  });

  test('unverifiable feedback does not claim success', () {
    final message = planErrorMessage(
      feedbackError('FEEDBACK_GOAL_UNVERIFIABLE'),
    );

    expect(message, contains('휴식시간'));
    expect(message, contains('기존 일정은 그대로 유지됩니다'));
  });

  test('existing preview storage error remains supported', () {
    final error = ApiException(503, {
      'error': {
        'code': 'PREVIEW_STORAGE_UNAVAILABLE',
        'message': 'Preview storage unavailable',
      },
    });

    final message = planErrorMessage(error);

    expect(message, contains('수정안 저장소'));
  });
}
