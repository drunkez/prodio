from mutagen import File as MutagenFile


def probe_duration(path: str) -> float | None:
    try:
        audio = MutagenFile(path)
        if audio is not None and audio.info is not None:
            return float(audio.info.length)
    except Exception:
        return None
    return None


def probe_tags(path: str) -> tuple[str | None, str | None]:
    """Return (title, artist) if present."""
    try:
        audio = MutagenFile(path, easy=True)
        if not audio or not audio.tags:
            return None, None
        title = (audio.tags.get("title") or [None])[0]
        artist = (audio.tags.get("artist") or [None])[0]
        return title, artist
    except Exception:
        return None, None
