from typing import List, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TrackOut(BaseModel):
    id: int
    title: str
    artist: Optional[str] = None
    filename: str
    duration: Optional[float] = None
    source_url: Optional[str] = None

    class Config:
        from_attributes = True


class PlaylistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    shuffle: bool = False


class PlaylistUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    shuffle: Optional[bool] = None
    track_ids: Optional[List[int]] = None


class PlaylistOut(BaseModel):
    id: int
    name: str
    shuffle: bool
    tracks: List[TrackOut] = []

    class Config:
        from_attributes = True


class ScheduleCreate(BaseModel):
    playlist_id: int
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str
    shuffle: bool = False
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    playlist_id: Optional[int] = None
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    shuffle: Optional[bool] = None
    enabled: Optional[bool] = None
    position: Optional[int] = None


class ScheduleOut(BaseModel):
    id: int
    playlist_id: int
    playlist_name: str = ""
    day_of_week: int
    start_time: str
    end_time: str
    shuffle: bool
    position: int
    enabled: bool

    class Config:
        from_attributes = True


class DownloadRequest(BaseModel):
    url: str
    title: Optional[str] = None


class StreamStatus(BaseModel):
    is_playing: bool
    active_playlist_id: Optional[int] = None
    active_playlist_name: Optional[str] = None
    listeners: Optional[int] = None
    stream_url: str
    station_name: str
    now_playing: Optional[str] = None
    next_playing: Optional[str] = None
    liquidsoap_ok: bool = False
