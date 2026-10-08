from pydantic import BaseModel


class YouTubePauseEvent(BaseModel):
    event: str
    video_id: str
    position_sec: int
    page_url: str | None = None
