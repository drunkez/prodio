from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


playlist_tracks = Table(
    "playlist_tracks",
    Base.metadata,
    Column("playlist_id", ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True),
    Column("track_id", ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, nullable=False, default=0),
)


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    artist: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    filename: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    duration: Mapped[Optional[float]] = mapped_column(nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    playlists: Mapped[list["Playlist"]] = relationship(
        secondary=playlist_tracks, back_populates="tracks"
    )


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    shuffle: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    tracks: Mapped[list[Track]] = relationship(
        secondary=playlist_tracks, back_populates="playlists", order_by=playlist_tracks.c.position
    )
    schedule_entries: Mapped[list["ScheduleEntry"]] = relationship(
        back_populates="playlist", cascade="all, delete-orphan"
    )


class ScheduleEntry(Base):
    """Radiolist: scheduled playlist slots."""

    __tablename__ = "schedule_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"))
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon .. 6=Sun
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    shuffle: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    playlist: Mapped[Playlist] = relationship(back_populates="schedule_entries")


class StreamState(Base):
    __tablename__ = "stream_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    is_playing: Mapped[bool] = mapped_column(Boolean, default=False)
    active_playlist_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


_engine = None
SessionLocal = None


def init_db():
    global _engine, SessionLocal
    settings = get_settings()
    _engine = create_engine(
        f"sqlite:///{settings.db_path}", connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = SessionLocal()
    try:
        if not db.query(StreamState).first():
            db.add(StreamState(is_playing=False))
            db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
