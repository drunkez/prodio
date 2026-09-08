import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import Track, get_db
from ..routers.auth import require_user
from ..schemas import TrackOut
from ..services.media import probe_duration, probe_tags

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


@router.get("", response_model=list[TrackOut])
def list_tracks(db: Session = Depends(get_db), _: str = Depends(require_user)):
    return db.query(Track).order_by(Track.created_at.desc()).all()


@router.post("/upload", response_model=TrackOut)
async def upload_track(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
):
    settings = get_settings()
    if not file.filename:
        raise HTTPException(400, "Missing filename")
    filename = _safe_name(file.filename)
    dest = settings.media_dir / filename
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")
    dest.write_bytes(content)

    title, artist = probe_tags(str(dest))
    duration = probe_duration(str(dest))
    track = Track(
        title=title or Path(file.filename).stem,
        artist=artist,
        filename=filename,
        duration=duration,
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


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
