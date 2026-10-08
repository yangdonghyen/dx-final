import 'package:flutter/material.dart';

import '../../data/api/api_client.dart';
import '../../services/scene_image_service.dart';
import 'place_result_screen.dart';

/// 찍은 사진을 서버로 보내 장소를 분석하고, 끝나면 결과 화면으로 이동합니다.
class AnalyzingScreen extends StatefulWidget {
  const AnalyzingScreen({super.key, required this.imagePath});
  final String imagePath;

  @override
  State<AnalyzingScreen> createState() => _AnalyzingScreenState();
}

class _AnalyzingScreenState extends State<AnalyzingScreen> {
  final SceneImageService _sceneImageService = SceneImageService();
  String? _error;

  @override
  void initState() {
    super.initState();
    _analyze();
  }

  Future<void> _analyze() async {
    setState(() => _error = null);
    try {
      final result = await _sceneImageService.analyze(widget.imagePath);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) =>
              PlaceResultScreen(imagePath: widget.imagePath, result: result),
        ),
      );
    } catch (error) {
      debugPrint('[Scene] analyze failed: $error');
      if (mounted) setState(() => _error = _errorMessage(error));
    }
  }

  static String _errorMessage(Object error) {
    if (error is StateError) return '로그인한 뒤 다시 시도해주세요.';
    if (error is ApiException) {
      final detail = error.body['error'];
      final code = detail is Map ? detail['code'] : null;
      switch (code) {
        case 'IMAGE_TOO_LARGE':
          return '사진이 너무 커요. 다른 사진으로 시도해주세요.';
        case 'UNSUPPORTED_IMAGE_TYPE':
          return 'JPG, PNG 사진만 분석할 수 있어요.';
        case 'SCENE_RECOGNITION_NOT_CONFIGURED':
          return '서버에 사진 분석 설정이 되어 있지 않아요.';
      }
      if (error.statusCode == 401) return '로그인이 만료됐어요. 다시 로그인해주세요.';
      return '사진을 분석하지 못했어요. 잠시 후 다시 시도해주세요.';
    }
    return '서버에 연결하지 못했어요. 인터넷 연결을 확인해주세요.';
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 28),
          child: _error == null
              ? const Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    CircularProgressIndicator(),
                    SizedBox(height: 20),
                    Text(
                      'AI가 사진 속 장소를 분석하고 있어요',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 21,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ],
                )
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.error_outline,
                      size: 52,
                      color: Color(0xFFB91C1C),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      _error!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: _analyze,
                      style: FilledButton.styleFrom(
                        minimumSize: const Size(160, 52),
                      ),
                      child: const Text(
                        '다시 분석하기',
                        style: TextStyle(fontSize: 17),
                      ),
                    ),
                    TextButton(
                      onPressed: () => Navigator.of(context).maybePop(),
                      child: const Text('닫기', style: TextStyle(fontSize: 16)),
                    ),
                  ],
                ),
        ),
      ),
    ),
  );
}
