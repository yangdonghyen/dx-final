import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../services/youtube_saved_discovery_service.dart';
import '../trip/trip_places_screen.dart';
import 'youtube_recommended_place_detail_screen.dart';

/// Detail for a saved YouTube discovery. The representative image describes
/// the destination area; it is not treated as a separately identified place.
class YouTubeSavedDetailScreen extends StatelessWidget {
  const YouTubeSavedDetailScreen({super.key, required this.discovery});

  final YouTubeSavedDiscovery discovery;

  String get _destinationTitle {
    final destinationName = discovery.destinationName?.trim();
    return destinationName == null || destinationName.isEmpty
        ? discovery.title
        : destinationName;
  }

  String? get _verifiedDestination {
    final destinationName = discovery.destinationName?.trim();
    return destinationName == null || destinationName.isEmpty
        ? null
        : destinationName;
  }

  String? get _representativeImageUrl {
    final url = discovery.representativeImageUrl?.trim();
    return url == null || url.isEmpty ? null : url;
  }

  String? get _thumbnailUrl {
    final url = discovery.thumbnailUrl?.trim();
    return url == null || url.isEmpty ? null : url;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            SizedBox(
              height: 280,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  _HeroImage(
                    representativeImageUrl: _representativeImageUrl,
                    thumbnailUrl: _thumbnailUrl,
                  ),
                  const DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.bottomCenter,
                        end: Alignment.center,
                        colors: [Color(0x66000000), Colors.transparent],
                      ),
                    ),
                  ),
                  Positioned(
                    top: 48,
                    left: 16,
                    child: _RoundIconButton(
                      icon: Icons.arrow_back_ios_new_rounded,
                      tooltip: '뒤로가기',
                      onPressed: () => Navigator.of(context).maybePop(),
                    ),
                  ),
                  const Positioned(
                    top: 48,
                    right: 16,
                    child: _SavedIndicator(),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 24, 20, 28),
                children: [
                  Text(
                    _destinationTitle,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontSize: 28,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 8),
                  _DestinationContent(
                    discovery: discovery,
                    destinationTitle: _destinationTitle,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Container(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
          decoration: const BoxDecoration(
            color: Colors.white,
            border: Border(top: BorderSide(color: Color(0xFFF3F4F6))),
          ),
          child: FilledButton(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => TripPlacesScreen(
                  initialPlaces: {_destinationTitle},
                  destination: _verifiedDestination,
                ),
              ),
            ),
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(56),
              backgroundColor: AppColors.primary,
              textStyle: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
              ),
            ),
            child: const Text('이 지역으로 여행 만들기'),
          ),
        ),
      ),
    );
  }
}

class _DestinationContent extends StatefulWidget {
  const _DestinationContent({
    required this.discovery,
    required this.destinationTitle,
  });

  final YouTubeSavedDiscovery discovery;
  final String destinationTitle;

  @override
  State<_DestinationContent> createState() => _DestinationContentState();
}

class _DestinationContentState extends State<_DestinationContent> {
  late Future<DestinationRecommendations> _recommendationsFuture;

  @override
  void initState() {
    super.initState();
    _recommendationsFuture = YouTubeSavedDiscoveryService()
        .destinationRecommendations(
          widget.destinationTitle,
          savedDiscoveryId: widget.discovery.savedDiscoveryId,
        );
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      FutureBuilder<DestinationRecommendations>(
        future: _recommendationsFuture,
        builder: (context, snapshot) {
          final themes = snapshot.data?.themes ?? const <String>[];
          if (themes.isEmpty) return const SizedBox.shrink();
          return Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: themes
                  .map(
                    (theme) => Chip(
                      label: Text(theme),
                      backgroundColor: AppColors.soft,
                      side: BorderSide.none,
                      labelStyle: const TextStyle(
                        color: AppColors.primary,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  )
                  .toList(),
            ),
          );
        },
      ),
      const SizedBox(height: 28),
      const Text(
        '발견한 영상',
        style: TextStyle(
          color: AppColors.ink,
          fontSize: 18,
          fontWeight: FontWeight.w800,
        ),
      ),
      const SizedBox(height: 12),
      _VideoSourceCard(discovery: widget.discovery),
      const SizedBox(height: 28),
      Text(
        '${widget.destinationTitle}에서 가볼 만한 곳',
        style: const TextStyle(
          color: AppColors.ink,
          fontSize: 18,
          fontWeight: FontWeight.w800,
        ),
      ),
      const SizedBox(height: 12),
      FutureBuilder<DestinationRecommendations>(
        future: _recommendationsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Center(child: CircularProgressIndicator()),
            );
          }
          if (snapshot.hasError) {
            return const _RecommendationMessage('추천 장소를 불러오지 못했어요.');
          }
          final places = snapshot.data?.places ?? const [];
          if (places.isEmpty) {
            return const _RecommendationMessage('추천 장소 정보가 아직 없어요.');
          }
          return Column(
            children: places
                .map((place) => _RecommendationPlaceCard(place: place))
                .toList(),
          );
        },
      ),
    ],
  );
}

class _RecommendationMessage extends StatelessWidget {
  const _RecommendationMessage(this.message);

  final String message;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 20),
    child: Center(
      child: Text(
        message,
        textAlign: TextAlign.center,
        style: const TextStyle(color: Color(0xFF6B7280), fontSize: 15),
      ),
    ),
  );
}

class _RecommendationPlaceCard extends StatelessWidget {
  const _RecommendationPlaceCard({required this.place});

  final DestinationRecommendationPlace place;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Material(
      color: const Color(0xFFF9FAFB),
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => YouTubeRecommendedPlaceDetailScreen(place: place),
          ),
        ),
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: SizedBox(
                  width: 76,
                  height: 76,
                  child: place.imageUrl.isEmpty
                      ? _imagePlaceholder()
                      : Image.network(
                          place.imageUrl,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => _imagePlaceholder(),
                        ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      place.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.ink,
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      place.category,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Color(0xFF6B7280),
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Icon(
                Icons.chevron_right_rounded,
                color: Color(0xFF6B7280),
                size: 28,
              ),
            ],
          ),
        ),
      ),
    ),
  );

  Widget _imagePlaceholder() => Container(
    color: AppColors.soft,
    alignment: Alignment.center,
    child: const Icon(Icons.place_outlined, color: AppColors.primary, size: 32),
  );
}

class _HeroImage extends StatelessWidget {
  const _HeroImage({
    required this.representativeImageUrl,
    required this.thumbnailUrl,
  });

  final String? representativeImageUrl;
  final String? thumbnailUrl;

  @override
  Widget build(BuildContext context) {
    if (representativeImageUrl != null) {
      return Image.network(
        representativeImageUrl!,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => _thumbnailOrPlaceholder(),
      );
    }
    return _thumbnailOrPlaceholder();
  }

  Widget _thumbnailOrPlaceholder() {
    if (thumbnailUrl != null) {
      return Image.network(
        thumbnailUrl!,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => _placeholder(),
      );
    }
    return _placeholder();
  }

  Widget _placeholder() => Container(
    color: AppColors.soft,
    alignment: Alignment.center,
    child: const Icon(
      Icons.play_circle_fill,
      color: Color(0xFFEF4444),
      size: 72,
    ),
  );
}

class _RoundIconButton extends StatelessWidget {
  const _RoundIconButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) => Material(
    color: const Color(0xEFFFFFFF),
    shape: const CircleBorder(),
    child: IconButton(
      onPressed: onPressed,
      tooltip: tooltip,
      icon: Icon(icon, color: AppColors.ink),
    ),
  );
}

class _SavedIndicator extends StatelessWidget {
  const _SavedIndicator();

  @override
  Widget build(BuildContext context) => Semantics(
    label: '저장됨',
    child: const SizedBox(
      width: 48,
      height: 48,
      child: Material(
        color: Color(0xEFFFFFFF),
        shape: CircleBorder(),
        child: Center(
          child: Icon(Icons.favorite, color: Color(0xFFEF4444), size: 24),
        ),
      ),
    ),
  );
}

class _VideoSourceCard extends StatelessWidget {
  const _VideoSourceCard({required this.discovery});

  final YouTubeSavedDiscovery discovery;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: const Color(0xFFF9FAFB),
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: const Color(0xFFF1F3F5)),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.play_circle_fill, color: Color(0xFFEF4444), size: 32),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                discovery.title,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: AppColors.ink,
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (discovery.channelTitle?.trim().isNotEmpty == true) ...[
                const SizedBox(height: 6),
                Text(
                  discovery.channelTitle!.trim(),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Color(0xFF6B7280),
                    fontSize: 14,
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    ),
  );
}
