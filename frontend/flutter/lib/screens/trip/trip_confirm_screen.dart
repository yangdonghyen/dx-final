import 'package:flutter/material.dart';
import '../../widgets/app_header.dart';
import '../../widgets/info_tile.dart';

/// 여행 조건을 최종 확인하고 일정 생성을 시작하는 단계입니다.
class TripConfirmScreen extends StatelessWidget {
  const TripConfirmScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('여행 확인'),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: const [
                InfoTile('📅', '9/24 ~ 9/28', '5일 여행'),
                InfoTile('👥', '2명', '동행자 조건 반영'),
                InfoTile('🚆', '기차 · 택시', '이동수단'),
                InfoTile('💳', '30~50만원', '예산'),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
