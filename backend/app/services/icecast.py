import logging
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.error import URLError
from urllib.request import urlopen

from ..config import get_settings

log = logging.getLogger("prodio.icecast")


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
        req = __import__("urllib.request").request.Request(
            url, headers={"Authorization": f"Basic {token}"}
        )
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
        # fallback total
        listeners = root.findtext("listeners")
        return int(listeners) if listeners is not None else 0
    except (URLError, OSError, ET.ParseError, ValueError) as exc:
        log.debug("Icecast stats unavailable: %s", exc)
        return None


def fetch_now_playing() -> Optional[str]:
    settings = get_settings()
    url = (
        f"http://{settings.icecast_host}:{settings.icecast_port}"
        f"/status-json.xsl"
    )
    try:
        with urlopen(url, timeout=3) as resp:
            import json

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
        log.debug("Now playing unavailable: %s", exc)
        return None
