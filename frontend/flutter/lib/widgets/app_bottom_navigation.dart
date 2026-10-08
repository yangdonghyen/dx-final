import 'package:flutter/material.dart';

import '../screens/home/home_screen.dart';
import '../core/layout/app_responsive.dart';

/// The same primary navigation stays available on screens opened from Home.
class AppBottomNavigation extends StatelessWidget {
  const AppBottomNavigation({super.key, required this.selectedIndex});

  final int selectedIndex;

  void _goTo(BuildContext context, int index) {
    if (index == selectedIndex && index == 0) {
      Navigator.of(context).popUntil((route) => route.isFirst);
      return;
    }
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => HomeScreen(initialTab: index)),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) => NavigationBarTheme(
    data: NavigationBarThemeData(
      height: ResponsiveLayout.bottomNavigationHeight(context),
      labelTextStyle: WidgetStatePropertyAll(TextStyle(
        fontSize: ResponsiveLayout.isCompact(context) ? 11 : 12,
      )),
    ),
    child: NavigationBar(
    selectedIndex: selectedIndex,
    onDestinationSelected: (index) => _goTo(context, index),
    destinations: const [
      NavigationDestination(
        icon: Icon(Icons.home_outlined),
        selectedIcon: Icon(Icons.home),
        label: '홈',
      ),
      NavigationDestination(
        icon: Icon(Icons.map_outlined),
        selectedIcon: Icon(Icons.map),
        label: '탐색',
      ),
      NavigationDestination(
        icon: Icon(Icons.bookmark_outline),
        selectedIcon: Icon(Icons.bookmark),
        label: '저장',
      ),
      NavigationDestination(
        icon: Icon(Icons.person_outline),
        selectedIcon: Icon(Icons.person),
        label: '마이',
      ),
    ],
    ),
  );
}
