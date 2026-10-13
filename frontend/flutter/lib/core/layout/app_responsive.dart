import 'dart:math' as math;

import 'package:flutter/material.dart';

/// 기기 폭, 화면 높이, 시스템 글자 크기에 맞춰 공통 레이아웃을 조정합니다.
class AppResponsive extends StatelessWidget {
  const AppResponsive({super.key, required this.child});

  final Widget child;

  static const double _maxContentWidth = 600;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final media = MediaQuery.of(context);
        final systemTextScale = media.textScaler.scale(1);
        final safeTextScale = systemTextScale.clamp(0.85, 1.15).toDouble();
        final contentWidth = math.min(constraints.maxWidth, _maxContentWidth);

        return ColoredBox(
          color: Theme.of(context).scaffoldBackgroundColor,
          child: Center(
            child: SizedBox(
              width: contentWidth,
              height: constraints.maxHeight,
              child: MediaQuery(
                data: media.copyWith(textScaler: TextScaler.linear(safeTextScale)),
                child: child,
              ),
            ),
          ),
        );
      },
    );
  }
}

/// 카드와 공통 컴포넌트가 화면 크기에 맞게 사용할 수 있는 기준값입니다.
class ResponsiveLayout {
  const ResponsiveLayout._();

  static Size sizeOf(BuildContext context) => MediaQuery.sizeOf(context);

  static bool isCompact(BuildContext context) {
    final size = sizeOf(context);
    return size.width <= 360 || size.height <= 720;
  }

  static double gap(BuildContext context) {
    final width = sizeOf(context).width;
    if (width <= 340) return 8;
    if (width >= 480) return 14;
    return 12;
  }

  static double sectionSpacing(BuildContext context) =>
      isCompact(context) ? 12 : 16;

  static double cardPadding(BuildContext context) =>
      isCompact(context) ? 14 : 16;

  static double pageHorizontal(BuildContext context) {
    final width = sizeOf(context).width;
    if (width <= 360) return 16;
    if (width >= 480) return 24;
    return 20;
  }

  static double headerSideWidth(BuildContext context) =>
      isCompact(context) ? 44 : 52;

  static double primaryButtonHeight(BuildContext context) =>
      isCompact(context) ? 52 : 56;

  static double bottomNavigationHeight(BuildContext context) =>
      isCompact(context) ? 72 : 80;

  /// 주요 메뉴는 기기 폭과 관계없이 두 열을 유지해 과도한 세로 여백을 막습니다.
  static int twoColumnCount(BuildContext context) => 2;

  static double profileMenuExtent(BuildContext context) =>
      isCompact(context) ? 126 : 154;

  static double homeMenuExtent(BuildContext context) =>
      isCompact(context) ? 132 : 156;

  static double savedPlaceExtent(BuildContext context) =>
      isCompact(context) ? 248 : 260;

  static double selectionCardExtent(BuildContext context) =>
      isCompact(context) ? 156 : 172;
}