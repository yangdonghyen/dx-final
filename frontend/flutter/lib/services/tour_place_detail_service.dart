import '../data/api/api_client.dart';
import 'auth_service.dart';

class TourPlaceDetail {
  const TourPlaceDetail({
    required this.contentId,
    this.contentTypeId,
    this.title,
    this.address,
    this.imageUrl,
    this.overview,
    this.homepage,
    this.mapX,
    this.mapY,
    this.cat1,
    this.cat2,
    this.cat3,
    this.operatingHours,
    this.restDate,
    this.useFee,
    this.parking,
    this.infoCenter,
  });

  final String contentId;
  final int? contentTypeId;
  final String? title;
  final String? address;
  final String? imageUrl;
  final String? overview;
  final String? homepage;
  final double? mapX;
  final double? mapY;
  final String? cat1;
  final String? cat2;
  final String? cat3;
  final String? operatingHours;
  final String? restDate;
  final String? useFee;
  final String? parking;
  final String? infoCenter;

  factory TourPlaceDetail.fromJson(Map<String, dynamic> json) {
    String? optionalText(String key) {
      final value = json[key]?.toString().trim();
      return value == null || value.isEmpty ? null : value;
    }

    return TourPlaceDetail(
      contentId: json['content_id']?.toString() ?? '',
      contentTypeId: (json['content_type_id'] as num?)?.toInt(),
      title: optionalText('title'),
      address: optionalText('address'),
      imageUrl: optionalText('image_url'),
      overview: optionalText('overview'),
      homepage: optionalText('homepage'),
      mapX: (json['map_x'] as num?)?.toDouble(),
      mapY: (json['map_y'] as num?)?.toDouble(),
      cat1: optionalText('cat1'),
      cat2: optionalText('cat2'),
      cat3: optionalText('cat3'),
      operatingHours: optionalText('operating_hours'),
      restDate: optionalText('rest_date'),
      useFee: optionalText('use_fee'),
      parking: optionalText('parking'),
      infoCenter: optionalText('info_center'),
    );
  }
}

class TourPlaceDetailService {
  TourPlaceDetailService({ApiClient? apiClient})
    : _apiClient = apiClient ?? ApiClient();

  final ApiClient _apiClient;

  Future<TourPlaceDetail> get(String contentId, {int? contentTypeId}) async {
    final token = AuthSession.accessToken;
    if (token == null || token.isEmpty) {
      throw StateError('Login is required.');
    }
    final query = contentTypeId == null
        ? ''
        : '?content_type_id=$contentTypeId';
    final response = await _apiClient.get(
      '/api/v1/discovery/tour-places/${Uri.encodeComponent(contentId)}$query',
      accessToken: token,
    );
    return TourPlaceDetail.fromJson(response);
  }
}
