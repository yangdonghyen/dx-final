import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../data/travel_taste_options.dart';
import '../../widgets/app_header.dart';
import '../trip/trip_places_screen.dart';

/// AI가 분석한 여행 취향을 사용자가 확인·수정하는 화면입니다.
class TasteConfirmScreen extends StatefulWidget {
  const TasteConfirmScreen({super.key});

  @override
  State<TasteConfirmScreen> createState() => _TasteConfirmScreenState();
}

class _TasteConfirmScreenState extends State<TasteConfirmScreen> {
  Iterable<String> get _allTastes =>
      travelTasteOptions.map((item) => '${item.$1} ${item.$2}');

  final Set<String> _selectedTastes = {
    '🌊 바다',
    '🌿 자연',
    '🍲 맛집',
    '☕ 카페',
    '😌 휴식',
  };

  Future<void> _editTastes() async {
    final updatedTastes = await showModalBottomSheet<Set<String>>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) {
        final draft = {..._selectedTastes};
        return StatefulBuilder(
          builder: (context, setSheetState) => SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      width: 48,
                      height: 5,
                      decoration: BoxDecoration(
                        color: const Color(0xFFD1D5DB),
                        borderRadius: BorderRadius.circular(99),
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    '여행 취향 수정',
                    style: TextStyle(fontSize: 26, fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    '원하는 항목을 여러 개 골라주세요.',
                    style: TextStyle(fontSize: 17, color: Color(0xFF6B7280)),
                  ),
                  const SizedBox(height: 20),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: _allTastes.map((taste) {
                      final selected = draft.contains(taste);
                      return FilterChip(
                        label: Text(taste),
                        selected: selected,
                        onSelected: (value) => setSheetState(() {
                          if (value) {
                            draft.add(taste);
                          } else {
                            draft.remove(taste);
                          }
                        }),
                        selectedColor: AppColors.soft,
                        checkmarkColor: AppColors.primary,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 10,
                        ),
                        side: BorderSide(
                          color: selected
                              ? AppColors.primary
                              : const Color(0xFFE5E7EB),
                          width: selected ? 2 : 1,
                        ),
                        labelStyle: TextStyle(
                          fontSize: 17,
                          color: selected
                              ? AppColors.primary
                              : const Color(0xFF374151),
                          fontWeight: FontWeight.w700,
                        ),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    height: 58,
                    child: FilledButton(
                      onPressed: draft.isEmpty
                          ? null
                          : () => Navigator.of(sheetContext).pop(draft),
                      child: const Text(
                        '적용하기',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );

    if (updatedTastes == null || !mounted) return;
    setState(() {
      _selectedTastes
        ..clear()
        ..addAll(updatedTastes);
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('취향 확인'),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const Text(
                  '이런 여행을 좋아하시네요',
                  style: TextStyle(fontSize: 30, fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 20),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _selectedTastes
                      .map(
                        (taste) => Chip(
                          label: Text(
                            taste,
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 10,
                          ),
                        ),
                      )
                      .toList(),
                ),
                const SizedBox(height: 22),
                SizedBox(
                  width: double.infinity,
                  height: 64,
                  child: OutlinedButton.icon(
                    onPressed: _editTastes,
                    icon: const Icon(Icons.tune_rounded, size: 27),
                    label: const Text(
                      '취향 수정',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.primary,
                      side: const BorderSide(
                        color: AppColors.primary,
                        width: 2,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          SafeArea(
            top: false,
            child: Container(
              color: Colors.white,
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
              child: SizedBox(
                width: double.infinity,
                height: 56,
                child: FilledButton(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => TripPlacesScreen(
                        preferredTastes: _selectedTastes
                            .map(
                              (taste) =>
                                  taste.substring(taste.indexOf(' ') + 1),
                            )
                            .toSet(),
                      ),
                    ),
                  ),
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  child: const Text(
                    '이 취향으로 여행 만들기',
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    ),
  );
}
