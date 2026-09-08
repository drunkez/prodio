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
# true = shuffled rounds (library / shuffle playlists)
use_random = ref(true)

# Anti-repeat: never play the same file twice in a row
last_uri = ref("")
reject_streak = ref(0)

def rec take(n, l) =
  if n <= 0 then
    []
  elsif list.is_empty(l) then
    []
  else
    list.hd(l) :: take(n - 1, list.tl(l))
  end
end

# Remember recent tracks (up to 8) to avoid near-repeats in small reshuffles
recent = ref([])

def track_uri(m) =
  if m["filename"] != "" then
    m["filename"]
  else
    m["initial_uri"]
  end
end

def mark_played(m) =
  uri = track_uri(m)
  if uri != "" then
    last_uri := uri
    recent := take(8, uri :: !recent)
    reject_streak := 0
  end
end

def no_repeat(req) =
  m = request.metadata(req)
  uri = if m["filename"] != "" then m["filename"] else request.uri(req) end
  if uri == "" then
    true
  elsif list.mem(uri, !recent) then
    # Same as a recent track — reject, unless we keep failing (tiny library)
    reject_streak := !reject_streak + 1
    if !reject_streak > 20 then
      reject_streak := 0
      true
    else
      false
    end
  else
    reject_streak := 0
    true
  end
end

# One-shot inject queue (library "Play" button)
inject = request.queue(id="inject")

pl_normal = playlist(
  id="onair_ord",
  playlist_path,
  mode="normal",
  reload_mode="manual"
)

# randomize = shuffle full list, play through with no repeats, then reshuffle
pl_random = playlist(
  id="onair_rnd",
  playlist_path,
  mode="randomize",
  reload_mode="manual",
  check_next=no_repeat
)

automation = switch(id="automation", track_sensitive=true, [
  ({!use_random}, mksafe(pl_random)),
  ({true}, mksafe(pl_normal))
])

automation.on_track(mark_played)

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
  recent := []
  last_uri := ""
  reject_streak := 0
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
