import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/theme/app_theme.dart';
import '../../widgets/primary_button.dart';
import '../../services/auth_service.dart';
import '../home/home_screen.dart';
import 'register_screen.dart';

/// 로그인 입력을 받고 성공 시 홈 화면으로 이동시키는 화면입니다.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _S();
}

class _S extends State<LoginScreen> {
  final id = TextEditingController(), pw = TextEditingController();
  String notice = '';
  bool loggingIn = false;
  bool autoLogin = false;
  final AuthService authService = AuthService();

  Future<void> loginWithKakao() async {
    if (loggingIn) return;

    setState(() {
      loggingIn = true;
      notice = '';
    });

    try {
      await authService.loginWithKakao();

      if (!mounted) return;

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const HomeScreen()),
      );
    } catch (e) {
      if (!mounted) return;

      setState(() {
        notice = '서버 로그인에 실패했습니다.';
        loggingIn = false;
      });
    }
  }

  Future<void> loginWithNaver() async {
    if (loggingIn) return;
    setState(() {
      loggingIn = true;
      notice = '';
    });
    try {
      await authService.loginWithNaver();
      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const HomeScreen()),
      );
    } on PlatformException catch (error) {
      if (!mounted) return;
      setState(() {
        notice = error.code == 'NAVER_LOGIN_CANCELLED'
            ? '네이버 로그인을 취소했습니다.'
            : '네이버 로그인에 실패했습니다.';
        loggingIn = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        notice = '네이버 로그인에 실패했습니다.';
        loggingIn = false;
      });
    }
  }

  Future<void> login() async {
    if (loggingIn) return;

    final loginId = id.text.trim();
    final password = pw.text;

    if (loginId.isEmpty || password.isEmpty) {
      setState(() {
        notice = '아이디와 비밀번호를 입력해주세요.';
      });
      return;
    }

    setState(() {
      loggingIn = true;
      notice = '';
    });

    try {
      await authService.loginLocal(loginId, password);

      if (!mounted) return;

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const HomeScreen()),
      );
    } catch (_) {
      if (!mounted) return;

      setState(() {
        notice = '아이디 또는 비밀번호가 올바르지 않습니다.';
        loggingIn = false;
      });
    }
  }

  @override
  Widget build(BuildContext c) => Scaffold(
    backgroundColor: Colors.white,
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(32, 48, 32, 28),
        children: [
          Center(
            child: Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(24),
                boxShadow: const [
                  BoxShadow(
                    color: Color(0x22000000),
                    blurRadius: 20,
                    offset: Offset(0, 8),
                  ),
                ],
              ),
              alignment: Alignment.center,
              child: const Text('✈️', style: TextStyle(fontSize: 42)),
            ),
          ),
          const SizedBox(height: 18),
          const Text(
            '보고가고',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 30, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 6),
          const Text(
            '나에게 맞는 여행을 시작해볼까요?',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.grey),
          ),
          const SizedBox(height: 34),
          TextField(
            controller: id,
            decoration: const InputDecoration(hintText: '아이디 또는 이메일'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: pw,
            obscureText: true,
            decoration: const InputDecoration(hintText: '비밀번호'),
          ),
          if (notice.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Text(
                notice,
                style: const TextStyle(color: AppColors.primary),
              ),
            ),
          Row(
            children: [
              Semantics(
                label: '자동 로그인',
                checked: autoLogin,
                child: InkWell(
                  onTap: () => setState(() => autoLogin = !autoLogin),
                  borderRadius: BorderRadius.circular(8),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Checkbox(
                          value: autoLogin,
                          onChanged: (value) =>
                              setState(() => autoLogin = value ?? false),
                          visualDensity: VisualDensity.compact,
                        ),
                        const Text('자동 로그인', style: TextStyle(fontSize: 13)),
                      ],
                    ),
                  ),
                ),
              ),
              const Spacer(),
              TextButton(
                style: TextButton.styleFrom(
                  minimumSize: Size.zero,
                  padding: const EdgeInsets.symmetric(horizontal: 6),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                onPressed: () =>
                    setState(() => notice = '가입한 아이디 또는 비밀번호를 재설정할 수 있어요.'),
                child: const Text('아이디/비밀번호 찾기'),
              ),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 5),
                child: Text('|', style: TextStyle(color: Color(0xFFD1D5DB))),
              ),
              TextButton(
                style: TextButton.styleFrom(
                  minimumSize: Size.zero,
                  padding: const EdgeInsets.symmetric(horizontal: 6),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                onPressed: () => Navigator.push(
                  c,
                  MaterialPageRoute(builder: (_) => const RegisterScreen()),
                ),
                child: const Text(
                  '회원가입',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
          PrimaryButton('로그인하기', onPressed: loggingIn ? null : login),
          const SizedBox(height: 22),
          const Row(
            children: [
              Expanded(child: Divider()),
              Padding(
                padding: EdgeInsets.symmetric(horizontal: 12),
                child: Text('또는', style: TextStyle(color: Colors.grey)),
              ),
              Expanded(child: Divider()),
            ],
          ),
          const SizedBox(height: 20),
          PrimaryButton(
            '♡  카카오로 로그인하기',
            color: Color(0xFFFFE500),
            onPressed: loginWithKakao,
          ),
          const SizedBox(height: 12),
          PrimaryButton(
            '◯  네이버로 로그인하기',
            color: Color(0xFF03C75A),
            onPressed: loggingIn ? null : loginWithNaver,
          ),
        ],
      ),
    ),
  );
}
