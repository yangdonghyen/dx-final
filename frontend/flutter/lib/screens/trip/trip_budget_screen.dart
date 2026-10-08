import 'package:flutter/material.dart';
import '../../widgets/app_header.dart';
import '../../widgets/info_tile.dart';

/// 여행 만들기 과정에서 예산 범위를 선택하는 단계입니다.
class TripBudgetScreen extends StatelessWidget {
  const TripBudgetScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('예산'),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: const [
                InfoTile('💳', '20만원 이하', '알뜰 여행'),
                InfoTile('💳', '20~30만원', '실속 여행'),
                InfoTile('💳', '30~50만원', '여유 여행'),
                InfoTile('💳', '50만원 이상', '프리미엄 여행'),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
