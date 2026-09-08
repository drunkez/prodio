#!/usr/bin/liquidsoap

# ProDio automation / encoder — Liquidsoap 2.1.x compatible
# Controlled via telnet on port 1234

settings.server.telnet.set(true)
settings.server.telnet.port.set(1234)
settings.server.telnet.bind_addr.set("127.0.0.1")

log.level.set(3)
settings.init.daemon.set(false)
settings.init.allow_root.set(true)

icecast_host = getenv(default="127.0.0.1", "ICECAST_HOST")
icecast_port = int_of_string(getenv(default="8000", "ICECAST_PORT"))
icecast_password = getenv(default="hackme", "ICECAST_SOURCE_PASSWORD")
icecast_mount = getenv(default="/live", "ICECAST_MOUNT")
station_name = getenv(default="ProDio", "STATION_NAME")
station_description = getenv(default="All-in-one web radio", "STATION_DESCRIPTION")
station_genre = getenv(default="Various", "STATION_GENRE")
playlist_path = getenv(default="/data/playlists/onair.m3u", "PRODIO_ONAIR_PLAYLIST")

# Start stopped until admin hits Start
playing = ref(false)
# true = pick a random track each time (library / shuffle playlists)
use_random = ref(true)

# One-shot inject queue (library "Play" button)
inject = request.queue(id="inject")

pl_normal = playlist(
  id="onair_ord",
  playlist_path,
  mode="normal",
  reload_mode="manual"
)

pl_random = playlist(
  id="onair_rnd",
  playlist_path,
  mode="random",
  reload_mode="manual"
)

automation = switch(id="automation", track_sensitive=true, [
  ({!use_random}, mksafe(pl_random)),
  ({true}, mksafe(pl_normal))
])

# Prefer injected track, then automation playlist
onair_src = fallback(
  id="onair_src",
  track_sensitive=true,
  [inject, automation]
)

silence = blank(duration=1.)

radio = switch(track_sensitive=false, [
  ({!playing}, onair_src),
  ({true}, silence)
])

radio = mksafe(radio)

# Prefer annotate/song/title metadata for Icecast "now playing"
def fix_meta(m) =
  title =
    if m["title"] != "" and m["title"] != "Unknown" then
      m["title"]
    elsif m["song"] != "" then
      m["song"]
    else
      m["title"]
    end
  [("title", title), ("song", title)]
end

radio = metadata.map(fix_meta, update=false, radio)
radio = crossfade(duration=2.5, radio)

def do_reload(_) =
  pl_normal.reload()
  pl_random.reload()
  "Playlist reloaded"
end

def do_skip(_) =
  onair_src.skip()
  "Skipped"
end

def do_start(_) =
  playing := true
  "Streaming started"
end

def do_stop(_) =
  playing := false
  "Streaming stopped"
end

def do_status(_) =
  if !playing then "playing" else "stopped" end
end

def do_mode_random(_) =
  use_random := true
  pl_random.reload()
  "random"
end

def do_mode_ordered(_) =
  use_random := false
  pl_normal.reload()
  "ordered"
end

# Queue a URI and skip current track so crossfade brings it in
def do_play(uri) =
  inject.push(request.create(uri))
  if !playing then
    playing := true
  else
    onair_src.skip()
  end
  "Playing #{uri}"
end

server.register(namespace="prodio", "reload", do_reload)
server.register(namespace="prodio", "skip", do_skip)
server.register(namespace="prodio", "start", do_start)
server.register(namespace="prodio", "stop", do_stop)
server.register(namespace="prodio", "status", do_status)
server.register(namespace="prodio", "mode_random", do_mode_random)
server.register(namespace="prodio", "mode_ordered", do_mode_ordered)
server.register(namespace="prodio", "play", do_play)

output.icecast(
  %mp3(bitrate=128, samplerate=44100, stereo=true),
  host=icecast_host,
  port=icecast_port,
  password=icecast_password,
  mount=icecast_mount,
  name=station_name,
  description=station_description,
  genre=station_genre,
  url="http://localhost:8080",
  public=true,
  fallible=true,
  radio
)
