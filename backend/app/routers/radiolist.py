from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import Playlist, ScheduleEntry, get_db
from ..routers.auth import require_user
from ..schemas import ScheduleCreate, ScheduleOut, ScheduleUpdate

router = APIRouter(prefix="/api/radiolist", tags=["radiolist"])

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _out(e: ScheduleEntry) -> ScheduleOut:
    return ScheduleOut(
        id=e.id,
        playlist_id=e.playlist_id,
        playlist_name=e.playlist.name if e.playlist else "",
        day_of_week=e.day_of_week,
        start_time=e.start_time,
        end_time=e.end_time,
        shuffle=e.shuffle,
        position=e.position,
        enabled=e.enabled,
    )


def _valid_hhmm(value: str) -> bool:
    if len(value) != 5 or value[2] != ":":
        return False
    try:
        h, m = int(value[:2]), int(value[3:])
        return 0 <= h <= 23 and 0 <= m <= 59
    except ValueError:
        return False


@router.get("", response_model=list[ScheduleOut])
def list_schedule(db: Session = Depends(get_db), _: str = Depends(require_user)):
    entries = (
        db.query(ScheduleEntry)
        .order_by(ScheduleEntry.day_of_week, ScheduleEntry.position, ScheduleEntry.start_time)
        .all()
    )
    return [_out(e) for e in entries]


@router.get("/days")
def list_days(_: str = Depends(require_user)):
    return [{"id": i, "name": n} for i, n in enumerate(DAYS)]


@router.post("", response_model=ScheduleOut)
def create_entry(
    body: ScheduleCreate, db: Session = Depends(get_db), _: str = Depends(require_user)
):
    if not db.query(Playlist).get(body.playlist_id):
        raise HTTPException(400, "Playlist not found")
    if not _valid_hhmm(body.start_time) or not _valid_hhmm(body.end_time):
        raise HTTPException(400, "Times must be HH:MM")
    max_pos = (
        db.query(ScheduleEntry)
        .filter(ScheduleEntry.day_of_week == body.day_of_week)
        .count()
    )
    e = ScheduleEntry(
        playlist_id=body.playlist_id,
        day_of_week=body.day_of_week,
        start_time=body.start_time,
        end_time=body.end_time,
        shuffle=body.shuffle,
        enabled=body.enabled,
        position=max_pos,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _out(e)


@router.put("/{entry_id}", response_model=ScheduleOut)
def update_entry(
    entry_id: int,
    body: ScheduleUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
):
    e = db.query(ScheduleEntry).get(entry_id)
    if not e:
        raise HTTPException(404, "Entry not found")
    data = body.model_dump(exclude_unset=True)
    if "playlist_id" in data and not db.query(Playlist).get(data["playlist_id"]):
        raise HTTPException(400, "Playlist not found")
    for key in ("start_time", "end_time"):
        if key in data and not _valid_hhmm(data[key]):
            raise HTTPException(400, "Times must be HH:MM")
    for k, v in data.items():
        setattr(e, k, v)
    db.commit()
    db.refresh(e)
    return _out(e)


@router.delete("/{entry_id}")
def delete_entry(
    entry_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)
):
    e = db.query(ScheduleEntry).get(entry_id)
    if not e:
        raise HTTPException(404, "Entry not found")
    db.delete(e)
    db.commit()
    return {"ok": True}


@router.post("/reorder")
def reorder(
    ordered_ids: list[int],
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
):
    for pos, eid in enumerate(ordered_ids):
        e = db.query(ScheduleEntry).get(eid)
        if e:
            e.position = pos
    db.commit()
    return {"ok": True}
