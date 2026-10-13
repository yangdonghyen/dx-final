import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:travel_mate/data/api/api_client.dart';
import 'package:travel_mate/services/auth_service.dart';
import 'package:travel_mate/services/trip_service.dart';

void main() {
  setUp(() {
    AuthSession.accessToken = 'test-access-token';
  });

  tearDown(() {
    AuthSession.accessToken = null;
  });

  test('creates a trip with the selected itinerary-scoped travel style', () async {
    late http.Request captured;
    final service = TripService(
      apiClient: ApiClient(
        baseUrl: 'https://trip.test',
        client: MockClient((request) async {
          captured = request;
          return http.Response(jsonEncode({'trip_id': 81, 'status': 'DRAFT'}), 201);
        }),
      ),
    );

    await service.create(
      destination: 'Busan',
      interestCodes: const ['CAFE', 'REST'],
      travelStyle: 'SLOW',
    );

    expect(captured.method, 'POST');
    expect(captured.url.path, '/api/v1/trips');
    expect(jsonDecode(captured.body), {
      'destination': 'Busan',
      'interest_codes': ['CAFE', 'REST'],
      'trip_preferences': {'travel_style': 'SLOW'},
    });
  });
}
