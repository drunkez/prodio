from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import Track, get_db
from ..routers.auth import require_user
from ..schemas import DownloadRequest, TrackOut
from ..services.media import write_tags
from ..services.ytdlp import download_audio

router = APIRouter(prefix="/api/download", tags=["download"])


@router.post("/youtube", response_model=TrackOut)
def download_youtube(
    body: DownloadRequest, db: Session = Depends(get_db), _: str = Depends(require_user)
):
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http(s)://")
    try:
        meta = download_audio(url, title_hint=body.title)
    except Exception as exc:
        raise HTTPException(400, f"Download failed: {exc}") from exc

    from ..config import get_settings

    settings = get_settings()
    path = settings.media_dir / meta["filename"]
    write_tags(str(path), title=meta["title"], artist=None)

    track = Track(
        title=meta["title"],
        artist=None,
        filename=meta["filename"],
        duration=meta.get("duration"),
        source_url=meta.get("source_url"),
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track
