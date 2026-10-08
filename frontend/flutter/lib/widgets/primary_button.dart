import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';
import '../core/layout/app_responsive.dart';

/// 화면 하단의 주요 행동에 공통으로 쓰는 전체 너비 버튼입니다.
class PrimaryButton extends StatelessWidget {
  const PrimaryButton(
    this.label, {
    super.key,
    required this.onPressed,
    this.color = AppColors.primary,
  });
  final String label;
  final VoidCallback? onPressed;
  final Color color;
  @override
  Widget build(BuildContext c) => SizedBox(
    width: double.infinity,
    height: ResponsiveLayout.primaryButtonHeight(c),
    child: FilledButton(
      style: FilledButton.styleFrom(
        backgroundColor: color,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      onPressed: onPressed,
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          fontSize: ResponsiveLayout.isCompact(c) ? 16 : 17,
          fontWeight: FontWeight.w800,
        ),
      ),
    ),
  );
}
