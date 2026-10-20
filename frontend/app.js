/* Cinemagic frontend: Netflix-style UI, no framework, no build step. */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const ROTATE_MS = 8000;
  const RING = 2 * Math.PI * 18;
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canHover = matchMedia("(hover: hover) and (pointer: fine)").matches;

  // ---------- icons: one 24px line-icon set, inline SVG (no emoji, no icon font) ----------
  const ICONS = {
    heart: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    play: '<path d="M6 4.5v15a1 1 0 0 0 1.5.86l12.5-7.5a1 1 0 0 0 0-1.72L7.5 3.64A1 1 0 0 0 6 4.5Z" fill="currentColor" stroke="none"/>',
    chevronDown: '<path d="m6 9 6 6 6-6"/>',
    chevronLeft: '<path d="m15 18-6-6 6-6"/>',
    chevronRight: '<path d="m9 18 6-6-6-6"/>',
    star: '<path d="M11.48 3.5a.56.56 0 0 1 1.04 0l2.13 5.11a.56.56 0 0 0 .48.35l5.52.44c.5.04.7.66.32.99l-4.2 3.6a.56.56 0 0 0-.18.56l1.28 5.39a.56.56 0 0 1-.84.61l-4.73-2.89a.56.56 0 0 0-.59 0l-4.73 2.89a.56.56 0 0 1-.84-.61l1.28-5.39a.56.56 0 0 0-.18-.56l-4.2-3.6a.56.56 0 0 1 .32-.99l5.52-.44a.56.56 0 0 0 .48-.35Z" fill="currentColor" stroke="none"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    help: '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.82 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    reset: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    film: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 12h18M3 7.5h4M3 16.5h4M17 7.5h4M17 16.5h4"/>',
    tag: '<path d="M12.59 2.59A2 2 0 0 0 11.17 2H4a2 2 0 0 0-2 2v7.17a2 2 0 0 0 .59 1.42l8.7 8.7a2.43 2.43 0 0 0 3.42 0l6.58-6.58a2.43 2.43 0 0 0 0-3.42Z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    // mood chips
    moon: '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z"/>',
    infinity: '<path d="M18.18 8c5.1 0 5.1 8 0 8-5.1 0-7.14-8-12.74-8-4.59 0-4.59 8 0 8 5.6 0 7.64-8 12.74-8Z"/>',
    droplet: '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7Z"/>',
    zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z"/>',
    smile: '<circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><path d="M9 9h.01M15 9h.01"/>',
    mountain: '<path d="m8 3 4 8 5-5 5 15H2L8 3Z"/>',
    rocket: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09Z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2Z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
  };
  const icon = (name, cls = "") =>
    `<svg class="ic ic-${name} ${cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICONS[name]}</svg>`;

  const MOODS = [
    ["moon", "Cozy night in", "cozy and heartwarming"],
    ["infinity", "Mind-bending", "mind-bending with a twist"],
    ["droplet", "Make me cry", "emotional, make me cry"],
    ["zap", "Edge of my seat", "scary suspense thriller"],
    ["smile", "Laugh out loud", "funny and quirky"],
    ["mountain", "Epic adventure", "epic heroic adventure"],
    ["heart", "Date night", "romantic date night"],
    ["rocket", "Into space", "space sci-fi"],
  ];
  const GENRE_TITLES = {
    "Sci-Fi": "Mind-Expanding Sci-Fi", Comedy: "Feel-Good Comedies", Animation: "Animated Worlds",
    Thriller: "Edge-of-Your-Seat Thrillers", Horror: "Lights-Off Horror", Romance: "Romantic Favourites",
    Drama: "Critically Acclaimed Dramas", Action: "Adrenaline-Fuelled Action", Adventure: "Epic Adventures",
    Fantasy: "Fantasy & Magic", Crime: "Crime Stories", Mystery: "Twisty Mysteries", Family: "Family Night",
    History: "Based on History", War: "War Epics", Music: "Music & Musicals", Western: "Westerns",
  };
  const ROW_LIMIT = 30; // keep rows light when the catalogue has hundreds of films

  const state = {
    movies: [],
    byId: new Map(),
    liked: new Set(),
    disliked: new Set(),
    mood: "",
    query: "",
    scored: [],
    recMap: new Map(),
    taste: null,
    mode: "popular",
    becauseRows: [],
    watchedRows: [],
  };
  const bb = { key: "", items: [], i: 0, timer: null, mode: "popular", broader: false };
  let viewingStorage;
  try { viewingStorage = window.localStorage; } catch { /* session-only viewing */ }
  const viewing = new CinemagicViewingStore(viewingStorage);
  const preferences = new CinemagicPreferenceStore(viewingStorage);
  let preferenceSource = null;
  let preferenceWarningShown = false;
  let catalogue = null;
  let preferenceResolver = null;
  const providers = CinemagicProviders;
  const movieKey = (m) => providers.reference(m)?.key;
  const canWatch = (m) => !!providers.reference(m)?.tmdbId && providers.list().length > 0;
  const moviePlayer = new CinemagicMoviePlayer({ providers, viewing,
    onChange: () => { if (state.movies.length) { renderRows(); refresh(); } } });

  // ---------- persistence ----------
  function load() {
    preferenceSource = state.movies[0]?.source === "tmdb" ? "tmdb" : "curated";
    const saved = preferences.load(preferenceSource);
    state.liked = new Set(saved.liked);
    state.disliked = new Set(saved.disliked);
    state.mood = saved.mood;
  }
  function save() {
    if (!preferenceSource) return;
    const saved = preferences.save(preferenceSource, { liked: [...state.liked], disliked: [...state.disliked], mood: state.mood });
    if (!saved && !preferenceWarningShown) {
      preferenceWarningShown = true;
      toast("Your browser isn't allowing preferences to be saved. Changes will last for this session.");
    }
  }

  // ---------- helpers ----------
  // On GitHub Pages there is no Python server: the same engine runs in the browser.
  let engine = null;
  const STATIC_HOST = location.hostname.endsWith("github.io");
  async function useStaticEngine() {
    engine = await CinemagicEngine.load("data/model.json");
  }

  async function api(path, body, options = {}) {
    if (engine) return engine.handle(path, body);
    const res = await fetch(path, body
      ? { ...options, method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      : options);
    if (!res.ok) throw Object.assign(new Error(`${res.status} ${res.statusText}`), { status: res.status });
    return res.json();
  }
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const byId = (id) => catalogue?.get(id) || state.byId.get(id) || preferenceResolver?.get(id);
  const isSeen = (id) => state.liked.has(id) || state.disliked.has(id);
  const nextFrame = (fn) => requestAnimationFrame(() => requestAnimationFrame(fn));
  const personalised = () => state.mode !== "popular";

  function fallbackHTML(m) {
    const [c1, c2] = m.palette || ["#1f1f1f", "#7f1d1d"];
    return `<div class="fallback" style="--c1:${c1};--c2:${c2}"><span class="emoji">${icon("film")}</span><b>${esc(m.title)}</b></div>`;
  }
  function imgHTML(m, cls = "") {
    return m.poster
      ? `<img src="${esc(m.poster)}" alt="${esc(m.title)} poster" loading="lazy" decoding="async" data-fallback="${m.id}" class="${cls}">`
      : fallbackHTML(m);
  }
  function matchHTML(m) {
    const rec = state.recMap.get(m.id);
    return rec && personalised() ? `<span class="match">${rec.match}% Match</span>` : "";
  }
  function metaHTML(m) {
    return `${matchHTML(m)}<span>${m.year || "Year unknown"}</span><span class="rating">${icon("star")}${m.rating || "Not rated"}</span>`;
  }

  // ---------- tiles & rows ----------
  function tileHTML(m, { i = 0, fresh = false, showMatch = false, isNew = false } = {}) {
    const rec = state.recMap.get(m.id);
    return `
      <div class="tile ${fresh ? "fresh" : ""} ${state.disliked.has(m.id) ? "noped" : ""}" data-id="${m.id}" tabindex="0" role="button" aria-label="${esc(m.title)}" style="--i:${i}">
        ${imgHTML(m)}
        ${state.liked.has(m.id) ? `<span class="badge-love" aria-hidden="true">${icon("heart")}</span>` : ""}
        ${showMatch && rec && personalised() ? `<span class="badge-match">${rec.match}%</span>` : ""}
        ${isNew ? `<span class="badge-new">NEW PICK</span>` : ""}
        ${rec?.dynamic && !isNew ? `<span class="badge-discovered">Discovered</span>` : ""}
      </div>`;
  }

  function top10TileHTML(m, rank) {
    return `
      <div class="tile" data-id="${m.id}" tabindex="0" role="button" aria-label="Number ${rank}: ${esc(m.title)}">
        <div class="rank" aria-hidden="true">${rank}</div>
        <div class="poster-box">${imgHTML(m)}${state.liked.has(m.id) ? `<span class="badge-love" aria-hidden="true">${icon("heart")}</span>` : ""}</div>
      </div>`;
  }

  function searchTileHTML(m) {
    const image = m.backdrop || m.poster;
    return `<div class="tile search-tile ${state.disliked.has(m.id) ? "noped" : ""}" data-id="${m.id}" tabindex="0" role="button" aria-label="${esc(m.title)}${m.year ? ` (${esc(m.year)})` : ""}">
      <div class="search-artwork${m.backdrop ? "" : " poster-artwork"}">${image ? `<img src="${esc(image)}" alt="" loading="lazy" decoding="async" data-fallback="${m.id}">` : fallbackHTML(m)}
        ${state.liked.has(m.id) ? `<span class="badge-love" aria-hidden="true">${icon("heart")}</span>` : ""}
      </div><div class="search-caption"><span class="search-title">${esc(m.title)}</span><span class="search-year">${esc(m.year || "Year unknown")}</span></div>
    </div>`;
  }

  function rowHTML(row, r, isStatic) {
    if (!row.items.length && !row.empty) return "";
    if (row.key === "search") return `<section class="row search-results static" id="row-search" data-row="search" aria-labelledby="searchHeading" aria-busy="${!!catalogue?.state.loading}">
      <div class="row-head"><h1 id="searchHeading">Movies</h1><p class="row-sub">${row.title}</p></div>
      <div class="search-grid">${row.items.map(searchTileHTML).join("") || `<p class="empty">${esc(row.empty)}</p>`}</div>
      ${searchControlsHTML()}<p class="search-hint">Looking for a feeling? Describe a mood and press Enter.</p>
    </section>`;
    const tiles = row.items.length
      ? row.items.map((m, i) => row.kind === "top10" ? top10TileHTML(m, i + 1) : tileHTML(m, {
          i, showMatch: row.showMatch, fresh: row.freshIds?.has(m.id), isNew: row.freshIds?.has(m.id),
        })).join("")
      : `<div class="row-empty"><p class="empty">${esc(row.empty)}</p>${row.showAllPicks ? `<button class="btn btn-grey btn-sm" data-show-all-picks>Show all picks</button>` : ""}</div>`;
    return `
      <section class="row ${row.kind === "top10" ? "top10" : ""} ${isStatic ? "static" : ""}" id="row-${row.key}" data-row="${row.key}" style="--r:${r}">
        <div class="row-head">
          <h2 class="row-title">${row.title}</h2>
          ${row.sub ? `<span class="row-sub">${row.sub}</span>` : ""}
          ${row.sub2 ? `<span class="row-sub">${esc(row.sub2)}</span>` : ""}
        </div>
        <div class="row-wrap">
          <button class="arrow left" data-scroll="-1" aria-label="Scroll left">${icon("chevronLeft")}</button>
          <div class="scroller">${tiles}</div>
          <button class="arrow right" data-scroll="1" aria-label="Scroll right">${icon("chevronRight")}</button>
        </div>
      </section>`;
  }

  function searchControlsHTML() {
    const remote = catalogue?.state;
    const live = catalogue?.live;
    const language = catalogue?.language || "en-US";
    const languages = [["en-US", "English"], ["hi-IN", "Hindi"], ["ta-IN", "Tamil"], ["te-IN", "Telugu"], ["ja-JP", "Japanese"], ["ko-KR", "Korean"], ["fr-FR", "French"], ["es-ES", "Spanish"]];
    const status = remote?.error || (remote?.loading ? "Searching movies…" : remote?.stale ? "Showing cached results; live search is temporarily unavailable." : live ? `Page ${remote?.page || 1} · Movie details language does not change playback audio` : "Downloaded catalogue only · Live search is available in the configured backend app");
    return `<div class="catalogue-controls">${live ? `<label for="catalogueLanguage">Details language</label><select id="catalogueLanguage">${languages.map(([code, label]) => `<option value="${code}" ${code === language ? "selected" : ""}>${label}</option>`).join("")}</select>` : ""}<span role="status">${esc(status)}</span>${live && remote?.page < remote?.totalPages ? `<button class="btn btn-grey btn-sm" data-search-more ${remote.loading ? "disabled" : ""}>${remote.loading ? "Loading…" : "Load more"}</button>` : ""}${remote?.error ? `<button class="btn btn-grey btn-sm" data-search-retry>Retry search</button>` : ""}</div>`;
  }

  function discoveryNote() {
    const d = state.discovery, v = state.viewingStatus;
    const parts = [];
    if (d?.status === "unavailable") parts.push("Live discovery is unavailable right now · showing the downloaded catalogue");
    else if (d) {
      parts.push(d.recommended ? `includes ${d.recommended} newly discovered film${d.recommended > 1 ? "s" : ""}` : "no new discoveries made the cut");
      if (d.status === "partial") parts.push("some discovery sources were unavailable");
      if (d.stale) parts.push("using cached results");
    }
    // Watched films outside the catalogue apply once their metadata is cached (S5C).
    if (v?.pending) parts.push(`${v.pending} watched film${v.pending > 1 ? "s" : ""} waiting for metadata`);
    return parts.join(" · ");
  }

  function buildRows(freshIds) {
    const rows = [];
    const q = state.query.toLowerCase();
    const notDisliked = (m) => !state.disliked.has(m.id);

    if (q) {
      const local = [...state.movies, ...(catalogue?.savedMovies() || [])].filter((m) =>
        [m.title, m.original_title, ...(m.alternative_titles || []), ...m.tags, ...m.genres].some((text) => String(text || "").toLowerCase().includes(q)));
      const remote = catalogue?.state;
      const hits = catalogue?.live && remote?.query.toLowerCase() === q && !remote.error ? remote.items : [...new Map([...(remote?.items || []), ...local].map((movie) => [movie.id, movie])).values()];
      return [{
        key: "search", title: `Results for “${esc(state.query)}”`, items: hits,
        empty: remote?.loading ? "Searching movies…" : "No titles match. Press Enter to search by mood instead.",
      }];
    }

    const pickTitle = {
      popular: "Trending Now",
      mood: `Because you're in the mood for “${esc(state.mood)}”`,
      personal: state.mood ? `Top Picks for You × “${esc(state.mood)}”` : "Top Picks for You",
      viewing: "Inspired by Your Viewing",
    }[state.mode];
    rows.push({
      key: "picks", title: pickTitle, items: state.scored.slice(0, 14), showMatch: true, freshIds,
      sub: viewing.options().recent_playback_only ? "Only titles with playback recorded on this device in the last 7 days; availability may change" : state.mode === "viewing" ? "A small influence from substantial viewing; likes and dislikes remain explicit" : state.mode === "personal" ? "Re-ranked live from every like and pass" : state.mode === "popular" ? "Like a few titles to make this yours" : "",
      sub2: discoveryNote(),
      empty: viewing.options().recent_playback_only ? "No matching titles have recent playback evidence on this device. Show all picks to discover more movies." : "Nothing matched that mood. Try different words.",
      showAllPicks: viewing.options().recent_playback_only,
    });

    const myList = [...state.liked].reverse().map(byId).filter(Boolean);
    if (myList.length) rows.push({ key: "mylist", title: "My List", items: myList });

    const savedMovies = new Map([...state.movies, ...(catalogue?.savedMovies() || [])].map((m) => [movieKey(m), m]));
    const continuing = viewing.continueKeys().map((key) => savedMovies.get(key)).filter(Boolean);
    if (continuing.length) rows.splice(q ? 1 : 0, 0, { key: "continue", title: "Continue Watching",
      items: continuing, sub: "Open a movie to resume or start over" });
    const watchlist = viewing.watchlistKeys().map((key) => savedMovies.get(key)).filter(Boolean);
    rows.push({ key: "watchlist", title: "Watchlist", items: watchlist,
      sub: "Saved for later, independently of your likes", empty: "Open a movie and choose Save to watchlist." });

    for (const { source, items } of state.becauseRows) {
      const list = items.filter((m) => !isSeen(m.id));
      if (source && list.length) rows.push({ key: `because-${source.id}`, title: `Because you loved ${esc(source.title)}`, items: list, showMatch: true });
    }
    for (const { source, items } of state.watchedRows) {
      const list = items.filter((m) => !isSeen(m.id));
      if (source && list.length) rows.push({ key: `watched-${source.source}-${source.id}`,
        title: `Because you watched ${esc(source.title)}`, items: list,
        sub: "At least 30% and 2 minutes measured playing · Viewing does not mark a film as liked" });
    }

    const top10 = [...state.movies].filter(notDisliked).sort((a, b) => b.rating - a.rating).slice(0, 10);
    rows.push({ key: "top10", kind: "top10", title: "Top 10 Highest Rated", items: top10 });

    const counts = {};
    state.movies.forEach((m) => m.genres.forEach((g) => (counts[g] = (counts[g] || 0) + 1)));
    const base = Object.keys(counts).filter((g) => counts[g] >= 5).sort((a, b) => counts[b] - counts[a]);
    const tasteGenres = (state.taste?.genres || []).map((g) => g.name).filter((g) => base.includes(g));
    const ordered = [...tasteGenres, ...base.filter((g) => !tasteGenres.includes(g))].slice(0, 9);
    const scoreOf = (m) => state.recMap.get(m.id)?.score ?? -1;
    for (const g of ordered) {
      const items = state.movies.filter((m) => m.genres.includes(g) && notDisliked(m))
        .sort((a, b) => personalised() ? scoreOf(b) - scoreOf(a) || b.rating - a.rating : b.rating - a.rating)
        .slice(0, ROW_LIMIT);
      rows.push({
        key: `genre-${g.toLowerCase()}`, title: esc(GENRE_TITLES[g] || `${g} Movies`), items, showMatch: true,
        sub: tasteGenres.includes(g) ? "From your Taste DNA" : "",
      });
    }
    return rows;
  }

  function renderRows(freshIds = null) {
    document.body.classList.toggle("searching", !!state.query);
    $("#searchClear").hidden = !state.query;
    const restoreLanguageFocus = document.activeElement?.id === "catalogueLanguage";
    const list = $("#rowList");
    const prevKeys = new Set($$(".row", list).map((r) => r.dataset.row));
    const scroll = new Map($$(".row", list).map((r) => [r.dataset.row, $(".scroller", r)?.scrollLeft || 0]));
    list.innerHTML = buildRows(freshIds).map((row, r) => rowHTML(row, r, prevKeys.has(row.key))).join("");
    $$(".row", list).forEach((r) => {
      const left = scroll.get(r.dataset.row);
      if (left && $(".scroller", r)) $(".scroller", r).scrollLeft = left;
    });
    if (restoreLanguageFocus) $("#catalogueLanguage")?.focus();
  }

  function renderOnboard() {
    const n = Math.round((state.taste?.confidence || 0) * 5);
    $("#onboard").innerHTML = n >= 3 ? "" : `
      <div class="onboard">
        <b>${["Love 3 titles to unlock your Taste DNA", "Great start! Love 2 more…", "One more like and your profile unlocks…"][n]}</b>
        <span>Hover any poster and tap the heart, or press <kbd>L</kbd> on a focused title.</span>
        <div class="steps">${[0, 1, 2].map((i) => `<i class="${i < n ? "on" : ""}"></i>`).join("")}</div>
      </div>`;
  }

  function renderMoods() {
    const known = MOODS.some(([, , q]) => q === state.mood);
    $("#moods").innerHTML =
      MOODS.map(([emo, label, q]) => `<button class="mood ${q === state.mood ? "active" : ""}" data-mood="${esc(q)}">${icon(emo)}<span>${esc(label)}</span></button>`).join("") +
      (state.mood && !known ? `<button class="mood active" data-mood="${esc(state.mood)}">${icon("search")}<span>${esc(state.mood)}</span>${icon("x")}</button>` : "");
  }

  // ---------- billboard ----------
  function setBillboardItems(items, { mode = state.mode, broader = false } = {}) {
    if (!items.length) {
      clearTimeout(bb.timer);
      bb.key = ""; bb.items = []; bb.i = 0; bb.timer = null; bb.broader = false;
      $("#bbBg").replaceChildren();
      $(".billboard").classList.remove("has-backdrop");
      $("#bbPoster").hidden = true;
      $("#bbPoster").removeAttribute("src");
      $("#bbDots").replaceChildren();
      $("#bbContent").innerHTML = `<div class="bb-kicker">Keep exploring</div><h1 class="bb-title">No matching picks yet</h1>
        <p class="bb-overview" role="status">${viewing.options().recent_playback_only ? "Your recent-playback filter has no matching titles. Show all picks to discover more movies." : "Try a different mood or browse the catalogue to find your next movie."}</p>
        <div class="bb-actions">${viewing.options().recent_playback_only ? `<button class="btn btn-white" data-show-all-picks>Show all picks</button>` : ""}<a class="btn btn-grey" href="#rows">Browse movies</a></div>`;
      return;
    }
    const key = JSON.stringify([mode, broader, state.mood, items.map((m) => [m.id, m.score, m.reason])]);
    if (key === bb.key) return;
    bb.key = key;
    bb.items = items;
    bb.mode = mode;
    bb.broader = broader;
    showBillboard(0);
  }

  function showBillboard(i) {
    clearTimeout(bb.timer);
    bb.i = i;
    const m = bb.items[i];
    if (!m) return;
    const rec = bb.broader ? null : state.recMap.get(m.id);

    const bg = $("#bbBg");
    const bgSrc = m.backdrop || m.poster;
    $(".billboard").classList.toggle("has-backdrop", !!m.backdrop);
    if (bgSrc) {
      const img = new Image();
      img.className = m.backdrop ? "bb-img backdrop" : "bb-img";
      img.alt = "";
      img.src = bgSrc;
      bg.appendChild(img);
      (img.decode ? img.decode() : Promise.resolve()).catch(() => {}).finally(() => nextFrame(() => img.classList.add("show")));
      setTimeout(() => { while (bg.children.length > 1) bg.firstElementChild.remove(); }, 1300);
    } else bg.replaceChildren();
    const poster = $("#bbPoster");
    poster.hidden = !m.poster || !!m.backdrop; // a real backdrop says it all
    if (!poster.hidden) {
      poster.src = m.poster;
      poster.alt = `${m.title} poster`;
      poster.style.animation = "none";
      void poster.offsetWidth;
      poster.style.animation = "";
    }

    const kicker = bb.broader ? "More to discover" : {
      popular: `<b>#${i + 1}</b> Trending tonight`,
      mood: `<b>For</b> “${esc(state.mood)}”`,
      personal: `<b>#${i + 1}</b> Top pick for you`,
      viewing: `<b>For you</b> Inspired by your viewing`,
    }[bb.mode];
    const reason = bb.broader ? "No recent-playback matches. Showing broader suggestions." : rec?.because ? `Because you ${rec.because.type === "watched" ? "watched" : "loved"} <b>&nbsp;${esc(rec.because.title)}</b>` : bb.mode === "mood" && rec ? esc(rec.reason) : "";
    const content = $("#bbContent");
    content.innerHTML = `
      <div class="bb-kicker">${kicker}</div>
      <h1 class="bb-title">${esc(m.title)}</h1>
      <div class="meta">${metaHTML(m)}<span>${m.genres.map(esc).join(" · ")}</span></div>
      <div>
        <p class="bb-overview">${esc(m.overview)}</p>
        ${reason ? `<p class="bb-reason">${reason}</p>` : ""}
      </div>
      <div class="bb-actions">
        ${bb.broader ? `<button class="btn btn-grey" data-show-all-picks>Show all picks</button>` : ""}
        ${canWatch(m) ? `<button class="btn btn-white" data-watch="${m.id}">${icon("play")}Watch movie</button>` : ""}
        ${m.trailer ? `<button class="btn ${canWatch(m) ? "btn-grey" : "btn-white"}" data-trailer="${m.id}">${icon("play")}Play Trailer</button>` : ""}
        <button class="btn ${m.trailer ? "btn-grey" : "btn-white"}" data-open="${m.id}">${icon("info")}More Info</button>
        <button class="btn btn-grey" data-act="love" data-id="${m.id}" aria-pressed="${state.liked.has(m.id)}">${icon("heart")}Love it</button>
        <button class="btn btn-grey" data-act="nope" data-id="${m.id}" aria-pressed="${state.disliked.has(m.id)}" aria-label="Not for me">${icon("x")}</button>
      </div>`;
    content.classList.remove("bb-anim");
    void content.offsetWidth;
    content.classList.add("bb-anim");

    $("#bbDots").innerHTML = bb.items.length > 1 ? bb.items.map((_, k) =>
      `<button class="bb-dot ${k === i ? "active" : ""} ${k < i ? "done" : ""}" data-bb="${k}" aria-label="Show pick ${k + 1}" style="--dur:${ROTATE_MS}ms"><i></i></button>`).join("") : "";
    if (!reducedMotion && bb.items.length > 1 && !$("#modal").classList.contains("open")) bb.timer = setTimeout(() => showBillboard((i + 1) % bb.items.length), ROTATE_MS);
  }

  // ---------- hover preview ----------
  let hoverTimer = null;
  let previewTile = null;

  function showPreview(tile) {
    const m = byId(Number(tile.dataset.id));
    if (!m || !tile.isConnected) return;
    const pv = $("#preview");
    const box = ($(".poster-box", tile) || tile).getBoundingClientRect();
    const w = Math.max(box.width * 1.6, 270);
    const headH = (w * 9) / 16;
    const left = Math.min(Math.max(box.left + box.width / 2 - w / 2, 8), innerWidth - w - 8) + scrollX;
    const top = box.top + scrollY + box.height / 2 - headH / 2 - 40;
    pv.style.cssText = `left:${left}px;top:${top}px;width:${w}px;transform-origin:${box.left + scrollX + box.width / 2 - left}px ${headH / 2}px`;
    const rec = state.recMap.get(m.id);
    const titleLeft = 12 + headH * 0.82 * (2 / 3) + 14;
    pv.innerHTML = `
      <div class="pv-head" data-open="${m.id}">
        ${m.backdrop ? `<img class="backdrop" src="${esc(m.backdrop)}" alt="">`
          : m.poster ? `<img class="blur" src="${esc(m.poster)}" alt=""><img class="sharp" src="${esc(m.poster)}" alt="">` : fallbackHTML(m)}
        <div class="pv-title" style="left:${m.backdrop ? 14 : titleLeft}px">${esc(m.title)}</div>
      </div>
      <div class="pv-body">
        <div class="pv-actions">
          ${canWatch(m) ? `<button class="circle solid" data-watch="${m.id}" aria-label="Watch movie" title="Watch movie">${icon("play")}</button>` : m.trailer ? `<button class="circle solid" data-trailer="${m.id}" aria-label="Play trailer" title="Play trailer">${icon("play")}</button>`
            : `<button class="circle solid" data-open="${m.id}" aria-label="More info" title="More info">${icon("info")}</button>`}
          <button class="circle love" data-act="love" data-id="${m.id}" aria-pressed="${state.liked.has(m.id)}" aria-label="Love it" title="Love it (L)">${icon("heart")}</button>
          <button class="circle nope" data-act="nope" data-id="${m.id}" aria-pressed="${state.disliked.has(m.id)}" aria-label="Not for me" title="Not for me (D)">${icon("x")}</button>
          <button class="circle more" data-open="${m.id}" aria-label="Details" title="Details">${icon("chevronDown")}</button>
        </div>
        <div class="meta" style="font-size:.85rem">${metaHTML(m)}</div>
        <div class="pv-genres">${m.genres.map((g) => `<span>${esc(g)}</span>`).join("")}</div>
        ${rec?.because ? `<p class="pv-reason">Because you ${rec.because.type === "watched" ? "watched" : "loved"} <b>${esc(rec.because.title)}</b></p>`
          : rec?.shared?.length && personalised() ? `<p class="pv-reason">${rec.shared.map((t) => esc(prettyTag(t))).join(" · ")}</p>` : ""}
      </div>`;
    pv.setAttribute("aria-hidden", "false");
    previewTile = tile;
    void pv.offsetWidth; // commit the closed state so the open transition runs
    pv.classList.add("open");
  }

  function hidePreview() {
    clearTimeout(hoverTimer);
    const pv = $("#preview");
    pv.classList.remove("open");
    pv.setAttribute("aria-hidden", "true");
    previewTile = null;
  }

  function bindPreview() {
    if (!canHover) return;
    const list = $("#rowList");
    list.addEventListener("pointerover", (e) => {
      const tile = e.target.closest(".tile[data-id]");
      if (!tile || tile === previewTile) return;
      clearTimeout(hoverTimer);
      hoverTimer = setTimeout(() => showPreview(tile), 450);
    });
    list.addEventListener("pointerout", (e) => {
      const tile = e.target.closest(".tile[data-id]");
      if (tile && !tile.contains(e.relatedTarget)) clearTimeout(hoverTimer);
    });
    $("#preview").addEventListener("pointerleave", hidePreview);
    list.addEventListener("scroll", hidePreview, true);
  }

  // ---------- drawer ----------
  function preferenceMessage(id) {
    if (state.movies[0]?.source !== "tmdb" || state.byId.has(id) || !state.liked.has(id) && !state.disliked.has(id)) return "";
    const info = preferenceResolver?.status(`tmdb:${id}`);
    if (info?.status === "applied") return "Preference applied to your taste using resolved movie metadata.";
    return info?.reason || "Preference saved. Waiting for movie metadata before it can affect your taste.";
  }

  function renderDrawer() {
    const focusedControl = ["useViewing", "recentPlaybackOnly", "clearViewing"].includes(document.activeElement?.id) ? document.activeElement.id : null;
    const options = viewing.options();
    const n = state.liked.size;
    const resolution = preferenceResolver?.summary();
    const appliedLikes = state.movies.filter(m => state.liked.has(m.id) && !state.disliked.has(m.id)).length + (preferenceResolver?.payload()?.positive_count || 0);
    const taste = state.taste || { genres: [], tags: [], confidence: 0 };
    const pct = Math.round(taste.confidence * 100);
    const top = taste.genres.slice(0, 2).map((g) => g.name.toLowerCase());
    const hint = appliedLikes === 0 ? "Love a few titles and I'll map your taste." : appliedLikes < 3 ? `${3 - appliedLikes} more applied likes to unlock your full profile.` : top.length ? `You're drawn to ${top.join(" & ")}.` : "Your resolved movie choices shape your picks.";
    const pick = (id, cls) => {
      const m = byId(id);
      const info = state.movies[0]?.source === "tmdb" && !state.byId.has(id) ? preferenceResolver?.status(`tmdb:${id}`) : null;
      return `<div class="pick ${cls}" title="${esc(m?.title || `Movie ${id}`)}${info ? ` · ${esc(info.status)}: ${esc(info.reason || "Included in taste")}` : ""}">${m ? imgHTML(m) : `<span class="pending-title">Movie ${id}</span>`}${info && info.status !== "applied" ? `<span class="preference-badge">${esc(info.status)}</span>` : ""}<button data-remove="${id}" aria-label="Remove ${esc(m?.title || `Movie ${id}`)}">${icon("x")}</button></div>`;
    };
    $("#drawer").innerHTML = `
      <button class="icon-btn drawer-close" data-close-drawer aria-label="Close">${icon("x")}</button>
      <h2>Your Taste DNA</h2>
      <p class="hint">${preferenceWarningShown ? "Session only: browser storage is unavailable." : "Saved in this browser. No account needed."}</p>
      <p class="hint">${hint}</p>
      ${resolution && resolution.applied + resolution.pending + resolution.unavailable ? `<div class="preference-resolution"><p class="hint" role="status">External choices: ${resolution.applied} applied · ${resolution.pending} pending · ${resolution.unavailable} unavailable.</p><p class="hint">Only resolved metadata affects taste. ${resolution.stale ? "Some cached features may be out of date. " : ""}Feature language is English; display language stays independent.</p>${resolution.pending || resolution.unavailable || resolution.stale ? `<button class="btn btn-grey btn-sm" data-retry-preferences>Retry metadata</button>` : ""}${preferenceResolver.storageFailed ? `<p class="hint">Feature caching is unavailable in this browser; saved choices will resolve again next visit.</p>` : ""}</div>` : ""}
      <div class="viewing-options">
        <label><input type="checkbox" id="useViewing" ${options.use_viewing ? "checked" : ""}> Use viewing history <span>Experimental</span></label>
        <p class="hint">Starts after at least 30% and 2 minutes measured playing. Earlier resume positions aren't treated as watched time. Likes and dislikes stay primary; playback problems aren't ratings.</p>
        <label><input type="checkbox" id="recentPlaybackOnly" ${options.recent_playback_only ? "checked" : ""}> Top picks: only recently played on this device</label>
        <p class="hint">Only films with at least 10 seconds measured playing in the last 7 days. A later source error invalidates that source's record. If there are no matches, the banner offers broader suggestions.</p>
        <button class="btn btn-grey btn-sm" id="clearViewing">Clear viewing history</button>
      </div>
      <div class="meter-row"><span>Taste confidence</span><span>${pct}%</span></div>
      <div class="meter-track"><div class="meter-fill" data-w="${pct}"></div></div>
      <h3>Genre affinity</h3>
      <div class="dna">${taste.genres.length ? taste.genres.map((g) => `
        <div class="dna-row"><span>${esc(g.name)}</span><div class="dna-bar"><i data-w="${g.weight * 100}"></i></div><em>${Math.round(g.weight * 100)}</em></div>`).join("")
        : `<p class="empty">Nothing yet.</p>`}</div>
      <h3>Your vibe</h3>
      <div class="chips">${taste.tags.length ? taste.tags.map((t) => `<span class="chip">#${esc(prettyTag(t))}</span>`).join("") : `<p class="empty">Your favourite moods will appear here.</p>`}</div>
      <h3>My List · ${n}</h3>
      <div class="pick-list">${[...state.liked].reverse().map((id) => pick(id, "")).join("") || `<p class="empty" style="grid-column:1/-1">No loved titles yet.</p>`}</div>
      ${state.disliked.size ? `<h3>Not for me · ${state.disliked.size}</h3><div class="pick-list">${[...state.disliked].map((id) => pick(id, "nope")).join("")}</div>` : ""}
      <div class="drawer-foot">
        <button class="btn btn-grey btn-sm" id="resetBtn">${icon("reset")}Start over</button>
        <button class="btn btn-white btn-sm" data-how>${icon("help")}How it works</button>
      </div>`;
    if ($("#drawer").classList.contains("open")) animateBars($("#drawer"));
    $("#avatarRing").style.strokeDashoffset = RING * (1 - taste.confidence);
    $$("[data-preference-status]").forEach(el => {
      const message = preferenceMessage(Number(el.dataset.preferenceStatus));
      el.textContent = message; el.hidden = !message;
    });
    if (focusedControl) $(`#${focusedControl}`)?.focus();
  }

  function animateBars(root) {
    void root.offsetWidth; // commit the 0-width state so the width transition runs
    $$("[data-w]", root).forEach((el) => (el.style.width = `${el.dataset.w}%`));
  }
  function toggleDrawer(open) {
    hidePreview();
    $("#drawer").classList.toggle("open", open);
    $("#drawer").setAttribute("aria-hidden", String(!open));
    $("#scrim").classList.toggle("open", open);
    if (open) { animateBars($("#drawer")); setTimeout(() => $("#drawer .drawer-close")?.focus(), 100); }
  }

  // ---------- data refresh ----------
  let refreshTimer = null;
  let refreshSeq = 0;
  let refreshController = null;
  function refresh({ announce = false, immediate = false } = {}) {
    preferenceResolver?.sync(state.liked, state.disliked);
    clearTimeout(refreshTimer);
    const seq = ++refreshSeq;
    refreshTimer = setTimeout(async () => {
      refreshController?.abort();   // an older pool must never overwrite the current rows
      const controller = refreshController = new AbortController();
      const recent = [...state.liked].filter((id) => state.byId.has(id)).slice(-2).reverse();
      const request = { liked: [...state.liked], disliked: [...state.disliked], mood: state.mood || null, k: 100, ...viewing.request() };
      const external = preferenceResolver?.payload();
      if (external) request.external_preferences = external;
      if (!engine && catalogue?.discovery) request.discover = true;   // backend-only live retrieval
      try {
        const [out, ...sims] = await Promise.all([
          api("/api/recommend", request, { signal: controller.signal }),
          ...recent.map((id) => api(`/api/movies/${id}/similar?k=14`)),
        ]);
        if (seq !== refreshSeq) return; // superseded by a newer request
        // Discovered titles are ordinary TMDB movies from here on: details, likes, watchlist, playback.
        out.items.filter((m) => m.dynamic).forEach((m) => catalogue?.register(m));
        state.discovery = out.discovery || null;
        state.viewingStatus = out.viewing_status || null;
        let broader = null;
        if (request.recent_playback_only && !out.items.length) {
          try { broader = await api("/api/recommend", { ...request, recent_playback_only: false }); }
          catch { /* Keep the empty-state recovery usable if broader discovery fails. */ }
          if (seq !== refreshSeq) return;
        }
        const prevPicks = new Set(state.scored.slice(0, 14).map((m) => m.id));
        state.scored = out.items;
        state.recMap = new Map(out.items.map((r) => [r.id, r]));
        state.taste = out.taste;
        state.mode = out.mode;
        const becauseRows = new Map([...recent.map((id, k) => ({ source: byId(id), items: sims[k] })), ...(out.because_rows || [])].map(row => [row.source.id, row]));
        state.becauseRows = [...state.liked].filter(id => becauseRows.has(id)).slice(-2).reverse().map(id => becauseRows.get(id));
        state.watchedRows = out.watched_rows || [];

        const fresh = announce && prevPicks.size ? new Set(state.scored.slice(0, 14).map((m) => m.id).filter((id) => !prevPicks.has(id))) : null;
        renderOnboard();
        renderMoods();
        renderRows(fresh);
        setBillboardItems((broader?.items.length ? broader.items : state.scored).slice(0, 5),
          { mode: broader?.items.length ? broader.mode : state.mode, broader: !!broader?.items.length });
        renderDrawer();
        if (announce && fresh) toast(fresh.size ? `Taste updated: ${fresh.size} new pick${fresh.size > 1 ? "s" : ""} for you` : "Taste updated: picks re-ranked");
      } catch (err) {
        if (err.name === "AbortError" || seq !== refreshSeq) return;
        console.error(err);
        toast(err.status === 422 && request.external_preferences ? "Saved movie features are incompatible or invalid. Reload to refresh metadata; your choices are kept." : "Couldn't reach the recommender. Is the server running?");
      }
    }, immediate ? 0 : 150);
  }

  // ---------- interactions ----------
  function showAllPicks() {
    viewing.setOptions({ recent_playback_only: false });
    renderDrawer();
    refresh({ immediate: true });
  }

  function setTaste(id, kind, origin) {
    if (!byId(id)) return;
    const [set, other] = kind === "love" ? [state.liked, state.disliked] : [state.disliked, state.liked];
    const adding = !set.has(id);
    if (adding && set.size >= 10000) return toast("This browser has reached its saved preference limit. Remove a few choices before adding more.");
    other.delete(id);
    adding ? set.add(id) : set.delete(id);
    save();
    catalogue?.remember(byId(id));
    syncStates();
    if (adding && origin) burst(origin, kind === "love" ? "love" : "nope");
    if (adding && kind === "love" && state.liked.size === 3 && [...state.liked].every(key => state.byId.has(key))) toast("Taste DNA unlocked. Open your profile to see it.");
    if (adding && kind === "nope") toast(`Got it. Fewer films like ${byId(id).title}.`);
    refresh({ announce: true });
    renderDrawer();
    if (adding && !state.byId.has(id)) toast(preferenceMessage(id));
  }

  // Update pressed states and badges in place (rows re-render shortly after).
  function syncStates() {
    $$("[data-act][data-id]").forEach((b) => {
      const id = Number(b.dataset.id);
      b.setAttribute("aria-pressed", String(b.dataset.act === "love" ? state.liked.has(id) : state.disliked.has(id)));
    });
    $$(".tile[data-id]").forEach((t) => t.classList.toggle("noped", state.disliked.has(Number(t.dataset.id))));
  }

  const PARTICLES = {
    love: [icon("heart", "p-red"), icon("heart", "p-white"), '<i class="dot red"></i>'],
    nope: ['<i class="dot"></i>'],
    spark: [icon("star", "p-white"), '<i class="dot white"></i>'],
  };
  function burst(el, kind) {
    const glyphs = PARTICLES[kind];
    if (reducedMotion) return;
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    for (let i = 0; i < 14; i++) {
      const p = document.createElement("span");
      p.className = "particle";
      p.innerHTML = glyphs[i % glyphs.length];
      p.style.left = `${cx}px`;
      p.style.top = `${cy}px`;
      document.body.appendChild(p);
      const angle = (Math.PI * 2 * i) / 14 + Math.random() * 0.4;
      const dist = 40 + Math.random() * 60;
      p.animate([
        { transform: "translate(-50%,-50%) scale(0.4)", opacity: 1 },
        { transform: `translate(calc(-50% + ${Math.cos(angle) * dist}px), calc(-50% + ${Math.sin(angle) * dist - 20}px)) scale(${0.8 + Math.random() * 0.6})`, opacity: 0 },
      ], { duration: 700 + Math.random() * 300, easing: "cubic-bezier(.22,1,.36,1)" }).onfinish = () => p.remove();
    }
  }

  function toast(msg) {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    const wrap = $("#toasts");
    wrap.appendChild(t);
    while (wrap.children.length > 3) wrap.firstElementChild.remove();
    setTimeout(() => { t.classList.add("out"); t.addEventListener("animationend", () => t.remove(), { once: true }); }, 2600);
  }

  function conjure(mood, origin) {
    state.mood = mood.trim();
    save();
    state.query = "";
    $("#searchInput").value = "";
    catalogue?.setQuery("");
    hidePreview();
    if (state.mood) {
      if (origin) burst(origin, "spark");
      toast(`Finding films for “${state.mood}”…`);
    }
    renderMoods();
    refresh({ immediate: true });
    scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
  }

  // ---------- modal ----------
  let modalMovieId = null;
  let modalFocus = null;
  let modalFocusTimer = null;
  let modalEpoch = 0;
  let sourcePicker = null;
  function openModal(html) {
    modalEpoch++;
    hidePreview();
    sourcePicker?.destroy();
    sourcePicker = null;
    moviePlayer.close();
    clearTimeout(bb.timer);
    clearTimeout(modalFocusTimer);
    if (!$("#modal").classList.contains("open")) modalFocus = document.activeElement;
    $("#modalBody").classList.remove("has-player");
    $("#modalBody").innerHTML = `<button class="m-close" data-close aria-label="Close">${icon("x")}</button>${html}`;
    $("#modal").classList.add("open");
    $("#modal").scrollTop = 0;
    document.body.style.overflow = "hidden";
    modalFocusTimer = setTimeout(() => $("#modalBody .m-close")?.focus(), 60);
  }
  function closeModal() {
    modalEpoch++;
    const closingMovieId = modalMovieId;
    sourcePicker?.destroy();
    sourcePicker = null;
    moviePlayer.close();
    clearTimeout(modalFocusTimer);
    $("#modal").classList.remove("open");
    document.body.style.overflow = "";
    modalMovieId = null;
    $("#modalBody iframe")?.remove(); // stop trailer playback
    const focusTarget = modalFocus?.isConnected ? modalFocus : $(`.tile[data-id="${closingMovieId}"]`) || $("#searchToggle");
    focusTarget?.focus();
    if (!reducedMotion && bb.items.length > 1) bb.timer = setTimeout(() => showBillboard((bb.i + 1) % bb.items.length), ROTATE_MS);
  }

  function openWatch(id, startOver = false) {
    const m = byId(id);
    if (!providers.list().length) return toast("Movie sources are currently unavailable. You can still explore recommendations and trailers.");
    if (!canWatch(m)) return toast("Full-movie playback is unavailable for this title.");
    catalogue?.remember(m);
    modalMovieId = id;
    const saved = viewing.progress(movieKey(m));
    openModal(`
      <section class="movie-player" aria-label="Movie player">
        <div class="player-heading"><span class="player-kicker">NOW WATCHING</span>
          <h2 id="modalTitle">${esc(m.title)}</h2><p>${esc(m.year)} · Choose another source whenever you need to.</p></div>
        <div class="player-controls"><div class="source-picker" id="movieSourcePicker"></div><select id="movieSource" hidden aria-label="Source"></select>
          <div class="player-actions"><button class="btn btn-grey btn-sm" id="movieRestart">${icon("reset")}Start over</button>
          <button class="btn btn-grey btn-sm" data-watchlist="${m.id}" aria-pressed="${viewing.has(movieKey(m))}">${icon("film")}${viewing.has(movieKey(m)) ? "Saved to watchlist" : "Save to watchlist"}</button></div>
        </div>
        <p class="player-status" id="movieStatus" role="status" aria-live="polite"></p>
        <div class="movie-frame" id="movieFrame"></div>
        <div class="player-foot"><span>Playback is provided by the selected source. Press Play if your browser pauses it.</span>
          <button class="btn btn-grey btn-sm" id="movieForget">Remove from history</button></div>
      </section>`);
    $("#modalBody").classList.add("has-player");
    try {
      moviePlayer.open(m, { host: $("#movieFrame"), select: $("#movieSource"), status: $("#movieStatus"),
        restart: $("#movieRestart"), removeHistory: $("#movieForget") }, startOver);
      sourcePicker = new CinemagicSourcePicker($("#movieSourcePicker"), $("#movieSource"));
      if (saved.position > 10 && !startOver && !saved.completed) toast(`Resuming ${m.title}`);
    } catch {
      $("#movieStatus").textContent = "This movie could not be opened. Please choose another title.";
    }
  }

  function openTrailer(id) {
    const m = byId(id);
    if (!m?.trailer) return;
    modalMovieId = id;
    openModal(`
      <div class="trailer">
        <iframe src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(m.trailer)}?autoplay=1&rel=0" title="${esc(m.title)} trailer"
          allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen></iframe>
      </div>
      <div class="trailer-bar">
        <div><b>${esc(m.title)}</b> <span class="meta" style="display:inline-flex;margin-left:8px">${metaHTML(m)}</span></div>
        <div class="bb-actions" style="margin:0">
          <button class="btn btn-grey btn-sm" data-act="love" data-id="${m.id}" aria-pressed="${state.liked.has(m.id)}">${icon("heart")}Love it</button>
          <button class="btn btn-white btn-sm" data-open="${m.id}">${icon("info")}Details</button>
        </div>
      </div>`);
  }

  const runtimeText = (min) => (min ? `${Math.floor(min / 60)}h ${min % 60}m` : "");
  const prettyTag = (t) => (t === "sci-fi" ? t : t.replace(/-/g, " "));

  async function similarMovies(id, k = 30) {
    if (!engine || state.byId.has(id)) return api(`/api/movies/${id}/similar?k=${k}`);
    const cached = preferenceResolver?.records.get(`tmdb:${id}`);
    if (preferenceResolver?.compatible(cached)) return engine.similarExternal(cached, k);
    const movie = byId(id);
    if (movie?.full_details && movie.metadata_language === "en-US") return engine.similarExternal(engine.resolvePreference(movie), k);
    throw Object.assign(new Error("Similar movies need compatible cached English metadata or the backend app."), { status: 503 });
  }

  async function configurePreferenceResolver() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const meta = await api("/api/meta", null, { signal: controller.signal });
      preferenceResolver.configure(meta.preferences, { backend: !engine, localResolve: engine ? movie => engine.resolvePreference(movie) : null });
    } finally { clearTimeout(timeout); }
  }

  function discoverySources(info) {
    const names = { related: "TMDB related titles", taste: "your taste genres", new_release: "new releases", starter: "popular starter picks" };
    return (info?.sources || []).map((s) => names[s] || s).join(", ") || "TMDB discovery";
  }

  async function openMovie(id) {
    let m = byId(id);
    if (!m) return;
    modalMovieId = id;
    let detailsUnavailable = false;
    if (catalogue?.live && (!state.byId.has(id) || catalogue.get(id)) && !m.full_details) {
      openModal(`<div class="how"><h2 id="modalTitle">${esc(m.title)}</h2><p role="status">Loading movie details…</p></div>`);
      const epoch = modalEpoch;
      try { m = await catalogue.details(id); }
      catch { detailsUnavailable = true; }
      if (modalEpoch !== epoch || modalMovieId !== id) return;
    }
    catalogue?.remember(m);
    const rec = state.byId.has(id) || state.recMap.get(id)?.dynamic ? state.recMap.get(id) : null;
    const share = (k) => (rec ? (rec.breakdown[k] || 0) / Math.max(rec.score, 0.001) : 0);
    const why = rec && personalised() ? `
      <div class="why">
        <h4>Why we picked this · ${rec.match}% match</h4>
        <div class="dna">
          ${[["content", "Story & vibe match"], ["collab", rec.dynamic ? "Related to your likes (TMDB)" : "Fans like you"], ["quality", "Critic quality"], ["viewing", "Viewing history"]].filter(([k]) => k in rec.breakdown && rec.component_availability?.[k] !== false).map(([k, label]) => `
            <div class="dna-row"><span>${label}</span><div class="dna-bar"><i data-w="${share(k) * 100}"></i></div><em>${Math.round(share(k) * 100)}%</em></div>`).join("")}
        </div>
        ${!rec.because ? `<p class="pv-reason" style="margin-top:12px">${esc(rec.reason)}</p>` : ""}
        ${rec.shared.length ? `<p class="pv-reason" style="margin-top:12px">Shares: <b>${rec.shared.map((t) => esc(prettyTag(t))).join(", ")}</b></p>` : ""}
        ${rec.dynamic ? `<p class="pv-reason" style="margin-top:8px">Discovered outside the downloaded catalogue via ${esc(discoverySources(rec.discovery))}${rec.discovery.features === "summary" ? " · ranked from summary metadata (no keywords or cast yet)" : ""}${rec.component_availability?.collab === false ? " · no related-title evidence, so it is ranked on story match and quality only" : ""}</p>` : ""}
      </div>` : "";
    openModal(`
      <div class="m-head ${m.backdrop ? "has-backdrop" : ""}">
        ${m.backdrop ? `<img class="blur backdrop" src="${esc(m.backdrop)}" alt="">` : m.poster ? `<img class="blur" src="${esc(m.poster)}" alt="">` : ""}
        <div class="m-poster">${imgHTML(m)}</div>
        <div>
          <h2 id="modalTitle">${esc(m.title)}</h2>
          ${m.tagline ? `<p class="tagline">${esc(m.tagline)}</p>` : ""}
          <div class="bb-actions" style="margin-top:0">
            ${canWatch(m) ? `<button class="btn btn-white btn-sm" data-watch="${m.id}">${icon("play")}${viewing.progress(movieKey(m)).position > 10 && !viewing.progress(movieKey(m)).completed ? "Resume movie" : "Watch movie"}</button>` : `<span class="playback-unavailable">${providers.list().length ? "Full-movie playback unavailable for this catalogue entry." : "Movie sources are currently unavailable. Recommendations and trailers are still available."}</span>`}
            ${m.trailer ? `<button class="btn btn-white btn-sm" data-trailer="${m.id}">${icon("play")}Play Trailer</button>` : ""}
            <button class="btn btn-grey btn-sm" data-watchlist="${m.id}" aria-pressed="${viewing.has(movieKey(m))}">${viewing.has(movieKey(m)) ? "Saved to watchlist" : "Save to watchlist"}</button>
            <button class="btn btn-grey btn-sm" data-act="love" data-id="${m.id}" aria-pressed="${state.liked.has(m.id)}">${icon("heart")}Love it <kbd>L</kbd></button>
            <button class="btn btn-grey btn-sm" data-act="nope" data-id="${m.id}" aria-pressed="${state.disliked.has(m.id)}">${icon("x")}Not for me <kbd>D</kbd></button>
          </div>
        </div>
      </div>
      <div class="m-body">
        <div>
          <div class="meta">${metaHTML(m)}${m.runtime ? `<span>${runtimeText(m.runtime)}</span>` : ""}</div>
          <p class="overview">${esc(m.overview)}</p>
          ${m.original_title && m.original_title !== m.title ? `<p class="catalogue-note">Original title: ${esc(m.original_title)}</p>` : ""}
          ${m.original_language ? `<p class="catalogue-note">Original language: ${esc(m.original_language)}</p>` : ""}
          ${detailsUnavailable ? `<p class="catalogue-note">Full details are temporarily unavailable. Showing saved information.</p>` : ""}
          <p class="catalogue-note" data-preference-status="${id}" role="status" ${preferenceMessage(id) ? "" : "hidden"}>${esc(preferenceMessage(id))}</p>
          ${why}
        </div>
        <div class="m-side">
          ${m.director ? `<div><b>Director:</b> ${esc(m.director)}</div>` : ""}
          ${m.cast?.length ? `<div><b>Cast:</b> ${m.cast.map(esc).join(", ")}</div>` : ""}
          <div><b>Genres:</b> ${m.genres.map(esc).join(", ")}</div>
          ${m.tags.length ? `<div><b>This film is:</b> ${m.tags.slice(0, 8).map((t) => esc(prettyTag(t))).join(", ")}</div>` : ""}
          ${rec?.because ? `<div><b>Because you ${rec.because.type === "watched" ? "watched" : "loved"}:</b> ${esc(rec.because.title)}</div>` : ""}
        </div>
      </div>
      <div class="m-section">
        ${viewing.progress(movieKey(m)).position > 0 ? `<div class="history-actions"><button class="btn btn-grey btn-sm" data-start-over="${m.id}">Start over</button><button class="btn btn-grey btn-sm" data-forget="${m.id}">Remove from history</button></div>` : ""}
        <h3>More Like This</h3>
        <div class="like-grid" id="similarGrid">${Array.from({ length: 6 }, () => `<div class="like-card skeleton" style="height:230px"></div>`).join("")}</div>
      </div>`);
    animateBars($("#modalBody"));
    const detailEpoch = modalEpoch;
    try {
      const sims = (await similarMovies(id)).filter(s => !state.disliked.has(s.id)).slice(0, 9);
      if (modalMovieId !== id || modalEpoch !== detailEpoch) return;
      $("#similarGrid").innerHTML = sims.map((s, i) => {
        const r = state.recMap.get(s.id);
        const label = state.liked.has(s.id) ? `${icon("heart")}In My List` : r && personalised() ? `${r.match}% Match` : `${icon("star")}${s.rating}`;
        return `
          <article class="like-card" data-sim="${s.id}" style="--i:${i}" tabindex="0">
            <div class="lc-img">${s.backdrop ? `<img src="${esc(s.backdrop.replace("/w1280/", "/w500/"))}" alt="" loading="lazy">` : imgHTML(s)}</div>
            <div class="lc-body">
              <div class="lc-top"><span class="match">${label}</span>
                <button class="circle love" data-act="love" data-id="${s.id}" aria-pressed="${state.liked.has(s.id)}" aria-label="Love ${esc(s.title)}">${icon("heart")}</button></div>
              <div class="lc-title">${esc(s.title)}</div>
              <div>${s.year} · ${s.genres.slice(0, 2).map(esc).join(", ")}</div>
            </div>
          </article>`;
      }).join("") || `<p class="empty">No matching films have usable metadata in the current catalogue.</p>`;
    } catch (error) {
      if (modalMovieId === id && modalEpoch === detailEpoch) $("#similarGrid").innerHTML = `<p class="empty">${error.status === 503 ? "Similar movies need compatible cached metadata or an available backend." : "Couldn't load similar films. Please try again."}</p>`;
    }
  }

  async function openHow() {
    toggleDrawer(false);
    let meta = null;
    try { meta = await api("/api/meta"); } catch { /* offline */ }
    const w = meta?.weights || { content: 0.55, collab: 0.35, quality: 0.1 };
    const graph = meta?.collab_source === "tmdb-graph";
    openModal(`
      <div class="how">
        <h2 id="modalTitle">How the recommendations work</h2>
        <p>Cinemagic is a <b>hybrid recommender</b>. Every time you like or pass on a film, three signals are blended and re-ranked in a few milliseconds.</p>
        <div class="pipeline">
          <div class="stage">${icon("tag")}<b>Content · ${Math.round(w.content * 100)}%</b><p>TF-IDF vectors over genres, mood tags and plot. Your likes form a taste vector; cosine similarity finds neighbours.</p></div>
          <div class="stage">${icon("users")}<b>Collaborative · ${Math.round(w.collab * 100)}%</b><p>${graph
            ? `Item-item similarity over TMDB's audience-driven recommendation graph (${meta.graph_edges.toLocaleString()} links): films that share neighbours share fans.`
            : `Item-item adjusted-cosine similarity from ${meta ? meta.ratings.toLocaleString() : "thousands of"} ratings: "people who loved X also loved Y".`}</p></div>
          <div class="stage">${icon("star")}<b>Quality · ${Math.round(w.quality * 100)}%</b><p>A vote-weighted rating nudges towards good, well-known films, then MMR re-ranking (λ=${meta?.mmr_lambda ?? 0.75}) keeps every row diverse.</p></div>
        </div>
        ${catalogue?.discovery ? `<p style="margin-top:18px;font-size:.85rem"><b>Beyond the starter catalogue.</b> The ${meta?.movies ?? ""} downloaded films are a starting point. Each refresh also asks TMDB for films related to your likes, acclaimed films in your favourite genres and recent releases, then ranks them with the same engine; they carry a <b>Discovered</b> badge. Little-known titles are judged against the films they were found with, so a handful of votes cannot outrank a well-loved classic. Likes and passes on any TMDB film count once its details load. Results are cached for hours, so repeat visits are fast; if TMDB is unreachable, picks fall back to the starter catalogue and the Top Picks line says so.</p>`
          : `<p style="margin-top:18px;font-size:.85rem"><b>Starter catalogue only.</b> Live discovery of films beyond these ${meta?.movies ?? ""} needs the backend app with a TMDB key; this build ranks the downloaded catalogue and any saved film details it already has.</p>`}
        <p style="margin-top:18px;font-size:.85rem">"Because you loved…" only appears when a pick genuinely shares story, style or audience with that film; otherwise the reason says the pick is there to widen your taste.</p>
        <p style="margin-top:18px;font-size:.85rem">Optionally enable <b>Use viewing history</b> in My Taste. Substantial, measured viewing contributes up to 10% of the score; the existing blend retains 90%. Rewatching has a capped influence. Playback errors, source changes and seeking never create likes or dislikes. The recent-playback filter uses only this device's last 7 days of evidence.</p>
        ${meta ? `<div class="stats">
          <div class="stat"><b>${meta.movies}</b><span>films</span></div>
          ${graph
            ? `<div class="stat"><b>${meta.graph_edges.toLocaleString()}</b><span>graph links</span></div><div class="stat"><b>${meta.avg_degree}</b><span>avg. neighbours</span></div>`
            : `<div class="stat"><b>${meta.simulated_users}</b><span>simulated users</span></div><div class="stat"><b>${(meta.sparsity * 100).toFixed(0)}%</b><span>matrix sparsity</span></div>`}
          <div class="stat"><b>${meta.vocabulary.toLocaleString()}</b><span>TF-IDF terms</span></div>
        </div>` : ""}
        ${graph ? `<p style="margin-top:18px;font-size:.85rem">Movie data, posters and trailers from <a href="https://www.themoviedb.org" target="_blank" rel="noopener" style="color:#01b4e4">TMDB</a>.</p>` : ""}
        ${engine ? `<p style="margin-top:18px;font-size:.85rem">This build runs the recommender <b>entirely in your browser</b>: the model trained in Python is exported to JSON and scored by a JavaScript port of the same engine.</p>` : ""}
        <p style="margin-top:18px;font-size:.85rem">Search understands moods: type "make me cry" and press Enter. Shortcuts: <kbd>/</kbd> search · <kbd>L</kbd>/<kbd>D</kbd> love/pass a focused title · <kbd>Enter</kbd> details · <kbd>Esc</kbd> close.</p>
      </div>`);
  }

  // ---------- search ----------
  function bindSearch() {
    const form = $("#searchForm"), input = $("#searchInput");
    const open = () => { form.classList.add("open"); input.focus(); };
    const update = () => {
      const had = !!state.query;
      state.query = input.value.trim();
      hidePreview();
      catalogue?.setQuery(state.query);
      renderRows();
      if (state.query && !had) scrollTo({ top: 0, behavior: "auto" });
    };
    $("#searchClear").addEventListener("click", () => { input.value = ""; update(); open(); });
    $("#searchToggle").addEventListener("click", () => (form.classList.contains("open") && !input.value ? form.classList.remove("open") : open()));
    input.addEventListener("input", () => { if (!input.composing) update(); });
    input.addEventListener("compositionstart", () => { input.composing = true; });
    input.addEventListener("compositionend", () => { input.composing = false; update(); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { input.value = ""; update(); input.blur(); form.classList.remove("open"); }
    });
    input.addEventListener("blur", () => { if (!input.value) form.classList.remove("open"); });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      if (!input.value.trim()) return;
      conjure(input.value, $("#searchToggle"));
      input.blur();
    });
    return open;
  }

  // ---------- global wiring ----------
  function bindAll() {
    const openSearch = bindSearch();
    bindPreview();
    document.addEventListener("change", (event) => {
      if (event.target.id === "catalogueLanguage") catalogue?.setQuery(state.query, event.target.value);
      if (event.target.id === "useViewing" || event.target.id === "recentPlaybackOnly") {
        viewing.setOptions(event.target.id === "useViewing" ? { use_viewing: event.target.checked } : { recent_playback_only: event.target.checked });
        refresh({ immediate: true });
      }
    });

    // Swap broken posters for the generated gradient fallback.
    document.addEventListener("error", (e) => {
      const img = e.target;
      if (img.tagName === "IMG" && img.dataset.fallback) {
        const m = byId(Number(img.dataset.fallback));
        if (m) img.outerHTML = fallbackHTML(m);
      }
    }, true);

    document.addEventListener("click", (e) => {
      const t = e.target;
      if (t.closest(".logo, .nav-links a") && state.query) {
        $("#searchClear").click();
        $("#searchInput").blur();
        $("#searchForm").classList.remove("open");
      }
      if (t.closest("[data-show-all-picks]")) return showAllPicks();
      if (t.closest("[data-search-more]")) return catalogue?.more();
      if (t.closest("[data-search-retry]")) return catalogue?.setQuery(state.query);
      if (t.closest("[data-retry-preferences]")) {
        if (preferenceResolver?.config) return preferenceResolver.retry();
        configurePreferenceResolver().then(() => preferenceResolver.retry()).catch(() => toast("Movie metadata is still unavailable. Your preferences are saved."));
        return;
      }
      const act = t.closest("[data-act]");
      if (act) { e.stopPropagation(); setTaste(Number(act.dataset.id), act.dataset.act, act); return; }
      if (t.closest("[data-close]") || t.id === "modal") return closeModal();
      if (t.closest("[data-close-drawer]") || t.id === "scrim") return toggleDrawer(false);
      if (t.closest("#clearViewing")) { moviePlayer.forget(true); toast("Viewing history cleared. Your likes and watchlist are kept."); return; }
      if (t.closest("#resetBtn")) {
        state.liked.clear(); state.disliked.clear(); save();
        toggleDrawer(false);
        conjure("");
        toast("Fresh start. Tell me what you love.");
        return;
      }
      if (t.closest("[data-how]")) return openHow();
      const watchlist = t.closest("[data-watchlist]");
      if (watchlist) {
        const m = byId(Number(watchlist.dataset.watchlist));
        if (!m) return;
        catalogue?.remember(m);
        const saved = viewing.toggle(movieKey(m));
        $$(`[data-watchlist="${m.id}"]`).forEach((button) => { button.setAttribute("aria-pressed", String(saved)); button.textContent = saved ? "Saved to watchlist" : "Save to watchlist"; });
        renderRows();
        return;
      }
      const forget = t.closest("[data-forget]");
      if (forget) { const m = byId(Number(forget.dataset.forget)); viewing.removeProgress(movieKey(m)); refresh(); renderRows(); return openMovie(m.id); }
      const restart = t.closest("[data-start-over]");
      if (restart) return openWatch(Number(restart.dataset.startOver), true);
      const watch = t.closest("[data-watch]");
      if (watch) { hidePreview(); return openWatch(Number(watch.dataset.watch)); }
      const trailer = t.closest("[data-trailer]");
      if (trailer) { hidePreview(); return openTrailer(Number(trailer.dataset.trailer)); }
      const open = t.closest("[data-open]");
      if (open) { hidePreview(); return openMovie(Number(open.dataset.open)); }
      const sim = t.closest("[data-sim]");
      if (sim) return openMovie(Number(sim.dataset.sim));
      const tile = t.closest(".tile[data-id]");
      if (tile) { hidePreview(); return openMovie(Number(tile.dataset.id)); }
      const arrow = t.closest("[data-scroll]");
      if (arrow) {
        const sc = $(".scroller", arrow.parentElement);
        sc.scrollBy({ left: Number(arrow.dataset.scroll) * sc.clientWidth * 0.9, behavior: reducedMotion ? "auto" : "smooth" });
        return;
      }
      const dot = t.closest("[data-bb]");
      if (dot) return showBillboard(Number(dot.dataset.bb));
      const mood = t.closest("[data-mood]");
      if (mood) return conjure(mood.dataset.mood === state.mood ? "" : mood.dataset.mood, mood);
      const rm = t.closest("[data-remove]");
      if (rm) {
        const id = Number(rm.dataset.remove);
        state.liked.delete(id); state.disliked.delete(id); save();
        refresh({ announce: true });
      }
    });

    $("#howBtn").addEventListener("click", openHow);
    $("#tasteBtn").addEventListener("click", () => toggleDrawer(!$("#drawer").classList.contains("open")));

    document.addEventListener("keydown", (e) => {
      const typing = /INPUT|TEXTAREA/.test(document.activeElement?.tagName);
      const modalOpen = $("#modal").classList.contains("open");
      if (e.key === "Escape") {
        if (modalOpen) return closeModal();
        if ($("#drawer").classList.contains("open")) return toggleDrawer(false);
        return hidePreview();
      }
      if (modalOpen && e.key === "Tab") {
        const focusable = $$("button, select, input, iframe, a[href]", $("#modalBody")).filter((el) => !el.disabled && el.getClientRects().length);
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }
      if (typing) return;
      if (document.activeElement?.tagName === "SELECT" || document.activeElement?.getAttribute("role") === "combobox") return;
      const key = e.key.toLowerCase();
      if (e.key === "/" || ((e.ctrlKey || e.metaKey) && key === "k")) { e.preventDefault(); openSearch(); return; }
      if (modalOpen && modalMovieId && (key === "l" || key === "d")) {
        setTaste(modalMovieId, key === "l" ? "love" : "nope", $(`#modalBody [data-act="${key === "l" ? "love" : "nope"}"]`));
        return;
      }
      const tile = document.activeElement?.closest?.(".tile[data-id]");
      if (!tile) return;
      const id = Number(tile.dataset.id);
      if (e.key === "Enter") openMovie(id);
      if (key === "l") setTaste(id, "love", tile);
      if (key === "d") setTaste(id, "nope", tile);
    });

    addEventListener("scroll", () => $("#nav").classList.toggle("solid", scrollY > 40), { passive: true });
    addEventListener("pagehide", () => moviePlayer.save());
    document.addEventListener("visibilitychange", () => { if (document.hidden) moviePlayer.suspend(); });
  }

  function skeletonRows() {
    const row = (w) => `
      <section class="row static"><div class="row-head"><div class="skeleton" style="width:${w}px;height:20px;border-radius:4px"></div></div>
        <div class="row-wrap"><div class="scroller">${Array.from({ length: 9 }, () => `<div class="tile skeleton"></div>`).join("")}</div></div></section>`;
    return row(180) + row(240);
  }

  async function boot() {
    bindAll();
    renderMoods();
    $("#rowList").innerHTML = skeletonRows();
    try {
      if (STATIC_HOST) await useStaticEngine();
      state.movies = await api("/api/movies");
    } catch {
      try {
        await useStaticEngine(); // no server reachable: fall back to the in-browser engine
        state.movies = await api("/api/movies");
      } catch {
        $("#rowList").innerHTML = `<p class="empty" style="padding:0 4%">Couldn't load the recommender. Start the server with <code>python run.py</code>.</p>`;
        return;
      }
    }
    state.byId = new Map(state.movies.map((m) => [m.id, m]));
    catalogue = new CinemagicCatalogueBrowser(state.movies, { storage: viewingStorage, onChange: () => renderRows() });
    load(); // Restore taste before the first recommendation request.
    preferenceResolver = new CinemagicPreferenceResolver(state.movies, { storage: viewingStorage,
      fetcher: (path, options) => api(path, null, options), lookup: id => catalogue.get(id),
      onChange: () => { refresh({ immediate: true }); renderDrawer(); } });
    preferenceResolver.sync(state.liked, state.disliked);
    try {
      await configurePreferenceResolver();
    } catch { /* Choices remain saved and pending until features are available. */ }
    renderMoods();
    renderOnboard();
    renderDrawer();
    refresh({ immediate: true });
    catalogue.configure(!engine).then(() => {
      if (state.query) catalogue.setQuery(state.query);
      if (catalogue.discovery) refresh({ immediate: true });   // first pool with live discovery
    });
  }

  boot();
})();
