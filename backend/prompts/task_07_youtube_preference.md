# Codex Task 07 — YouTube Source + Preference Analysis API

Task 01~06은 완료되었다.

현재 상태:
- FastAPI Backend skeleton 완료
- MySQL 연결 완료
- SQLAlchemy Model 22개 완료
- Alembic 001_initial_schema 적용 완료
- Alembic 002_seed_interest_codes 적용 완료
- Auth/User/JWT/Refresh/Preferences 완료
- Companion API 완료
- Trip CRUD + Snapshot 완료
- Mock External Provider 계층 완료
- Mock YouTube / Preference / Place / Plan Provider 완료
- pytest 139 passed
- Task 06까지 GitHub push 완료
- working tree clean

이번 Task에서는 **YouTube Source 등록/비활성화 + Mock 기반 Preference Analysis API**만 구현한다.

---

# 1. 구현 전 반드시 읽을 문서

다음 문서를 다시 읽고 작업해라.

1. `docs/01_planning/01_core_features.md`
2. `docs/02_api/02_api_spec.md`
3. `docs/03_database/03_db_schema.md`
4. `docs/04_external_api/04_external_apis.md`
5. `docs/05_architecture/05_project_structure.md`
6. `docs/06_mock/06_mock_data.md`
7. `docs/07_implementation/07_implementation_plan.md`

이번 Task의 Source of Truth:

- API: `docs/02_api/02_api_spec.md`
- DB: `docs/03_database/03_db_schema.md`
- 외부 Provider 역할: `docs/04_external_api/04_external_apis.md`
- Mock 구조: `docs/06_mock/06_mock_data.md`
- Architecture: `docs/05_architecture/05_project_structure.md`

문서와 이 프롬프트가 충돌하면 문서를 우선하고 결과에 충돌 내용을 보고해라.

---

# 2. 이번 Task 범위

구현 API:

```text
POST   /api/v1/trips/{trip_id}/sources/youtube
DELETE /api/v1/trips/{trip_id}/sources/{source_id}
POST   /api/v1/trips/{trip_id}/analyze-preferences
```

주요 Table:

```text
trips
trip_sources
trip_interests
interest_codes
```

참조:

```text
user_interests
trip_preferences
trip_companions
```

Provider:

```text
ContentProvider / Mock Content Provider
Preference Analysis Provider / Mock AI Provider
```

흐름:

```text
YouTube URL 또는 videoId
→ video_id 정규화
→ Mock Content Provider로 metadata 조회
→ trip_sources 저장
→ analyze-preferences 호출
→ 활성 source metadata 수집
→ Mock Preference Analysis
→ 허용 interest code 검증
→ trip_interests 반영
```

---

# 3. 이번 Task에서 구현하지 말 것

이번 Task에서는 다음을 구현하지 마라.

- 실제 YouTube Data API 호출
- 실제 EXAONE 호출
- Kakao Local
- TourAPI
- Weather
- Routing
- Place 검색 API
- Plan 생성 API
- Plan 수정/재생성/confirm
- Smart Docent
- Gemini
- 실제 Kakao/Naver 로그인
- Frontend 수정

즉, **Task 06의 Mock Provider를 실제 API 흐름에 연결하는 단계**다.

---

# 4. 인증 / Trip 소유권

세 API 모두 기존 `get_current_user()`를 사용한다.

반드시:

```text
trip.user_id == current_user.id
```

를 검증한다.

다른 사용자의 Trip에는:
- Source 추가 금지
- Source 삭제/비활성화 금지
- Preference 분석 금지

클라이언트가 전달하는 user_id를 신뢰하지 마라.

ARCHIVED Trip에 대한 동작은 API 문서를 따른다.
문서가 명확하지 않다면 새 Source 추가/분석은 허용하지 않는 방향으로 처리하고 결과에 명시한다.

---

# 5. POST /trips/{trip_id}/sources/youtube

YouTube URL 또는 videoId를 받는다.

정확한 request field는 API 문서를 따른다.

예시 개념:

```json
{
  "url": "https://www.youtube.com/watch?v=abc123"
}
```

또는 문서가 video_id를 받도록 정의했다면 그 구조를 따른다.

---

# 6. YouTube URL / videoId 정규화

가능하면 다음 일반 형식을 안전하게 처리한다.

```text
https://www.youtube.com/watch?v=<id>
https://youtu.be/<id>
https://www.youtube.com/shorts/<id>
videoId 직접 입력
```

단:
- 지나치게 복잡한 URL parser를 만들지 마라.
- 문서에서 허용한 입력 범위를 우선한다.
- host가 YouTube가 아닌 URL은 거부한다.
- query string의 다른 값 때문에 잘못된 ID를 저장하지 마라.

정규화 결과는 provider에 전달할 `video_id`다.

---

# 7. Mock Content Provider 사용

Task 06의 기존 Content Provider Interface를 재사용한다.

Router/Service에서 mock JSON을 직접 읽지 마라.

흐름:

```text
YouTubeSourceService
→ ContentProvider
→ MockContentProvider
```

현재는 Mock Provider를 사용한다.

실제 YouTube HTTP 호출 금지.

---

# 8. trip_sources 저장

`trip_sources` DB Schema를 정확히 따른다.

Source type은 YouTube에 해당하는 기존 Enum/문자열을 사용한다.

반드시:
- trip_id
- source_type
- external_id(video_id)
- metadata 관련 문서 필드
- tags JSON
- is_active

를 문서 기준으로 저장한다.

중복 규칙:

```text
UNIQUE(trip_id, source_type, external_id)
```

를 존중한다.

이미 같은 source가 존재할 때:
- active이면 중복 생성 금지
- inactive이면 문서/API 정책에 따라 re-activate 또는 conflict 처리

문서가 명확하지 않다면 **기존 row를 재활성화하고 metadata를 갱신하는 방식**을 우선 검토하되, 실제 구현 전에 현재 DB/API 구조와 충돌이 없는지 확인한다.

새 row를 무한 중복 생성하지 마라.

---

# 9. Source metadata

Provider에서 얻은 metadata를 문서에 맞게 저장/응답한다.

예:
- title
- description
- channel
- tags
- external_id

단, DB에 존재하지 않는 column을 만들지 마라.

원본 YouTube response 전체를 그대로 DB에 저장하지 마라.

현재 Schema에 들어가는 최소 필드만 사용한다.

---

# 10. DELETE /trips/{trip_id}/sources/{source_id}

실제 DELETE SQL 금지.

반드시:

```text
is_active = false
```

로 처리한다.

source row 및 과거 분석 근거를 물리 삭제하지 마라.

반드시:
- trip 소유권
- source가 해당 trip 소속인지
- source 존재 여부

를 검증한다.

다른 Trip의 source_id를 조합해서 비활성화할 수 없어야 한다.

---

# 11. POST /trips/{trip_id}/analyze-preferences

현재 Trip의 **활성 YouTube Source**를 기반으로 Mock Preference Analysis를 수행한다.

흐름:

```text
1. current user / trip ownership 확인
2. active trip_sources 조회
3. source metadata를 분석 입력으로 구성
4. Mock Preference Analysis Provider 호출
5. 반환 interest code를 interest_codes Master와 대조
6. trip_interests 반영
7. 결과 반환
```

활성 Source가 0개인 경우:
- API 문서 정의를 따른다.
- 문서가 없다면 validation error로 처리한다.
- 빈 분석 결과를 성공처럼 저장하지 마라.

---

# 12. Preference Analysis 원칙

현재 Task에서는 **Mock 결과**만 사용한다.

실제 EXAONE 호출 금지.

Mock Provider가 반환하는 결과는 deterministic 해야 한다.

중요:
- Provider 결과를 그대로 신뢰하지 마라.
- 모든 interest code를 `interest_codes`와 검증한다.
- 없는 code가 반환되면 저장하지 말고 명확한 오류 처리
- 문서 밖 코드 생성 금지

허용 Master:

```text
FOOD
CAFE
NATURE
CULTURE
HISTORY
SHOPPING
EXHIBITION
ACTIVITY
```

---

# 13. trip_interests 반영 규칙

기존 Trip 생성 시 이미 존재할 수 있는:

```text
PROFILE
USER
```

interest를 보존해야 한다.

이번 분석으로 생성되는 것은:

```text
CONTENT_AI
```

source_type을 사용한다.

중요:
- 기존 PROFILE interest 삭제 금지
- 기존 USER interest 삭제 금지
- 분석 재실행 시 CONTENT_AI 결과는 최신 분석 결과와 일치하도록 갱신
- 중복 `(trip_id, interest_code)` 제약을 깨지 않게 처리

현재 DB Schema가 한 interest_code당 source_type 하나만 허용하는 구조라면,
기존 PROFILE/USER와 CONTENT_AI가 같은 interest_code일 때 어떻게 표현해야 하는지
`03_db_schema.md`를 확인하고 그 설계에 맞춰 처리한다.

이 부분을 임의로 추측하지 말고 현재 schema/문서를 우선한다.

필요하면:
- 기존 우선 source 유지
- is_confirmed 갱신
등 문서 규칙을 적용한다.

Schema 변경은 하지 마라.

---

# 14. is_confirmed

`trip_interests.is_confirmed` 의미를 DB/API 문서 기준으로 처리한다.

Mock AI 분석 결과를 사용자 확정 관심사로 자동 간주하지 마라.

즉 문서가 별도로 정의하지 않았다면
AI 분석 결과는 기본적으로 미확정 상태를 유지하는 방향이 안전하다.

사용자 직접 입력 USER interest와 동일하게 취급하지 마라.

---

# 15. Service / Repository 구조

최소 역할 분리:

```text
TripSourceRepository
TripInterestRepository
YouTubeSourceService 또는 TripSourceService
PreferenceAnalysisService
```

기존 `TripRepository`, `TripInterestRepository`가 있으면
중복 클래스를 만들지 말고 재사용/확장한다.

Router에서 직접 SQLAlchemy Query 금지.

Router에서 Mock Provider 직접 접근 금지.

---

# 16. Provider Factory / DI

Task 06의 기존 Factory / DI 구조를 재사용한다.

예:

```text
get_content_provider()
get_ai_provider()
```

새로운 mock switch 체계를 중복 생성하지 마라.

현재 Task에서는 Factory가 Mock 구현을 반환해도 된다.

---

# 17. Transaction

Source 저장 및 Preference 분석 결과 반영은
각 API 단위로 Transaction 일관성을 유지한다.

특히 분석 중:
- 일부 interest만 저장되고 실패
- 기존 CONTENT_AI가 사라지고 신규 결과 저장 실패

같은 상태가 남지 않도록 rollback을 보장한다.

---

# 18. Error Handling

기존 Exception 구조를 재사용한다.

최소 상황:

```text
TRIP_NOT_FOUND
SOURCE_NOT_FOUND
INVALID_YOUTUBE_URL
YOUTUBE_VIDEO_NOT_FOUND 또는 Provider Not Found
NO_ACTIVE_SOURCES
INVALID_INTEREST_CODE
UNAUTHORIZED
VALIDATION_ERROR
```

정확한 Error Code는 API 문서와 기존 프로젝트 스타일을 우선한다.

---

# 19. 테스트

현재 기준:

```text
139 passed
```

최소 다음 테스트를 추가한다.

## 인증 / 소유권
- 인증 없이 source 등록 → 401
- 인증 없이 analyze → 401
- 다른 사용자 Trip source 등록 금지
- 다른 사용자 Trip 분석 금지

## YouTube Source 생성
- watch URL 정상
- youtu.be URL 정상
- shorts URL 정상 (문서 범위 내)
- videoId 직접 입력 정상 (문서 범위 내)
- 잘못된 URL 거부
- Mock에 없는 video_id 처리
- metadata / tags 저장 확인
- 동일 source 중복 처리
- 다른 trip에는 같은 video_id 사용 가능

## Source 삭제
- DELETE → row 삭제가 아니라 is_active=false
- 다른 Trip source 조작 금지
- 없는 source 처리
- inactive source가 분석에 사용되지 않음

## Preference Analysis
- active source 기반 정상 분석
- source 0개면 오류
- CONTENT_AI source_type 확인
- interest master 검증
- 재분석 deterministic
- 기존 PROFILE/USER interest 보존
- duplicate interest constraint 위반 없음
- provider가 invalid interest code를 반환할 때 rollback

## Network
- 실제 YouTube HTTP 호출 없음
- 실제 EXAONE 호출 없음

---

# 20. DB 보호

기존 Migration:

```text
001_initial_schema
002_seed_interest_codes
```

수정 금지.

이번 Task에서 Migration 생성 금지.

DB Schema 변경 금지.

Soft delete / is_active 규칙을 기존 Column으로 해결한다.

---

# 21. 기존 기능 보호

Task 01~06 기능이 모두 유지되어야 한다.

전체 테스트:

```bash
pytest --basetemp=tmp/pytest-task07
```

기존 139개 + 신규 테스트 전부 통과해야 한다.

---

# 22. Git 규칙

현재 Git worktree이며 Task 06까지 push된 상태다.

금지:
- git reset --hard
- git clean -fd
- 과거 commit 수정
- 사용자 변경사항 임의 삭제

Task 07 완료 후 자동 commit/push하지 마라.
사용자가 결과를 확인한 뒤 직접 commit한다.

---

# 23. Secret 보호

절대 출력/저장 금지:

- `.env`
- MYSQL_PASSWORD
- JWT_SECRET_KEY
- YouTube API Key
- EXAONE API Key
- Kakao/Naver Secret
- Raw JWT / Refresh Token

실제 외부 API Key가 없어도 Task 07은 Mock으로 동작해야 한다.

---

# 24. 완료 보고 형식

```text
[Task 07 작업 결과]

1. 생성한 파일
- ...

2. 수정한 파일
- ...

3. 구현 API
- POST /trips/{trip_id}/sources/youtube
- DELETE /trips/{trip_id}/sources/{source_id}
- POST /trips/{trip_id}/analyze-preferences

4. YouTube Source 구현
- URL/videoId parsing:
- Metadata:
- 중복 처리:
- Soft delete:

5. Preference Analysis
- Provider:
- CONTENT_AI 처리:
- 기존 PROFILE/USER 보존:
- Interest 검증:

6. 실제 외부 API 호출 여부
- YouTube:
- EXAONE:

7. DB 변경 여부
- Migration:
- Schema:

8. 테스트
- 기존 테스트:
- 신규 테스트:
- 총 collected:
- passed:
- failed:

9. 발견된 버그
- ...

10. 문서와 구현 충돌
- ...

11. Task 07 완료 여부
- ...

12. 다음 Task
- Task 08 Place Search
```

---

# 25. 완료 조건

- [ ] POST YouTube Source 구현
- [ ] DELETE Source = is_active false
- [ ] analyze-preferences 구현
- [ ] Trip ownership 검증
- [ ] YouTube 입력 정규화
- [ ] Task 06 Content Provider 사용
- [ ] Task 06 Preference Provider 사용
- [ ] 실제 YouTube 호출 없음
- [ ] 실제 EXAONE 호출 없음
- [ ] trip_sources 저장
- [ ] CONTENT_AI trip_interests 반영
- [ ] PROFILE/USER interest 보존
- [ ] Interest Master 검증
- [ ] 분석 재실행 deterministic
- [ ] Transaction rollback
- [ ] 기존 001/002 migration 수정 없음
- [ ] 새 Migration 없음
- [ ] 전체 pytest 통과
- [ ] Task 08 이상 범위 구현 없음
- [ ] 자동 Git commit/push 없음

**지금은 Task 07만 진행해라.**
