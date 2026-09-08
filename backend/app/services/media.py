from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3


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


def write_tags(path: str, title: str | None = None, artist: str | None = None) -> None:
    """Embed title/artist so Liquidsoap/Icecast show real now-playing."""
    if not title and not artist:
        return
    try:
        lower = path.lower()
        if lower.endswith(".mp3"):
            try:
                tags = EasyID3(path)
            except ID3NoHeaderError:
                audio = MP3(path)
                if audio.tags is None:
                    audio.add_tags(ID3())
                    audio.save()
                tags = EasyID3(path)
            if title:
                tags["title"] = title
            if artist:
                tags["artist"] = artist
            tags.save()
            return

        audio = MutagenFile(path, easy=True)
        if audio is None:
            return
        if audio.tags is None:
            audio.add_tags()
        if title:
            audio["title"] = [title]
        if artist:
            audio["artist"] = [artist]
        audio.save()
    except Exception:
        # Non-fatal — playout annotate / DB fallback still cover the UI
        pass
