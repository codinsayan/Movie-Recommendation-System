/* Cinemagic frontend: Netflix-style UI, no framework, no build step. */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const STORE_KEY = "cinemagic:v1";
  const ROTATE_MS = 8000;
  const RING = 2 * Math.PI * 18;
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canHover = matchMedia("(hover: hover) and (pointer: fine)").matches;

  const MOODS = [
    ["🌧️", "Cozy night in", "cozy and heartwarming"],
    ["🌀", "Mind-bending", "mind-bending with a twist"],
    ["😭", "Make me cry", "emotional, make me cry"],
    ["😱", "Edge of my seat", "scary suspense thriller"],
    ["😂", "Laugh out loud", "funny and quirky"],
    ["⚔️", "Epic adventure", "epic heroic adventure"],
    ["💘", "Date night", "romantic date night"],
    ["🚀", "Into space", "space sci-fi"],
  ];
  const GENRE_TITLES = {
    "Sci-Fi": "Mind-Expanding Sci-Fi", Comedy: "Feel-Good Comedies", Animation: "Animated Worlds",
    Thriller: "Edge-of-Your-Seat Thrillers", Horror: "Lights-Off Horror", Romance: "Romantic Favourites",
    Drama: "Critically Acclaimed Dramas", Action: "Adrenaline-Fuelled Action", Adventure: "Epic Adventures",
    Fantasy: "Fantasy & Magic", Crime: "Crime Stories", Mystery: "Twisty Mysteries", Family: "Family Night",
  };

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
  };
  const bb = { key: "", items: [], i: 0, timer: null };

  // ---------- persistence ----------
  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
      state.liked = new Set(saved.liked || []);
      state.disliked = new Set(saved.disliked || []);
    } catch { /* storage unavailable: start fresh */ }
  }
  function save() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ liked: [...state.liked], disliked: [...state.disliked] }));
    } catch { /* ignore */ }
  }

  // ---------- helpers ----------
  async function api(path, body) {
    const res = await fetch(path, body
      ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      : undefined);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  }
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const byId = (id) => state.byId.get(id);
  const isSeen = (id) => state.liked.has(id) || state.disliked.has(id);
  const nextFrame = (fn) => requestAnimationFrame(() => requestAnimationFrame(fn));
  const personalised = () => state.mode !== "popular";

  function fallbackHTML(m) {
    return `<div class="fallback" style="--c1:${m.palette[0]};--c2:${m.palette[1]}"><span class="emoji">${m.emoji}</span><b>${esc(m.title)}</b></div>`;
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
    return `${matchHTML(m)}<span>${m.year}</span><span>★ ${m.rating}</span><span class="hd">HD</span>`;
  }

  // ---------- tiles & rows ----------
  function tileHTML(m, { i = 0, fresh = false, showMatch = false, isNew = false } = {}) {
    const rec = state.recMap.get(m.id);
    return `
      <div class="tile ${fresh ? "fresh" : ""} ${state.disliked.has(m.id) ? "noped" : ""}" data-id="${m.id}" tabindex="0" role="button" aria-label="${esc(m.title)}" style="--i:${i}">
        ${imgHTML(m)}
        ${state.liked.has(m.id) ? `<span class="badge-love" aria-hidden="true">♥</span>` : ""}
        ${showMatch && rec && personalised() ? `<span class="badge-match">${rec.match}%</span>` : ""}
        ${isNew ? `<span class="badge-new">NEW PICK</span>` : ""}
      </div>`;
  }

  function top10TileHTML(m, rank) {
    return `
      <div class="tile" data-id="${m.id}" tabindex="0" role="button" aria-label="Number ${rank}: ${esc(m.title)}">
        <div class="rank" aria-hidden="true">${rank}</div>
        <div class="poster-box">${imgHTML(m)}${state.liked.has(m.id) ? `<span class="badge-love" aria-hidden="true">♥</span>` : ""}</div>
      </div>`;
  }

  function rowHTML(row, r, isStatic) {
    if (!row.items.length && !row.empty) return "";
    const tiles = row.items.length
      ? row.items.map((m, i) => row.kind === "top10" ? top10TileHTML(m, i + 1) : tileHTML(m, {
          i, showMatch: row.showMatch, fresh: row.freshIds?.has(m.id), isNew: row.freshIds?.has(m.id),
        })).join("")
      : `<p class="empty" style="padding:20px 0">${esc(row.empty)}</p>`;
    return `
      <section class="row ${row.kind === "top10" ? "top10" : ""} ${isStatic ? "static" : ""}" id="row-${row.key}" data-row="${row.key}" style="--r:${r}">
        <div class="row-head">
          <h2 class="row-title">${row.title}</h2>
          ${row.sub ? `<span class="row-sub">${row.sub}</span>` : ""}
        </div>
        <div class="row-wrap">
          <button class="arrow left" data-scroll="-1" aria-label="Scroll left"><span>‹</span></button>
          <div class="scroller">${tiles}</div>
          <button class="arrow right" data-scroll="1" aria-label="Scroll right"><span>›</span></button>
        </div>
      </section>`;
  }

  function buildRows(freshIds) {
    const rows = [];
    const q = state.query.toLowerCase();
    const notDisliked = (m) => !state.disliked.has(m.id);

    if (q) {
      const hits = state.movies.filter((m) =>
        m.title.toLowerCase().includes(q) || m.tags.some((t) => t.includes(q)) || m.genres.some((g) => g.toLowerCase().includes(q)));
      rows.push({
        key: "search", title: `Results for “${esc(state.query)}”`, items: hits,
        sub: "Press Enter to conjure films that <i>feel</i> like this ✦",
        empty: "No titles match. Press Enter and I'll search by mood instead ✦",
      });
    }

    const pickTitle = {
      popular: "Trending Now",
      mood: `Because you're in the mood for “${esc(state.mood)}”`,
      personal: state.mood ? `Top Picks for You × “${esc(state.mood)}”` : "Top Picks for You",
    }[state.mode];
    rows.push({
      key: "picks", title: pickTitle, items: state.scored.slice(0, 14), showMatch: true, freshIds,
      sub: state.mode === "personal" ? "Re-ranked live from every ♥ and ✕" : state.mode === "popular" ? "♥ a few titles to make this yours" : "",
      empty: "Nothing matched that mood. Try different words ✦",
    });

    const myList = [...state.liked].reverse().map(byId).filter(Boolean);
    if (myList.length) rows.push({ key: "mylist", title: "My List", items: myList });

    for (const { source, items } of state.becauseRows) {
      const list = items.filter((m) => !isSeen(m.id));
      if (source && list.length) rows.push({ key: `because-${source.id}`, title: `Because you loved ${esc(source.title)}`, items: list, showMatch: true });
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
        .sort((a, b) => personalised() ? scoreOf(b) - scoreOf(a) || b.rating - a.rating : b.rating - a.rating);
      rows.push({
        key: `genre-${g.toLowerCase()}`, title: esc(GENRE_TITLES[g] || `${g} Movies`), items, showMatch: true,
        sub: tasteGenres.includes(g) ? "From your Taste DNA" : "",
      });
    }
    return rows;
  }

  function renderRows(freshIds = null) {
    const list = $("#rowList");
    const prevKeys = new Set($$(".row", list).map((r) => r.dataset.row));
    const scroll = new Map($$(".row", list).map((r) => [r.dataset.row, $(".scroller", r).scrollLeft]));
    list.innerHTML = buildRows(freshIds).map((row, r) => rowHTML(row, r, prevKeys.has(row.key))).join("");
    $$(".row", list).forEach((r) => {
      const left = scroll.get(r.dataset.row);
      if (left) $(".scroller", r).scrollLeft = left;
    });
  }

  function renderOnboard() {
    const n = state.liked.size;
    $("#onboard").innerHTML = n >= 3 ? "" : `
      <div class="onboard">
        <b>✦ ${["Love 3 titles to unlock your Taste DNA", "Great start! Love 2 more…", "One more ♥ and the magic kicks in…"][n]}</b>
        <span>Hover any poster and tap ♥, or press <kbd>L</kbd> on a focused title.</span>
        <div class="steps">${[0, 1, 2].map((i) => `<i class="${i < n ? "on" : ""}"></i>`).join("")}</div>
      </div>`;
  }

  function renderMoods() {
    const known = MOODS.some(([, , q]) => q === state.mood);
    $("#moods").innerHTML =
      MOODS.map(([emo, label, q]) => `<button class="mood ${q === state.mood ? "active" : ""}" data-mood="${esc(q)}">${emo} ${esc(label)}</button>`).join("") +
      (state.mood && !known ? `<button class="mood active" data-mood="${esc(state.mood)}">✦ ${esc(state.mood)} ✕</button>` : "");
  }

  // ---------- billboard ----------
  function setBillboardItems(items) {
    if (!items.length) return;
    const key = items.map((m) => m.id).join(",") + state.mode;
    if (key === bb.key) return;
    bb.key = key;
    bb.items = items;
    showBillboard(0);
  }

  function showBillboard(i) {
    clearTimeout(bb.timer);
    bb.i = i;
    const m = bb.items[i];
    if (!m) return;
    const rec = state.recMap.get(m.id);

    const bg = $("#bbBg");
    if (m.poster) {
      const img = new Image();
      img.className = "bb-img";
      img.alt = "";
      img.src = m.poster;
      bg.appendChild(img);
      (img.decode ? img.decode() : Promise.resolve()).catch(() => {}).finally(() => nextFrame(() => img.classList.add("show")));
      setTimeout(() => { while (bg.children.length > 1) bg.firstElementChild.remove(); }, 1300);
    }
    const poster = $("#bbPoster");
    poster.hidden = !m.poster;
    if (m.poster) {
      poster.src = m.poster;
      poster.alt = `${m.title} poster`;
      poster.style.animation = "none";
      void poster.offsetWidth;
      poster.style.animation = "";
    }

    const kicker = {
      popular: `<b>#${i + 1}</b> Trending tonight`,
      mood: `<b>✦</b> Conjured for “${esc(state.mood)}”`,
      personal: `<b>✦ ${i + 1}</b> Top pick for you`,
    }[state.mode];
    const reason = rec?.because ? `Because you loved <b>&nbsp;${esc(rec.because.title)}</b>` : state.mode === "mood" && rec ? esc(rec.reason) : "";
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
        <button class="btn btn-white" data-open="${m.id}">ⓘ&nbsp; More Info</button>
        <button class="btn btn-grey" data-act="love" data-id="${m.id}" aria-pressed="${state.liked.has(m.id)}">♥&nbsp; Love it</button>
        <button class="btn btn-grey" data-act="nope" data-id="${m.id}" aria-pressed="${state.disliked.has(m.id)}" aria-label="Not for me">✕</button>
      </div>`;
    content.classList.remove("bb-anim");
    void content.offsetWidth;
    content.classList.add("bb-anim");

    $("#bbDots").innerHTML = bb.items.length > 1 ? bb.items.map((_, k) =>
      `<button class="bb-dot ${k === i ? "active" : ""} ${k < i ? "done" : ""}" data-bb="${k}" aria-label="Show pick ${k + 1}" style="--dur:${ROTATE_MS}ms"><i></i></button>`).join("") : "";
    if (!reducedMotion && bb.items.length > 1) bb.timer = setTimeout(() => showBillboard((i + 1) % bb.items.length), ROTATE_MS);
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
        ${m.poster ? `<img class="blur" src="${esc(m.poster)}" alt=""><img class="sharp" src="${esc(m.poster)}" alt="">` : fallbackHTML(m)}
        <div class="pv-title" style="left:${titleLeft}px">${esc(m.title)}</div>
      </div>
      <div class="pv-body">
        <div class="pv-actions">
          <button class="circle solid" data-open="${m.id}" aria-label="More info" title="More info">ⓘ</button>
          <button class="circle love" data-act="love" data-id="${m.id}" aria-pressed="${state.liked.has(m.id)}" aria-label="Love it" title="Love it (L)">♥</button>
          <button class="circle nope" data-act="nope" data-id="${m.id}" aria-pressed="${state.disliked.has(m.id)}" aria-label="Not for me" title="Not for me (D)">✕</button>
          <button class="circle more" data-open="${m.id}" aria-label="Details" title="Details">⌄</button>
        </div>
        <div class="meta" style="font-size:.85rem">${metaHTML(m)}</div>
        <div class="pv-genres">${m.genres.map((g) => `<span>${esc(g)}</span>`).join("")}</div>
        ${rec?.because ? `<p class="pv-reason">✦ Because you loved <b>${esc(rec.because.title)}</b></p>`
          : rec?.shared?.length && personalised() ? `<p class="pv-reason">✦ ${rec.shared.map(esc).join(" · ")}</p>` : ""}
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
  function renderDrawer() {
    const n = state.liked.size;
    const taste = state.taste || { genres: [], tags: [], confidence: 0 };
    const pct = Math.round(taste.confidence * 100);
    const top = taste.genres.slice(0, 2).map((g) => g.name.toLowerCase());
    const hint = n === 0 ? "Love a few titles and I'll map your taste." : n < 3 ? `${3 - n} more ♥ to unlock your full profile.` : `You're drawn to ${top.join(" & ")}.`;
    const pick = (id, cls) => {
      const m = byId(id);
      return m ? `<div class="pick ${cls}" title="${esc(m.title)}">${imgHTML(m)}<button data-remove="${id}" aria-label="Remove ${esc(m.title)}">✕</button></div>` : "";
    };
    $("#drawer").innerHTML = `
      <button class="icon-btn drawer-close" data-close-drawer aria-label="Close">✕</button>
      <h2>Your Taste DNA ${n >= 3 ? "✨" : "🧬"}</h2>
      <p class="hint">${hint}</p>
      <div class="meter-row"><span>Taste confidence</span><span>${pct}%</span></div>
      <div class="meter-track"><div class="meter-fill" data-w="${pct}"></div></div>
      <h3>Genre affinity</h3>
      <div class="dna">${taste.genres.length ? taste.genres.map((g) => `
        <div class="dna-row"><span>${esc(g.name)}</span><div class="dna-bar"><i data-w="${g.weight * 100}"></i></div><em>${Math.round(g.weight * 100)}</em></div>`).join("")
        : `<p class="empty">Nothing yet.</p>`}</div>
      <h3>Your vibe</h3>
      <div class="chips">${taste.tags.length ? taste.tags.map((t) => `<span class="chip">#${esc(t)}</span>`).join("") : `<p class="empty">Your favourite moods will appear here.</p>`}</div>
      <h3>My List · ${n}</h3>
      <div class="pick-list">${[...state.liked].reverse().map((id) => pick(id, "")).join("") || `<p class="empty" style="grid-column:1/-1">No loved titles yet.</p>`}</div>
      ${state.disliked.size ? `<h3>Not for me · ${state.disliked.size}</h3><div class="pick-list">${[...state.disliked].map((id) => pick(id, "nope")).join("")}</div>` : ""}
      <div class="drawer-foot">
        <button class="btn btn-grey btn-sm" id="resetBtn">↺ Start over</button>
        <button class="btn btn-white btn-sm" data-how>🔮 How it works</button>
      </div>`;
    if ($("#drawer").classList.contains("open")) animateBars($("#drawer"));
    $("#avatarRing").style.strokeDashoffset = RING * (1 - taste.confidence);
  }

  function animateBars(root) {
    nextFrame(() => $$("[data-w]", root).forEach((el) => (el.style.width = `${el.dataset.w}%`)));
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
  function refresh({ announce = false, immediate = false } = {}) {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(async () => {
      const seq = ++refreshSeq;
      const recent = [...state.liked].slice(-2).reverse();
      try {
        const [out, ...sims] = await Promise.all([
          api("/api/recommend", { liked: [...state.liked], disliked: [...state.disliked], mood: state.mood || null, k: 100 }),
          ...recent.map((id) => api(`/api/movies/${id}/similar?k=14`)),
        ]);
        if (seq !== refreshSeq) return; // superseded by a newer request
        const prevPicks = new Set(state.scored.slice(0, 14).map((m) => m.id));
        state.scored = out.items;
        state.recMap = new Map(out.items.map((r) => [r.id, r]));
        state.taste = out.taste;
        state.mode = out.mode;
        state.becauseRows = recent.map((id, k) => ({ source: byId(id), items: sims[k] }));

        const fresh = announce && prevPicks.size ? new Set(state.scored.slice(0, 14).map((m) => m.id).filter((id) => !prevPicks.has(id))) : null;
        renderOnboard();
        renderMoods();
        renderRows(fresh);
        setBillboardItems(state.scored.slice(0, 5));
        renderDrawer();
        if (announce && fresh) toast(fresh.size ? `✦ Taste updated: ${fresh.size} new pick${fresh.size > 1 ? "s" : ""} for you` : "✦ Taste updated: picks re-ranked");
      } catch (err) {
        console.error(err);
        toast("⚠️ Couldn't reach the recommender. Is the server running?");
      }
    }, immediate ? 0 : 150);
  }

  // ---------- interactions ----------
  function setTaste(id, kind, origin) {
    if (!byId(id)) return;
    const [set, other] = kind === "love" ? [state.liked, state.disliked] : [state.disliked, state.liked];
    const adding = !set.has(id);
    other.delete(id);
    adding ? set.add(id) : set.delete(id);
    save();
    syncStates();
    if (adding && origin) burst(origin, kind === "love" ? ["❤️", "♥", "✦", "💖"] : ["💨", "·", "✕"]);
    if (adding && kind === "love" && state.liked.size === 3) toast("🔓 Taste DNA unlocked. Open 🧬 to see your profile.");
    if (adding && kind === "nope") toast(`Got it. Fewer films like ${byId(id).title}.`);
    refresh({ announce: true });
  }

  // Update pressed states and badges in place (rows re-render shortly after).
  function syncStates() {
    $$("[data-act][data-id]").forEach((b) => {
      const id = Number(b.dataset.id);
      b.setAttribute("aria-pressed", String(b.dataset.act === "love" ? state.liked.has(id) : state.disliked.has(id)));
    });
    $$(".tile[data-id]").forEach((t) => t.classList.toggle("noped", state.disliked.has(Number(t.dataset.id))));
  }

  function burst(el, glyphs) {
    if (reducedMotion) return;
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    for (let i = 0; i < 14; i++) {
      const p = document.createElement("span");
      p.className = "particle";
      p.textContent = glyphs[i % glyphs.length];
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
    state.query = "";
    hidePreview();
    if (state.mood) {
      if (origin) burst(origin, ["✨", "✦", "⭐", "🪄"]);
      toast(`🪄 Conjuring films for “${state.mood}”…`);
    }
    renderMoods();
    refresh({ immediate: true });
    scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
  }

  // ---------- modal ----------
  let modalMovieId = null;
  function openModal(html) {
    hidePreview();
    $("#modalBody").innerHTML = `<button class="m-close" data-close aria-label="Close">✕</button>${html}`;
    $("#modal").classList.add("open");
    $("#modal").scrollTop = 0;
    document.body.style.overflow = "hidden";
    setTimeout(() => $("#modalBody .m-close")?.focus(), 60);
  }
  function closeModal() {
    $("#modal").classList.remove("open");
    document.body.style.overflow = "";
    modalMovieId = null;
  }

  async function openMovie(id) {
    const m = byId(id);
    if (!m) return;
    modalMovieId = id;
    const rec = state.recMap.get(id);
    const share = (k) => (rec ? rec.breakdown[k] / Math.max(rec.score, 0.001) : 0);
    const why = rec && personalised() ? `
      <div class="why">
        <h4>Why we picked this · ${rec.match}% match</h4>
        <div class="dna">
          ${[["content", "Story & vibe match"], ["collab", "Fans like you"], ["quality", "Critic quality"]].map(([k, label]) => `
            <div class="dna-row"><span>${label}</span><div class="dna-bar"><i data-w="${share(k) * 100}"></i></div><em>${Math.round(share(k) * 100)}%</em></div>`).join("")}
        </div>
        ${rec.shared.length ? `<p class="pv-reason" style="margin-top:12px">Shares: <b>${rec.shared.map(esc).join(", ")}</b></p>` : ""}
      </div>` : "";
    openModal(`
      <div class="m-head">
        ${m.poster ? `<img class="blur" src="${esc(m.poster)}" alt="">` : ""}
        <div class="m-poster">${imgHTML(m)}</div>
        <div>
          <h2 id="modalTitle">${esc(m.title)}</h2>
          <div class="bb-actions" style="margin-top:0">
            <button class="btn btn-grey btn-sm" data-act="love" data-id="${m.id}" aria-pressed="${state.liked.has(m.id)}">♥&nbsp; Love it <kbd>L</kbd></button>
            <button class="btn btn-grey btn-sm" data-act="nope" data-id="${m.id}" aria-pressed="${state.disliked.has(m.id)}">✕&nbsp; Not for me <kbd>D</kbd></button>
          </div>
        </div>
      </div>
      <div class="m-body">
        <div>
          <div class="meta">${metaHTML(m)}</div>
          <p class="overview">${esc(m.overview)}</p>
          ${why}
        </div>
        <div class="m-side">
          <div><b>Genres:</b> ${m.genres.map(esc).join(", ")}</div>
          <div><b>This film is:</b> ${m.tags.map(esc).join(", ")}</div>
          ${rec?.because ? `<div><b>Because you loved:</b> ${esc(rec.because.title)}</div>` : ""}
        </div>
      </div>
      <div class="m-section">
        <h3>More Like This</h3>
        <div class="like-grid" id="similarGrid">${Array.from({ length: 6 }, () => `<div class="like-card skeleton" style="height:230px"></div>`).join("")}</div>
      </div>`);
    animateBars($("#modalBody"));
    try {
      const sims = await api(`/api/movies/${id}/similar?k=9`);
      if (modalMovieId !== id) return;
      $("#similarGrid").innerHTML = sims.map((s, i) => {
        const r = state.recMap.get(s.id);
        const label = state.liked.has(s.id) ? "♥ In My List" : r && personalised() ? `${r.match}% Match` : `★ ${s.rating}`;
        return `
          <article class="like-card" data-sim="${s.id}" style="--i:${i}" tabindex="0">
            <div class="lc-img">${imgHTML(s)}</div>
            <div class="lc-body">
              <div class="lc-top"><span class="match">${label}</span>
                <button class="circle love" data-act="love" data-id="${s.id}" aria-pressed="${state.liked.has(s.id)}" aria-label="Love ${esc(s.title)}">♥</button></div>
              <div class="lc-title">${esc(s.title)}</div>
              <div>${s.year} · ${s.genres.slice(0, 2).map(esc).join(", ")}</div>
            </div>
          </article>`;
      }).join("");
    } catch {
      $("#similarGrid").innerHTML = `<p class="empty">Couldn't load similar films.</p>`;
    }
  }

  async function openHow() {
    toggleDrawer(false);
    let meta = null;
    try { meta = await api("/api/meta"); } catch { /* offline */ }
    const w = meta?.weights || { content: 0.55, collab: 0.35, quality: 0.1 };
    openModal(`
      <div class="how">
        <h2 id="modalTitle">How the magic works 🔮</h2>
        <p>Cinemagic is a <b>hybrid recommender</b>. Every time you tap ♥ or ✕, three signals are blended and re-ranked in a few milliseconds.</p>
        <div class="pipeline">
          <div class="stage">🧬<b>Content · ${Math.round(w.content * 100)}%</b><p>TF-IDF vectors over genres, mood tags and plot. Your likes form a taste vector; cosine similarity finds neighbours.</p></div>
          <div class="stage">👥<b>Collaborative · ${Math.round(w.collab * 100)}%</b><p>Item-item adjusted-cosine similarity from ${meta ? meta.ratings.toLocaleString() : "thousands of"} ratings: "people who loved X also loved Y".</p></div>
          <div class="stage">⭐<b>Quality · ${Math.round(w.quality * 100)}%</b><p>A gentle prior towards well-rated films, then MMR re-ranking (λ=${meta?.mmr_lambda ?? 0.75}) keeps every row diverse.</p></div>
        </div>
        ${meta ? `<div class="stats">
          <div class="stat"><b>${meta.movies}</b><span>films</span></div>
          <div class="stat"><b>${meta.simulated_users}</b><span>simulated users</span></div>
          <div class="stat"><b>${(meta.sparsity * 100).toFixed(0)}%</b><span>matrix sparsity</span></div>
          <div class="stat"><b>${meta.vocabulary}</b><span>TF-IDF terms</span></div>
        </div>` : ""}
        <p style="margin-top:18px;font-size:.85rem">Search understands moods: type "make me cry" and press Enter. Shortcuts: <kbd>/</kbd> search · <kbd>L</kbd>/<kbd>D</kbd> love/pass a focused title · <kbd>Enter</kbd> details · <kbd>Esc</kbd> close.</p>
      </div>`);
  }

  // ---------- search ----------
  function bindSearch() {
    const form = $("#searchForm"), input = $("#searchInput");
    const open = () => { form.classList.add("open"); input.focus(); };
    $("#searchToggle").addEventListener("click", () => (form.classList.contains("open") && !input.value ? form.classList.remove("open") : open()));
    input.addEventListener("input", () => {
      const had = !!state.query;
      state.query = input.value.trim();
      hidePreview();
      renderRows();
      if (state.query && !had) scrollTo({ top: $("#rows").offsetTop - 80, behavior: reducedMotion ? "auto" : "smooth" });
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { input.value = ""; state.query = ""; renderRows(); input.blur(); form.classList.remove("open"); }
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
      const act = t.closest("[data-act]");
      if (act) { e.stopPropagation(); setTaste(Number(act.dataset.id), act.dataset.act, act); return; }
      if (t.closest("[data-close]") || t.id === "modal") return closeModal();
      if (t.closest("[data-close-drawer]") || t.id === "scrim") return toggleDrawer(false);
      if (t.closest("#resetBtn")) {
        state.liked.clear(); state.disliked.clear(); save();
        toggleDrawer(false);
        conjure("");
        toast("↺ Fresh start. Tell me what you love.");
        return;
      }
      if (t.closest("[data-how]")) return openHow();
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
      if (typing) return;
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
  }

  function skeletonRows() {
    const row = (w) => `
      <section class="row static"><div class="row-head"><div class="skeleton" style="width:${w}px;height:20px;border-radius:4px"></div></div>
        <div class="row-wrap"><div class="scroller">${Array.from({ length: 9 }, () => `<div class="tile skeleton"></div>`).join("")}</div></div></section>`;
    return row(180) + row(240);
  }

  async function boot() {
    load();
    bindAll();
    renderMoods();
    $("#rowList").innerHTML = skeletonRows();
    try {
      state.movies = await api("/api/movies");
    } catch {
      $("#rowList").innerHTML = `<p class="empty" style="padding:0 4%">Couldn't reach the API. Start the server with <code>python run.py</code>.</p>`;
      return;
    }
    state.byId = new Map(state.movies.map((m) => [m.id, m]));
    renderOnboard();
    renderDrawer();
    refresh({ immediate: true });
  }

  boot();
})();
