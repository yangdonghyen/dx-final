import 'package:flutter/material.dart';

import '../../core/layout/app_responsive.dart';
import '../../core/theme/app_theme.dart';
import '../../services/favorite_places_service.dart';
import '../../widgets/app_bottom_navigation.dart';
import '../../widgets/app_header.dart';
import '../discovery/place_detail_screen.dart';

/// 사진 찾기 결과에서 저장한 장소를 보여줍니다.
class SavedPhotoPlacesScreen extends StatefulWidget {
  const SavedPhotoPlacesScreen({super.key, this.selectedTab = 2});

  final int selectedTab;

  @override
  State<SavedPhotoPlacesScreen> createState() => _SavedPhotoPlacesScreenState();
}

class _SavedPhotoPlacesScreenState extends State<SavedPhotoPlacesScreen> {
  Future<void> _delete(String name) async {
    final shouldDelete = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('저장 장소를 삭제할까요?'),
        content: Text('“$name”을(를) 저장 목록에서 삭제합니다.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('취소'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFFD92D20),
            ),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('삭제하기'),
          ),
        ],
      ),
    );
    if (shouldDelete == true && mounted) {
      setState(() => FavoritePlacesService.removePhotoSaved(name));
    }
  }

  @override
  Widget build(BuildContext context) {
    final places = FavoritePlacesService.photoSavedPlaces.values.toList();
    return Scaffold(
      backgroundColor: const Color(0xFFF7F8FF),
      bottomNavigationBar: AppBottomNavigation(selectedIndex: widget.selectedTab),
      body: SafeArea(
        child: Column(
          children: [
            const AppHeader('저장 장소 보기'),
            Expanded(
              child: places.isEmpty
                  ? const Center(
                      child: Padding(
                        padding: EdgeInsets.all(24),
                        child: Text(
                          '사진으로 찾은 장소를 모아보세요.',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 17,
                            color: Color(0xFF6B7280),
                          ),
                        ),
                      ),
                    )
                  : ListView.separated(
                      padding: EdgeInsets.all(ResponsiveLayout.pageHorizontal(context)),
                      itemCount: places.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        final place = places[index];
                        return Material(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(18),
                          child: InkWell(
                            onTap: () => Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => PlaceDetailScreen(
                                  placeName: place.name,
                                  location: place.location,
                                  emoji: place.emoji,
                                  tags: place.tags,
                                ),
                              ),
                            ),
                            borderRadius: BorderRadius.circular(18),
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Row(
                                children: [
                                  Container(
                                    width: 58,
                                    height: 58,
                                    alignment: Alignment.center,
                                    decoration: BoxDecoration(
                                      color: AppColors.soft,
                                      borderRadius: BorderRadius.circular(14),
                                    ),
                                    child: Text(
                                      place.emoji,
                                      style: const TextStyle(fontSize: 32),
                                    ),
                                  ),
                                  const SizedBox(width: 14),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          place.name,
                                          style: const TextStyle(
                                            fontSize: 18,
                                            fontWeight: FontWeight.w800,
                                          ),
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          place.location,
                                          style: const TextStyle(
                                            color: Color(0xFF6B7280),
                                          ),
                                        ),
                                        const SizedBox(height: 4),
                                        const Text(
                                          '사진으로 저장한 장소',
                                          style: TextStyle(
                                            color: AppColors.primary,
                                            fontSize: 12,
                                            fontWeight: FontWeight.w700,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  TextButton(onPressed: () => _delete(place.name), style: TextButton.styleFrom(foregroundColor: const Color(0xFFD9363E)), child: const Text('삭제')),
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
