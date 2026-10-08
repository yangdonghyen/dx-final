import 'package:flutter/material.dart';
import '../../widgets/app_header.dart';
import '../../widgets/info_tile.dart';

/// 여행 동선에 맞는 숙소 후보를 보여주고 선택할 수 있는 화면입니다.
class AccommodationScreen extends StatelessWidget {
  const AccommodationScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('숙소 추천'),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: const [
                InfoTile('🏨', '경포 오션뷰 호텔', '일정 동선과 가까워요'),
                InfoTile('🛏️', '안목 스테이', '카페거리 도보 이동 가능'),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
