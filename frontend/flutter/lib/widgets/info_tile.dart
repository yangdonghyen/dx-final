import 'package:flutter/material.dart';

/// 아이콘·제목·설명으로 구성된 설정 및 정보 목록 항목입니다.
class InfoTile extends StatelessWidget {
  const InfoTile(
    this.emoji,
    this.title,
    this.subtitle, {
    super.key,
    this.onTap,
  });
  final String emoji, title, subtitle;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext c) => Card(
    color: Colors.white,
    elevation: 0,
    child: ListTile(
      onTap: onTap,
      leading: CircleAvatar(child: Text(emoji)),
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
      subtitle: Text(subtitle),
      trailing: onTap == null ? null : const Icon(Icons.chevron_right),
    ),
  );
}
