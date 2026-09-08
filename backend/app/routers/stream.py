from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import Playlist, StreamState, get_db
from ..routers.auth import require_user
from ..schemas import StreamStatus
from ..services.icecast import fetch_listener_count, fetch_now_playing
from ..services.liquidsoap import LiquidsoapClient
from ..services.playout import activate_playlist, current_schedule_entry

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
    return StreamStatus(
        is_playing=bool(state and state.is_playing),
        active_playlist_id=active_id,
        active_playlist_name=active_name,
        listeners=fetch_listener_count(),
        stream_url=settings.stream_public_url,
        station_name=settings.station_name,
        now_playing=fetch_now_playing(),
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

    entry = current_schedule_entry(db)
    playlist = None
    shuffle = False
    if entry:
        playlist = db.query(Playlist).get(entry.playlist_id)
        shuffle = entry.shuffle
    elif state.active_playlist_id:
        playlist = db.query(Playlist).get(state.active_playlist_id)
        shuffle = playlist.shuffle if playlist else False
    else:
        playlist = db.query(Playlist).order_by(Playlist.id).first()
        shuffle = playlist.shuffle if playlist else False

    if playlist and playlist.tracks:
        activate_playlist(db, playlist, shuffle=shuffle)

    try:
        LiquidsoapClient().start()
    except OSError as exc:
        raise HTTPException(503, f"Liquidsoap unavailable: {exc}") from exc

    state.is_playing = True
    db.commit()
    return _status(db)


@router.post("/stop", response_model=StreamStatus)
def stop(db: Session = Depends(get_db), _: str = Depends(require_user)):
    state = db.query(StreamState).first()
    try:
        LiquidsoapClient().stop()
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
