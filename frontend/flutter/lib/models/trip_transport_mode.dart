/// Serializes the single primary transport selection used when creating a Trip.
///
/// ``walkEnabled`` is false until the backend WALK enum migration is applied
/// and the client is deliberately released with the corresponding dart-define.
String? tripPrimaryTransportModeForSelection(
  Iterable<String> selections, {
  required bool walkEnabled,
}) {
  final selected = selections.toSet();
  if (selected.length != 1) return null;

  switch (selected.single) {
    case '자동차':
    case '택시':
      return 'CAR';
    case '대중교통':
      return 'PUBLIC_TRANSIT';
    case '도보':
      return walkEnabled ? 'WALK' : null;
    default:
      return null;
  }
}
