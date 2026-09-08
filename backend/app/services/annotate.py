"""Helpers to build Liquidsoap annotate: URIs with library metadata."""

from pathlib import Path

from ..database import Track


def _esc(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", " ")
    )


def display_title(track: Track) -> str:
    if track.artist:
        return f"{track.artist} - {track.title}"
    return track.title


def annotate_uri(track: Track, media_dir: Path) -> str:
    """Build annotate:title=...,artist=...:/path for Liquidsoap."""
    path = media_dir / track.filename
    title = _esc(track.title or path.stem)
    parts = [f'title="{title}"']
    if track.artist:
        parts.append(f'artist="{_esc(track.artist)}"')
    # Also set song for Icecast clients that read that field
    parts.append(f'song="{_esc(display_title(track))}"')
    return f'annotate:{",".join(parts)}:{path}'
