import logging
import random
from pathlib import Path
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import Playlist, ScheduleEntry, StreamState, Track
from .annotate import annotate_uri, display_title
from .liquidsoap import LiquidsoapClient

log = logging.getLogger("prodio.playout")

LIBRARY_LABEL = "Library (random)"


def _m3u_entry(track: Track, media_dir: Path) -> str:
    display = display_title(track).replace("\n", " ")
    duration = int(track.duration or -1)
    uri = annotate_uri(track, media_dir)
    return f"#EXTINF:{duration},{display}\n{uri}"


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


def _reload_liquidsoap() -> None:
    try:
        LiquidsoapClient().reload()
    except OSError:
        log.warning("Could not reload liquidsoap after on-air change")


def activate_playlist(db: Session, playlist: Playlist, shuffle: Optional[bool] = None) -> None:
    use_shuffle = playlist.shuffle if shuffle is None else shuffle
    tracks = list(playlist.tracks)
    write_onair_m3u(tracks, shuffle=use_shuffle)
    state = db.query(StreamState).first()
    if state:
        state.active_playlist_id = playlist.id
        db.commit()
    _reload_liquidsoap()


def activate_library_random(db: Session) -> int:
    """Put the whole library on air in random order. Clears selected playlist."""
    tracks = db.query(Track).order_by(Track.id).all()
    if not tracks:
        raise ValueError("Library is empty")
    write_onair_m3u(tracks, shuffle=True)
    state = db.query(StreamState).first()
    if state:
        state.active_playlist_id = None
        db.commit()
    _reload_liquidsoap()
    return len(tracks)


def resolve_onair_source(
    db: Session, state: Optional[StreamState] = None
) -> Tuple[str, Optional[Playlist], bool]:
    """
    Pick what should be on air.
    Returns (kind, playlist|None, shuffle) where kind is:
      - "playlist" — scheduled or selected playlist
      - "library"  — random from full library
      - "empty"    — nothing to play
    """
    state = state or db.query(StreamState).first()
    entry = current_schedule_entry(db)
    if entry:
        playlist = db.query(Playlist).get(entry.playlist_id)
        if playlist and playlist.tracks:
            return ("playlist", playlist, entry.shuffle)

    if state and state.active_playlist_id:
        playlist = db.query(Playlist).get(state.active_playlist_id)
        if playlist and playlist.tracks:
            return ("playlist", playlist, playlist.shuffle)

    if db.query(Track).first():
        return ("library", None, True)
    return ("empty", None, False)


def apply_onair_source(db: Session, state: Optional[StreamState] = None) -> str:
    """Resolve and activate the correct on-air source. Returns a short label."""
    state = state or db.query(StreamState).first()
    kind, playlist, shuffle = resolve_onair_source(db, state)
    if kind == "playlist" and playlist:
        activate_playlist(db, playlist, shuffle=shuffle)
        return playlist.name
    if kind == "library":
        activate_library_random(db)
        return LIBRARY_LABEL
    raise ValueError("Library is empty — upload tracks first")


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
    """Keep on-air source in sync with radiolist while streaming."""
    state = db.query(StreamState).first()
    if not state or not state.is_playing:
        return None

    entry = current_schedule_entry(db)
    if entry:
        if state.active_playlist_id == entry.playlist_id:
            return f"already on playlist {entry.playlist_id}"
        playlist = db.query(Playlist).get(entry.playlist_id)
        if not playlist or not playlist.tracks:
            return None
        activate_playlist(db, playlist, shuffle=entry.shuffle)
        return f"switched to {playlist.name}"

    # No active radiolist slot: keep selected playlist, else library random
    if state.active_playlist_id:
        playlist = db.query(Playlist).get(state.active_playlist_id)
        if playlist and playlist.tracks:
            return f"holding playlist {playlist.name}"
        # selected playlist empty/missing → fall through to library

    if not db.query(Track).first():
        return None

    # Already in library mode (no playlist selected) — leave current shuffle alone
    if state.active_playlist_id is None:
        onair = get_settings().onair_playlist
        if onair.exists() and onair.stat().st_size > 10:
            return "holding library random"

    activate_library_random(db)
    return f"switched to {LIBRARY_LABEL}"
