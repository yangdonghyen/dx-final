import 'package:flutter/material.dart';
import '../../widgets/app_header.dart';

/// 입력한 여행 조건으로 AI 일정안을 만드는 동안의 로딩 화면입니다.
class AiLoadingScreen extends StatelessWidget {
  const AiLoadingScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('AI 일정 생성'),
          Expanded(
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: const [
                  CircularProgressIndicator(),
                  SizedBox(height: 18),
                  Text(
                    'AI가 여행 일정을 만들고 있어요',
                    style: TextStyle(fontSize: 21, fontWeight: FontWeight.w900),
                  ),
                  Text('이동 거리 · 취향 · 휴식 시간을 함께 고려해요'),
                ],
              ),
            ),
          ),
        ],
      ),
    ),
  );
}
