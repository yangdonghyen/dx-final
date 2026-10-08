import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../../core/theme/app_theme.dart';
import '../../services/youtube_saved_discovery_service.dart';
import '../preference/youtube_saved_detail_screen.dart';
import '../discovery/place_detail_screen.dart';
import '../discovery/camera_screen.dart';
import '../preference/youtube_saved_screen.dart';

enum _SearchMode { region, link }

/// 직접 입력 검색과 원본 웹의 지역 행사·축제 태그를 제공한다.
class TextSearchScreen extends StatefulWidget {
  const TextSearchScreen({
    super.key,
    this.initialQuery = '',
    this.startWithLink = false,
    this.initialLink = '',
    this.resultsOnly = false,
  });

  final String initialQuery;
  final bool startWithLink;
  final String initialLink;
  final bool resultsOnly;

  @override
  State<TextSearchScreen> createState() => _TextSearchScreenState();
}

class _TextSearchScreenState extends State<TextSearchScreen> {
  final controller = TextEditingController();
  final linkController = TextEditingController();

  _SearchMode mode = _SearchMode.region;
  String query = '';
  bool linkSubmitted = false;
  String? linkError;
  bool linkLoading = false;

  @override
  void initState() {
    super.initState();
    query = widget.initialQuery;
    controller.text = query;
    mode = widget.startWithLink ? _SearchMode.link : _SearchMode.region;
    if (widget.initialLink.isNotEmpty) {
      linkController.text = widget.initialLink;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _searchLink();
      });
    }
  }

  static const places = [
    ('안목해변', '강원 강릉시', '🌊', '강릉커피축제', '축제 진행 중'),
    ('황리단길', '경북 경주시', '🏯', '신라문화제', '축제 진행 중'),
    ('애월 해안도로', '제주 제주시', '🚗', '제주들불축제', '축제 진행 중'),
    ('광안리해수욕장', '부산 수영구', '🌃', '부산불꽃축제', '행사 진행 중'),
    ('전주 한옥마을', '전북 전주시', '🏘️', '전주비빔밥축제', '축제 진행 중'),
  ];

  @override
  void dispose() {
    controller.dispose();
    linkController.dispose();
    super.dispose();
  }

  List<(String, String, String, String, String)> _findPlaces(String input) {
    final normalized = input.trim();
    if (normalized.isEmpty) return [];
    return places
        .where(
          (place) =>
              place.$1.contains(normalized) ||
              place.$2.contains(normalized) ||
              normalized.contains(place.$1) ||
              place.$2
                  .split(' ')
                  .any(
                    (part) => normalized.contains(
                      part.replaceFirst(RegExp(r'[시도군구]$'), ''),
                    ),
                  ),
        )
        .toList();
  }

  /// YouTube 주소에서 영상 ID를 꺼냅니다. YouTube 링크가 아니면 null입니다.
  static String? _youtubeVideoId(Uri uri) {
    final host = uri.host.toLowerCase().replaceFirst(RegExp(r'^(www|m|music)\.'), '');
    final segments = uri.pathSegments.where((part) => part.isNotEmpty).toList();
    String? id;
    if (host == 'youtu.be') {
      id = segments.isEmpty ? null : segments.first;
    } else if (host == 'youtube.com' || host == 'youtube-nocookie.com') {
      if (segments.isNotEmpty && segments.first == 'watch') {
        id = uri.queryParameters['v'];
      } else if (segments.length >= 2 &&
          const {'shorts', 'live', 'embed', 'v'}.contains(segments.first)) {
        id = segments[1];
      }
    }
    if (id == null || !RegExp(r'^[A-Za-z0-9_-]{11}$').hasMatch(id)) return null;
    return id;
  }

  /// 링크의 t= 값(90, 90s, 1m30s, 1h2m3s)을 초로 바꿉니다. 없으면 0초입니다.
  static int _startSeconds(Uri uri) {
    final raw = uri.queryParameters['t'] ?? uri.queryParameters['start'];
    if (raw == null || raw.isEmpty) return 0;
    final plain = int.tryParse(raw.replaceAll('s', ''));
    if (plain != null) return plain;
    final match = RegExp(r'^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$').firstMatch(raw);
    if (match == null) return 0;
    int part(int index) => int.tryParse(match.group(index) ?? '') ?? 0;
    return part(1) * 3600 + part(2) * 60 + part(3);
  }

  /// 키 없이 쓰는 YouTube oEmbed로 제목·채널·썸네일을 가져옵니다. 실패하면 빈 값입니다.
  static Future<Map<String, String?>> _videoMetadata(String videoId) async {
    try {
      final response = await http
          .get(
            Uri.https('www.youtube.com', '/oembed', {
              'url': 'https://www.youtube.com/watch?v=$videoId',
              'format': 'json',
            }),
          )
          .timeout(const Duration(seconds: 8));
      if (response.statusCode != 200) return const {};
      final json = jsonDecode(utf8.decode(response.bodyBytes));
      if (json is! Map<String, dynamic>) return const {};
      return {
        'title': json['title']?.toString(),
        'channel_title': json['author_name']?.toString(),
        'thumbnail_url': json['thumbnail_url']?.toString(),
      };
    } catch (_) {
      return const {};
    }
  }

  Future<void> _searchLink() async {
    if (linkLoading) return;
    final uri = Uri.tryParse(linkController.text.trim());
    if (uri == null ||
        (uri.scheme != 'http' && uri.scheme != 'https') ||
        uri.host.isEmpty) {
      setState(() {
        linkSubmitted = true;
        linkError = 'http:// 또는 https://로 시작하는 링크를 입력해주세요.';
      });
      return;
    }
    final videoId = _youtubeVideoId(uri);
    if (videoId == null) {
      setState(() {
        linkSubmitted = true;
        linkError = '지금은 YouTube 영상 링크만 찾을 수 있어요.';
      });
      return;
    }

    setState(() {
      linkSubmitted = true;
      linkError = null;
      linkLoading = true;
    });
    try {
      final metadata = await _videoMetadata(videoId);
      final saved = await YouTubeSavedDiscoveryService().save({
        'video_id': videoId,
        'position_sec': _startSeconds(uri),
        'page_url': uri.toString(),
        ...metadata,
      });
      if (!mounted) return;
      setState(() => linkLoading = false);
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => YouTubeSavedDetailScreen(discovery: saved),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        linkLoading = false;
        linkError = error is StateError
            ? '로그인이 필요해요. 다시 로그인한 뒤 시도해주세요.'
            : '영상 정보를 가져오지 못했어요. 잠시 후 다시 시도해주세요.';
      });
    }
  }

  Widget _inputMethod({
    required IconData icon,
    required String title,
    required String description,
    bool selected = false,
    Color? iconColor,
    VoidCallback? onTap,
  }) => Material(
    color: selected ? AppColors.soft : Colors.white,
    borderRadius: BorderRadius.circular(16),
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: selected ? AppColors.primary : const Color(0xFFE5E7EB), width: selected ? 2 : 1),
        ),
        child: Row(children: [
          Icon(icon, color: iconColor ?? AppColors.primary, size: 27),
          const SizedBox(width: 13),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
            const SizedBox(height: 2),
            Text(description, style: const TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
          ])),
          Icon(selected ? Icons.check_circle_rounded : Icons.chevron_right_rounded, color: AppColors.primary),
        ]),
      ),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final normalized = query.trim();
    final filtered = _findPlaces(normalized);

    if (widget.resultsOnly) {
      return Scaffold(
        appBar: AppBar(
          leading: IconButton(
            onPressed: () => Navigator.of(context).maybePop(),
            icon: const Icon(Icons.chevron_left_rounded),
            tooltip: '뒤로가기',
          ),
          title: const Text('검색 결과'),
          backgroundColor: Colors.white,
        ),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Text(
              '검색 결과 ${filtered.length}곳',
              style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 12),
            if (filtered.isEmpty)
              const Text('일치하는 여행지가 없어요. 다른 지역이나 짧은 검색어로 찾아보세요.')
            else
              ...filtered.map((place) => _PlaceResult(place: place)),
          ],
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          onPressed: () => Navigator.of(context).maybePop(),
          icon: const Icon(Icons.chevron_left_rounded),
          tooltip: '뒤로가기',
        ),
        title: const Text('여행지 검색'),
        backgroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          SegmentedButton<_SearchMode>(
            segments: const [
              ButtonSegment(
                value: _SearchMode.region,
                label: Text('지역'),
                icon: Icon(Icons.place_outlined),
              ),
              ButtonSegment(
                value: _SearchMode.link,
                label: Text('링크'),
                icon: Icon(Icons.link_rounded),
              ),
            ],
            selected: {mode},
            onSelectionChanged: (selection) {
              setState(() => mode = selection.first);
            },
          ),
          const SizedBox(height: 20),
          if (mode == _SearchMode.region) ...[
            TextField(
              controller: controller,
              onChanged: (value) => setState(() => query = value),
              onSubmitted: (value) => setState(() => query = value),
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                hintText: '예: 강릉, 제주, 안목해변',
                suffixIcon: IconButton(
                  onPressed: () {
                    controller.clear();
                    setState(() => query = '');
                  },
                  icon: const Icon(Icons.close),
                ),
              ),
            ),
            const SizedBox(height: 20),
            if (normalized.isEmpty)
              const Text(
                '가고 싶은 여행지 이름이나 지역을 입력해주세요.',
                style: TextStyle(color: Color(0xFF6B7280)),
              ),
            if (normalized.isNotEmpty) ...[
              Text(
                '검색 결과 ${filtered.length}곳',
                style: const TextStyle(
                  fontSize: 19,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 12),
              if (filtered.isEmpty)
                const Text('일치하는 여행지가 없어요. 다른 지역이나 짧은 검색어로 찾아보세요.')
              else
                ...filtered.map((place) => _PlaceResult(place: place)),
            ],
          ] else ...[
            TextField(
              controller: linkController,
              keyboardType: TextInputType.url,
              textInputAction: TextInputAction.search,
              onChanged: (_) => setState(() {
                linkSubmitted = false;
                linkError = null;
              }),
              onSubmitted: (_) => _searchLink(),
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.link_rounded),
                hintText: 'YouTube 영상 링크',
                suffixIcon: IconButton(
                  onPressed: () {
                    linkController.clear();
                    setState(() {
                      linkSubmitted = false;
                      linkError = null;
                    });
                  },
                  icon: const Icon(Icons.close),
                ),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: linkLoading ? null : _searchLink,
                icon: linkLoading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.search),
                label: Text(linkLoading ? '영상 지역을 확인하는 중이에요' : '링크 검색'),
              ),
            ),
            const SizedBox(height: 20),
            if (!linkSubmitted || linkLoading)
              const Text(
                'YouTube 영상 링크를 붙여 넣으면 영상 정보로 여행 지역을 찾아드려요.',
                style: TextStyle(color: Color(0xFF6B7280)),
              )
            else if (linkError != null)
              Text(linkError!, style: const TextStyle(color: Colors.red)),
          ],
          const SizedBox(height: 28),
          const Text(
            '장소 입력 방식',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 6),
          const Text(
            '원하는 방법으로 여행지를 찾아보세요.',
            style: TextStyle(color: Color(0xFF6B7280)),
          ),
          const SizedBox(height: 14),
          _inputMethod(
            icon: Icons.play_circle_fill,
            title: 'YouTube로 장소 찾기',
            description: '저장해 둔 장소에서 선택',
            iconColor: const Color(0xFFEF4444),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const YoutubeSavedScreen()),
            ),
          ),
          const SizedBox(height: 10),
          _inputMethod(
            icon: Icons.image_search_outlined,
            title: '이미지에서 장소 찾기',
            description: '사진에서 장소를 추출',
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const CameraScreen(galleryOnly: true)),
            ),
          ),
          const SizedBox(height: 24),

        ],
      ),
    );
  }
}

class _PlaceResult extends StatelessWidget {
  const _PlaceResult({required this.place});

  final (String, String, String, String, String) place;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: Color(0xFFE5E7EB)),
      ),
      child: InkWell(
        // 검색 결과 카드를 누르면 해당 장소 정보를 상세 페이지로 전달
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => PlaceDetailScreen(
                placeName: place.$1,
                location: place.$2,
                emoji: place.$3,
                tags: _tagsFor(place.$1),
              ),
            ),
          );
        },
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${place.$3}  ${place.$1}',
                style: const TextStyle(
                  fontSize: 19,
                  fontWeight: FontWeight.w900,
                ),
              ),

              const SizedBox(height: 4),

              Text(place.$2, style: const TextStyle(color: Color(0xFF6B7280))),

              const SizedBox(height: 10),

              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 7,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFF3D6),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '🎉 ${place.$5} · ${place.$4}',
                  style: const TextStyle(
                    fontSize: 13,
                    color: Color(0xFF8A5200),
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),

              const SizedBox(height: 11),

              const Text(
                '장소 자세히 보기 →',
                style: TextStyle(
                  color: AppColors.primary,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

List<String> _tagsFor(String placeName) {
  if (placeName.contains('애월')) return const ['바다', '드라이브', '휴식'];
  if (placeName.contains('안목')) return const ['바다', '카페', '산책'];
  if (placeName.contains('황리단')) return const ['맛집', '전통', '카페'];
  if (placeName.contains('광안리')) return const ['바다', '야경', '맛집'];
  return const ['전통문화', '맛집', '체험'];
}
