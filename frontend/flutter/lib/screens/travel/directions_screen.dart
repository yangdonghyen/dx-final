import 'package:flutter/material.dart';
import '../../widgets/app_header.dart';
import '../../widgets/info_tile.dart';

/// 선택한 목적지까지의 이동 경로와 출발 안내를 보여주는 화면입니다.
class DirectionsScreen extends StatelessWidget {
  const DirectionsScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('길찾기'),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: const [
                InfoTile('📍', '안목해변 → 강릉 중앙시장', '택시 12분 · 약 7,500원'),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
