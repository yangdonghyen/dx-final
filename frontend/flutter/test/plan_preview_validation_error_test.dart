import 'package:flutter_test/flutter_test.dart';
import 'package:travel_mate/data/api/api_client.dart';
import 'package:travel_mate/services/plan_service.dart';

void main() {
  test('time conflict keeps the confirmed itinerary and avoids HTTP fallback', () {
    final message = planErrorMessage(const ApiException(422, {
      'error': {'code': 'TIME_CONFLICT', 'message': 'Schedule overlaps'},
    }));

    expect(message, contains('\uAE30\uC874 \uC77C\uC815'));
    expect(message, isNot(contains('HTTP 422')));
  });

  test('stored preview conflict remains distinguishable from validation failure', () {
    final message = planErrorMessage(const ApiException(409, {
      'error': {'code': 'PREVIEW_VERSION_CONFLICT', 'message': 'Plan changed'},
    }));

    expect(message, isNot(contains('HTTP 409')));
  });
}
