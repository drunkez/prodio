import logging
import re
import subprocess
from pathlib import Path
from typing import Optional
from uuid import uuid4

from ..config import get_settings

log = logging.getLogger("prodio.ytdlp")

SAFE_NAME = re.compile(r"[^A-Za-z0-9._\- ]+")


def _safe_filename(name: str, suffix: str) -> str:
    cleaned = SAFE_NAME.sub("", name).strip().replace(" ", "_")[:80] or "download"
    return f"{cleaned}_{uuid4().hex[:8]}{suffix}"


def download_audio(url: str, title_hint: Optional[str] = None) -> dict:
    """Download best audio with yt-dlp, prefer mp3/ogg."""
    settings = get_settings()
    out_tmpl = str(settings.media_dir / "%(title).80B.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "--print",
        "after_move:filepath",
        "--print",
        "title",
        "--print",
        "duration",
        "-o",
        out_tmpl,
        url,
    ]
    log.info("Running yt-dlp for %s", url)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "yt-dlp failed")

    lines = [ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("yt-dlp produced no output")

    filepath = Path(lines[0])
    title = title_hint or (lines[1] if len(lines) > 1 else filepath.stem)
    duration = None
    if len(lines) > 2:
        try:
            duration = float(lines[2])
        except ValueError:
            duration = None

    # Normalize filename into our media dir
    if not filepath.exists():
        # sometimes path is relative
        candidate = settings.media_dir / filepath.name
        if candidate.exists():
            filepath = candidate
        else:
            raise RuntimeError(f"Downloaded file not found: {filepath}")

    final_name = _safe_filename(title, filepath.suffix or ".mp3")
    final_path = settings.media_dir / final_name
    if filepath.resolve() != final_path.resolve():
        filepath.rename(final_path)

    return {
        "filename": final_name,
        "title": title,
        "duration": duration,
        "source_url": url,
    }
