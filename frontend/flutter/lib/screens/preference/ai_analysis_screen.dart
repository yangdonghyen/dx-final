import 'package:flutter/material.dart';

import '../../widgets/app_header.dart';
import 'taste_confirm_screen.dart';

/// 저장한 장소와 선택한 취향을 바탕으로 여행 취향을 요약하는 화면입니다.
class AiAnalysisScreen extends StatefulWidget {
  const AiAnalysisScreen({super.key});

  @override
  State<AiAnalysisScreen> createState() => _AiAnalysisScreenState();
}

class _AiAnalysisScreenState extends State<AiAnalysisScreen> {
  @override
  void initState() {
    super.initState();
    _completeAnalysis();
  }

  Future<void> _completeAnalysis() async {
    await Future<void>.delayed(const Duration(seconds: 1));
    if (!mounted) return;

    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const TasteConfirmScreen()),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('AI 취향 분석'),
          Expanded(
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: const [
                  CircularProgressIndicator(),
                  SizedBox(height: 18),
                  Text('저장한 콘텐츠로 취향을 분석해요'),
                ],
              ),
            ),
          ),
        ],
      ),
    ),
  );
}
