from functools import lru_cache
from pathlib import Path
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path("/data") if Path("/data").exists() else BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    admin_user: str = "admin"
    admin_password: str = "changeme"
    secret_key: str = "change-this-to-a-long-random-string"

    icecast_host: str = "icecast"
    icecast_port: int = 8000
    icecast_source_password: str = "hackme"
    icecast_admin_password: str = "hackme"
    icecast_mount: str = "/live"

    prodio_public_url: str = "http://localhost:8080"
    stream_public_url: str = "http://localhost:8000/live"

    station_name: str = "ProDio"
    station_description: str = "All-in-one web radio"
    station_genre: str = "Various"

    liquidsoap_host: str = "127.0.0.1"
    liquidsoap_port: int = 1234

    media_dir: Path = DATA_DIR / "media"
    playlists_dir: Path = DATA_DIR / "playlists"
    db_path: Path = DATA_DIR / "db" / "prodio.db"
    onair_playlist: Path = DATA_DIR / "playlists" / "onair.m3u"

    session_cookie: str = "prodio_session"
    session_max_age: int = 60 * 60 * 24 * 7


@lru_cache
def get_settings() -> Settings:
    s = Settings(
        admin_user=os.environ.get("PRODIO_ADMIN_USER", "admin"),
        admin_password=os.environ.get("PRODIO_ADMIN_PASSWORD", "changeme"),
        secret_key=os.environ.get(
            "PRODIO_SECRET_KEY", "change-this-to-a-long-random-string"
        ),
        icecast_host=os.environ.get("ICECAST_HOST", "127.0.0.1"),
        icecast_port=int(os.environ.get("ICECAST_PORT", "8000")),
        icecast_source_password=os.environ.get("ICECAST_SOURCE_PASSWORD", "hackme"),
        icecast_admin_password=os.environ.get("ICECAST_ADMIN_PASSWORD", "hackme"),
        icecast_mount=os.environ.get("ICECAST_MOUNT", "/live"),
        prodio_public_url=os.environ.get("PRODIO_PUBLIC_URL", "http://localhost:8080"),
        stream_public_url=os.environ.get(
            "STREAM_PUBLIC_URL", "http://localhost:8000/live"
        ),
        station_name=os.environ.get("STATION_NAME", "ProDio"),
        station_description=os.environ.get(
            "STATION_DESCRIPTION", "All-in-one web radio"
        ),
        station_genre=os.environ.get("STATION_GENRE", "Various"),
    )
    s.media_dir.mkdir(parents=True, exist_ok=True)
    s.playlists_dir.mkdir(parents=True, exist_ok=True)
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    if not s.onair_playlist.exists():
        s.onair_playlist.write_text("#EXTM3U\n", encoding="utf-8")
    return s
