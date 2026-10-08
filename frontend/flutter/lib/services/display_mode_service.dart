import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Holds the selected display mode (편한 모드 / 기본 모드).
///
/// The choice is written to the device so it stays the same after an app
/// restart, until the user picks the other mode.
class DisplayModeService {
  DisplayModeService._();

  static const _seniorModeKey = 'display_senior_mode';

  static bool _seniorMode = false;

  static bool get seniorMode => _seniorMode;

  static set seniorMode(bool value) {
    if (_seniorMode == value) return;
    _seniorMode = value;
    unawaited(
      _persist().catchError(
        (Object error) => debugPrint('[DisplayMode] save failed: $error'),
      ),
    );
  }

  /// Loads the mode saved on a previous app run.
  static Future<void> restore() async {
    try {
      final preferences = await SharedPreferences.getInstance();
      _seniorMode = preferences.getBool(_seniorModeKey) ?? false;
    } catch (error) {
      debugPrint('[DisplayMode] restore failed: $error');
    }
  }

  static Future<void> _persist() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setBool(_seniorModeKey, _seniorMode);
  }
}
