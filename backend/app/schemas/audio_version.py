from pydantic import BaseModel
from app.schemas.voice_sample import ReferenceAudioRead


class AudioVersion(ReferenceAudioRead):
    audio_url: str
    download_url: str
    available: bool
    preset: str | None = None


class AudioVersions(BaseModel):
    items: list[AudioVersion]
