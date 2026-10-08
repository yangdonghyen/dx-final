import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../services/trip_service.dart';
import '../../widgets/app_bottom_navigation.dart';

class PastTripsScreen extends StatefulWidget {
  const PastTripsScreen({super.key, this.selectedTab = 3});

  final int selectedTab;

  @override
  State<PastTripsScreen> createState() => _PastTripsScreenState();
}

class _PastTripsScreenState extends State<PastTripsScreen> {
  final TripService _tripService = TripService();

  bool _loading = true;
  String? _errorMessage;
  List<TripListItem> _pastTrips = const [];

  @override
  void initState() {
    super.initState();
    _loadTrips();
  }

  Future<void> _loadTrips() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });

    try {
      final trips = await _tripService.list();

      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);

      final pastTrips =
          trips.where((trip) {
            final endDate = trip.endDate;
            if (endDate == null) {
              return false;
            }

            final endDay = DateTime(endDate.year, endDate.month, endDate.day);

            return endDay.isBefore(today);
          }).toList()..sort((a, b) {
            final aDate = a.endDate;
            final bDate = b.endDate;

            if (aDate == null && bDate == null) return 0;
            if (aDate == null) return 1;
            if (bDate == null) return -1;

            return bDate.compareTo(aDate);
          });

      if (!mounted) return;

      setState(() {
        _pastTrips = pastTrips;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _loading = false;
        _errorMessage = '지난 여행을 불러오지 못했어요.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7F8FF),
      bottomNavigationBar: AppBottomNavigation(
        selectedIndex: widget.selectedTab,
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SizedBox(
                    height: 48,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        const Text(
                          '지난 여행',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w800,
                            color: AppColors.ink,
                          ),
                        ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: IconButton(
                            onPressed: () => Navigator.of(context).maybePop(),
                            icon: const Icon(
                              Icons.chevron_left_rounded,
                              size: 34,
                            ),
                            tooltip: '뒤로 가기',
                            padding: EdgeInsets.zero,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 5),
                  const Text(
                    '소중한 여행 기록이에요',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 14, color: Color(0xFF9CA3AF)),
                  ),
                ],
              ),
            ),
            Expanded(child: _buildBody()),
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _errorMessage!,
                style: const TextStyle(fontSize: 16, color: Color(0xFF6B7280)),
              ),
              const SizedBox(height: 16),
              FilledButton(onPressed: _loadTrips, child: const Text('다시 시도')),
            ],
          ),
        ),
      );
    }

    if (_pastTrips.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.flight_takeoff_outlined,
                size: 56,
                color: Color(0xFFB8BFCC),
              ),
              SizedBox(height: 16),
              Text(
                '아직 지난 여행이 없어요',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink,
                ),
              ),
              SizedBox(height: 7),
              Text(
                '여행을 다녀오면 이곳에서 확인할 수 있어요.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 14, color: Color(0xFF9CA3AF)),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadTrips,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        itemCount: _pastTrips.length,
        separatorBuilder: (_, _) => const SizedBox(height: 16),
        itemBuilder: (context, index) {
          return _TripCard(trip: _pastTrips[index]);
        },
      ),
    );
  }
}

class _TripCard extends StatelessWidget {
  const _TripCard({required this.trip});

  final TripListItem trip;

  @override
  Widget build(BuildContext context) {
    final title = _displayTitle(trip);
    final destination = trip.destination?.trim();
    final departure = trip.departure?.trim();
    final chips = <_ChipData>[
      if (destination != null && destination.isNotEmpty)
        _ChipData(Icons.place_outlined, destination),
      if (departure != null && departure.isNotEmpty)
        _ChipData(Icons.my_location_outlined, '출발: $departure'),
    ];

    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(24),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: 160,
            child: Stack(
              fit: StackFit.expand,
              children: [
                const DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [AppColors.soft, Color(0xFFC7D4F5)],
                    ),
                  ),
                  child: Align(
                    alignment: Alignment(0, -0.3),
                    child: Icon(
                      Icons.luggage_rounded,
                      size: 56,
                      color: AppColors.primary,
                    ),
                  ),
                ),
                const DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.bottomCenter,
                      end: Alignment.center,
                      colors: [Color(0x99000000), Colors.transparent],
                    ),
                  ),
                ),
                Positioned(
                  left: 16,
                  right: 16,
                  bottom: 14,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 19,
                          fontWeight: FontWeight.w800,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        _dateRange(trip.startDate, trip.endDate),
                        style: const TextStyle(
                          fontSize: 12,
                          color: Color(0xDFFFFFFF),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          if (chips.isNotEmpty)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Wrap(
                spacing: 5,
                runSpacing: 5,
                children: chips.map((chip) => _PlaceChip(data: chip)).toList(),
              ),
            ),
        ],
      ),
    );
  }

  static String _displayTitle(TripListItem trip) {
    final title = trip.title?.trim();
    if (title != null && title.isNotEmpty) {
      return title;
    }

    final destination = trip.destination?.trim();
    if (destination != null && destination.isNotEmpty) {
      return '$destination 여행';
    }

    return '지난 여행';
  }

  static String _dateRange(DateTime? startDate, DateTime? endDate) {
    if (startDate == null && endDate == null) {
      return '날짜 정보 없음';
    }

    if (startDate == null) {
      return _formatDate(endDate!);
    }

    if (endDate == null) {
      return _formatDate(startDate);
    }

    return '${_formatDate(startDate)} ~ ${_formatDate(endDate)}';
  }

  static String _formatDate(DateTime date) {
    final month = date.month.toString().padLeft(2, '0');
    final day = date.day.toString().padLeft(2, '0');

    return '${date.year}.$month.$day';
  }
}

class _ChipData {
  const _ChipData(this.icon, this.text);

  final IconData icon;
  final String text;
}

class _PlaceChip extends StatelessWidget {
  const _PlaceChip({required this.data});

  final _ChipData data;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0xFFF3F4F6),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(data.icon, size: 13, color: const Color(0xFF4B5563)),
          const SizedBox(width: 3),
          Flexible(
            child: Text(
              data.text,
              style: const TextStyle(fontSize: 11, color: Color(0xFF4B5563)),
            ),
          ),
        ],
      ),
    );
  }
}
