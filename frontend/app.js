const params = new URLSearchParams(window.location.search);
const API_BASE_URL = (params.get("api") || window.MUSIC_API_URL || localStorage.getItem("MUSIC_API_URL") || "http://localhost:8000").replace(/\/$/, "");
const state = { currentUser: "3143", liveTicker: null, liveStarting: false };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: { Accept: "application/json", ...(options.headers || {}) }, ...options });
  let payload = {};
  try { payload = await response.json(); } catch { payload = {}; }
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
}

function setMessage(text = "", isError = false) {
  const el = $("#message");
  if (!el) return;
  el.textContent = text;
  el.classList.toggle("error", isError);
}

function setGlobalMessage(text = "") { $("#globalMessage").textContent = text; }

function renderHealth(health) {
  $("#statInteractions").textContent = Number(health.dataset_interactions_count || 0).toLocaleString();
  $("#statCatalog").textContent = Number(health.catalog_items_count || 0).toLocaleString();
  $("#statProfiles").textContent = Number(health.active_recommendation_count || 0).toLocaleString();
  $("#statServing").textContent = health.status === "healthy" ? "Online" : "Degraded";
  $("#statServingDetail").textContent = health.mongodb_available ? "FastAPI + MongoDB connected" : "FastAPI online - cache fallback";
  $("#apiStatusDot").className = `status-dot ${health.status === "healthy" ? "online" : "offline"}`;
  $("#apiStatusText").textContent = health.status === "healthy" ? "FastAPI online" : "FastAPI degraded";
}

function renderRecommendations(items, response) {
  const list = $("#recommendations");
  list.innerHTML = "";
  if (!items?.length) {
    list.innerHTML = '<div class="empty-state">No recommendations found for this listener.</div>';
    return;
  }
  items.forEach((item, index) => {
    const title = item.track_name || `Item ${item.item_id}`;
    const artist = item.artist_name || "Metadata not available";
    const coverClass = ["", "cover-two", "cover-three", "cover-four"][index % 4];
    list.insertAdjacentHTML("beforeend", `<article class="recommendation-card"><div class="track-cover ${coverClass}" aria-hidden="true">♫</div><div><div class="track-title" title="${escapeHtml(title)}">${escapeHtml(title)}</div><div class="artist-name">${escapeHtml(artist)}</div><div class="track-meta"><span>#${item.rank || index + 1}</span><span>ITEM ${escapeHtml(item.item_id)}</span><span class="track-score">SCORE ${Number(item.score || 0).toFixed(4)}</span></div><div class="reason">${escapeHtml(item.reason || response.strategy || "Mahout recommendation")}</div></div></article>`);
  });
}

async function loadHistory(userId) {
  const history = $("#history");
  try {
    const data = await apiFetch(`/user/${encodeURIComponent(userId)}/history?limit=6`);
    $("#historyCount").textContent = `${Number(data.total_interactions || 0).toLocaleString()} interactions`;
    if (!data.history?.length) {
      history.innerHTML = '<div class="empty-state">No recorded history for this listener.</div>';
      return;
    }
    history.innerHTML = data.history.map((item) => `<div class="history-row"><div><strong>${escapeHtml(item.track_name || `Item ${item.item_id}`)}</strong><small>${escapeHtml(item.artist_name || item.song_code || "Mapped catalog item")}</small></div><b>${Number(item.play_count || 0).toLocaleString()} plays</b></div>`).join("");
  } catch {
    $("#historyCount").textContent = "Unavailable";
    history.innerHTML = '<div class="empty-state">History is unavailable for this listener.</div>';
  }
}

async function loadRecommendations(event) {
  event?.preventDefault();
  const userId = $("#userId").value.trim();
  const limit = $("#limit").value;
  const strategy = $("#strategy").value;
  if (!userId) { setMessage("Enter a user ID first.", true); return; }
  const button = $("#recommendationForm .primary-button");
  button.disabled = true;
  button.classList.add("is-loading");
  button.querySelector(".button-label").textContent = "Finding tracks...";
  $("#resultCount").textContent = "Loading";
  setMessage("Reading this listener's real profile...");
  try {
    const response = await apiFetch(`/recommend/${encodeURIComponent(userId)}?n=${limit}&strategy=${strategy}`);
    state.currentUser = userId;
    renderRecommendations(response.recommendations, response);
    $("#resultCount").textContent = `${response.count} tracks`;
    setMessage(`${response.strategy} strategy served in ${response.execution_time_ms ?? "-"} ms.`);
    await loadHistory(userId);
  } catch (error) {
    $("#resultCount").textContent = "Error";
    setMessage(error.message, true);
    $("#recommendations").innerHTML = '<div class="empty-state">The API could not return recommendations. Check the service status above.</div>';
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
    button.querySelector(".button-label").textContent = "Generate recommendations";
  }
}

async function loadSimilar(event) {
  event?.preventDefault();
  const songId = $("#songId").value.trim();
  const limit = $("#similarLimit").value;
  const target = $("#similarResults");
  const button = $("#similarForm .primary-button");
  if (!songId) return;
  button.disabled = true;
  button.classList.add("is-loading");
  button.querySelector(".button-label").textContent = "Finding matches...";
  target.innerHTML = '<div class="empty-state">Mapping metadata and interaction neighbours...</div>';
  try {
    const data = await apiFetch(`/similar/${encodeURIComponent(songId)}?n=${limit}`);
    $("#similarTitle").textContent = `Matches for item ${songId}`;
    target.innerHTML = data.similar_songs?.length ? data.similar_songs.map((item, index) => `<article class="recommendation-card"><div class="track-cover ${["", "cover-two", "cover-three", "cover-four"][index % 4]}" aria-hidden="true">♫</div><div><div class="track-title">${escapeHtml(item.track_name || `Item ${item.item_id}`)}</div><div class="artist-name">${escapeHtml(item.artist_name || "Metadata not available")}</div><div class="track-meta"><span>#${item.rank}</span><span>ITEM ${escapeHtml(item.item_id)}</span><span class="track-score">SIM ${Number(item.similarity_score || 0).toFixed(4)}</span></div><div class="reason">${escapeHtml(item.similarity_type || "Similarity")}</div></div></article>`).join("") : '<div class="empty-state">No similar tracks found for this item.</div>';
  } catch (error) {
    target.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
    button.querySelector(".button-label").textContent = "Find similar tracks";
  }
}

async function loadActivity() {
  try {
    const data = await apiFetch("/live/stats");
    $("#liveEvents").textContent = Number(data.total_events_processed || 0).toLocaleString();
    $("#liveUsers").textContent = Number(data.unique_active_users || 0).toLocaleString();
    $("#liveSimulator").textContent = data.simulator_active ? "Active" : "Idle";
    $("#liveLastEvent").textContent = data.last_event_timestamp ? `Last event ${data.last_event_timestamp.split("T")[1]?.slice(0, 8) || "now"}` : "Waiting for stream";
    const events = await apiFetch("/live/events?limit=12");
    $("#activityTable").innerHTML = events.events?.length ? `<table class="event-table"><thead><tr><th>Time</th><th>User</th><th>Item</th><th>Action</th><th>Duration</th></tr></thead><tbody>${events.events.map((event) => `<tr><td>${escapeHtml(event.timestamp?.split("T")[1]?.slice(0, 8) || "-")}</td><td>User ${escapeHtml(event.user_id)}</td><td><code>${escapeHtml(event.song_id)}</code></td><td>${escapeHtml(String(event.event_type).toUpperCase())}</td><td>${escapeHtml(event.duration_seconds)}s</td></tr>`).join("")}</tbody></table>` : '<div class="empty-state">Start the live stream to see listening activity.</div>';
  } catch (error) {
    $("#activityTable").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  }
}

async function startLiveStream(notify = true) {
  if (state.liveStarting) return;
  state.liveStarting = true;
  try {
    await apiFetch("/live/simulator/start?interval_seconds=1", { method: "POST" });
    if (notify) setGlobalMessage("Live listening stream started. New events will appear automatically.");
    await loadActivity();
    clearInterval(state.liveTicker);
    state.liveTicker = setInterval(() => { if ($('[data-view-panel="activity"]').classList.contains("is-visible")) loadActivity(); }, 2000);
  } catch (error) {
    $("#activityTable").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  } finally { state.liveStarting = false; }
}

async function stopLiveStream() {
  try {
    await apiFetch("/live/simulator/stop", { method: "POST" });
    clearInterval(state.liveTicker);
    state.liveTicker = null;
    setGlobalMessage("Live listening stream stopped.");
    await loadActivity();
  } catch (error) { setGlobalMessage(error.message); }
}

async function loadEvaluation() {
  try {
    const data = await apiFetch("/evaluation/metrics");
    $("#evaluationContent").innerHTML = `<div class="metric-grid"><div class="metric-tile"><span>Precision@${data.k}</span><strong>${Number(data.precision_at_k).toFixed(4)}</strong></div><div class="metric-tile"><span>Recall@${data.k}</span><strong>${Number(data.recall_at_k).toFixed(4)}</strong></div><div class="metric-tile"><span>MRR@${data.k}</span><strong>${Number(data.mrr_at_k).toFixed(4)}</strong></div><div class="metric-tile"><span>Catalog coverage</span><strong>${Number(data.catalog_coverage_pct).toFixed(2)}%</strong></div></div><p class="evaluation-note">${escapeHtml(data.description || "Metrics calculated from the configured interaction dataset and Mahout output.")} Evaluated users: ${Number(data.evaluated_users_count || 0).toLocaleString()}. Split: ${escapeHtml(data.dataset_split || "deterministic holdout")}.</p>`;
  } catch (error) { $("#evaluationContent").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`; }
}

function switchView(view) {
  $$(".nav-item").forEach((item) => item.classList.toggle("is-active", item.dataset.view === view));
  $$(".view").forEach((panel) => panel.classList.toggle("is-visible", panel.dataset.viewPanel === view));
  $("#pageTitle").textContent = ({ recommendations: "Recommendations", similar: "Similar songs", activity: "Live activity", architecture: "Architecture", evaluation: "Evaluation" })[view];
  if (view === "similar") loadSimilar();
  if (view === "activity") { loadActivity(); startLiveStream(false); }
  if (view === "evaluation") loadEvaluation();
}

async function boot() {
  $("#apiOrigin").textContent = API_BASE_URL.replace(/^https?:\/\//, "");
  try { renderHealth(await apiFetch("/health")); await loadRecommendations(); }
  catch (error) { $("#apiStatusDot").className = "status-dot offline"; $("#apiStatusText").textContent = "API unavailable"; setGlobalMessage("FastAPI is not reachable. Start the backend and reload this page."); setMessage(error.message, true); }
}

$("#recommendationForm").addEventListener("submit", loadRecommendations);
$("#similarForm").addEventListener("submit", loadSimilar);
$("#refreshActivity").addEventListener("click", loadActivity);
$("#startSimulator").addEventListener("click", () => startLiveStream(true));
$("#stopSimulator").addEventListener("click", stopLiveStream);
$$(".nav-item").forEach((item) => item.addEventListener("click", () => switchView(item.dataset.view)));
$$('button[data-view-link]').forEach((button) => button.addEventListener("click", () => switchView(button.dataset.viewLink)));
$$('button[data-song]').forEach((button) => button.addEventListener("click", () => { $("#songId").value = button.dataset.song; loadSimilar(); }));
$$('.quick-picks button[data-user]').forEach((button) => button.addEventListener("click", () => { $("#userId").value = button.dataset.user === "new" ? "999999" : button.dataset.user; loadRecommendations(); }));
boot();
