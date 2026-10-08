import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../widgets/primary_button.dart';
import '../trip/trip_places_screen.dart';

/// 선택한 여행지의 상세 정보와 여행 계획 추가 기능을 제공하는 화면입니다.
class PlaceDetailScreen extends StatefulWidget {
  const PlaceDetailScreen({super.key, required this.placeName, required this.location, required this.emoji, required this.tags});
  final String placeName;
  final String location;
  final String emoji;
  final List<String> tags;

  @override
  State<PlaceDetailScreen> createState() => _PlaceDetailScreenState();
}

class _PlaceDetailScreenState extends State<PlaceDetailScreen> {
  bool saved = true;

  String get imageUrl => widget.placeName.contains('애월')
      ? 'https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=600&h=400&fit=crop'
      : 'https://images.unsplash.com/photo-1500534623283-312aade485b7?w=600&h=400&fit=crop';

  @override
  Widget build(BuildContext context) {
    const facilities = <({String icon, String label})>[
      (icon: '🚗', label: '주차 가능'), (icon: '🚶', label: '걷기 쉬움'), (icon: '♿', label: '이동 편리'),
      (icon: '🚻', label: '화장실 있음'), (icon: '🪜', label: '계단 없음'), (icon: '🎟️', label: '무료 입장'),
    ];
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(child: Column(children: [
        SizedBox(height: 240, child: Stack(fit: StackFit.expand, children: [
          Image.network(imageUrl, fit: BoxFit.cover, errorBuilder: (_, __, ___) => Container(color: AppColors.soft, alignment: Alignment.center, child: Text(widget.emoji, style: const TextStyle(fontSize: 72)))),
          const DecoratedBox(decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment.bottomCenter, end: Alignment.center, colors: [Color(0x80000000), Colors.transparent]))),
          Positioned(top: 12, left: 16, child: _RoundButton(icon: Icons.chevron_left_rounded, tooltip: '이전 화면으로', onPressed: () => Navigator.of(context).maybePop())),
          Positioned(top: 12, right: 16, child: _RoundButton(icon: saved ? Icons.favorite : Icons.favorite_border, tooltip: saved ? '저장한 장소에서 제거' : '장소 저장', foreground: Colors.white, background: saved ? const Color(0xFFEF4444) : const Color(0xDDFFFFFF), onPressed: () => setState(() => saved = !saved))),
        ])),
        Expanded(child: ListView(padding: const EdgeInsets.fromLTRB(20, 16, 20, 28), children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: Text(widget.placeName, style: const TextStyle(color: AppColors.ink, fontSize: 24, fontWeight: FontWeight.w700))), const SizedBox(width: 12), const Row(children: [Icon(Icons.star_rounded, color: Color(0xFFFBBF24), size: 15), SizedBox(width: 4), Text('4.8', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600))])]),
          const SizedBox(height: 3), Text(widget.location, style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 14)), const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: widget.tags.map((tag) => _Tag('${tagIcon(tag)} $tag')).toList()), const SizedBox(height: 20),
          GridView.builder(shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), itemCount: facilities.length, gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 3, crossAxisSpacing: 8, mainAxisSpacing: 8, childAspectRatio: 1.15), itemBuilder: (_, i) => Container(padding: const EdgeInsets.all(10), decoration: BoxDecoration(color: const Color(0xFFF9FAFB), borderRadius: BorderRadius.circular(12)), child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [Text(facilities[i].icon, style: const TextStyle(fontSize: 20)), const SizedBox(height: 2), Text(facilities[i].label, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF4B5563), fontSize: 12, fontWeight: FontWeight.w500))]))),
          const SizedBox(height: 20),
          Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: const Color(0xFFF7F9FF), borderRadius: BorderRadius.circular(16)), child: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('이런 분들께 추천해요', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)), SizedBox(height: 8), _Recommendation('걷기 어려우신 분들도 해안 산책로로 편하게 즐길 수 있어요'), _Recommendation('주차장이 넓어 차량으로 방문하기 좋아요'), _Recommendation('화장실이 바로 근처에 있어 안심하고 머물 수 있어요')])),
        ])),
        SafeArea(top: false, child: Container(padding: const EdgeInsets.fromLTRB(20, 12, 20, 24), decoration: const BoxDecoration(color: Colors.white, border: Border(top: BorderSide(color: Color(0xFFF3F4F6)))), child: PrimaryButton('이 장소로 여행 만들기', onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => TripPlacesScreen(initialPlaces: {widget.placeName})))))),
      ])),
    );
  }
}

class _RoundButton extends StatelessWidget {
  const _RoundButton({required this.icon, required this.tooltip, required this.onPressed, this.foreground = AppColors.ink, this.background = const Color(0xDDFFFFFF)});
  final IconData icon; final String tooltip; final VoidCallback onPressed; final Color foreground; final Color background;
  @override
  Widget build(BuildContext context) => Material(color: background, shape: const CircleBorder(), child: IconButton(onPressed: onPressed, tooltip: tooltip, icon: Icon(icon, color: foreground, size: 22)));
}

class _Tag extends StatelessWidget {
  const _Tag(this.label); final String label;
  @override
  Widget build(BuildContext context) => Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6), decoration: BoxDecoration(color: AppColors.soft, borderRadius: BorderRadius.circular(20)), child: Text(label, style: const TextStyle(color: Color(0xFF2F4FBF), fontSize: 13, fontWeight: FontWeight.w700)));
}

class _Recommendation extends StatelessWidget {
  const _Recommendation(this.text); final String text;
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.only(bottom: 5), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Padding(padding: EdgeInsets.only(top: 2), child: Icon(Icons.check, size: 14, color: AppColors.primary)), const SizedBox(width: 8), Expanded(child: Text(text, style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 12, height: 1.3)))]));
}

String tagIcon(String tag) => switch (tag) { '바다' => '🌊', '카페' => '☕', '드라이브' => '🚗', '휴식' => '🌿', '맛집' => '🍽️', '전통' => '🏛️', _ => '📍' };
