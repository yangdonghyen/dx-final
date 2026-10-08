/// 여행에 함께하는 동행자의 이름과 역할을 담는 데이터입니다.
class Companion {
  const Companion({
    required this.name,
    required this.age,
    this.prefs = const [],
    this.walking = '',
    this.avoid = const [],
  });
  final String name, age, walking;
  final List<String> prefs, avoid;
}
