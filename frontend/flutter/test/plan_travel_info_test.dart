import 'package:flutter_test/flutter_test.dart';
import 'package:travel_mate/services/plan_service.dart';

Map<String, dynamic> _item(Map<String, dynamic> travel) => {
  'item_id': 1,
  'name': '카페',
  'validation_status': 'VALID',
  'item_type': 'PLACE',
  ...travel,
};

void main() {
  test('KNOWN shows the mode and minutes', () {
    final item = GeneratedPlanItem.fromJson(
      _item({
        'transport_mode_from_previous': 'PUBLIC_TRANSIT',
        'travel_minutes_from_previous': 21,
        'travel_status': 'KNOWN',
      }),
    );
    expect(item.travelMinutesFromPrevious, 21);
    expect(item.travelLabel, '대중교통 21분');
  });

  test('UNKNOWN says the time is not known', () {
    final item = GeneratedPlanItem.fromJson(
      _item({
        'transport_mode_from_previous': null,
        'travel_minutes_from_previous': null,
        'travel_status': 'UNKNOWN',
      }),
    );
    expect(item.travelLabel, '이동시간 정보 없음');
  });

  test('NONE shows nothing', () {
    final item = GeneratedPlanItem.fromJson(_item({'travel_status': 'NONE'}));
    expect(item.travelLabel, isNull);
  });

  test('older responses without travel fields show nothing', () {
    final item = GeneratedPlanItem.fromJson(_item({}));
    expect(item.travelStatus, isNull);
    expect(item.travelMinutesFromPrevious, isNull);
    expect(item.travelLabel, isNull);
  });

  test('previews without travel_status show only known minutes', () {
    expect(planTravelLabel(mode: 'CAR', minutes: 75), '자동차 1시간 15분');
    expect(planTravelLabel(mode: 'WALK', minutes: null), isNull);
    expect(planTravelLabel(), isNull);
  });
}
