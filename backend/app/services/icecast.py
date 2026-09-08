import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import Track
from .annotate import display_title
from .liquidsoap import LiquidsoapClient

log = logging.getLogger("prodio.icecast")

_UNKNOWN = re.compile(r"^\s*(unknown|n/?a|-)?\s*$", re.I)


def fetch_listener_count() -> Optional[int]:
    settings = get_settings()
    url = (
        f"http://{settings.icecast_host}:{settings.icecast_port}"
        f"/admin/stats.xml"
    )
    try:
        from base64 import b64encode

        token = b64encode(
            f"admin:{settings.icecast_admin_password}".encode()
        ).decode()
        req = Request(url, headers={"Authorization": f"Basic {token}"})
        with urlopen(req, timeout=3) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        mount = settings.icecast_mount
        if not mount.startswith("/"):
            mount = "/" + mount
        for source in root.findall("source"):
            if source.get("mount") == mount:
                listeners = source.findtext("listeners")
                return int(listeners) if listeners is not None else 0
        listeners = root.findtext("listeners")
        return int(listeners) if listeners is not None else 0
    except (URLError, OSError, ET.ParseError, ValueError) as exc:
        log.debug("Icecast stats unavailable: %s", exc)
        return None


def _icecast_title() -> Optional[str]:
    settings = get_settings()
    url = (
        f"http://{settings.icecast_host}:{settings.icecast_port}"
        f"/status-json.xsl"
    )
    try:
        with urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        sources = data.get("icestats", {}).get("source")
        if not sources:
            return None
        if isinstance(sources, dict):
            sources = [sources]
        mount = settings.icecast_mount
        for src in sources:
            listenurl = src.get("listenurl", "")
            if mount in listenurl or src.get("server_name"):
                title = src.get("title") or src.get("yp_currently_playing")
                if title:
                    return title
        return sources[0].get("title")
    except Exception as exc:
        log.debug("Icecast now-playing unavailable: %s", exc)
        return None


def _title_from_library(db: Session, filename: str) -> Optional[str]:
    name = Path(filename).name
    track = db.query(Track).filter(Track.filename == name).first()
    if not track:
        # annotate URIs / paths sometimes include query-ish suffixes — try endswith
        track = (
            db.query(Track)
            .filter(Track.filename.like(f"%{name}"))
            .order_by(Track.id.desc())
            .first()
        )
    if track:
        return display_title(track)
    # last resort: humanize filename stem
    stem = Path(name).stem
    # strip trailing _deadbeef hash from our safe_name
    stem = re.sub(r"_[0-9a-f]{8}$", "", stem)
    return stem.replace("_", " ") if stem else None


def fetch_now_playing(db: Optional[Session] = None) -> Optional[str]:
    """Prefer Icecast title; if missing/Unknown, resolve via Liquidsoap + library."""
    title = _icecast_title()
    if title and not _UNKNOWN.match(title):
        return title

    filename = None
    try:
        filename = LiquidsoapClient().current_filename()
    except Exception as exc:
        log.debug("Liquidsoap filename lookup failed: %s", exc)

    if filename and db is not None:
        resolved = _title_from_library(db, filename)
        if resolved:
            return resolved

    if filename:
        return Path(filename).stem.replace("_", " ")

    return None if (not title or _UNKNOWN.match(title)) else title
