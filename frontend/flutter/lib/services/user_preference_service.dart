import '../data/api/api_client.dart';
import 'auth_service.dart';

/// Converts setup-screen display values to the API's stable preference codes.
class UserPreferenceService {
  UserPreferenceService({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  final ApiClient _apiClient;

  static const _interestCodes = <String, String>{
    '바다': 'SEA',
    '자연': 'NATURE',
    '도시': 'CITY',
    '전통문화': 'CULTURE',
    '맛집': 'FOOD',
    '카페': 'CAFE',
    '전시': 'EXHIBITION',
    '체험': 'ACTIVITY',
    '휴식': 'REST',
  };

  static const _travelStyles = <String, String>{
    '여유롭게': 'SLOW',
    '알차게': 'STANDARD',
    '맛집 중심': 'FOOD_FOCUSED',
  };

  Future<void> saveSetup({
    required Set<String> selectedInterests,
    required String travelStyle,
    required bool seniorMode,
  }) async {
    final accessToken = AuthSession.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      throw StateError('An authenticated session is required.');
    }

    final styleCode = _travelStyles[travelStyle];
    if (styleCode == null) {
      throw ArgumentError.value(travelStyle, 'travelStyle');
    }

    final interestCodes = <String>{};
    for (final label in selectedInterests) {
      final code = _interestCodes[label];
      if (code == null) {
        throw ArgumentError.value(label, 'selectedInterests');
      }
      interestCodes.add(code);
    }

    await _apiClient.patch(
      '/api/v1/users/me/preferences',
      accessToken: accessToken,
      body: {
        'interests': interestCodes.toList()..sort(),
        'travel_style': styleCode,
        'senior_mode': seniorMode,
      },
    );
  }
}
