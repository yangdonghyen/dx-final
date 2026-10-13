import 'package:flutter/material.dart';

import '../../core/layout/app_responsive.dart';
import '../../core/theme/app_theme.dart';
import '../../data/travel_taste_options.dart';
import '../../services/display_mode_service.dart';
import '../../widgets/primary_button.dart';
import '../home/home_screen.dart';

/// 로그인 직후 원본 웹과 동일하게 복수 취향과 편한 모드를 설정한다.
class SetupScreen extends StatefulWidget {
  const SetupScreen({super.key});

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen> {
  final prefs = <String>{'바다', '맛집', '카페'};
  String style = '여유롭게';
  bool senior = true;

  static const items = travelTasteOptions;

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 16),
              children: [
                const Text(
                  '여행 취향을 알려주세요',
                  style: TextStyle(fontSize: 27, fontWeight: FontWeight.w900),
                ),

                const SizedBox(height: 5),

                const Text(
                  '나중에 언제든 바꿀 수 있어요.',
                  style: TextStyle(color: Color(0xFF6B7280)),
                ),

                const SizedBox(height: 22),

                const Text(
                  '여행 스타일',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
                ),

                const SizedBox(height: 10),

                // 여행 스타일 선택
                Row(
                  children: ['여유롭게', '알차게', '맛집 중심']
                      .map(
                        (value) => Expanded(
                          child: Padding(
                            padding: EdgeInsets.only(
                              right: value == '맛집 중심' ? 0 : 8,
                            ),
                            child: ChoiceChip(
                              label: Center(child: Text(value)),
                              selected: style == value,
                              selectedColor: AppColors.primary,
                              labelStyle: TextStyle(
                                color: style == value
                                    ? Colors.white
                                    : AppColors.primary,
                                fontWeight: FontWeight.bold,
                              ),
                              onSelected: (_) {
                                setState(() {
                                  style = value;
                                });
                              },
                            ),
                          ),
                        ),
                      )
                      .toList(),
                ),

                const SizedBox(height: 22),

                // 여행 취향 선택 영역
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '여행 취향 선택',
                                  style: TextStyle(
                                    fontSize: 19,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                                SizedBox(height: 3),
                                Text(
                                  '원하는 항목을 여러 개 골라주세요.',
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: Color(0xFF6B7280),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Chip(label: Text('복수 선택 가능')),
                        ],
                      ),

                      const SizedBox(height: 14),

                      // 여행 취향 그리드
                      GridView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        itemCount: items.length,
                        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                              crossAxisCount: ResponsiveLayout.isCompact(context) ? 2 : 3,
                              mainAxisSpacing: 10,
                              crossAxisSpacing: 10,
                              mainAxisExtent: ResponsiveLayout.isCompact(context) ? 118 : 108,
                            ),
                        itemBuilder: (context, index) {
                          final item = items[index];
                          final selected = prefs.contains(item.$2);

                          return Material(
                            color: selected
                                ? AppColors.soft
                                : const Color(0xFFF9FAFF),
                            borderRadius: BorderRadius.circular(18),
                            child: InkWell(
                              onTap: () {
                                setState(() {
                                  if (selected) {
                                    prefs.remove(item.$2);
                                  } else {
                                    prefs.add(item.$2);
                                  }
                                });
                              },
                              borderRadius: BorderRadius.circular(18),
                              child: Stack(
                                children: [
                                  Center(
                                    child: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Text(
                                          item.$1,
                                          style: const TextStyle(fontSize: 25),
                                        ),
                                        const SizedBox(height: 6),
                                        Text(
                                          item.$2,
                                          textAlign: TextAlign.center,
                                          style: TextStyle(
                                            fontSize: 14,
                                            fontWeight: FontWeight.w900,
                                            color: selected
                                                ? AppColors.primary
                                                : AppColors.ink,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),

                                  // 선택 체크 표시
                                  if (selected)
                                    const Positioned(
                                      right: 7,
                                      top: 7,
                                      child: CircleAvatar(
                                        radius: 10,
                                        backgroundColor: AppColors.primary,
                                        child: Icon(
                                          Icons.check,
                                          size: 14,
                                          color: Colors.white,
                                        ),
                                      ),
                                    ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 20),

                // 화면 모드
                const Text(
                  '화면 모드',
                  style: TextStyle(fontWeight: FontWeight.w900),
                ),

                const SizedBox(height: 12),

                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: _ModeCard(
                        icon: '📱',
                        label: '기본 모드',
                        description: '빠르고 컴팩트하게',
                        selected: !senior,
                        onTap: () {
                          setState(() {
                            senior = false;
                          });
                        },
                      ),
                    ),

                    const SizedBox(width: 12),

                    Expanded(
                      child: _ModeCard(
                        icon: '🔎',
                        label: '편한 모드',
                        description: '크고 단순하게',
                        selected: senior,
                        onTap: () {
                          setState(() {
                            senior = true;
                          });
                        },
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // 시작하기 버튼
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
            child: PrimaryButton(
              '시작하기',
              onPressed: prefs.isEmpty
                  ? null
                  : () {
                      DisplayModeService.seniorMode = senior;
                      Navigator.pushAndRemoveUntil(
                        context,
                        MaterialPageRoute(
                          builder: (_) => HomeScreen(seniorMode: senior),
                        ),
                        (_) => false,
                      );
                    },
            ),
          ),
        ],
      ),
    ),
  );
}

/// 기본 모드와 편한 모드 중 하나를 선택하는 카드형 컨트롤입니다.
/// 카드 전체를 누르면 [onTap]으로 선택 상태가 변경됩니다.
class _ModeCard extends StatelessWidget {
  const _ModeCard({
    required this.icon,
    required this.label,
    required this.description,
    required this.selected,
    required this.onTap,
  });

  final String icon;
  final String label;
  final String description;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? AppColors.soft : const Color(0xFFF9FAFB),

      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: selected ? AppColors.primary : Colors.transparent,
          width: 2,
        ),
      ),

      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),

        // 카드 전체를 터치 영역으로 사용합니다.
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),

          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // 아이콘
              Text(
                icon,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 30, height: 1.0),
              ),

              const SizedBox(height: 8),

              // 모드 이름
              Text(
                label,
                textAlign: TextAlign.center,
                maxLines: 1,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: AppColors.ink,
                  height: 1.3,
                ),
              ),

              const SizedBox(height: 4),

              // 모드 설명
              Text(
                description,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: Color(0xFF6B7280),
                  height: 1.3,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
