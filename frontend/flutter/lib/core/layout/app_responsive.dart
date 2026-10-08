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
        final safeTextScale = systemTextScale.clamp(0.85, 1.3).toDouble();
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
    return size.width <= 360 || size.height <= 700;
  }

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
}