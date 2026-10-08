import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

/// 여행 중 가까운 휴식 장소를 찾는 화면입니다.
class RestPlaceSelection {
  const RestPlaceSelection(this.icon, this.name, this.travel);

  final String icon;
  final String name;
  final String travel;
}

class RestSearchScreen extends StatelessWidget {
  const RestSearchScreen({super.key, this.targetPlace = '선택한 장소'});
  final String targetPlace;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          onPressed: () => Navigator.of(context).maybePop(),
          icon: const Icon(Icons.chevron_left_rounded),
          tooltip: '뒤로가기',
        ),
        title: const Text('휴식 장소 찾기'),
        backgroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.soft,
              borderRadius: BorderRadius.circular(22),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '선택한 장소',
                  style: TextStyle(fontSize: 13, color: Color(0xFF6B7280)),
                ),
                const SizedBox(height: 4),
                Text(
                  '$targetPlace 주변',
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 8),
                const Text('다음 장소로 가는 길에서 크게 벗어나지 않는 쉼터를 찾았어요.'),
              ],
            ),
          ),
          const SizedBox(height: 18),
          const Text(
            '주변 추천',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 10),
          const _RestPlaceCard('🪑', '안목 해변 쉼터', '현재 위치에서 4분'),
          const _RestPlaceCard('🌳', '가까운 작은 공원', '현재 위치에서 6분'),
        ],
      ),
    );
  }
}

class _RestPlaceCard extends StatelessWidget {
  const _RestPlaceCard(this.icon, this.name, this.time);
  final String icon;
  final String name;
  final String time;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '$icon  $name',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 5),
            Text(
              time,
              style: const TextStyle(
                color: AppColors.primary,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 10),
            const Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                Chip(label: Text('앉아서 쉴 수 있음')),
                Chip(label: Text('화장실 있음')),
                Chip(label: Text('그늘 있음')),
              ],
            ),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(
                RestPlaceSelection(icon, name, time),
              ),
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(46),
              ),
              child: const Text('이곳에서 휴식하기'),
            ),
          ],
        ),
      ),
    );
  }
}
