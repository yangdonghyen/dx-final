import '../data/api/api_client.dart';
import 'auth_service.dart';

/// One verified place from GET /api/v1/places/search.
class PlaceSearchResult {
  const PlaceSearchResult({
    required this.placeId,
    required this.name,
    this.region,
    this.address,
    this.latitude,
    this.longitude,
  });

  final int placeId;
  final String name;
  final String? region;
  final String? address;
  final double? latitude;
  final double? longitude;

  factory PlaceSearchResult.fromJson(Map<String, dynamic> json) {
    return PlaceSearchResult(
      placeId: (json['place_id'] as num).toInt(),
      name: json['name']?.toString() ?? '',
      region: json['region']?.toString(),
      address: json['address']?.toString(),
      latitude: _toDouble(json['latitude']),
      longitude: _toDouble(json['longitude']),
    );
  }

  /// Decimal fields may arrive as JSON numbers or strings.
  static double? _toDouble(dynamic value) {
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }
}

class PlaceSearchService {
  PlaceSearchService({ApiClient? apiClient})
    : _apiClient = apiClient ?? ApiClient();

  final ApiClient _apiClient;

  /// Searches real places. [region] narrows the search when it is given.
  Future<List<PlaceSearchResult>> search(String query, {String? region}) async {
    final trimmedQuery = query.trim();
    final trimmedRegion = region?.trim();
    final parameters = <String, String>{
      'query': trimmedQuery,
      if (trimmedRegion != null && trimmedRegion.isNotEmpty)
        'region': trimmedRegion,
    };
    final token = AuthSession.accessToken;
    final response = await _apiClient.get(
      '/api/v1/places/search?${Uri(queryParameters: parameters).query}',
      accessToken: token == null || token.isEmpty ? null : token,
    );

    final places = response['places'];

    if (places is! List) {
      throw const FormatException(
        'places search response does not contain a places list.',
      );
    }

    return places
        .whereType<Map<String, dynamic>>()
        .map(PlaceSearchResult.fromJson)
        .where((place) => place.name.isNotEmpty)
        .toList();
  }
}
