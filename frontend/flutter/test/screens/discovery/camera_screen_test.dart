import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

import 'package:travel_mate/data/api/api_client.dart';
import 'package:travel_mate/screens/discovery/camera_screen.dart';
import 'package:travel_mate/services/auth_service.dart';
import 'package:travel_mate/services/scene_image_service.dart';

class _RecordingClient extends http.BaseClient {
  http.BaseRequest? request;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    this.request = request;
    const body = '{"received":true,"filename":"camera.png","content_type":"image/png","size_bytes":67,"recognized":false,"primary_candidate":null,"candidates":[],"evidence":[],"confidence":"LOW","needs_verification":true,"place_verified":false}';
    return http.StreamedResponse(Stream.value(utf8.encode(body)), 200);
  }
}

void main() {
  tearDown(AuthSession.clear);

  testWidgets('camera photo is previewed and sent through the analysis flow',
      (tester) async {
    final cameraImage = XFile.fromData(Uint8List.fromList(const [
      137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82,
      0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0, 31, 21, 196, 137,
      0, 0, 0, 10, 73, 68, 65, 84, 120, 156, 99, 0, 1, 0, 0, 5,
      0, 1, 13, 10, 42, 186, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66,
      96, 130,
    ]), name: 'camera.png', mimeType: 'image/png');

    final client = _RecordingClient();
    ImageSource? selectedSource;
    SceneImageAnalysisResult? completedAnalysis;
    AuthSession.accessToken = 'access-token';

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          pickImage: (source) async {
            selectedSource = source;
            return cameraImage;
          },
          sceneImageService: SceneImageService(
            apiClient: ApiClient(baseUrl: 'https://api.example', client: client),
          ),
          onAnalysisComplete: (analysis) => completedAnalysis = analysis,
          imagePreviewBuilder: (_) => const Text('camera-preview'),
        ),
      ),
    );

    await tester.tap(find.byIcon(Icons.camera_alt));
    await tester.pump();
    expect(selectedSource, ImageSource.camera);
    expect(find.text('camera-preview'), findsOneWidget);
    expect(find.text('이 사진으로 장소 찾기'), findsOneWidget);

    await tester.tap(find.text('이 사진으로 장소 찾기'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 1));

    final request = client.request! as http.MultipartRequest;
    expect(request.fields['analyze'], 'true');
    expect(request.files.single.field, 'file');
    expect(request.files.single.length, 67);
    expect(request.headers['Authorization'], 'Bearer access-token');
    expect(completedAnalysis!.recognized, isFalse);
  });

  testWidgets('camera cancellation leaves the preview and upload action hidden',
      (tester) async {
    ImageSource? selectedSource;

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          pickImage: (source) async {
            selectedSource = source;
            return null;
          },
        ),
      ),
    );

    await tester.tap(find.byIcon(Icons.camera_alt));
    await tester.pump();

    expect(selectedSource, ImageSource.camera);
    expect(find.text('이 사진으로 장소 찾기'), findsNothing);
  });
}
