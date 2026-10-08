import 'package:flutter/material.dart';
import '../../widgets/app_header.dart';

/// 여행 날짜와 기간을 선택하는 단계입니다.
class TripDateScreen extends StatelessWidget {
  const TripDateScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('날짜 선택'),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const Text(
                  '여행 기간을 선택해주세요',
                  style: TextStyle(fontSize: 23, fontWeight: FontWeight.w900),
                ),
                CalendarDatePicker(
                  initialDate: DateTime(2026, 9, 24),
                  firstDate: DateTime(2026),
                  lastDate: DateTime(2027),
                  onDateChanged: (_) {},
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
