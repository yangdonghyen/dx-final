/// Keeps favorite places while the app is running, independent of each screen.
class FavoritePlacesService {
  FavoritePlacesService._();

  static final Set<String> likedPlaceNames = <String>{};
  static final Set<String> removedSavedPlaceNames = <String>{};
  static final Map<String, PhotoSavedPlace> photoSavedPlaces =
      <String, PhotoSavedPlace>{};

  static bool isLiked(String placeName) => likedPlaceNames.contains(placeName);
  static bool isRemovedSavedPlace(String name) => removedSavedPlaceNames.contains(name);
  static void removeSavedPlace(String name) { removedSavedPlaceNames.add(name); likedPlaceNames.remove(name); }
  static bool isPhotoSaved(String placeName) =>
      photoSavedPlaces.containsKey(placeName);

  static void saveFromPhoto(
    String placeName, {
    required String location,
    required String emoji,
    required List<String> tags,
  }) {
    likedPlaceNames.add(placeName);
    photoSavedPlaces[placeName] = PhotoSavedPlace(
      name: placeName,
      location: location,
      emoji: emoji,
      tags: tags,
    );
  }

  static bool togglePhotoSaved(
    String placeName, {
    required String location,
    required String emoji,
    required List<String> tags,
  }) {
    if (photoSavedPlaces.remove(placeName) != null) {
      likedPlaceNames.remove(placeName);
      return false;
    }
    saveFromPhoto(placeName, location: location, emoji: emoji, tags: tags);
    return true;
  }
  static void removePhotoSaved(String placeName) {
    photoSavedPlaces.remove(placeName);
    likedPlaceNames.remove(placeName);
  }

  static void toggle(String placeName) {
    if (!likedPlaceNames.add(placeName)) {
      likedPlaceNames.remove(placeName);
    }
  }
}

class PhotoSavedPlace {
  const PhotoSavedPlace({
    required this.name,
    required this.location,
    required this.emoji,
    required this.tags,
  });

  final String name;
  final String location;
  final String emoji;
  final List<String> tags;
}
