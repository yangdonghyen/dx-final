/// 여행지 카드와 검색 결과에 표시할 장소 데이터입니다.
class Place {
  const Place({
    required this.id,
    required this.name,
    required this.region,
    required this.tags,
    required this.image,
  });
  final String id, name, region, image;
  final List<String> tags;
}
