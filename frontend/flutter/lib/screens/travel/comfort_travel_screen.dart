import 'package:flutter/material.dart';
import '../../widgets/app_header.dart';
import '../../widgets/info_tile.dart';

/// 편한 모드에서 다음 일정과 길찾기·휴식 기능을 크게 안내하는 화면입니다.
class ComfortTravelScreen extends StatelessWidget {
  const ComfortTravelScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('편안한 여행'),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: const [
                InfoTile('🛋️', '오늘의 여행 안내', '걷는 시간을 줄이고 휴식을 추가했어요'),
                InfoTile('🌊', '10:30 안목해변', '산책 10분'),
                InfoTile('☕', '11:20 카페 휴식', '30분 쉬어가기'),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
