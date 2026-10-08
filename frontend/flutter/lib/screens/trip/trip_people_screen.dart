import 'package:flutter/material.dart';
import '../../widgets/app_header.dart';

/// 여행 인원을 선택하는 단계입니다.
class TripPeopleScreen extends StatelessWidget {
  const TripPeopleScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          const AppHeader('여행 인원'),
          Expanded(
            child: Center(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: const [
                  Icon(Icons.remove_circle_outline, size: 38),
                  Padding(
                    padding: EdgeInsets.symmetric(horizontal: 25),
                    child: Text(
                      '2명',
                      style: TextStyle(
                        fontSize: 30,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                  Icon(Icons.add_circle_outline, size: 38),
                ],
              ),
            ),
          ),
        ],
      ),
    ),
  );
}
