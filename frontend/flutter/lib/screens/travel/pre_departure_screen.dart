import 'package:flutter/material.dart';
import '../../widgets/app_header.dart';
import '../../widgets/info_tile.dart';

/// 출발 전 교통·숙소·준비물 등을 확인하는 체크리스트 화면입니다.
class PreDepartureScreen extends StatelessWidget {
  const PreDepartureScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('출발 전 확인'),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: const [
                InfoTile('🎫', '기차표 확인', '출발 시간과 좌석 확인'),
                InfoTile('☂️', '우산 챙기기', '강릉 비 예보'),
                InfoTile('💊', '상비약', '필요한 약 준비'),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
