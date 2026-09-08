import logging
import random
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import Playlist, ScheduleEntry, StreamState, Track
from .liquidsoap import LiquidsoapClient

log = logging.getLogger("prodio.playout")


def _m3u_entry(track: Track, media_dir: Path) -> str:
    path = media_dir / track.filename
    title = track.title.replace("\n", " ")
    artist = (track.artist or "").replace("\n", " ")
    display = f"{artist} - {title}" if artist else title
    duration = int(track.duration or -1)
    return f"#EXTINF:{duration},{display}\n{path}"


def write_onair_m3u(tracks: Iterable[Track], shuffle: bool = False) -> Path:
    settings = get_settings()
    track_list = list(tracks)
    if shuffle:
        random.shuffle(track_list)
    lines = ["#EXTM3U"]
    for t in track_list:
        path = settings.media_dir / t.filename
        if path.exists():
            lines.append(_m3u_entry(t, settings.media_dir))
        else:
            log.warning("Missing media file: %s", path)
    settings.onair_playlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return settings.onair_playlist


def activate_playlist(db: Session, playlist: Playlist, shuffle: Optional[bool] = None) -> None:
    use_shuffle = playlist.shuffle if shuffle is None else shuffle
    # preserve playlist order from association table
    tracks = list(playlist.tracks)
    write_onair_m3u(tracks, shuffle=use_shuffle)
    state = db.query(StreamState).first()
    if state:
        state.active_playlist_id = playlist.id
        db.commit()
    try:
        LiquidsoapClient().reload()
    except OSError:
        log.warning("Could not reload liquidsoap after playlist activate")


def current_schedule_entry(db: Session, now=None) -> Optional[ScheduleEntry]:
    from datetime import datetime

    now = now or datetime.now()
    dow = now.weekday()  # Mon=0
    hhmm = now.strftime("%H:%M")
    entries = (
        db.query(ScheduleEntry)
        .filter(ScheduleEntry.enabled.is_(True), ScheduleEntry.day_of_week == dow)
        .order_by(ScheduleEntry.position, ScheduleEntry.start_time)
        .all()
    )
    for e in entries:
        if e.start_time <= hhmm < e.end_time:
            return e
        # overnight wrap e.g. 22:00-02:00
        if e.start_time > e.end_time and (hhmm >= e.start_time or hhmm < e.end_time):
            return e
    return None


def sync_schedule(db: Session) -> Optional[str]:
    """Apply radiolist schedule to on-air playlist if streaming."""
    state = db.query(StreamState).first()
    if not state or not state.is_playing:
        return None
    entry = current_schedule_entry(db)
    if not entry:
        return None
    if state.active_playlist_id == entry.playlist_id:
        return f"already on playlist {entry.playlist_id}"
    playlist = db.query(Playlist).get(entry.playlist_id)
    if not playlist:
        return None
    activate_playlist(db, playlist, shuffle=entry.shuffle)
    return f"switched to {playlist.name}"
