import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../services/tour_place_detail_service.dart';
import '../../services/youtube_saved_discovery_service.dart';
import '../trip/trip_places_screen.dart';

class YouTubeRecommendedPlaceDetailScreen extends StatefulWidget {
  const YouTubeRecommendedPlaceDetailScreen({super.key, required this.place});

  final DestinationRecommendationPlace place;

  @override
  State<YouTubeRecommendedPlaceDetailScreen> createState() =>
      _YouTubeRecommendedPlaceDetailScreenState();
}

class _YouTubeRecommendedPlaceDetailScreenState
    extends State<YouTubeRecommendedPlaceDetailScreen> {
  final TourPlaceDetailService _service = TourPlaceDetailService();
  late Future<TourPlaceDetail> _detailFuture;

  @override
  void initState() {
    super.initState();
    _detailFuture = _load();
  }

  Future<TourPlaceDetail> _load() => _service.get(
    widget.place.contentId,
    contentTypeId: widget.place.contentTypeId,
  );

  void _retry() => setState(() => _detailFuture = _load());

  String? _usable(String? value) {
    final trimmed = value?.trim();
    return trimmed == null || trimmed.isEmpty ? null : trimmed;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: AppColors.bg,
    body: FutureBuilder<TourPlaceDetail>(
      future: _detailFuture,
      builder: (context, snapshot) {
        final detail = snapshot.data;
        final title = _usable(detail?.title) ?? widget.place.title;
        final imageUrl = _usable(detail?.imageUrl) ?? widget.place.imageUrl;
        final address =
            _usable(detail?.address) ?? _usable(widget.place.address);
        return CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: _hero(imageUrl, _usable(widget.place.imageUrl)),
            ),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 22, 20, 28),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  Text(
                    title,
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontSize: 28,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  if (_usable(widget.place.category) != null) ...[
                    const SizedBox(height: 10),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Chip(
                        label: Text(widget.place.category),
                        backgroundColor: AppColors.soft,
                        side: BorderSide.none,
                        labelStyle: const TextStyle(
                          color: AppColors.primary,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                  if (address != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      address,
                      style: const TextStyle(
                        fontSize: 16,
                        color: Color(0xFF667085),
                      ),
                    ),
                  ],
                  if (snapshot.connectionState != ConnectionState.done &&
                      detail == null)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 36),
                      child: Center(child: CircularProgressIndicator()),
                    ),
                  if (snapshot.hasError) ...[
                    const SizedBox(height: 20),
                    _errorPanel(onRetry: _retry),
                  ],
                  if (detail != null) ...[
                    if (_usable(detail.overview) != null) ...[
                      const SizedBox(height: 28),
                      _sectionTitle('소개'),
                      const SizedBox(height: 10),
                      Text(
                        detail.overview!,
                        style: const TextStyle(
                          fontSize: 16,
                          height: 1.55,
                          color: AppColors.ink,
                        ),
                      ),
                    ],
                    if (_hasVisitInfo(detail)) ...[
                      const SizedBox(height: 28),
                      _sectionTitle('이용 정보'),
                      const SizedBox(height: 10),
                      _infoRows(detail),
                    ],
                    if (address != null ||
                        detail.mapX != null ||
                        detail.mapY != null) ...[
                      const SizedBox(height: 28),
                      _sectionTitle('위치'),
                      const SizedBox(height: 10),
                      if (address != null) _infoRow('주소', address),
                      if (detail.mapX != null && detail.mapY != null)
                        _infoRow('좌표', '${detail.mapY}, ${detail.mapX}'),
                    ],
                  ],
                ]),
              ),
            ),
          ],
        );
      },
    ),
    bottomNavigationBar: SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
        child: FilledButton(
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => TripPlacesScreen(
                initialPlaces: {widget.place.title},
                destination: regionFromAddress(widget.place.address),
              ),
            ),
          ),
          style: FilledButton.styleFrom(
            backgroundColor: AppColors.primary,
            minimumSize: const Size.fromHeight(58),
            textStyle: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
            ),
          ),
          child: const Text('이 장소로 여행 만들기'),
        ),
      ),
    ),
  );

  Widget _hero(String? imageUrl, String? fallbackImageUrl) => SizedBox(
    height: 300,
    child: Stack(
      fit: StackFit.expand,
      children: [
        if (imageUrl != null && imageUrl.isNotEmpty)
          Image.network(
            imageUrl,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => _fallbackImage(fallbackImageUrl),
          )
        else
          _imagePlaceholder(),
        const DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.bottomCenter,
              end: Alignment.center,
              colors: [Color(0x44000000), Colors.transparent],
            ),
          ),
        ),
        Positioned(
          top: MediaQuery.paddingOf(context).top + 12,
          left: 16,
          child: Material(
            color: Colors.white.withValues(alpha: 0.92),
            shape: const CircleBorder(),
            child: IconButton(
              tooltip: '뒤로가기',
              onPressed: () => Navigator.of(context).maybePop(),
              icon: const Icon(Icons.arrow_back_ios_new_rounded),
            ),
          ),
        ),
      ],
    ),
  );

  Widget _fallbackImage(String? imageUrl) {
    if (imageUrl == null || imageUrl.isEmpty) return _imagePlaceholder();
    return Image.network(
      imageUrl,
      fit: BoxFit.cover,
      errorBuilder: (_, __, ___) => _imagePlaceholder(),
    );
  }

  Widget _imagePlaceholder() => Container(
    color: AppColors.soft,
    alignment: Alignment.center,
    child: const Icon(Icons.place_outlined, size: 64, color: AppColors.primary),
  );

  Widget _sectionTitle(String title) => Text(
    title,
    style: const TextStyle(
      fontSize: 20,
      fontWeight: FontWeight.w800,
      color: AppColors.ink,
    ),
  );

  bool _hasVisitInfo(TourPlaceDetail detail) =>
      _usable(detail.operatingHours) != null ||
      _usable(detail.restDate) != null ||
      _usable(detail.useFee) != null ||
      _usable(detail.parking) != null ||
      _usable(detail.infoCenter) != null ||
      _usable(detail.homepage) != null;

  Widget _infoRows(TourPlaceDetail detail) => Column(
    children: [
      if (_usable(detail.operatingHours) case final value?)
        _infoRow('이용시간', value),
      if (_usable(detail.restDate) case final value?) _infoRow('휴무일', value),
      if (_usable(detail.useFee) case final value?) _infoRow('이용요금', value),
      if (_usable(detail.parking) case final value?) _infoRow('주차', value),
      if (_usable(detail.infoCenter) case final value?) _infoRow('문의처', value),
      if (_usable(detail.homepage) case final value?) _infoRow('홈페이지', value),
    ],
  );

  Widget _infoRow(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 80,
          child: Text(
            label,
            style: const TextStyle(fontSize: 15, color: Color(0xFF667085)),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(fontSize: 15, color: AppColors.ink),
          ),
        ),
      ],
    ),
  );

  Widget _errorPanel({required VoidCallback onRetry}) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
    ),
    child: Row(
      children: [
        const Expanded(
          child: Text('상세 정보를 불러오지 못했어요.', style: TextStyle(fontSize: 15)),
        ),
        TextButton(onPressed: onRetry, child: const Text('다시 시도')),
      ],
    ),
  );
}

const _metroRegions = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종'];

/// 관광공사 주소에서 여행 지역을 꺼냅니다. 광역시는 시 이름, 도는 시·군 이름입니다.
/// 예: "경기도 수원시 팔달구 정조로" → 수원, "부산광역시 수영구" → 부산.
/// 주소가 없거나 형식이 다르면 null이라 여행 만들기에서 지역을 다시 물어요.
String? regionFromAddress(String? address) {
  final tokens = (address ?? '').trim().split(RegExp(r'\s+'));
  if (tokens.isEmpty || tokens.first.isEmpty) return null;
  final first = tokens.first;
  if (first.startsWith('제주')) return '제주';
  for (final metro in _metroRegions) {
    if (first.startsWith(metro)) return metro;
  }
  if (tokens.length < 2) return null;
  final city = tokens[1];
  if (city.length >= 3 && (city.endsWith('시') || city.endsWith('군'))) {
    return city.substring(0, city.length - 1);
  }
  return null;
}
