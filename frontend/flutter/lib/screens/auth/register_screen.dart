import 'package:flutter/material.dart';

import '../../services/auth_service.dart';
import '../../widgets/app_header.dart';
import '../../widgets/primary_button.dart';
import '../home/home_screen.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final nameController = TextEditingController();
  final idController = TextEditingController();
  final passwordController = TextEditingController();
  final passwordConfirmController = TextEditingController();

  final AuthService authService = AuthService();

  bool registering = false;
  String notice = '';

  @override
  void dispose() {
    nameController.dispose();
    idController.dispose();
    passwordController.dispose();
    passwordConfirmController.dispose();
    super.dispose();
  }

  Future<void> register() async {
    if (registering) return;

    final nickname = nameController.text.trim();
    final loginId = idController.text.trim();
    final password = passwordController.text;
    final passwordConfirm = passwordConfirmController.text;

    if (nickname.isEmpty ||
        loginId.isEmpty ||
        password.isEmpty ||
        passwordConfirm.isEmpty) {
      setState(() {
        notice =
            '\ubaa8\ub4e0 \ud56d\ubaa9\uc744 \uc785\ub825\ud574 \uc8fc\uc138\uc694.';
      });
      return;
    }

    if (nickname.length > 50) {
      setState(() {
        notice =
            '\uc774\ub984\uc740 50\uc790 \uc774\ud558\ub85c \uc785\ub825\ud574 \uc8fc\uc138\uc694.';
      });
      return;
    }

    if (loginId.length < 3 || loginId.length > 255) {
      setState(() {
        notice =
            '\uc544\uc774\ub514\ub294 3\uc790 \uc774\uc0c1 255\uc790 \uc774\ud558\ub85c \uc785\ub825\ud574 \uc8fc\uc138\uc694.';
      });
      return;
    }

    if (!RegExp(r'^[A-Za-z0-9._@+-]+$').hasMatch(loginId)) {
      setState(() {
        notice =
            '\uc544\uc774\ub514\ub294 \uc601\ubb38, \uc22b\uc790, . _ @ + - \ub9cc \uc0ac\uc6a9\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4.';
      });
      return;
    }

    if (password.length < 8 || password.length > 128) {
      setState(() {
        notice =
            '\ube44\ubc00\ubc88\ud638\ub294 8\uc790 \uc774\uc0c1 128\uc790 \uc774\ud558\ub85c \uc785\ub825\ud574 \uc8fc\uc138\uc694.';
      });
      return;
    }

    if (password != passwordConfirm) {
      setState(() {
        notice =
            '\ube44\ubc00\ubc88\ud638\uac00 \uc77c\uce58\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.';
      });
      return;
    }

    setState(() {
      registering = true;
      notice = '';
    });

    try {
      await authService.registerLocal(loginId, password, nickname);

      if (!mounted) return;

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const HomeScreen()),
      );
    } catch (_) {
      if (!mounted) return;

      setState(() {
        notice =
            '\ud68c\uc6d0\uac00\uc785\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4. \uc774\ubbf8 \uc0ac\uc6a9 \uc911\uc778 \uc544\uc774\ub514\uc778\uc9c0 \ud655\uc778\ud574 \uc8fc\uc138\uc694.';
        registering = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            AppHeader(
              '\ud68c\uc6d0\uac00\uc785',
              onBack: () => Navigator.pop(context),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(24),
                children: [
                  const Text(
                    '\ubcf4\uace0\uac00\uace0 \uc2dc\uc791\ud558\uae30',
                    style: TextStyle(fontSize: 25, fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 22),
                  TextField(
                    controller: nameController,
                    decoration: const InputDecoration(
                      labelText: '\uc774\ub984',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: idController,
                    decoration: const InputDecoration(
                      labelText:
                          '\uc544\uc774\ub514 \ub610\ub294 \uc774\uba54\uc77c',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: passwordController,
                    obscureText: true,
                    decoration: const InputDecoration(
                      labelText: '\ube44\ubc00\ubc88\ud638',
                      helperText: '8\uc790 \uc774\uc0c1',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: passwordConfirmController,
                    obscureText: true,
                    decoration: const InputDecoration(
                      labelText: '\ube44\ubc00\ubc88\ud638 \ud655\uc778',
                    ),
                  ),
                  if (notice.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text(notice, style: const TextStyle(color: Colors.red)),
                  ],
                  const SizedBox(height: 24),
                  PrimaryButton(
                    '\uac00\uc785\ud558\uace0 \uc2dc\uc791\ud558\uae30',
                    onPressed: registering ? null : register,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
