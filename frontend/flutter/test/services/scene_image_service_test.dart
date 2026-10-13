import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:travel_mate/data/api/api_client.dart';
import 'package:travel_mate/services/auth_service.dart';
import 'package:travel_mate/services/scene_image_service.dart';

class _RecordingClient extends http.BaseClient {
  http.BaseRequest? request;
  int responseStatus = 200;
  bool analysisResponse = false;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    this.request = request;
    final body = responseStatus == 200
        ? analysisResponse
            ? '{"received":true,"filename":"tv.jpg","content_type":"image/jpeg","size_bytes":3,"recognized":true,"primary_candidate":{"place_name":"성산일출봉","city":"서귀포시","region":"제주특별자치도","country":"대한민국","category":"관광지"},"candidates":[{"place_name":"성산일출봉","city":"서귀포시","region":"제주특별자치도","country":"대한민국","category":"관광지"}],"evidence":["화산 분화구"],"confidence":"HIGH","needs_verification":true,"place_verified":true,"verified_place":{"verified":true,"place_name":"성산일출봉","address":"제주특별자치도 서귀포시 성산읍","road_address":"제주특별자치도 서귀포시 성산읍 성산리","latitude":33.458,"longitude":126.942,"category":"관광명소","source":"KAKAO"}}'
            : '{"received":true,"filename":"tv.jpg","content_type":"image/jpeg","size_bytes":3}'
        : '{"error":{"code":"INVALID_IMAGE","message":"bad"}}';
    return http.StreamedResponse(Stream.value(utf8.encode(body)), responseStatus);
  }
}

void main() {
  tearDown(AuthSession.clear);

  test('uploads a JWT-authenticated multipart image to the scene endpoint', () async {
    final client = _RecordingClient();
    final service = SceneImageService(
      apiClient: ApiClient(baseUrl: 'https://api.example', client: client),
    );
    AuthSession.accessToken = 'access-token';

    final result = await service.upload(
      bytes: Uint8List.fromList([1, 2, 3]),
      filename: 'tv.jpg',
      contentType: 'image/jpeg',
    );

    final request = client.request! as http.MultipartRequest;
    expect(request.url.toString(), 'https://api.example/api/v1/discovery/scene-image');
    expect(request.headers['Authorization'], 'Bearer access-token');
    expect(request.files.single.field, 'file');
    expect(request.files.single.filename, 'tv.jpg');
    expect(result.sizeBytes, 3);
  });

  test('propagates API errors without crashing', () async {
    final client = _RecordingClient()..responseStatus = 415;
    final service = SceneImageService(
      apiClient: ApiClient(baseUrl: 'https://api.example', client: client),
    );
    AuthSession.accessToken = 'access-token';

    await expectLater(
      () => service.upload(
        bytes: Uint8List.fromList([1]),
        filename: 'tv.jpg',
        contentType: 'image/jpeg',
      ),
      throwsA(isA<ApiException>()),
    );
  });

  test('does not send a request without an authenticated session', () async {
    final client = _RecordingClient();
    final service = SceneImageService(
      apiClient: ApiClient(baseUrl: 'https://api.example', client: client),
    );

    await expectLater(
      () => service.upload(
        bytes: Uint8List.fromList([1]),
        filename: 'tv.jpg',
        contentType: 'image/jpeg',
      ),
      throwsStateError,
    );
    expect(client.request, isNull);
  });

  test('uploads once and parses structured place-analysis results', () async {
    final client = _RecordingClient()..analysisResponse = true;
    final service = SceneImageService(
      apiClient: ApiClient(baseUrl: 'https://api.example', client: client),
    );
    AuthSession.accessToken = 'access-token';

    final result = await service.uploadAndAnalyze(
      bytes: Uint8List.fromList([1, 2, 3]),
      filename: 'tv.jpg',
      contentType: 'image/jpeg',
    );

    final request = client.request! as http.MultipartRequest;
    expect(request.fields['analyze'], 'true');
    expect(result.recognized, isTrue);
    expect(result.primaryCandidate!.placeName, '성산일출봉');
    expect(result.evidence, ['화산 분화구']);
    expect(result.verifiedPlace!.latitude, 33.458);
    expect(result.placeVerified, isTrue);
    expect(result.verifiedPlace!.address, contains('서귀포시'));
  });

  test('parses an unrecognized result without treating it as an API error', () async {
    AuthSession.accessToken = 'access-token';
    final noMatch = _NoMatchClient();
    final noMatchService = SceneImageService(
      apiClient: ApiClient(baseUrl: 'https://api.example', client: noMatch),
    );
    final result = await noMatchService.uploadAndAnalyze(
      bytes: Uint8List.fromList([1]),
      filename: 'tv.jpg',
      contentType: 'image/jpeg',
    );
    expect(result.recognized, isFalse);
    expect(result.candidates, isEmpty);
    expect(result.verifiedPlace, isNull);
  });
}

class _NoMatchClient extends _RecordingClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    this.request = request;
    return Future.value(
      http.StreamedResponse(
        Stream.value(utf8.encode('{"received":true,"filename":"tv.jpg","content_type":"image/jpeg","size_bytes":1,"recognized":false,"primary_candidate":null,"candidates":[],"evidence":[],"confidence":"LOW","needs_verification":true,"place_verified":false}')),
        200,
      ),
    );
  }
}
