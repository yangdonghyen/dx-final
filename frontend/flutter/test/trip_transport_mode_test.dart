import 'package:flutter_test/flutter_test.dart';
import 'package:travel_mate/models/trip_transport_mode.dart';

void main() {
  test('serializes one primary Trip transport without reclassifying legacy states', () {
    expect(tripPrimaryTransportModeForSelection(['자동차'], walkEnabled: false), 'CAR');
    expect(tripPrimaryTransportModeForSelection(['택시'], walkEnabled: false), 'CAR');
    expect(tripPrimaryTransportModeForSelection(['대중교통'], walkEnabled: false), 'PUBLIC_TRANSIT');
    expect(tripPrimaryTransportModeForSelection(['도보'], walkEnabled: false), isNull);
    expect(tripPrimaryTransportModeForSelection(['도보'], walkEnabled: true), 'WALK');
    expect(tripPrimaryTransportModeForSelection(const [], walkEnabled: true), isNull);
    expect(tripPrimaryTransportModeForSelection(['자동차', '대중교통'], walkEnabled: true), isNull);
  });
}
