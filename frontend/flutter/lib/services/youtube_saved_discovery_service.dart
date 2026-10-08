import '../data/api/api_client.dart';
import 'auth_service.dart';

class YouTubeSavedDiscovery {
  const YouTubeSavedDiscovery({
    required this.savedDiscoveryId,
    required this.videoId,
    required this.positionSec,
    required this.title,
    required this.createdAt,
    this.pageUrl,
    this.channelTitle,
    this.thumbnailUrl,
    this.destinationName,
    this.representativeImageUrl,
  });

  final int savedDiscoveryId;
  final String videoId;
  final int positionSec;
  final String title;
  final DateTime createdAt;
  final String? pageUrl;
  final String? channelTitle;
  final String? thumbnailUrl;
  final String? destinationName;
  final String? representativeImageUrl;

  factory YouTubeSavedDiscovery.fromJson(Map<String, dynamic> json) {
    return YouTubeSavedDiscovery(
      savedDiscoveryId: json['saved_discovery_id'] as int,
      videoId: json['video_id'] as String,
      positionSec: json['position_sec'] as int,
      title: json['title'] as String,
      pageUrl: json['page_url']?.toString(),
      channelTitle: json['channel_title']?.toString(),
      thumbnailUrl: json['thumbnail_url']?.toString(),
      destinationName: json['destination_name']?.toString(),
      representativeImageUrl: json['representative_image_url']?.toString(),
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

class DestinationRecommendationPlace {
  const DestinationRecommendationPlace({
    required this.contentId,
    required this.title,
    required this.imageUrl,
    required this.category,
    this.address,
    this.contentTypeId,
    this.cat1,
    this.cat2,
    this.cat3,
    this.mapX,
    this.mapY,
  });

  final String contentId;
  final String title;
  final String imageUrl;
  final String category;
  final String? address;
  final int? contentTypeId;
  final String? cat1;
  final String? cat2;
  final String? cat3;
  final double? mapX;
  final double? mapY;

  factory DestinationRecommendationPlace.fromJson(Map<String, dynamic> json) {
    return DestinationRecommendationPlace(
      contentId: json['content_id'] as String,
      title: json['title'] as String,
      imageUrl: json['image_url'] as String,
      category: json['category'] as String,
      address: json['address']?.toString(),
      contentTypeId: (json['content_type_id'] as num?)?.toInt(),
      cat1: json['cat1']?.toString(),
      cat2: json['cat2']?.toString(),
      cat3: json['cat3']?.toString(),
      mapX: (json['map_x'] as num?)?.toDouble(),
      mapY: (json['map_y'] as num?)?.toDouble(),
    );
  }
}

class DestinationRecommendations {
  const DestinationRecommendations({
    required this.destinationName,
    required this.themes,
    required this.places,
  });

  final String destinationName;
  final List<String> themes;
  final List<DestinationRecommendationPlace> places;

  factory DestinationRecommendations.fromJson(Map<String, dynamic> json) {
    return DestinationRecommendations(
      destinationName: json['destination_name'] as String,
      themes: (json['themes'] as List? ?? const [])
          .whereType<String>()
          .toList(),
      places: (json['places'] as List? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(DestinationRecommendationPlace.fromJson)
          .toList(),
    );
  }
}

class YouTubeSavedDiscoveryService {
  YouTubeSavedDiscoveryService({ApiClient? apiClient})
    : _apiClient = apiClient ?? ApiClient();

  final ApiClient _apiClient;

  String get _accessToken {
    final token = AuthSession.accessToken;
    if (token == null || token.isEmpty) {
      throw StateError('Login is required.');
    }
    return token;
  }

  Future<YouTubeSavedDiscovery> save(Map<String, dynamic> event) async {
    final response = await _apiClient.post(
      '/api/v1/discovery/youtube-saved',
      accessToken: _accessToken,
      body: {
        'video_id': event['video_id'],
        'position_sec': event['position_sec'],
        'page_url': event['page_url'],
        'title': event['title'],
        'channel_title': event['channel_title'],
        'thumbnail_url': event['thumbnail_url'],
      },
    );

    return YouTubeSavedDiscovery.fromJson(response);
  }

  Future<void> delete(int savedDiscoveryId) async {
    await _apiClient.delete(
      '/api/v1/discovery/youtube-saved/$savedDiscoveryId',
      accessToken: _accessToken,
    );
  }

  Future<DestinationRecommendations> destinationRecommendations(
    String destinationName, {
    required int savedDiscoveryId,
  }) async {
    final encodedDestination = Uri.encodeComponent(destinationName);
    final response = await _apiClient.get(
      '/api/v1/discovery/destinations/$encodedDestination/recommendations'
      '?saved_discovery_id=$savedDiscoveryId',
      accessToken: _accessToken,
    );
    return DestinationRecommendations.fromJson(response);
  }

  Future<List<YouTubeSavedDiscovery>> list() async {
    final response = await _apiClient.get(
      '/api/v1/discovery/youtube-saved',
      accessToken: _accessToken,
    );

    final items = response['items'];
    if (items is! List) {
      throw const FormatException(
        'youtube-saved response does not contain an items list.',
      );
    }

    return items
        .whereType<Map<String, dynamic>>()
        .map(YouTubeSavedDiscovery.fromJson)
        .toList();
  }
}
