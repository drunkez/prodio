from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from ..database import Playlist, Track, get_db, playlist_tracks
from ..routers.auth import require_user
from ..schemas import PlaylistCreate, PlaylistOut, PlaylistUpdate
from ..services.playout import activate_playlist

router = APIRouter(prefix="/api/playlists", tags=["playlists"])


def _playlist_out(p: Playlist) -> PlaylistOut:
    # reload tracks ordered by position
    return PlaylistOut.model_validate(p)


@router.get("", response_model=list[PlaylistOut])
def list_playlists(db: Session = Depends(get_db), _: str = Depends(require_user)):
    return db.query(Playlist).order_by(Playlist.name).all()


@router.post("", response_model=PlaylistOut)
def create_playlist(
    body: PlaylistCreate, db: Session = Depends(get_db), _: str = Depends(require_user)
):
    if db.query(Playlist).filter(Playlist.name == body.name).first():
        raise HTTPException(400, "Playlist name already exists")
    p = Playlist(name=body.name, shuffle=body.shuffle)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/{playlist_id}", response_model=PlaylistOut)
def get_playlist(
    playlist_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)
):
    p = db.query(Playlist).get(playlist_id)
    if not p:
        raise HTTPException(404, "Playlist not found")
    return p


@router.put("/{playlist_id}", response_model=PlaylistOut)
def update_playlist(
    playlist_id: int,
    body: PlaylistUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
):
    p = db.query(Playlist).get(playlist_id)
    if not p:
        raise HTTPException(404, "Playlist not found")
    if body.name is not None:
        clash = (
            db.query(Playlist)
            .filter(Playlist.name == body.name, Playlist.id != playlist_id)
            .first()
        )
        if clash:
            raise HTTPException(400, "Playlist name already exists")
        p.name = body.name
    if body.shuffle is not None:
        p.shuffle = body.shuffle
    if body.track_ids is not None:
        db.execute(delete(playlist_tracks).where(playlist_tracks.c.playlist_id == p.id))
        for pos, tid in enumerate(body.track_ids):
            track = db.query(Track).get(tid)
            if not track:
                raise HTTPException(400, f"Track {tid} not found")
            db.execute(
                insert(playlist_tracks).values(
                    playlist_id=p.id, track_id=tid, position=pos
                )
            )
    db.commit()
    db.refresh(p)
    # expire relationship cache
    db.expire(p, ["tracks"])
    return db.query(Playlist).get(playlist_id)


@router.post("/{playlist_id}/tracks/{track_id}", response_model=PlaylistOut)
def add_track(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
):
    p = db.query(Playlist).get(playlist_id)
    t = db.query(Track).get(track_id)
    if not p or not t:
        raise HTTPException(404, "Playlist or track not found")
    existing = db.execute(
        select(playlist_tracks).where(
            playlist_tracks.c.playlist_id == playlist_id,
            playlist_tracks.c.track_id == track_id,
        )
    ).first()
    if not existing:
        max_pos = (
            db.execute(
                select(playlist_tracks.c.position)
                .where(playlist_tracks.c.playlist_id == playlist_id)
                .order_by(playlist_tracks.c.position.desc())
            ).first()
        )
        pos = (max_pos[0] + 1) if max_pos else 0
        db.execute(
            insert(playlist_tracks).values(
                playlist_id=playlist_id, track_id=track_id, position=pos
            )
        )
        db.commit()
    db.refresh(p)
    db.expire(p, ["tracks"])
    return db.query(Playlist).get(playlist_id)


@router.delete("/{playlist_id}/tracks/{track_id}", response_model=PlaylistOut)
def remove_track(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
):
    p = db.query(Playlist).get(playlist_id)
    if not p:
        raise HTTPException(404, "Playlist not found")
    db.execute(
        delete(playlist_tracks).where(
            playlist_tracks.c.playlist_id == playlist_id,
            playlist_tracks.c.track_id == track_id,
        )
    )
    db.commit()
    db.expire(p, ["tracks"])
    return db.query(Playlist).get(playlist_id)


@router.delete("/{playlist_id}")
def delete_playlist(
    playlist_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)
):
    p = db.query(Playlist).get(playlist_id)
    if not p:
        raise HTTPException(404, "Playlist not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/{playlist_id}/go-live", response_model=PlaylistOut)
def go_live(
    playlist_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)
):
    p = db.query(Playlist).get(playlist_id)
    if not p:
        raise HTTPException(404, "Playlist not found")
    activate_playlist(db, p)
    return p
