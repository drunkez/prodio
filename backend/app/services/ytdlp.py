import logging
import re
import subprocess
from pathlib import Path
from typing import Optional
from uuid import uuid4

from ..config import get_settings

log = logging.getLogger("prodio.ytdlp")

SAFE_NAME = re.compile(r"[^A-Za-z0-9._\- ]+")
AUDIO_EXT = {".mp3", ".ogg", ".oga", ".m4a", ".opus", ".webm", ".wav", ".flac", ".aac"}


def _safe_filename(name: str, suffix: str) -> str:
    cleaned = SAFE_NAME.sub("", name).strip().replace(" ", "_")[:80] or "download"
    return f"{cleaned}_{uuid4().hex[:8]}{suffix}"


def _friendly_error(stderr: str) -> str:
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    errors = [ln for ln in lines if ln.startswith("ERROR:")]
    if errors:
        msg = errors[-1]
        if msg.startswith("ERROR:"):
            msg = msg[6:].strip()
        return msg
    useful = [ln for ln in lines if not ln.startswith("WARNING:")]
    return useful[-1] if useful else (lines[-1] if lines else "yt-dlp failed")


def _pick_filepath(lines: list[str], media_dir: Path) -> Optional[Path]:
    candidates: list[Path] = []
    for ln in lines:
        p = Path(ln)
        if p.suffix.lower() in AUDIO_EXT and (p.is_absolute() or "/" in ln or "\\" in ln):
            candidates.append(p)
        elif p.suffix.lower() in AUDIO_EXT:
            candidates.append(media_dir / p.name)
    for p in reversed(candidates):
        if p.exists():
            return p
        alt = media_dir / p.name
        if alt.exists():
            return alt
    # last resort: newest audio file in media dir written in last minute
    newest = None
    newest_mtime = 0.0
    for p in media_dir.iterdir():
        if p.suffix.lower() in AUDIO_EXT:
            m = p.stat().st_mtime
            if m > newest_mtime:
                newest = p
                newest_mtime = m
    return newest


def download_audio(url: str, title_hint: Optional[str] = None) -> dict:
    """Download best audio with yt-dlp, convert to mp3."""
    settings = get_settings()
    out_tmpl = str(settings.media_dir / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "-f",
        "bestaudio/best",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "--extractor-args",
        "youtube:player_client=android,web",
        "--print",
        "before_dl:title",
        "--print",
        "before_dl:duration",
        "--print",
        "after_move:filepath",
        "-o",
        out_tmpl,
        url,
    ]
    log.info("Running yt-dlp for %s", url)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        log.error("yt-dlp stderr: %s", proc.stderr)
        raise RuntimeError(_friendly_error(proc.stderr or proc.stdout))

    lines = [ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()]
    filepath = _pick_filepath(lines, settings.media_dir)
    if not filepath or not filepath.exists():
        raise RuntimeError(
            "Download finished but output file was not found. "
            f"yt-dlp output: {lines!r}"
        )

    title = title_hint
    duration = None
    for ln in lines:
        if ln == str(filepath) or ln.endswith(filepath.name):
            continue
        if title is None and not ln.replace(".", "", 1).isdigit():
            title = ln
            continue
        if duration is None:
            try:
                duration = float(ln)
            except ValueError:
                if title is None:
                    title = ln

    title = title or filepath.stem

    final_name = _safe_filename(title, filepath.suffix or ".mp3")
    final_path = settings.media_dir / final_name
    if filepath.resolve() != final_path.resolve():
        if final_path.exists():
            final_path.unlink()
        filepath.rename(final_path)

    return {
        "filename": final_name,
        "title": title,
        "duration": duration,
        "source_url": url,
    }
