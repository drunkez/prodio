FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    ICECAST_HOST=127.0.0.1 \
    ICECAST_PORT=8000 \
    ICECAST_MOUNT=/live \
    ICECAST_SOURCE_PASSWORD=hackme \
    ICECAST_ADMIN_PASSWORD=hackme \
    ICECAST_RELAY_PASSWORD=hackme \
    ICECAST_HOSTNAME=localhost \
    STATION_NAME=ProDio \
    STATION_DESCRIPTION="All-in-one web radio" \
    STATION_GENRE=Various \
    PRODIO_ADMIN_USER=admin \
    PRODIO_ADMIN_PASSWORD=changeme \
    PRODIO_SECRET_KEY=change-this-to-a-long-random-string \
    STREAM_PUBLIC_URL=http://localhost:8000/live \
    PRODIO_PUBLIC_URL=http://localhost:8080 \
    PRODIO_ONAIR_PLAYLIST=/data/playlists/onair.m3u \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      ffmpeg \
      icecast2 \
      liquidsoap \
      nodejs \
      python3 \
      python3-pip \
      python3-venv \
      supervisor \
      netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Allow Icecast to run without interactive setup
RUN mkdir -p /var/log/icecast2 /usr/share/icecast2/web /usr/share/icecast2/admin \
    && touch /etc/icecast2/icecast.xml \
    && chown -R icecast2:icecast /var/log/icecast2 || true

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /app/backend/requirements.txt \
    && pip3 install --break-system-packages --no-cache-dir -U --pre "yt-dlp[default]"

COPY backend /app/backend
COPY liquidsoap /app/liquidsoap
COPY config /app/config
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/supervisord.conf /etc/supervisor/conf.d/prodio.conf

RUN chmod +x /entrypoint.sh \
    && mkdir -p /data/media /data/playlists /data/db

VOLUME ["/data"]
EXPOSE 8080 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=25s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
