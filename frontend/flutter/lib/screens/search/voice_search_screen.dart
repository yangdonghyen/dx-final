import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import '../../core/theme/app_theme.dart';
import '../../widgets/app_header.dart';
import 'text_search_screen.dart';

/// 음성 입력으로 여행지나 장소를 검색하는 화면입니다.
class VoiceSearchScreen extends StatefulWidget {
  const VoiceSearchScreen({super.key});

  @override
  State<VoiceSearchScreen> createState() => _VoiceSearchScreenState();
}

class _VoiceSearchScreenState extends State<VoiceSearchScreen> {
  final stt.SpeechToText _speech = stt.SpeechToText();

  bool _busy = false;
  bool _listening = false;
  bool _hasTried = false;
  bool _openingResults = false;
  String _recognizedQuery = '';
  String _message = '마이크 버튼을 누르고 여행지 이름을 말씀해주세요.';

  @override
  void dispose() {
    _speech.cancel();
    super.dispose();
  }

  Future<void> _toggleListening() async {
    if (_busy) return;
    if (_listening) {
      await _speech.stop();
      if (!mounted) return;
      setState(() {
        _listening = false;
        _message = _recognizedQuery.isEmpty
            ? '음성 입력을 멈췄어요. 다시 말하거나 직접 입력해주세요.'
            : '말씀하신 내용을 확인하고 검색해보세요.';
      });
      return;
    }

    setState(() {
      _busy = true;
      _hasTried = true;
      _message = '마이크 연결 중이에요. 권한 요청이 뜨면 허용해주세요.';
    });
    try {
      final available = await _speech.initialize(
        options: [stt.SpeechToText.androidNoBluetooth],
        onStatus: (status) {
          if (!mounted) return;
          if (status == 'done' || status == 'notListening') {
            setState(() {
              _listening = false;
              _message = _recognizedQuery.isEmpty
                  ? '음성 입력이 끝났어요. 다시 말하거나 직접 입력해주세요.'
                  : '말씀하신 내용으로 검색할 수 있어요.';
            });
          }
        },
        onError: (_) {
          if (!mounted) return;
          setState(() {
            _listening = false;
            _message = '음성을 인식하지 못했어요. 마이크 권한을 확인하거나 직접 입력해주세요.';
          });
        },
      );
      if (!mounted) return;
      if (!available) {
        setState(() {
          _message = '음성 검색을 사용할 수 없어요. 마이크 권한을 확인하거나 직접 입력해주세요.';
        });
        return;
      }

      final locales = await _speech.locales();
      if (!mounted) return;
      final koreanLocales = locales.where(
        (locale) => locale.localeId.toLowerCase().startsWith('ko'),
      );
      _recognizedQuery = '';
      await _speech.listen(
        listenOptions: stt.SpeechListenOptions(
          localeId: koreanLocales.isEmpty ? null : koreanLocales.first.localeId,
        ),
        onResult: (result) {
          if (!mounted) return;
          final recognized = result.recognizedWords.trim();
          setState(() {
            _recognizedQuery = recognized;
            if (result.finalResult) {
              _message = recognized.isEmpty
                  ? '말씀을 듣지 못했어요. 다시 시도해주세요.'
                  : '말씀하신 내용으로 검색하고 있어요.';
            }
          });
          if (result.finalResult && recognized.isNotEmpty) _openResults();
        },
      );
      if (!mounted) return;
      setState(() {
        _listening = _speech.isListening;
        if (_listening) _message = '듣고 있어요. 여행지 이름을 말씀해주세요.';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _listening = false;
        _message = '마이크를 시작할 수 없어요. 다시 시도하거나 직접 입력해주세요.';
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openResults() async {
    final query = _recognizedQuery;
    if (query.isEmpty || _openingResults) return;
    _openingResults = true;
    if (_listening) await _speech.stop();
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => TextSearchScreen(initialQuery: query)),
    );
    _openingResults = false;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: Colors.white,
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('말로 여행지 찾기'),
          Expanded(
            child: Align(
              alignment: Alignment.topCenter,
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 24, 20, 20),
                child: SizedBox(width: double.infinity, child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.fromLTRB(20, 36, 20, 28),
                      decoration: BoxDecoration(
                        color: AppColors.soft,
                        borderRadius: BorderRadius.circular(24),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          Center(child: Semantics(
                            label: _listening ? '음성 입력 중지' : '음성 검색 시작',
                            button: true,
                            child: InkWell(
                              onTap: _busy ? null : _toggleListening,
                              customBorder: const CircleBorder(),
                              child: CircleAvatar(
                                radius: 56,
                                backgroundColor: AppColors.primary,
                                child: Icon(
                                  _listening ? Icons.stop_rounded : Icons.mic_rounded,
                                  size: 56,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                          )),
                          const SizedBox(height: 24),
                          const Text(
                            '어디로 여행 갈까요?',
                            style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            _message,
                            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 18),
                          FilledButton(
                            onPressed: _busy ? null : _toggleListening,
                            style: FilledButton.styleFrom(
                              minimumSize: const Size(160, 48),
                              backgroundColor: Colors.white,
                              foregroundColor: AppColors.primary,
                            ),
                            child: Text(_listening ? '음성 입력 중지' : _hasTried ? '다시 말하기' : '말하기', style: const TextStyle(fontSize: 16)),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 20),
                    Center(child: TextButton(
                      onPressed: () async {
                        await _speech.cancel();
                        if (!context.mounted) return;
                        Navigator.of(context).push(
                          MaterialPageRoute(builder: (_) => const TextSearchScreen()),
                        );
                      },
                      child: const Text('직접 입력으로 전환', style: TextStyle(fontSize: 19)),
                    )),
                  ],
                )),
              ),
            ),
          ),
        ],
      ),
    ),
  );
}
