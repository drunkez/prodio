const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  user: null,
  tracks: [],
  playlists: [],
  schedule: [],
  days: [],
  editingPlaylistId: null,
  editingTrackIds: [],
  libQuery: "",
  libPage: 1,
  libPageSize: 100,
  peLibQuery: "",
};

function toast(msg, kind = "") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast ${kind}`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 3200);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: opts.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...opts,
  });
  if (res.status === 401) {
    showLogin();
    throw new Error("Unauthorized");
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { detail: text }; }
  if (!res.ok) {
    const detail = data?.detail;
    const msg = typeof detail === "string" ? detail : JSON.stringify(detail || res.statusText);
    throw new Error(msg);
  }
  return data;
}

function showLogin() {
  $("#login-view").classList.remove("hidden");
  $("#app-view").classList.add("hidden");
}

function showApp() {
  $("#login-view").classList.add("hidden");
  $("#app-view").classList.remove("hidden");
}

function fmtDur(sec) {
  if (sec == null || Number.isNaN(sec)) return "";
  const s = Math.round(sec);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

/* ---- tabs ---- */
$$(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".nav-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    $$(".tab").forEach((t) => t.classList.remove("active"));
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
  });
});

/* ---- auth ---- */
$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  $("#login-error").textContent = "";
  try {
    await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: fd.get("username"),
        password: fd.get("password"),
      }),
    });
    await boot();
  } catch (err) {
    $("#login-error").textContent = err.message || "Login failed";
  }
});

$("#logout-btn").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" });
  showLogin();
});

/* ---- dashboard ---- */
async function refreshStatus() {
  try {
    const s = await api("/api/stream/status");
    const panel = $(".onair-panel");
    panel.classList.toggle("live", !!s.is_playing);
    $("#st-playing").textContent = s.is_playing ? "LIVE" : "STOPPED";
    $("#st-playing").style.color = s.is_playing ? "var(--onair)" : "var(--muted)";
    $("#st-listeners").textContent = s.listeners == null ? "—" : String(s.listeners);
    $("#st-playlist").textContent = s.active_playlist_name || "—";
    $("#st-ls").textContent = s.liquidsoap_ok ? "ok" : "down";
    $("#st-np").textContent = s.now_playing || "—";
    const a = $("#st-url");
    a.href = s.stream_url;
    a.textContent = s.stream_url;
    const mon = $("#monitor");
    if (mon.src !== s.stream_url) mon.src = s.stream_url;
  } catch (_) { /* ignore while logged out */ }
}

$("#btn-start").addEventListener("click", async () => {
  try {
    await api("/api/stream/start", { method: "POST" });
    toast("Stream started", "good");
    refreshStatus();
  } catch (e) { toast(e.message, "bad"); }
});
$("#btn-stop").addEventListener("click", async () => {
  try {
    await api("/api/stream/stop", { method: "POST" });
    toast("Stream stopped");
    refreshStatus();
  } catch (e) { toast(e.message, "bad"); }
});
$("#btn-skip").addEventListener("click", async () => {
  try {
    await api("/api/stream/skip", { method: "POST" });
    toast("Skipped", "good");
    setTimeout(refreshStatus, 800);
  } catch (e) { toast(e.message, "bad"); }
});
$("#btn-reload").addEventListener("click", async () => {
  try {
    await api("/api/stream/reload", { method: "POST" });
    toast("Playlist reloaded", "good");
  } catch (e) { toast(e.message, "bad"); }
});

/* ---- library ---- */
function trackMatches(t, q) {
  if (!q) return true;
  const hay = `${t.title || ""} ${t.artist || ""} ${t.filename || ""}`.toLowerCase();
  return hay.includes(q);
}

function filteredTracks(query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return state.tracks;
  return state.tracks.filter((t) => trackMatches(t, q));
}

function renderPager(el, page, pageSize, total, onPage) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(1, page), pages);
  if (safePage !== page) onPage(safePage);
  el.innerHTML = "";
  if (total === 0) return;
  const info = document.createElement("span");
  info.className = "page-info";
  const from = (safePage - 1) * pageSize + 1;
  const to = Math.min(safePage * pageSize, total);
  info.textContent = `${from}–${to} / ${total}`;
  el.appendChild(info);
  const mk = (label, p, disabled = false) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.disabled = disabled;
    b.addEventListener("click", () => onPage(p));
    el.appendChild(b);
  };
  mk("Prev", safePage - 1, safePage <= 1);
  mk("Next", safePage + 1, safePage >= pages);
}

async function loadTracks() {
  state.tracks = await api("/api/media");
  renderTracks();
  renderPlaylistLibrary();
}

function renderTracks() {
  const root = $("#track-list");
  const filtered = filteredTracks(state.libQuery);
  const pageSize = state.libPageSize;
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  if (state.libPage > pages) state.libPage = pages;
  const start = (state.libPage - 1) * pageSize;
  const slice = filtered.slice(start, start + pageSize);

  $("#lib-count").textContent = state.libQuery.trim()
    ? `${filtered.length} match · ${state.tracks.length} total`
    : `${state.tracks.length} tracks`;

  if (!state.tracks.length) {
    root.innerHTML = `<tr><td colspan="5" class="muted">No tracks yet.</td></tr>`;
    $("#lib-pager").innerHTML = "";
    return;
  }
  if (!slice.length) {
    root.innerHTML = `<tr><td colspan="5" class="muted">No matches.</td></tr>`;
  } else {
    root.innerHTML = slice.map((t) => `
      <tr>
        <td class="col-title" title="${escapeHtml(t.title)}">${escapeHtml(t.title)}</td>
        <td class="col-artist" title="${escapeHtml(t.artist || "")}">${escapeHtml(t.artist || "—")}</td>
        <td class="col-dur">${fmtDur(t.duration) || "—"}</td>
        <td class="col-file" title="${escapeHtml(t.filename)}">${escapeHtml(t.filename)}</td>
        <td class="col-act"><span class="acts">
          <button data-play="${t.id}" class="primary" title="Play now">Play</button>
          <button data-del="${t.id}" class="danger" title="Delete">Del</button>
        </span></td>
      </tr>`).join("");
  }
  renderPager($("#lib-pager"), state.libPage, pageSize, filtered.length, (p) => {
    state.libPage = p;
    renderTracks();
  });
}

$("#track-list").addEventListener("click", async (e) => {
  const playBtn = e.target.closest("[data-play]");
  if (playBtn) {
    try {
      const res = await api(`/api/media/${playBtn.dataset.play}/play`, { method: "POST" });
      toast(`Playing: ${res.title || "track"}`, "good");
      refreshStatus();
    } catch (err) { toast(err.message, "bad"); }
    return;
  }
  const btn = e.target.closest("[data-del]");
  if (!btn) return;
  if (!confirm("Delete this track?")) return;
  try {
    await api(`/api/media/${btn.dataset.del}`, { method: "DELETE" });
    await loadTracks();
    await loadPlaylists();
    toast("Deleted");
  } catch (err) { toast(err.message, "bad"); }
});

$("#lib-search").addEventListener("input", (e) => {
  state.libQuery = e.target.value;
  state.libPage = 1;
  renderTracks();
});

$("#lib-page-size").addEventListener("change", (e) => {
  state.libPageSize = Number(e.target.value) || 100;
  state.libPage = 1;
  renderTracks();
});

$("#upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = e.target.querySelector('input[type="file"]');
  const files = [...(input?.files || [])];
  if (!files.length) return;
  const status = $("#upload-status");
  const btn = e.target.querySelector('button[type="submit"]');
  btn.disabled = true;
  status.textContent = `Uploading ${files.length} file${files.length === 1 ? "" : "s"}…`;
  try {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    const uploaded = await api("/api/media/upload", {
      method: "POST",
      body: fd,
      headers: {},
    });
    e.target.reset();
    status.textContent = "";
    await loadTracks();
    toast(`Uploaded ${uploaded.length} file${uploaded.length === 1 ? "" : "s"}`, "good");
  } catch (err) {
    status.textContent = "";
    toast(err.message, "bad");
  } finally {
    btn.disabled = false;
  }
});

$("#yt-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const status = $("#yt-status");
  status.textContent = "Downloading… this can take a minute.";
  try {
    await api("/api/download/youtube", {
      method: "POST",
      body: JSON.stringify({
        url: fd.get("url"),
        title: fd.get("title") || null,
      }),
    });
    e.target.reset();
    status.textContent = "";
    await loadTracks();
    toast("Downloaded", "good");
  } catch (err) {
    status.textContent = "";
    toast(err.message, "bad");
  }
});

/* ---- playlists ---- */
async function loadPlaylists() {
  state.playlists = await api("/api/playlists");
  renderPlaylists();
  fillSchedulePlaylistSelect();
  if (state.editingPlaylistId) {
    const p = state.playlists.find((x) => x.id === state.editingPlaylistId);
    if (p) selectPlaylist(p.id);
    else clearPlaylistEditor();
  }
}

function renderPlaylists() {
  const root = $("#playlist-list");
  root.innerHTML = "";
  if (!state.playlists.length) {
    root.innerHTML = `<div class="drow"><span class="muted">No playlists yet.</span></div>`;
    return;
  }
  root.innerHTML = state.playlists.map((p) => `
    <div class="drow${p.id === state.editingPlaylistId ? " selected" : ""}" data-edit="${p.id}">
      <span class="t">${escapeHtml(p.name)}<span class="meta-inline">${p.tracks.length}${p.shuffle ? " · shuf" : ""}</span></span>
      <span class="acts"><button data-edit="${p.id}">Edit</button></span>
    </div>`).join("");
}

$("#playlist-list").addEventListener("click", (e) => {
  const el = e.target.closest("[data-edit]");
  if (!el) return;
  selectPlaylist(Number(el.dataset.edit));
});

function selectPlaylist(id) {
  const p = state.playlists.find((x) => x.id === id);
  if (!p) return;
  state.editingPlaylistId = id;
  state.editingTrackIds = p.tracks.map((t) => t.id);
  $("#pe-name").textContent = p.name;
  $("#pe-shuffle").checked = p.shuffle;
  $("#pe-save").disabled = false;
  $("#pe-live").disabled = false;
  $("#pe-delete").disabled = false;
  renderPlaylists();
  renderPlaylistTracks();
  renderPlaylistLibrary();
}

function clearPlaylistEditor() {
  state.editingPlaylistId = null;
  state.editingTrackIds = [];
  $("#pe-name").textContent = "—";
  $("#pe-shuffle").checked = false;
  $("#pe-save").disabled = true;
  $("#pe-live").disabled = true;
  $("#pe-delete").disabled = true;
  $("#pe-tracks").innerHTML = "";
  $("#pe-track-count").textContent = "";
  renderPlaylistLibrary();
}

function renderPlaylistTracks() {
  const root = $("#pe-tracks");
  $("#pe-track-count").textContent = state.editingTrackIds.length
    ? `(${state.editingTrackIds.length})`
    : "";
  if (!state.editingTrackIds.length) {
    root.innerHTML = `<div class="drow"><span class="muted">Empty playlist.</span></div>`;
    return;
  }
  root.innerHTML = state.editingTrackIds.map((tid) => {
    const t = state.tracks.find((x) => x.id === tid) ||
      state.playlists.flatMap((p) => p.tracks).find((x) => x.id === tid);
    if (!t) return "";
    return `
      <div class="drow">
        <span class="t" title="${escapeHtml(t.title)}">${escapeHtml(t.title)}</span>
        <span class="acts">
          <button data-up="${t.id}">↑</button>
          <button data-down="${t.id}">↓</button>
          <button data-rm="${t.id}" class="danger">×</button>
        </span>
      </div>`;
  }).join("");
}

$("#pe-tracks").addEventListener("click", (e) => {
  const rm = e.target.closest("[data-rm]");
  const up = e.target.closest("[data-up]");
  const down = e.target.closest("[data-down]");
  if (rm) {
    const id = Number(rm.dataset.rm);
    state.editingTrackIds = state.editingTrackIds.filter((x) => x !== id);
    renderPlaylistTracks();
    renderPlaylistLibrary();
    return;
  }
  if (up) {
    const id = Number(up.dataset.up);
    const i = state.editingTrackIds.indexOf(id);
    if (i > 0) {
      [state.editingTrackIds[i - 1], state.editingTrackIds[i]] =
        [state.editingTrackIds[i], state.editingTrackIds[i - 1]];
      renderPlaylistTracks();
    }
    return;
  }
  if (down) {
    const id = Number(down.dataset.down);
    const i = state.editingTrackIds.indexOf(id);
    if (i >= 0 && i < state.editingTrackIds.length - 1) {
      [state.editingTrackIds[i + 1], state.editingTrackIds[i]] =
        [state.editingTrackIds[i], state.editingTrackIds[i + 1]];
      renderPlaylistTracks();
    }
  }
});

function renderPlaylistLibrary() {
  const root = $("#pe-library");
  const countEl = $("#pe-lib-count");
  if (!state.editingPlaylistId) {
    root.innerHTML = `<div class="drow"><span class="muted">Select a playlist to add tracks.</span></div>`;
    countEl.textContent = "";
    return;
  }
  const inPl = new Set(state.editingTrackIds);
  const available = filteredTracks(state.peLibQuery).filter((t) => !inPl.has(t.id));
  countEl.textContent = `${available.length} available`;
  if (!available.length) {
    root.innerHTML = `<div class="drow"><span class="muted">${state.peLibQuery.trim() ? "No matches." : "No more tracks to add."}</span></div>`;
    return;
  }
  // Cap DOM nodes for huge libraries; filter narrows further
  const LIMIT = 300;
  const slice = available.slice(0, LIMIT);
  root.innerHTML = slice.map((t) => `
    <div class="drow">
      <span class="t" title="${escapeHtml(t.title)}${t.artist ? " — " + escapeHtml(t.artist) : ""}">${escapeHtml(t.title)}${t.artist ? `<span class="meta-inline">${escapeHtml(t.artist)}</span>` : ""}</span>
      <span class="acts"><button data-add="${t.id}">+</button></span>
    </div>`).join("") + (available.length > LIMIT
    ? `<div class="drow"><span class="muted">Showing first ${LIMIT} — refine filter for more.</span></div>`
    : "");
}

$("#pe-library").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-add]");
  if (!btn) return;
  state.editingTrackIds.push(Number(btn.dataset.add));
  renderPlaylistTracks();
  renderPlaylistLibrary();
});

$("#pe-lib-search").addEventListener("input", (e) => {
  state.peLibQuery = e.target.value;
  renderPlaylistLibrary();
});

$("#playlist-create").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const p = await api("/api/playlists", {
      method: "POST",
      body: JSON.stringify({
        name: fd.get("name"),
        shuffle: fd.get("shuffle") === "on",
      }),
    });
    e.target.reset();
    await loadPlaylists();
    selectPlaylist(p.id);
    toast("Playlist created", "good");
  } catch (err) { toast(err.message, "bad"); }
});

$("#pe-save").addEventListener("click", async () => {
  if (!state.editingPlaylistId) return;
  try {
    await api(`/api/playlists/${state.editingPlaylistId}`, {
      method: "PUT",
      body: JSON.stringify({
        shuffle: $("#pe-shuffle").checked,
        track_ids: state.editingTrackIds,
      }),
    });
    await loadPlaylists();
    toast("Playlist saved", "good");
  } catch (e) { toast(e.message, "bad"); }
});

$("#pe-live").addEventListener("click", async () => {
  if (!state.editingPlaylistId) return;
  try {
    await api(`/api/playlists/${state.editingPlaylistId}/go-live`, { method: "POST" });
    toast("Playlist is on air", "good");
    refreshStatus();
  } catch (e) { toast(e.message, "bad"); }
});

$("#pe-delete").addEventListener("click", async () => {
  if (!state.editingPlaylistId) return;
  if (!confirm("Delete this playlist?")) return;
  try {
    await api(`/api/playlists/${state.editingPlaylistId}`, { method: "DELETE" });
    clearPlaylistEditor();
    await loadPlaylists();
    toast("Playlist deleted");
  } catch (e) { toast(e.message, "bad"); }
});

/* ---- radiolist ---- */
async function loadSchedule() {
  state.schedule = await api("/api/radiolist");
  state.days = await api("/api/radiolist/days");
  fillScheduleDaySelect();
  fillSchedulePlaylistSelect();
  renderSchedule();
}

function fillScheduleDaySelect() {
  const sel = $("#sch-day");
  sel.innerHTML = state.days.map((d) => `<option value="${d.id}">${d.name}</option>`).join("");
}

function fillSchedulePlaylistSelect() {
  const sel = $("#sch-playlist");
  sel.innerHTML = state.playlists
    .map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`)
    .join("");
}

function dayName(id) {
  return state.days.find((d) => d.id === id)?.name || String(id);
}

function renderSchedule() {
  const root = $("#schedule-list");
  root.innerHTML = "";
  if (!state.schedule.length) {
    root.innerHTML = `<p class="muted">No schedule slots yet.</p>`;
    return;
  }
  for (const e of state.schedule) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <div class="meta">
        <div class="title">${dayName(e.day_of_week)} ${e.start_time}–${e.end_time} · ${escapeHtml(e.playlist_name)}</div>
        <div class="sub">${e.shuffle ? "shuffle · " : ""}${e.enabled ? "enabled" : "disabled"}</div>
      </div>
      <div>
        <button data-tog="${e.id}">${e.enabled ? "Disable" : "Enable"}</button>
        <button data-shuf="${e.id}">${e.shuffle ? "No shuffle" : "Shuffle"}</button>
        <button data-del="${e.id}" class="danger">Remove</button>
      </div>`;
    root.appendChild(row);
  }
  root.querySelectorAll("[data-del]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api(`/api/radiolist/${btn.dataset.del}`, { method: "DELETE" });
        await loadSchedule();
        toast("Slot removed");
      } catch (e) { toast(e.message, "bad"); }
    });
  });
  root.querySelectorAll("[data-tog]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const entry = state.schedule.find((x) => x.id === Number(btn.dataset.tog));
      try {
        await api(`/api/radiolist/${btn.dataset.tog}`, {
          method: "PUT",
          body: JSON.stringify({ enabled: !entry.enabled }),
        });
        await loadSchedule();
      } catch (e) { toast(e.message, "bad"); }
    });
  });
  root.querySelectorAll("[data-shuf]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const entry = state.schedule.find((x) => x.id === Number(btn.dataset.shuf));
      try {
        await api(`/api/radiolist/${btn.dataset.shuf}`, {
          method: "PUT",
          body: JSON.stringify({ shuffle: !entry.shuffle }),
        });
        await loadSchedule();
      } catch (e) { toast(e.message, "bad"); }
    });
  });
}

$("#schedule-create").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await api("/api/radiolist", {
      method: "POST",
      body: JSON.stringify({
        playlist_id: Number(fd.get("playlist_id")),
        day_of_week: Number(fd.get("day_of_week")),
        start_time: fd.get("start_time"),
        end_time: fd.get("end_time"),
        shuffle: fd.get("shuffle") === "on",
      }),
    });
    await loadSchedule();
    toast("Slot added", "good");
  } catch (err) { toast(err.message, "bad"); }
});

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function boot() {
  try {
    const me = await api("/api/auth/me");
    state.user = me.user;
    showApp();
    await Promise.all([loadTracks(), loadPlaylists(), loadSchedule(), refreshStatus()]);
  } catch {
    showLogin();
  }
}

boot();
setInterval(refreshStatus, 5000);
