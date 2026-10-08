import 'package:flutter/material.dart';

/// 화면 전반에서 공통으로 사용하는 색상 토큰입니다.
class AppColors {
  static const primary = Color(0xFF4169D8),
      purple = Color(0xFF6B52D3),
      bg = Color(0xFFF7F8FC),
      ink = Color(0xFF111827),
      soft = Color(0xFFEEF2FF);
}

/// Material 컴포넌트의 기본 색상과 입력창 모양을 정의합니다.
class AppTheme {
  static ThemeData get light => ThemeData(
    useMaterial3: true,
    visualDensity: VisualDensity.adaptivePlatformDensity,
    scaffoldBackgroundColor: AppColors.bg,
    colorScheme: ColorScheme.fromSeed(seedColor: AppColors.primary),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.white,
      foregroundColor: AppColors.ink,
      elevation: 0,
      centerTitle: true,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 17),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: Color(0xFFE5E7EB)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: Color(0xFFE5E7EB)),
      ),
    ),
  );
}
