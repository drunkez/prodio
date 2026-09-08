import random
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import Playlist, StreamState, Track, get_db
from ..routers.auth import require_user
from ..schemas import StreamStatus
from ..services.icecast import fetch_listener_count, fetch_next_playing, fetch_now_playing
from ..services.liquidsoap import LiquidsoapClient
from ..services.playout import LIBRARY_LABEL, apply_onair_source

router = APIRouter(prefix="/api/stream", tags=["stream"])


def _status(db: Session) -> StreamStatus:
    settings = get_settings()
    state = db.query(StreamState).first()
    ls = LiquidsoapClient()
    ls_ok = ls.ping()
    active_name = None
    active_id = state.active_playlist_id if state else None
    if active_id:
        p = db.query(Playlist).get(active_id)
        active_name = p.name if p else None
    elif state and state.is_playing:
        active_name = LIBRARY_LABEL
    next_title = None
    if state and state.is_playing and ls_ok:
        next_title = fetch_next_playing(db)
    return StreamStatus(
        is_playing=bool(state and state.is_playing),
        active_playlist_id=active_id,
        active_playlist_name=active_name,
        listeners=fetch_listener_count(),
        stream_url=settings.stream_public_url,
        station_name=settings.station_name,
        now_playing=fetch_now_playing(db) if (state and state.is_playing) else None,
        next_playing=next_title,
        liquidsoap_ok=ls_ok,
    )


@router.get("/status", response_model=StreamStatus)
def status(db: Session = Depends(get_db), _: str = Depends(require_user)):
    return _status(db)


@router.post("/start", response_model=StreamStatus)
def start(db: Session = Depends(get_db), _: str = Depends(require_user)):
    state = db.query(StreamState).first()
    if not state:
        raise HTTPException(500, "Stream state missing")

    try:
        apply_onair_source(db, state)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    try:
        LiquidsoapClient().start()
    except OSError as exc:
        raise HTTPException(503, f"Liquidsoap unavailable: {exc}") from exc

    state = db.query(StreamState).first()
    if not state:
        raise HTTPException(500, "Stream state missing")
    state.is_playing = True
    db.commit()
    return _status(db)


@router.post("/stop", response_model=StreamStatus)
def stop(db: Session = Depends(get_db), _: str = Depends(require_user)):
    state = db.query(StreamState).first()
    try:
        client = LiquidsoapClient()
        client.clear_cue()
        client.stop()
    except OSError as exc:
        raise HTTPException(503, f"Liquidsoap unavailable: {exc}") from exc
    if state:
        state.is_playing = False
        db.commit()
    return _status(db)


@router.post("/skip")
def skip(_: str = Depends(require_user)):
    try:
        msg = LiquidsoapClient().skip()
        return {"ok": True, "message": msg}
    except OSError as exc:
        raise HTTPException(503, f"Liquidsoap unavailable: {exc}") from exc


@router.post("/reload")
def reload(_: str = Depends(require_user)):
    try:
        msg = LiquidsoapClient().reload()
        return {"ok": True, "message": msg}
    except OSError as exc:
        raise HTTPException(503, f"Liquidsoap unavailable: {exc}") from exc


@router.post("/reshuffle-next", response_model=StreamStatus)
def reshuffle_next(db: Session = Depends(get_db), _: str = Depends(require_user)):
    """Pick a new random up-next track from the active playlist or whole library."""
    state = db.query(StreamState).first()
    if not state or not state.is_playing:
        raise HTTPException(400, "Stream is not playing")

    settings = get_settings()
    client = LiquidsoapClient()

    # Candidate pool: selected playlist, else entire library
    candidates: list[Track] = []
    if state.active_playlist_id:
        playlist = db.query(Playlist).get(state.active_playlist_id)
        if playlist and playlist.tracks:
            candidates = list(playlist.tracks)
    if not candidates:
        candidates = db.query(Track).order_by(Track.id).all()
    if not candidates:
        raise HTTPException(400, "No tracks available to cue")

    # Avoid cueing whatever is currently on air
    current = None
    try:
        current = client.current_filename()
    except OSError:
        current = None
    current_name = Path(current).name if current else None

    pool = [t for t in candidates if t.filename != current_name]
    if not pool:
        pool = candidates

    pick = random.choice(pool)
    path = settings.media_dir / pick.filename
    if not path.exists():
        raise HTTPException(404, f"Media missing: {pick.filename}")

    try:
        client.cue(str(path))
    except OSError as exc:
        raise HTTPException(503, f"Liquidsoap unavailable: {exc}") from exc

    return _status(db)
