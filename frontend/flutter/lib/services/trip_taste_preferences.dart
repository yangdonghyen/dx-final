import 'package:shared_preferences/shared_preferences.dart';

/// 확정한 여행 코스의 스타일과 취향을 이 기기에 보관합니다.
class TripTastePreferences {
  TripTastePreferences._();

  static const _styleKey = 'confirmed_trip_style';
  static const _tastesKey = 'confirmed_trip_tastes';
  static final _storage = SharedPreferencesAsync();

  static Future<(String?, List<String>?)> load() async {
    final style = await _storage.getString(_styleKey);
    final tastes = await _storage.getStringList(_tastesKey);
    return (style, tastes);
  }

  static Future<void> save({
    required String style,
    required Set<String> tastes,
  }) async {
    await _storage.setString(_styleKey, style);
    await _storage.setStringList(_tastesKey, tastes.toList());
  }
}
