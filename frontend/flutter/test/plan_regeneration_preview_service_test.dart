import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:travel_mate/data/api/api_client.dart';
import 'package:travel_mate/services/auth_service.dart';
import 'package:travel_mate/services/plan_service.dart';

void main() {
  setUp(() {
    AuthSession.accessToken = 'test-access-token';
  });

  tearDown(() {
    AuthSession.accessToken = null;
  });

  test('creates a preview with all selected feedback codes', () async {
    late http.Request captured;
    final client = MockClient((request) async {
      captured = request;
      return http.Response(
        jsonEncode({
          'preview_id': 31,
          'plan_id': 7,
          'base_version': 4,
          'status': 'PENDING',
          'proposed_itinerary': {
            'items': [
              {'title': 'Museum', 'visit_date': '2026-10-09'},
            ],
          },
          'diff': [
            {
              'change_type': 'RESCHEDULED',
              'before': {'title': 'Museum'},
            },
          ],
          'validation_status': 'UNKNOWN',
          'expires_at': '2026-10-09T01:00:00Z',
        }),
        201,
      );
    });
    final service = PlanService(
      apiClient: ApiClient(baseUrl: 'https://preview.test', client: client),
    );

    final preview = await service.createRegenerationPreview(
      7,
      reason: 'USER_FATIGUE',
      instruction: 'Reduce walking.',
      feedbackCodes: const ['walking', 'places', 'travel', 'rest'],
    );

    expect(captured.method, 'POST');
    expect(captured.url.path, '/api/v1/plans/7/regeneration-previews');
    expect(captured.headers['authorization'], 'Bearer test-access-token');
    expect(jsonDecode(captured.body), {
      'reason': 'USER_FATIGUE',
      'instruction': 'Reduce walking.',
      'feedback_codes': ['walking', 'places', 'travel', 'rest'],
    });
    expect(preview.status, 'PENDING');
    expect(preview.proposedItinerary['items'], isA<List>());
    expect(preview.diff.single['change_type'], 'RESCHEDULED');
    expect(preview.validationStatus, 'UNKNOWN');
  });

  test(
    'approve posts no itinerary body and parses the applied version',
    () async {
      late http.Request captured;
      final client = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'preview_id': 31,
            'plan_id': 7,
            'status': 'APPLIED',
            'current_version': 5,
            'approved': true,
          }),
          200,
        );
      });
      final service = PlanService(
        apiClient: ApiClient(baseUrl: 'https://preview.test', client: client),
      );

      final result = await service.approveRegenerationPreview(7, 31);

      expect(captured.method, 'POST');
      expect(
        captured.url.path,
        '/api/v1/plans/7/regeneration-previews/31/approve',
      );
      expect(captured.body, isEmpty);
      expect(result.status, 'APPLIED');
      expect(result.currentVersion, 5);
      expect(result.approved, isTrue);
    },
  );

  test('cancel posts no itinerary body', () async {
    late http.Request captured;
    final client = MockClient((request) async {
      captured = request;
      return http.Response(
        jsonEncode({
          'preview_id': 31,
          'plan_id': 7,
          'status': 'CANCELLED',
          'approved': false,
        }),
        200,
      );
    });
    final service = PlanService(
      apiClient: ApiClient(baseUrl: 'https://preview.test', client: client),
    );

    final result = await service.cancelRegenerationPreview(7, 31);

    expect(captured.method, 'POST');
    expect(
      captured.url.path,
      '/api/v1/plans/7/regeneration-previews/31/cancel',
    );
    expect(captured.body, isEmpty);
    expect(result.status, 'CANCELLED');
    expect(result.approved, isFalse);
  });
}
