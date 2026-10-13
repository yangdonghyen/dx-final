import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:travel_mate/screens/discovery/place_result_screen.dart';
import 'package:travel_mate/screens/trip/trip_places_screen.dart';
import 'package:travel_mate/services/scene_image_service.dart';

SceneImageAnalysisResult _analysis({SceneVerifiedPlace? verifiedPlace}) {
  const candidate = ScenePlaceCandidate(placeName: 'Gyeongbokgung Palace');
  return SceneImageAnalysisResult(
    filename: 'scene.jpg',
    contentType: 'image/jpeg',
    sizeBytes: 1,
    recognized: true,
    primaryCandidate: candidate,
    candidates: const [candidate],
    evidence: const [],
    confidence: 'HIGH',
    needsVerification: true,
    placeVerified: verifiedPlace != null,
    verifiedPlace: verifiedPlace,
  );
}

void main() {
  testWidgets('blocks trip creation until the Kakao place is verified', (tester) async {
    await tester.pumpWidget(
      MaterialApp(home: PlaceResultScreen(analysis: _analysis())),
    );

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('create-trip-button')),
    );
    expect(button.onPressed, isNull);
  });

  testWidgets('passes only the verified place and coordinates into trip creation', (tester) async {
    const verifiedPlace = SceneVerifiedPlace(
      placeName: 'Gyeongbokgung Palace',
      address: 'Seoul Jongno-gu',
      roadAddress: '161 Sajik-ro',
      latitude: 37.5796,
      longitude: 126.9770,
      category: 'Attraction',
      source: 'KAKAO',
    );
    await tester.pumpWidget(
      MaterialApp(home: PlaceResultScreen(analysis: _analysis(verifiedPlace: verifiedPlace))),
    );

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('create-trip-button')),
    );
    expect(button.onPressed, isNotNull);
    await tester.tap(find.byKey(const Key('create-trip-button')));
    await tester.pumpAndSettle();

    final tripScreen = tester.widget<TripPlacesScreen>(find.byType(TripPlacesScreen));
    expect(tripScreen.initialPlaces, {'Gyeongbokgung Palace'});
    expect(tripScreen.initialVerifiedPlace!.latitude, 37.5796);
    expect(tripScreen.initialVerifiedPlace!.longitude, 126.9770);
  });
}
