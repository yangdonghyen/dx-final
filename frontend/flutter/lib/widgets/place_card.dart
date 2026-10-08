import 'package:flutter/material.dart';
import '../models/place.dart';

/// 장소의 이름, 지역, 태그를 공통 형식으로 보여주는 카드입니다.
class PlaceCard extends StatelessWidget {
  const PlaceCard(this.place, {super.key, this.onTap});
  final Place place;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext c) => Card(
    color: Colors.white,
    elevation: 0,
    child: ListTile(
      onTap: onTap,
      leading: CircleAvatar(child: Text(place.name == '안목해변' ? '🌊' : '📍')),
      title: Text(
        place.name,
        style: const TextStyle(fontWeight: FontWeight.w800),
      ),
      subtitle: Text('${place.region}\n${place.tags.join(' · ')}'),
      isThreeLine: true,
      trailing: const Icon(Icons.chevron_right),
    ),
  );
}
