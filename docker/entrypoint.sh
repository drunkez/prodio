#!/bin/bash
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR/media" "$DATA_DIR/playlists" "$DATA_DIR/db" /var/log/icecast2 /var/log/supervisor

# Render Icecast config from env placeholders
ICECAST_SRC="/app/config/icecast.xml"
ICECAST_DST="/etc/icecast2/icecast.xml"
sed -e "s|ICECAST_SOURCE_PASSWORD|${ICECAST_SOURCE_PASSWORD:-hackme}|g" \
    -e "s|ICECAST_ADMIN_PASSWORD|${ICECAST_ADMIN_PASSWORD:-hackme}|g" \
    -e "s|ICECAST_RELAY_PASSWORD|${ICECAST_RELAY_PASSWORD:-hackme}|g" \
    -e "s|ICECAST_HOSTNAME|${ICECAST_HOSTNAME:-localhost}|g" \
    "$ICECAST_SRC" > "$ICECAST_DST"

# Ensure on-air playlist exists
ONAIR="${PRODIO_ONAIR_PLAYLIST:-$DATA_DIR/playlists/onair.m3u}"
if [[ ! -f "$ONAIR" ]]; then
  printf '#EXTM3U\n' > "$ONAIR"
fi

# Icecast drops privileges via changeowner; ensure log dir is writable
chown -R icecast2:icecast /var/log/icecast2 2>/dev/null || true
mkdir -p /usr/share/icecast2/web /usr/share/icecast2/admin

export ICECAST_HOST="${ICECAST_HOST:-127.0.0.1}"
export ICECAST_PORT="${ICECAST_PORT:-8000}"
export PRODIO_ONAIR_PLAYLIST="$ONAIR"

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/prodio.conf -n
