# ProDio

All-in-one dockerized web radio: **encoder + automation + Icecast streaming + admin UI**.

Inspired by BUTT (encoder), LibreTime (automation), and Icecast/Shoutcast (streaming).

## Features

- Password-protected admin UI
- Start / stop / skip stream
- Upload MP3/OGG (and other common audio formats)
- Create / edit / delete playlists (name, shuffle, add/remove/reorder tracks)
- Radiolist schedule (day + time windows, shuffle, enable/disable)
- Download audio from YouTube via `yt-dlp`
- Listener count + now-playing from Icecast
- Crossfade between tracks (Liquidsoap)

## Quick start

```bash
cp .env.example .env
# edit passwords in .env
docker compose up --build -d
```

- Admin UI: http://localhost:8080  
- Stream: http://localhost:8000/live  
- Default login: `admin` / `changeme` (from `.env`)

Media and SQLite DB live in `./data` (persisted volume).

## Architecture

| Piece | Role |
|-------|------|
| FastAPI admin | Auth, library, playlists, radiolist, stream control |
| Liquidsoap | Playlist playout + MP3 encode to Icecast |
| Icecast2 | Public mount `/live` |
| yt-dlp + ffmpeg | YouTube → MP3 into the library |

One container runs all three processes under supervisord.

## Development notes

After code changes that affect the image:

```bash
docker compose up --build -d
docker compose logs -f
```

Health check: `GET /health`

## License

MIT
