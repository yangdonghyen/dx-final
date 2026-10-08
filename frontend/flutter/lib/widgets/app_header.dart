import 'package:flutter/material.dart';

import '../core/layout/app_responsive.dart';

/// Navigator에 이전 화면이 있으면 자동으로 뒤로가기 버튼을 노출한다.
class AppHeader extends StatelessWidget {
  const AppHeader(this.title, {super.key, this.onBack});
  final String title;
  final VoidCallback? onBack;

  @override
  Widget build(BuildContext context) {
    final canGoBack = onBack != null || Navigator.of(context).canPop();
    final sideWidth = ResponsiveLayout.headerSideWidth(context);
    final compact = ResponsiveLayout.isCompact(context);
    return Container(
      color: Colors.white,
      padding: EdgeInsets.symmetric(vertical: compact ? 6 : 8),
      child: Row(
        children: [
          SizedBox(
            width: sideWidth,
            child: canGoBack
                ? IconButton(
                    onPressed: onBack ?? () => Navigator.of(context).maybePop(),
                    icon: const Icon(Icons.chevron_left_rounded),
                  )
                : null,
          ),
          Expanded(
            child: Text(
              title,
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: compact ? 18 : 19, fontWeight: FontWeight.w900),
            ),
          ),
          SizedBox(width: sideWidth),
        ],
      ),
    );
  }
}
