import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../core/theme/app_theme.dart';

/// Shows ordered itinerary stops using the same live map as Explore.
class ItineraryRouteMap extends StatelessWidget {
  const ItineraryRouteMap({
    super.key,
    required this.points,
    required this.satellite,
    this.height = 192,
    this.label = '번호는 아래 일정 순서와 같아요.',
    this.onMarkerTap,
  });

  final List<ItineraryMapPoint> points;
  final bool satellite;
  final double height;
  final String label;
  final ValueChanged<int>? onMarkerTap;

  @override
  Widget build(BuildContext context) {
    final center = _centerFor(points);
    final urlTemplate = satellite
        ? 'https://server.arcgisonline.com/ArcGIS/rest/services/'
              'World_Imagery/MapServer/tile/{z}/{y}/{x}'
        : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

    return SizedBox(
      height: height,
      child: Stack(
        children: [
          FlutterMap(
            options: MapOptions(initialCenter: center, initialZoom: 13.2),
            children: [
              TileLayer(
                urlTemplate: urlTemplate,
                userAgentPackageName: 'com.example.travel_mate',
              ),
              if (points.length > 1)
                PolylineLayer(
                  polylines: [
                    Polyline(
                      points: points.map((item) => item.position).toList(),
                      color: AppColors.primary,
                      strokeWidth: 4,
                    ),
                  ],
                ),
              MarkerLayer(
                markers: points
                    .asMap()
                    .entries
                    .map(
                      (entry) => Marker(
                        point: entry.value.position,
                        width: 34,
                        height: 34,
                        child: Semantics(
                          button: onMarkerTap != null,
                          label: '${entry.key + 1}번 ${entry.value.name}',
                          child: GestureDetector(
                            onTap: onMarkerTap == null
                                ? null
                                : () => onMarkerTap!(entry.key),
                            child: _NumberMarker(
                              number: entry.key + 1,
                              active: entry.key == 0,
                            ),
                          ),
                        ),
                      ),
                    )
                    .toList(),
              ),
            ],
          ),
          Positioned(
            top: 12,
            left: 12,
            child: IgnorePointer(
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.94),
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x22000000),
                      blurRadius: 8,
                      offset: Offset(0, 2),
                    ),
                  ],
                ),
                child: Text(
                  label,
                  style: const TextStyle(
                    color: AppColors.primary,
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  LatLng _centerFor(List<ItineraryMapPoint> items) {
    if (items.isEmpty) return const LatLng(37.7519, 128.8761);
    final latitude =
        items.fold<double>(0, (sum, item) => sum + item.position.latitude) /
        items.length;
    final longitude =
        items.fold<double>(0, (sum, item) => sum + item.position.longitude) /
        items.length;
    return LatLng(latitude, longitude);
  }
}

class ItineraryMapPoint {
  const ItineraryMapPoint(this.name, this.position);

  final String name;
  final LatLng position;
}

class _NumberMarker extends StatelessWidget {
  const _NumberMarker({required this.number, required this.active});

  final int number;
  final bool active;

  @override
  Widget build(BuildContext context) => Container(
    alignment: Alignment.center,
    decoration: BoxDecoration(
      color: active ? const Color(0xFF16A34A) : AppColors.primary,
      shape: BoxShape.circle,
      border: Border.all(color: Colors.white, width: 3),
      boxShadow: const [
        BoxShadow(
          color: Color(0x33000000),
          blurRadius: 5,
          offset: Offset(0, 2),
        ),
      ],
    ),
    child: Text(
      '$number',
      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900),
    ),
  );
}
