from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppError
from app.services.youtube_source_service import extract_video_id


@dataclass
class Source:
    source_id: int
    trip_id: int
    external_id: str
    source_url: str
    title: str | None
    description: str | None
    tags: list[str]
    channel_id: str | None
    channel_title: str | None
    is_active: bool = True
    metadata_collected_at: object = None


@dataclass
class Interest:
    interest_code: str
    source_type: str
    is_confirmed: bool


class Session:
    def __init__(self):
        self.trips={1:SimpleNamespace(trip_id=1,user_id=1,status="DRAFT"),2:SimpleNamespace(trip_id=2,user_id=2,status="DRAFT"),3:SimpleNamespace(trip_id=3,user_id=1,status="ARCHIVED")}
        self.sources={}; self.interests={1:[Interest("FOOD","PROFILE",False),Interest("CAFE","USER",True),Interest("HISTORY","CONTENT_AI",False)]}
        self.codes={"FOOD","CAFE","NATURE","CULTURE","HISTORY","SHOPPING","EXHIBITION","ACTIVITY"}; self.commits=self.rollbacks=0
    def commit(self): self.commits+=1
    def rollback(self): self.rollbacks+=1


class Trips:
    def __init__(self,s): self.s=s
    def get(self,trip_id): return self.s.trips.get(trip_id)
class Sources:
    def __init__(self,s): self.s=s
    def get(self,source_id): return self.s.sources.get(source_id)
    def get_by_external(self,trip_id,external_id): return next((item for item in self.s.sources.values() if item.trip_id==trip_id and item.external_id==external_id),None)
    def list_active(self,trip_id): return [item for item in self.s.sources.values() if item.trip_id==trip_id and item.is_active]
    def create(self,trip_id,**fields):
        source=Source(len(self.s.sources)+1,trip_id,**fields); self.s.sources[source.source_id]=source; return source
    def update(self,source,**fields):
        for key,value in fields.items(): setattr(source,key,value)
        return source
class Interests:
    def __init__(self,s): self.s=s
    def list(self,trip_id): return list(self.s.interests.get(trip_id,[]))
    def create(self,trip_id,interest_code,source_type,is_confirmed):
        value=Interest(interest_code,source_type,is_confirmed); self.s.interests.setdefault(trip_id,[]).append(value); return value
    def remove_content_ai(self,trip_id): self.s.interests[trip_id]=[item for item in self.list(trip_id) if item.source_type!="CONTENT_AI"]
class Codes:
    def __init__(self,s): self.s=s
    def active_codes(self,codes): return set(codes)&self.s.codes
class Content:
    def get_video(self,video_id): return SimpleNamespace(video_id=video_id,title="Mock culture cafe",description="food culture",tags=["CULTURE","CAFE"],channel_id="channel",channel_title="Mock")
class Analysis:
    def __init__(self,codes): self.codes=codes
    def analyze_preferences(self,text): return SimpleNamespace(interest_codes=self.codes,summary="mock")


@pytest.fixture
def services(monkeypatch):
    import app.services.youtube_source_service as source_module
    import app.services.preference_analysis_service as analysis_module
    for module in (source_module,analysis_module):
        monkeypatch.setattr(module,"TripRepository",Trips); monkeypatch.setattr(module,"TripSourceRepository",Sources)
    monkeypatch.setattr(analysis_module,"TripInterestRepository",Interests); monkeypatch.setattr(analysis_module,"InterestCodeRepository",Codes)
    session=Session()
    return source_module.YouTubeSourceService(session,Content()),analysis_module.PreferenceAnalysisService(session,Analysis(["CULTURE","CAFE"])),session


@pytest.mark.parametrize("value,expected",[("mock-seoul-trip","mock-seoul-trip"),("https://www.youtube.com/watch?v=mock-seoul-trip","mock-seoul-trip"),("https://youtu.be/mock-seoul-trip","mock-seoul-trip"),("https://www.youtube.com/shorts/mock-seoul-trip","mock-seoul-trip")])
def test_extract_video_id_supported_inputs(value,expected): assert extract_video_id(value)==expected


def test_extract_video_id_rejects_unrelated_urls():
    with pytest.raises(AppError) as error: extract_video_id("https://example.com/watch?v=mock-seoul-trip")
    assert error.value.code=="INVALID_YOUTUBE_URL"


def test_youtube_source_adds_metadata_and_reactivates_same_row(services):
    source_service,analysis_service,session=services
    created=source_service.add(1,1,"https://youtu.be/mock-seoul-trip")
    assert created.video_id=="mock-seoul-trip" and created.tags==["CULTURE","CAFE"]
    session.sources[created.source_id].is_active=False
    renewed=source_service.add(1,1,"mock-seoul-trip")
    assert renewed.source_id==created.source_id and session.sources[created.source_id].is_active is True and len(session.sources)==1


def test_source_ownership_archive_and_deactivation_rules(services):
    source_service,analysis_service,session=services
    source=source_service.add(1,1,"mock-seoul-trip")
    source_service.deactivate(1,1,source.source_id)
    assert session.sources[source.source_id].is_active is False
    with pytest.raises(AppError) as forbidden: source_service.add(2,1,"mock-seoul-trip")
    with pytest.raises(AppError) as archived: source_service.add(1,3,"mock-seoul-trip")
    assert forbidden.value.code=="FORBIDDEN" and archived.value.code=="TRIP_ARCHIVED"


def test_analysis_requires_active_source_and_preserves_profile_user_interests(services):
    source_service,analysis_service,session=services
    with pytest.raises(AppError) as none: analysis_service.analyze(1,1)
    assert none.value.code=="NO_ACTIVE_SOURCES"
    source_service.add(1,1,"mock-seoul-trip")
    result=analysis_service.analyze(1,1)
    values={(item.interest_code,item.source_type,item.is_confirmed) for item in session.interests[1]}
    assert result.inferred_preferences==["CULTURE","CAFE"]
    assert ("FOOD","PROFILE",False) in values and ("CAFE","USER",True) in values
    assert ("CULTURE","CONTENT_AI",False) in values and not any(code=="HISTORY" and kind=="CONTENT_AI" for code,kind,_ in values)


def test_analysis_invalid_provider_code_does_not_replace_existing_ai(services):
    source_service,analysis_service,session=services
    source_service.add(1,1,"mock-seoul-trip")
    analysis_service.analysis_provider=Analysis(["UNKNOWN"])
    with pytest.raises(AppError) as error: analysis_service.analyze(1,1)
    assert error.value.code=="INVALID_INTEREST_CODE"
    assert any(item.interest_code=="HISTORY" and item.source_type=="CONTENT_AI" for item in session.interests[1])


def test_analysis_ownership_and_inactive_source_exclusion(services):
    source_service,analysis_service,session=services
    source=source_service.add(1,1,"mock-seoul-trip")
    with pytest.raises(AppError) as forbidden: analysis_service.analyze(2,1)
    source_service.deactivate(1,1,source.source_id)
    with pytest.raises(AppError) as none: analysis_service.analyze(1,1)
    assert forbidden.value.code=="FORBIDDEN" and none.value.code=="NO_ACTIVE_SOURCES"


def test_task_seven_endpoints_require_authentication(client):
    assert client.post("/api/v1/trips/1/sources/youtube",json={"youtube_url":"mock-seoul-trip"}).status_code==401
    assert client.post("/api/v1/trips/1/analyze-preferences").status_code==401


def test_provider_settings_are_not_exposed_as_fastapi_request_input(client):
    schema = client.get("/openapi.json").json()
    source_operation = schema["paths"]["/api/v1/trips/{trip_id}/sources/youtube"]["post"]
    request_schema = source_operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema == {"$ref": "#/components/schemas/YouTubeSourceRequest"}
    assert client.post("/api/v1/trips/1/sources/youtube", json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}).status_code == 401
    for path, method in (("/api/v1/places/search", "get"), ("/api/v1/trips/{trip_id}/analyze-preferences", "post"), ("/api/v1/trips/{trip_id}/plans/generate", "post"), ("/api/v1/plans/{plan_id}/regenerate", "post")):
        operation = schema["paths"][path][method]
        assert all(parameter["name"] != "settings" for parameter in operation.get("parameters", []))
        body = operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
        assert "settings" not in body.get("properties", {})
