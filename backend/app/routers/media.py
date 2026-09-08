import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import Track, get_db
from ..routers.auth import require_user
from ..schemas import TrackOut
from ..services.media import probe_duration, probe_tags, write_tags

router = APIRouter(prefix="/api/media", tags=["media"])

ALLOWED_EXT = {".mp3", ".ogg", ".oga", ".flac", ".wav", ".m4a", ".aac"}
SAFE = re.compile(r"[^A-Za-z0-9._\- ]+")


def _safe_name(original: str) -> str:
    p = Path(original)
    stem = SAFE.sub("", p.stem).strip().replace(" ", "_")[:80] or "track"
    ext = p.suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported type: {ext}")
    return f"{stem}_{uuid4().hex[:8]}{ext}"


async def _store_upload(file: UploadFile, db: Session) -> Track:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(400, "Missing filename")
    filename = _safe_name(file.filename)
    dest = settings.media_dir / filename
    content = await file.read()
    if not content:
        raise HTTPException(400, f"Empty file: {file.filename}")
    dest.write_bytes(content)

    title, artist = probe_tags(str(dest))
    duration = probe_duration(str(dest))
    resolved_title = title or Path(file.filename).stem
    if not title or not artist:
        write_tags(str(dest), title=resolved_title, artist=artist)
    track = Track(
        title=resolved_title,
        artist=artist,
        filename=filename,
        duration=duration,
    )
    db.add(track)
    db.flush()
    return track


@router.get("", response_model=list[TrackOut])
def list_tracks(db: Session = Depends(get_db), _: str = Depends(require_user)):
    return db.query(Track).order_by(Track.created_at.desc()).all()


@router.post("/upload", response_model=list[TrackOut])
async def upload_tracks(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
):
    if not files:
        raise HTTPException(400, "No files uploaded")
    tracks: list[Track] = []
    errors: list[str] = []
    for file in files:
        try:
            tracks.append(await _store_upload(file, db))
        except HTTPException as exc:
            errors.append(f"{file.filename or '?'}: {exc.detail}")
    if not tracks:
        raise HTTPException(400, "; ".join(errors) or "Upload failed")
    db.commit()
    for t in tracks:
        db.refresh(t)
    return tracks


@router.post("/{track_id}/play")
def play_track(
    track_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)
):
    """Crossfade into this track now (starts stream if needed)."""
    settings = get_settings()
    track = db.query(Track).get(track_id)
    if not track:
        raise HTTPException(404, "Track not found")
    path = settings.media_dir / track.filename
    if not path.exists():
        raise HTTPException(404, "Media file missing on disk")

    from ..database import StreamState
    from ..services.liquidsoap import LiquidsoapClient
    from ..services.media import write_tags
    from ..services.playout import apply_onair_source

    state = db.query(StreamState).first()
    client = LiquidsoapClient()

    # Ensure automation has something underneath the inject queue
    if state and not state.is_playing:
        try:
            apply_onair_source(db, state)
        except ValueError:
            # Library may only contain this one file — still allow direct play
            pass
        try:
            client.start()
        except OSError as exc:
            raise HTTPException(503, f"Liquidsoap unavailable: {exc}") from exc
        state = db.query(StreamState).first()
        if state:
            state.is_playing = True
            db.commit()

    # Embed library metadata so Icecast/Liquidsoap show the real title
    write_tags(str(path), title=track.title, artist=track.artist)

    try:
        msg = client.play(str(path))
    except OSError as exc:
        raise HTTPException(503, f"Liquidsoap unavailable: {exc}") from exc

    return {
        "ok": True,
        "message": msg,
        "track_id": track.id,
        "title": track.title,
    }


@router.delete("/{track_id}")
def delete_track(
    track_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)
):
    settings = get_settings()
    track = db.query(Track).get(track_id)
    if not track:
        raise HTTPException(404, "Track not found")
    path = settings.media_dir / track.filename
    db.delete(track)
    db.commit()
    if path.exists():
        path.unlink()
    return {"ok": True}
