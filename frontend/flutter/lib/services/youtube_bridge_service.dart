import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';

class YoutubeBridgeService {
  YoutubeBridgeService._();

  static final YoutubeBridgeService instance = YoutubeBridgeService._();

  final StreamController<Map<String, dynamic>> _eventController =
      StreamController<Map<String, dynamic>>.broadcast();

  Stream<Map<String, dynamic>> get events => _eventController.stream;

  WebSocket? _socket;
  bool _connecting = false;
  bool _stopped = false;
  Timer? _reconnectTimer;

  bool get isConnected => _socket != null;

  Future<void> start() async {
    if (_socket != null || _connecting) {
      return;
    }

    _stopped = false;
    _connecting = true;
    _reconnectTimer?.cancel();

    const apiBaseUrl = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://127.0.0.1:8000',
    );

    final apiUri = Uri.parse(apiBaseUrl);

    final wsUri = apiUri.replace(
      scheme: apiUri.scheme == 'https' ? 'wss' : 'ws',
      path: '/api/v1/discovery/youtube-events',
      query: null,
      fragment: null,
    );

    try {
      final socket = await WebSocket.connect(wsUri.toString());

      if (_stopped) {
        await socket.close();
        return;
      }

      socket.pingInterval = const Duration(seconds: 20);
      _socket = socket;

      debugPrint('[YouTube Bridge] SERVICE connected: $wsUri');

      socket.listen(
        (message) {
          debugPrint('[YouTube Bridge] SERVICE received: $message');

          try {
            final decoded = jsonDecode(message as String);

            if (decoded is Map<String, dynamic>) {
              _eventController.add(decoded);
            } else if (decoded is Map) {
              _eventController.add(
                decoded.map(
                  (key, value) => MapEntry(key.toString(), value),
                ),
              );
            }
          } catch (error) {
            debugPrint(
              '[YouTube Bridge] SERVICE parse error: $error',
            );
          }
        },
        onError: (Object error, StackTrace stackTrace) {
          debugPrint(
            '[YouTube Bridge] SERVICE error: $error',
          );
        },
        onDone: () {
          debugPrint(
            '[YouTube Bridge] SERVICE disconnected '
            'code=${socket.closeCode} '
            'reason=${socket.closeReason}',
          );

          if (identical(_socket, socket)) {
            _socket = null;
          }

          _scheduleReconnect();
        },
        cancelOnError: false,
      );
    } catch (error) {
      debugPrint(
        '[YouTube Bridge] SERVICE connection failed: $error',
      );

      _scheduleReconnect();
    } finally {
      _connecting = false;
    }
  }

  void _scheduleReconnect() {
    if (_stopped || _socket != null) {
      return;
    }

    _reconnectTimer?.cancel();

    debugPrint(
      '[YouTube Bridge] SERVICE reconnecting in 2 seconds',
    );

    _reconnectTimer = Timer(
      const Duration(seconds: 2),
      start,
    );
  }

  Future<void> stop() async {
    _stopped = true;
    _reconnectTimer?.cancel();

    final socket = _socket;
    _socket = null;

    if (socket != null) {
      await socket.close(
        WebSocketStatus.normalClosure,
        'service stopped',
      );
    }

    debugPrint('[YouTube Bridge] SERVICE stopped');
  }
}
