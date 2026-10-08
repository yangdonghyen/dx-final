import 'package:flutter/material.dart';
import 'core/layout/app_responsive.dart';
import 'core/theme/app_theme.dart';
import 'screens/auth/login_screen.dart';

/// 앱 전체의 테마, 제목, 첫 화면을 설정하는 최상위 위젯입니다.
class TravelMateApp extends StatelessWidget {
  const TravelMateApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: '보고가고',
    theme: AppTheme.light,
    builder: (context, child) => AppResponsive(child: child ?? const SizedBox.shrink()),
    home: const LoginScreen(),
  );
}
