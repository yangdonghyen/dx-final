import 'package:flutter/material.dart';
import '../../widgets/app_header.dart';
import '../../widgets/info_tile.dart';

/// 여행에 사용할 이동수단을 선택하는 단계입니다.
class TripTransportScreen extends StatelessWidget {
  const TripTransportScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('이동수단'),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: const [
                InfoTile('🚗', '자동차', '직접 운전'),
                InfoTile('🚌', '대중교통', '버스·지하철'),
                InfoTile('🚕', '택시', '짧은 이동'),
                InfoTile('🚶', '도보 중심', '걷기 좋은 코스'),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
