import '../data/api/api_client.dart';
import 'auth_service.dart';

/// One item of a generated day (PlanItemResponse).
class GeneratedPlanItem {
  const GeneratedPlanItem({
    required this.itemId,
    required this.name,
    required this.validationStatus,
    this.placeId,
    this.startTime,
    this.endTime,
    this.itemType,
    this.region,
    this.address,
    this.latitude,
    this.longitude,
    this.category,
  });

  final int itemId;
  final int? placeId;
  final String name;

  /// "HH:mm:ss" from the server, or null when the plan has no time.
  final String? startTime;
  final String? endTime;
  final String validationStatus;

  /// PLACE, MEAL, REST or FREE_TIME.
  final String? itemType;
  final String? region;
  final String? address;
  final double? latitude;
  final double? longitude;
  final String? category;

  factory GeneratedPlanItem.fromJson(Map<String, dynamic> json) {
    return GeneratedPlanItem(
      itemId: (json['item_id'] as num).toInt(),
      placeId: (json['place_id'] as num?)?.toInt(),
      name: json['name']?.toString() ?? '',
      startTime: json['start_time']?.toString(),
      endTime: json['end_time']?.toString(),
      validationStatus: json['validation_status']?.toString() ?? '',
      itemType: json['item_type']?.toString(),
      region: json['region']?.toString(),
      address: json['address']?.toString(),
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      category: json['category']?.toString(),
    );
  }
}

/// One day of a generated plan (PlanDayResponse).
class GeneratedPlanDay {
  const GeneratedPlanDay({
    required this.day,
    required this.visitDate,
    required this.items,
  });

  final int day;
  final DateTime? visitDate;
  final List<GeneratedPlanItem> items;

  factory GeneratedPlanDay.fromJson(Map<String, dynamic> json) {
    final items = json['items'];
    return GeneratedPlanDay(
      day: (json['day'] as num).toInt(),
      visitDate: DateTime.tryParse(json['visit_date']?.toString() ?? ''),
      items: items is List
          ? items
                .whereType<Map<String, dynamic>>()
                .map(GeneratedPlanItem.fromJson)
                .toList()
          : const [],
    );
  }
}

/// A plan made by the AI (PlanGenerateResponse / PlanDetailResponse).
class GeneratedPlan {
  const GeneratedPlan({
    required this.planId,
    required this.status,
    required this.days,
    required this.warnings,
  });

  final int planId;
  final String status;
  final List<GeneratedPlanDay> days;
  final List<String> warnings;

  factory GeneratedPlan.fromJson(Map<String, dynamic> json) {
    final days = json['days'];
    final warnings = json['warnings'];
    final parsedDays = days is List
        ? days
              .whereType<Map<String, dynamic>>()
              .map(GeneratedPlanDay.fromJson)
              .toList()
        : <GeneratedPlanDay>[];
    parsedDays.sort((a, b) => a.day.compareTo(b.day));
    return GeneratedPlan(
      planId: (json['plan_id'] as num).toInt(),
      status: json['status']?.toString() ?? '',
      days: parsedDays,
      warnings: warnings is List
          ? warnings.map((warning) => warning.toString()).toList()
          : const [],
    );
  }
}

/// A pending server-side itinerary change. Receiving this never changes the
/// current [GeneratedPlan] until the user explicitly approves it.
class PlanRegenerationPreview {
  const PlanRegenerationPreview({
    required this.previewId,
    required this.planId,
    required this.baseVersion,
    required this.status,
    required this.proposedItinerary,
    required this.diff,
    required this.validationStatus,
    required this.expiresAt,
  });
  final int previewId;
  final int planId;
  final int baseVersion;
  final String status;
  final Map<String, dynamic> proposedItinerary;
  final List<Map<String, dynamic>> diff;
  final String validationStatus;
  final DateTime? expiresAt;

  factory PlanRegenerationPreview.fromJson(Map<String, dynamic> json) {
    final rawDiff = json['diff'];
    return PlanRegenerationPreview(
      previewId: (json['preview_id'] as num).toInt(),
      planId: (json['plan_id'] as num).toInt(),
      baseVersion: (json['base_version'] as num).toInt(),
      status: json['status']?.toString() ?? 'PENDING',
      proposedItinerary: json['proposed_itinerary'] is Map
          ? Map<String, dynamic>.from(json['proposed_itinerary'] as Map)
          : const <String, dynamic>{},
      diff: rawDiff is List
          ? rawDiff
                .whereType<Map>()
                .map((row) => Map<String, dynamic>.from(row))
                .toList()
          : const <Map<String, dynamic>>[],
      validationStatus: json['validation_status']?.toString() ?? 'UNKNOWN',
      expiresAt: DateTime.tryParse(json['expires_at']?.toString() ?? ''),
    );
  }
}

class PlanRegenerationApplyResult {
  const PlanRegenerationApplyResult({
    required this.previewId,
    required this.planId,
    required this.status,
    this.currentVersion,
    required this.approved,
  });
  final int previewId;
  final int planId;
  final String status;
  final int? currentVersion;
  final bool approved;
  factory PlanRegenerationApplyResult.fromJson(Map<String, dynamic> json) =>
      PlanRegenerationApplyResult(
        previewId: (json['preview_id'] as num).toInt(),
        planId: (json['plan_id'] as num).toInt(),
        status: json['status']?.toString() ?? '',
        currentVersion: (json['current_version'] as num?)?.toInt(),
        approved: json['approved'] == true,
      );
}

class PlanService {
  PlanService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  final ApiClient _apiClient;

  String get _accessToken {
    final token = AuthSession.accessToken;

    if (token == null || token.isEmpty) {
      throw StateError('Login is required.');
    }

    return token;
  }

  /// POST /api/v1/trips/{tripId}/plans/generate. It can take minutes.
  ///
  /// [selectedPlaceIds] may be empty when the trip has a destination; the
  /// server then plans from citywide candidates of that destination.
  Future<GeneratedPlan> generate(
    int tripId, [
    List<int> selectedPlaceIds = const <int>[],
  ]) async {
    final response = await _apiClient.post(
      '/api/v1/trips/$tripId/plans/generate',
      accessToken: _accessToken,
      body: {'selected_place_ids': selectedPlaceIds},
    );

    return GeneratedPlan.fromJson(response);
  }

  Future<PlanRegenerationPreview> createRegenerationPreview(
    int planId, {
    required String reason,
    required String instruction,
    List<String> feedbackCodes = const <String>[],
  }) async {
    final response = await _apiClient.post(
      '/api/v1/plans/$planId/regeneration-previews',
      accessToken: _accessToken,
      body: {
        'reason': reason,
        'instruction': instruction,
        'feedback_codes': feedbackCodes,
      },
    );
    return PlanRegenerationPreview.fromJson(response);
  }

  Future<PlanRegenerationApplyResult> approveRegenerationPreview(
    int planId,
    int previewId,
  ) async {
    final response = await _apiClient.post(
      '/api/v1/plans/$planId/regeneration-previews/$previewId/approve',
      accessToken: _accessToken,
      sendBody: false,
    );
    return PlanRegenerationApplyResult.fromJson(response);
  }

  Future<PlanRegenerationApplyResult> cancelRegenerationPreview(
    int planId,
    int previewId,
  ) async {
    final response = await _apiClient.post(
      '/api/v1/plans/$planId/regeneration-previews/$previewId/cancel',
      accessToken: _accessToken,
      sendBody: false,
    );
    return PlanRegenerationApplyResult.fromJson(response);
  }

  /// POST /api/v1/plans/{planId}/regenerate. [reason] is USER_FATIGUE or
  /// WEATHER_CHANGE. It can take minutes, like [generate].
  Future<GeneratedPlan> regenerate(
    int planId, {
    required String reason,
    required String instruction,
    List<String> feedbackCodes = const <String>[],
  }) async {
    final response = await _apiClient.post(
      '/api/v1/plans/$planId/regenerate',
      accessToken: _accessToken,
      body: {
        'reason': reason,
        'instruction': instruction,
        'feedback_codes': feedbackCodes,
      },
    );

    return GeneratedPlan.fromJson(response);
  }

  /// GET /api/v1/plans/{planId}.
  Future<GeneratedPlan> get(int planId) async {
    final response = await _apiClient.get(
      '/api/v1/plans/$planId',
      accessToken: _accessToken,
    );

    return GeneratedPlan.fromJson(response);
  }
}

/// The server error code of an AppError response, if [error] carries one.
String? apiErrorCode(Object error) {
  if (error is! ApiException) return null;
  final detail = error.body['error'];
  if (detail is Map<String, dynamic>) return detail['code']?.toString();
  return null;
}

/// A Korean message for a failed plan request, with the server code attached.
String planErrorMessage(Object error) {
  if (error is StateError) return '로그인이 필요해요. 다시 로그인한 뒤 시도해주세요.';
  if (error is! ApiException) {
    return '서버에 연결하지 못했어요. 인터넷 연결을 확인해주세요.';
  }
  final detail = error.body['error'];
  final code = detail is Map<String, dynamic>
      ? detail['code']?.toString()
      : null;
  final serverMessage = detail is Map<String, dynamic>
      ? detail['message']?.toString()
      : null;
  const previewMessages = <String, String>{
    'FEEDBACK_GOAL_NOT_MET':
        '요청하신 조건에 맞는 수정안을 만들지 못했어요. 기존 일정은 그대로 유지됩니다. 다른 의견을 선택하거나 다시 시도해 주세요.',
    'FEEDBACK_GOAL_UNACHIEVABLE':
        '현재 일정에서 더 줄일 수 있는 선택 방문지가 없어요. 기존 일정은 유지됩니다. 다른 수정 의견을 선택해 주세요.',
    'FEEDBACK_GOAL_UNVERIFIABLE':
        '휴식시간을 정확히 확인할 수 없어 수정안을 만들지 못했어요. 기존 일정은 그대로 유지됩니다.',
    'PREVIEW_STORAGE_UNAVAILABLE': '수정안 저장소가 준비되지 않았어요. 기존 일정은 유지됩니다.',
    'PREVIEW_EXPIRED': '수정안이 만료되었어요. 기존 일정은 유지되며 다시 생성할 수 있어요.',
    'PREVIEW_NOT_PENDING': '이 수정안은 이미 처리되었어요. 최신 일정을 확인해 주세요.',
    'PREVIEW_VERSION_CONFLICT':
        '기존 일정이 변경되어 수정안을 적용할 수 없어요. 최신 일정에서 다시 만들어 주세요.',
    'PREVIEW_STALE': '기존 일정이 변경되어 수정안을 적용할 수 없어요. 최신 일정에서 다시 만들어 주세요.',
    'PREVIEW_NOT_FOUND': '수정안을 찾을 수 없어요. 기존 일정은 유지됩니다.',
  };
  const validationMessages = <String, String>{
    'TIME_CONFLICT':
        '\uC218\uC815\uC548\uC758 \uBC29\uBB38 \uC2DC\uAC04\uC774 \uACB9\uCCD0 \uC801\uC6A9\uD560 \uC218 \uC5C6\uC5B4\uC694. \uAE30\uC874 \uC77C\uC815\uC740 \uC720\uC9C0\uB429\uB2C8\uB2E4.',
    'ROUTE_TIME_CONFLICT':
        '\uD655\uC778\uB41C \uC774\uB3D9 \uC2DC\uAC04\uACFC \uC77C\uC815\uC774 \uB9DE\uC9C0 \uC54A\uC544 \uC801\uC6A9\uD560 \uC218 \uC5C6\uC5B4\uC694.',
    'OUTSIDE_OPENING_HOURS':
        '\uD655\uC778\uB41C \uC601\uC5C5 \uC2DC\uAC04 \uBC16\uC758 \uC77C\uC815\uC774\uB77C \uC801\uC6A9\uD560 \uC218 \uC5C6\uC5B4\uC694.',
    'AI_SCHEMA_VALIDATION_FAILED':
        '\uC218\uC815\uC548\uC758 \uC7A5\uC18C \uC815\uBCF4\uB97C \uAC80\uC99D\uD560 \uC218 \uC5C6\uC5B4 \uAE30\uC874 \uC77C\uC815\uC744 \uC720\uC9C0\uD569\uB2C8\uB2E4.',
  };
  if (code != null && validationMessages.containsKey(code)) {
    return validationMessages[code]!;
  }
  if (code != null && previewMessages.containsKey(code)) {
    return previewMessages[code]!;
  }
  final korean = switch (code) {
    'PLAN_ALREADY_EXISTS' => '이 여행에는 이미 만들어진 일정이 있어요.',
    'PLACE_NOT_FOUND' => '선택한 장소를 찾지 못했어요. 장소를 다시 골라주세요.',
    'PLACE_COORDINATES_REQUIRED' => '위치가 확인되지 않은 장소가 있어요. 다른 장소를 골라주세요.',
    'PLACE_OUTSIDE_DESTINATION' => '여행지와 다른 지역의 장소가 있어요.',
    'ANCHORS_DIFFERENT_DESTINATIONS' => '선택한 장소들이 서로 다른 지역에 있어요.',
    'PLACE_IDS_REQUIRED' => '장소를 하나 이상 골라주세요.',
    'TRIP_NOT_FOUND' => '여행 정보를 찾지 못했어요.',
    'TRIP_ARCHIVED' => '보관된 여행이라 일정을 만들 수 없어요.',
    'FORBIDDEN' => '이 여행에 접근할 권한이 없어요.',
    'AI_SCHEMA_VALIDATION_FAILED' => 'AI가 올바른 일정을 만들지 못했어요.',
    'EVENT_DATE_MISMATCH' => '행사 날짜가 여행 날짜와 맞지 않아요.',
    'OUTSIDE_OPENING_HOURS' => '운영 시간 밖에 방문하는 일정이 만들어졌어요.',
    'VALIDATION_ERROR' => '요청 내용이 올바르지 않아요.',
    'UNAUTHORIZED' => '로그인이 필요해요. 다시 로그인한 뒤 시도해주세요.',
    _ => '일정을 만들지 못했어요.',
  };
  final reason = [
    if (code != null && code.isNotEmpty) code,
    if (serverMessage != null && serverMessage.isNotEmpty) serverMessage,
  ].join(' · ');
  return reason.isEmpty
      ? '$korean (HTTP ${error.statusCode})'
      : '$korean\n($reason)';
}
