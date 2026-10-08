import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/foundation.dart';

/// 초대 링크로 앱이 열리면 초대 token을 받아 둡니다.
///
/// - 링크 페이지 버튼: `bogogago://invite?token=...`
/// - 카카오톡 "앱에서 참여하기" 버튼: `kakao{앱키}://kakaolink?invite_token=...`
///
/// 로그인한 홈 화면이 [pendingToken]을 꺼내 참여 창을 띄웁니다.
class InviteLinkService {
  InviteLinkService._();

  static final ValueNotifier<String?> pendingToken = ValueNotifier(null);
  static StreamSubscription<Uri>? _subscription;

  /// 앱이 꺼진 상태에서 링크로 열린 경우도 받으려면 runApp 전에 호출합니다.
  static void initialize() {
    if (kIsWeb || _subscription != null) return;
    _subscription = AppLinks().uriLinkStream.listen((uri) {
      final token = tokenFrom(uri);
      if (token != null) pendingToken.value = token;
    }, onError: (Object error) => debugPrint('[Invite] link error: $error'));
  }

  /// 초대 링크가 아니면 null입니다.
  static String? tokenFrom(Uri uri) {
    final String? token;
    if (uri.scheme == 'bogogago' && uri.host == 'invite') {
      token = uri.queryParameters['token'];
    } else if (uri.scheme.startsWith('kakao') && uri.host == 'kakaolink') {
      token = uri.queryParameters['invite_token'];
    } else {
      return null;
    }
    return token == null || token.isEmpty ? null : token;
  }

  /// 받아 둔 token을 꺼내고 비웁니다.
  static String? take() {
    final token = pendingToken.value;
    pendingToken.value = null;
    return token;
  }
}
