import 'dart:ui';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:workmanager/workmanager.dart';

import 'auth_service.dart';
import 'weather_notification_service.dart';
import 'weather_service.dart';

const _weatherPeriodicTaskName = 'weather-periodic-check';
const _weatherPeriodicTaskUniqueName = 'weather-periodic-check-v1';
const _lastWeatherLatitudeKey = 'last_weather_lat';
const _lastWeatherLongitudeKey = 'last_weather_lon';

/// Entry point invoked by Android WorkManager in a headless Flutter isolate.
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    WidgetsFlutterBinding.ensureInitialized();
    DartPluginRegistrant.ensureInitialized();

    if (task != _weatherPeriodicTaskName) return true;

    try {
      await AuthSession.restore();
      if (!AuthSession.isLoggedIn) return true;

      final preferences = await SharedPreferences.getInstance();
      final latitude = preferences.getDouble(_lastWeatherLatitudeKey);
      final longitude = preferences.getDouble(_lastWeatherLongitudeKey);
      if (latitude == null || longitude == null) return true;

      final weather = await WeatherService().getWeatherAt(
        latitude: latitude,
        longitude: longitude,
      );
      await WeatherNotificationService.instance.notifyForWeather(weather);
    } catch (_) {
      // Periodic work will be attempted again at its next scheduled interval.
    }
    return true;
  });
}

class WeatherBackgroundService {
  WeatherBackgroundService._();

  static Future<void> initialize() {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) {
      return Future.value();
    }
    return Workmanager().initialize(callbackDispatcher);
  }

  static Future<void> saveCurrentLocationAndSchedule({
    required double latitude,
    required double longitude,
  }) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setDouble(_lastWeatherLatitudeKey, latitude);
    await preferences.setDouble(_lastWeatherLongitudeKey, longitude);

    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) return;

    try {
      await Workmanager().registerPeriodicTask(
        _weatherPeriodicTaskUniqueName,
        _weatherPeriodicTaskName,
        frequency: const Duration(hours: 6),
        constraints: Constraints(networkType: NetworkType.connected),
        existingWorkPolicy: ExistingPeriodicWorkPolicy.update,
      );
    } catch (_) {
      // A scheduling issue must not make the foreground weather screen fail.
    }
  }
}
