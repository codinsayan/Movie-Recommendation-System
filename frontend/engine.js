/* In-browser port of backend/recommender.py for the static (GitHub Pages) build.
 * Loads the model exported by scripts/export_static.py and answers the same
 * API paths as the FastAPI server. Kept in lock-step with Python by
 * tests/test_static_engine.py.
 */
(function (root) {
  "use strict";

  const TOKEN = /\b[a-z0-9][a-z0-9-]+\b/g;
  const VIEWING = { version: 1, minSeconds: 120, minFraction: .30, baseStrength: .15,
    repeatStrength: .05, maxStrength: .25, blend: .10, freshnessMs: 7 * 24 * 60 * 60 * 1000 };
  const canonicalKey = (movie) => `${movie.source}:${movie.id}`;
  const number = (value) => typeof value === "number" && Number.isFinite(value);
  const validKey = (value) => typeof value === "string" && value.length <= 40 && /^(tmdb|curated):[1-9]\d*$/.test(value);

  function validateViewingRequest(body) {
    const fail = () => { throw Object.assign(new Error("Invalid viewing recommendation request"), { status: 422 }); };
    for (const key of ["use_viewing", "recent_playback_only"]) if (body[key] !== undefined && typeof body[key] !== "boolean") fail();
    if (body.eligible_keys != null && (!Array.isArray(body.eligible_keys) || body.eligible_keys.length > 5000 || !body.eligible_keys.every(validKey))) fail();
    const evidence = body.viewing;
    if (evidence == null) return;
    if (!evidence || typeof evidence !== "object" || Array.isArray(evidence) || evidence.version !== 1) fail();
    const signals = evidence.signals === undefined ? [] : evidence.signals;
    const playback = evidence.playback === undefined ? [] : evidence.playback;
    if (!Array.isArray(signals) || signals.length > 500 || !Array.isArray(playback) || playback.length > 1500) fail();
    for (const s of signals) {
      if (!s || !validKey(s.key) || !number(s.watched_seconds) || s.watched_seconds < 0 || s.watched_seconds > 86400 ||
          !number(s.duration) || s.duration <= 0 || s.duration > 86400 || !Number.isInteger(s.plays) || s.plays < 0 || s.plays > 100 ||
          !number(s.updated_at === undefined ? 0 : s.updated_at) || s.updated_at < 0) fail();
    }
    for (const p of playback) {
      if (!p || !validKey(p.key) || !["cinesrc", "vidlink", "vidsrc"].includes(p.provider) ||
          ![p.verified_at === undefined ? 0 : p.verified_at, p.failed_at === undefined ? 0 : p.failed_at].every((v) => number(v) && v >= 0)) fail();
    }
  }

  function minmax(x, mask) {
    const out = new Float64Array(x.length);
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < x.length; i++) if (mask[i]) { lo = Math.min(lo, x[i]); hi = Math.max(hi, x[i]); }
    if (lo === Infinity) return out;
    for (let i = 0; i < x.length; i++) if (mask[i]) out[i] = hi > lo ? (x[i] - lo) / (hi - lo) : 1;
    return out;
  }

  // Python's round(): ties go to the even neighbour.
  function roundHalfEven(x) {
    const r = Math.round(x);
    return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
  }
  /** Gram matrix S = R·Rᵀ of sparse rows ([[col, val], ...]) with a zero diagonal. */
  function gram(rows) {
    const n = rows.length;
    const postings = new Map();
    rows.forEach((row, i) => row.forEach(([j, v]) => {
      if (!postings.has(j)) postings.set(j, []);
      postings.get(j).push([i, v]);
    }));
    return rows.map((row, i) => {
      const out = new Float64Array(n);
      for (const [j, v] of row) for (const [k, w] of postings.get(j)) out[k] += v * w;
      out[i] = 0;
      return out;
    });
  }

  const round = (x, d) => Math.round(x * 10 ** d) / 10 ** d;
  const argmaxFirst = (arr) => arr.reduce((best, v, i) => (v > arr[best] ? i : best), 0);
  const sortedStrings = (set) => [...set].sort();

  class Engine {
    constructor(model) {
      this.movies = model.movies;
      this.vocab = model.vocab;
      this.idf = model.idf;
      this.X = model.X;
      this.contentSim = gram(model.X);
      this.collabSim = gram(model.C);
      this.quality = model.quality;
      this.metaInfo = model.meta;
      this.cfg = model.config;
      this.n = this.movies.length;
      this.byId = new Map(this.movies.map((m, i) => [m.id, i]));
      this.tokenSets = this.movies.map((m) => new Set([...m.genres.map((g) => g.toLowerCase()), ...m.tags, ...(m.people || [])]));
    }

    static async load(url) {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Could not load model: ${res.status}`);
      return new Engine(await res.json());
    }

    // ---------- helpers ----------
    indices(ids) {
      const out = [];
      for (const id of new Set(ids || [])) {
        const i = this.byId.get(id);
        if (i !== undefined) out.push(i);
      }
      return out;
    }

    expandMood(mood) {
      const text = mood.toLowerCase();
      // keys match at the start of a word, exactly like the Python engine
      const extra = Object.entries(this.cfg.moodSynonyms).filter(([k]) => new RegExp(`(?<![a-z])${k}`).test(text)).map(([, v]) => v);
      return [text, ...extra].join(" ");
    }

    moodTerms(mood) {
      return new Set(this.expandMood(mood).replace(/,/g, " ").split(/\s+/).filter((t) => t in this.vocab));
    }

    /** TfidfVectorizer.transform with sublinear tf and L2 norm. */
    transform(text) {
      const counts = new Map();
      for (const tok of text.toLowerCase().match(TOKEN) || []) {
        const j = this.vocab[tok];
        if (j !== undefined) counts.set(j, (counts.get(j) || 0) + 1);
      }
      const v = new Float64Array(this.idf.length);
      let norm = 0;
      for (const [j, c] of counts) { v[j] = (1 + Math.log(c)) * this.idf[j]; norm += v[j] * v[j]; }
      norm = Math.sqrt(norm);
      if (norm > 0) for (const j of counts.keys()) v[j] /= norm;
      return v;
    }

    mmr(candidates, relevance, k) {
      const lambda = this.cfg.mmrLambda;
      const selected = [];
      const pool = [...candidates];
      while (pool.length && selected.length < k) {
        const scores = pool.map((p) => {
          const redundancy = selected.length ? Math.max(...selected.map((s) => this.contentSim[p][s])) : 0;
          return lambda * relevance[p] - (1 - lambda) * redundancy;
        });
        selected.push(pool.splice(argmaxFirst(scores), 1)[0]);
      }
      return selected;
    }

    // ---------- public API (mirrors Recommender) ----------
    viewingEvidence(payload, excluded, now) {
      if (!payload || payload.version !== 1) return [[], new Set()];
      const cfg = this.cfg.viewing || VIEWING;
      const index = new Map(this.movies.map((m, i) => [canonicalKey(m), i]));
      const signals = new Map();
      for (const item of (Array.isArray(payload.signals) ? payload.signals : []).slice(0, 500)) {
        if (!item || typeof item !== "object") continue;
        const i = index.get(item.key), watched = item.watched_seconds, duration = item.duration, plays = item.plays;
        const updated = item.updated_at ?? 0;
        if (i === undefined || excluded.has(i) || ![watched, duration, plays, updated].every(number)) continue;
        if (!(duration > 0 && duration <= 86400 && watched >= Math.max(cfg.minSeconds, duration * cfg.minFraction) && watched <= duration &&
            Number.isInteger(plays) && plays >= 1 && plays <= 100)) continue;
        const strength = Math.min(cfg.maxStrength, cfg.baseStrength + cfg.repeatStrength * (plays - 1));
        const previous = signals.get(i);
        if (!previous || strength > previous.strength || strength === previous.strength && updated > previous.updated_at)
          signals.set(i, { index: i, key: item.key, watched_seconds: watched, duration, plays, updated_at: updated, strength });
      }
      const playback = new Map();
      for (const item of (Array.isArray(payload.playback) ? payload.playback : []).slice(0, 1500)) {
        if (!item || !["cinesrc", "vidlink", "vidsrc"].includes(item.provider) || !/^(tmdb|curated):[1-9]\d*$/.test(item.key)) continue;
        const success = item.verified_at ?? 0, failure = item.failed_at ?? 0;
        if (![success, failure].every((v) => number(v) && v >= 0)) continue;
        const pair = `${item.key}/${item.provider}`, previous = playback.get(pair);
        playback.set(pair, { key: item.key, success: Math.max(success, previous?.success || 0), failure: Math.max(failure, previous?.failure || 0) });
      }
      const recent = new Set([...playback.values()].filter(({ success, failure }) => success > failure && now - success >= 0 && now - success <= cfg.freshnessMs).map((p) => p.key));
      return [[...signals.values()].sort((a, b) => b.updated_at - a.updated_at || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0)), recent];
    }

    recommend(liked = [], disliked = [], mood = null, k = 12, options = {}) {
      const D = this.indices(disliked), L = this.indices(liked).filter((i) => !D.includes(i));
      let [signals, recent] = this.viewingEvidence(options.viewing, new Set([...L, ...D]), options.now ?? Date.now());
      if (!options.use_viewing) signals = [];
      mood = (mood || "").trim();
      const n = this.n, cfg = this.cfg;

      let content = new Float64Array(n);
      const collab = new Float64Array(n);
      const profile = new Float64Array(this.idf.length);
      const addRows = (rows, w) => rows.forEach((i) => this.X[i].forEach(([j, v]) => (profile[j] += w * v)));
      const addCollab = (rows, w) => {
        for (let j = 0; j < n; j++) {
          let s = 0;
          rows.forEach((i) => (s += this.collabSim[i][j]));
          collab[j] += (w * s) / rows.length;
        }
      };
      if (L.length) { addRows(L, 1); addCollab(L, 1); }
      if (D.length) { addRows(D, -cfg.dislikePenalty); addCollab(D, -cfg.dislikePenalty); }
      if (mood) {
        const q = this.transform(this.expandMood(mood));
        const boost = cfg.moodBoost * Math.max(1, L.length);
        q.forEach((v, j) => (profile[j] += boost * v));
      }
      const norm = Math.sqrt(profile.reduce((s, v) => s + v * v, 0));
      if (norm > 0) content = Float64Array.from(this.X, (row) => row.reduce((s, [j, v]) => s + v * profile[j], 0) / norm);

      const candidates = new Array(n).fill(true);
      [...L, ...D, ...signals.map((s) => s.index)].forEach((i) => (candidates[i] = false));
      const allowed = options.eligible_keys == null ? null : new Set(options.eligible_keys);
      this.movies.forEach((movie, i) => {
        if (allowed && !allowed.has(canonicalKey(movie))) candidates[i] = false;
        if (options.recent_playback_only && !recent.has(canonicalKey(movie))) candidates[i] = false;
      });

      let weights, mode;
      if (!L.length && !D.length && !mood) { weights = { content: 0, collab: 0, quality: 1 }; mode = "popular"; }
      else if (mood && !L.length) { weights = cfg.moodWeights; mode = "mood"; }
      else { weights = cfg.weights; mode = "personal"; }

      const parts = { content: minmax(content, candidates), collab: minmax(collab, candidates), quality: minmax(this.quality, candidates) };
      if (signals.length) {
        const viewingCfg = cfg.viewing || VIEWING;
        parts.viewing = Float64Array.from(this.movies, (_, i) => Math.max(0, Math.min(1,
          signals.reduce((sum, s) => sum + s.strength / viewingCfg.maxStrength *
            (.6 * this.contentSim[s.index][i] + .4 * this.collabSim[s.index][i]), 0) / signals.length)));
        weights = Object.fromEntries(Object.entries(weights).map(([name, w]) => [name, w * (1 - viewingCfg.blend)]));
        weights.viewing = viewingCfg.blend;
        if (mode === "popular") mode = "viewing";
      }
      const score = new Float64Array(n);
      for (let i = 0; i < n; i++) score[i] = Object.keys(parts).reduce((sum, name) => sum + weights[name] * parts[name][i], 0);
      if (mood) for (let i = 0; i < n; i++) candidates[i] = candidates[i] && content[i] > 0.05;

      const ranked = [...score.keys()].sort((a, b) => score[b] - score[a]).filter((i) => candidates[i]).slice(0, k * 3);
      const chosen = mode !== "popular" ? this.mmr(ranked, score, k) : ranked.slice(0, k);

      const moodTerms = mood ? this.moodTerms(mood) : new Set();
      const top = chosen.length ? Math.max(...chosen.map((i) => score[i])) : 1;
      const items = chosen.map((idx) => {
        let because = null, shared = [];
        if (L.length) {
          const j = L[argmaxFirst(L.map((l) => this.contentSim[idx][l] + this.collabSim[idx][l]))];
          because = { id: this.movies[j].id, title: this.movies[j].title };
          shared = sortedStrings([...this.tokenSets[idx]].filter((t) => this.tokenSets[j].has(t)));
        } else if (signals.length && parts.viewing[idx] > 0) {
          const s = signals[argmaxFirst(signals.map((s) => s.strength * (.6 * this.contentSim[idx][s.index] + .4 * this.collabSim[idx][s.index])))];
          const j = s.index;
          because = { id: this.movies[j].id, title: this.movies[j].title, type: "watched" };
          shared = sortedStrings([...this.tokenSets[idx]].filter((t) => this.tokenSets[j].has(t)));
        }
        if (moodTerms.size) shared = sortedStrings(new Set([...shared, ...[...this.tokenSets[idx]].filter((t) => moodTerms.has(t))]));
        const reason = because ? `Because you ${because.type === "watched" ? "watched" : "loved"} ${because.title}` : mood ? `Matches “${mood}”` : "A crowd favourite to get you started";
        return {
          ...this.movies[idx],
          score: round(score[idx], 4),
          match: top > 0 ? roundHalfEven(55 + (44 * score[idx]) / top) : 55,
          reason,
          because,
          shared: shared.slice(0, 4),
          breakdown: Object.fromEntries(Object.keys(parts).map((name) => [name, round(weights[name] * parts[name][idx], 4)])),
        };
      });
      const watched_rows = signals.slice(0, 2).map((s) => {
        const relevance = Float64Array.from(this.movies, (_, i) => .6 * this.contentSim[s.index][i] + .4 * this.collabSim[s.index][i]);
        const pool = [...relevance.keys()].sort((a, b) => relevance[b] - relevance[a]).filter((i) => candidates[i] && relevance[i] > 0).slice(0, 42);
        return { source: this.movies[s.index], watched_seconds: s.watched_seconds, duration: s.duration,
          items: this.mmr(pool, relevance, 14).map((i) => ({ ...this.movies[i] })) };
      });
      return { mode, items, taste: this.tasteProfile(L, D), watched_rows };
    }

    tasteProfile(L, D) {
      const genreW = new Map(), tagW = new Map();
      const add = (map, key, w) => map.set(key, (map.get(key) || 0) + w);
      [...L.map((i) => [i, 1]), ...D.map((i) => [i, -this.cfg.dislikePenalty])].forEach(([idx, w]) => {
        this.movies[idx].genres.forEach((g) => add(genreW, g, w));
        this.movies[idx].tags.forEach((t) => add(tagW, t, w));
      });
      const positives = (map) => [...map].filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
      const genres = positives(genreW);
      const top = genres.length ? Math.max(...genres.map(([, v]) => v)) : 1;
      return {
        genres: genres.slice(0, 6).map(([name, v]) => ({ name, weight: round(v / top, 3) })),
        tags: positives(tagW).slice(0, 8).map(([t]) => t),
        confidence: round(Math.min(1, L.length / 5), 2),
      };
    }

    similar(movieId, k = 6) {
      const i = this.byId.get(movieId);
      if (i === undefined) throw Object.assign(new Error("Movie not found"), { status: 404 });
      const sim = this.contentSim[i].map((c, j) => 0.6 * c + 0.4 * this.collabSim[i][j]);
      return [...sim.keys()].sort((a, b) => sim[b] - sim[a]).filter((j) => j !== i).slice(0, k).map((j) => ({
        ...this.movies[j],
        similarity: round(sim[j], 4),
        shared: sortedStrings([...this.tokenSets[j]].filter((t) => this.tokenSets[i].has(t))).slice(0, 4),
      }));
    }

    /** Route a request exactly like the FastAPI app would. */
    handle(path, body) {
      const url = new URL(path, "http://local");
      const p = url.pathname;
      if (p === "/api/health") return { status: "ok" };
      if (p === "/api/movies") return this.movies;
      if (p === "/api/meta") return this.metaInfo;
      if (p === "/api/recommend") {
        const k = body?.k ?? 12;
        if (!(k >= 1 && k <= 100)) throw Object.assign(new Error("k must be 1-100"), { status: 422 });
        validateViewingRequest(body || {});
        return this.recommend(body?.liked, body?.disliked, body?.mood, k, {
          viewing: body?.viewing, use_viewing: body?.use_viewing,
          recent_playback_only: body?.recent_playback_only, eligible_keys: body?.eligible_keys });
      }
      const sim = p.match(/^\/api\/movies\/(\d+)\/similar$/);
      if (sim) return this.similar(Number(sim[1]), Number(url.searchParams.get("k") || 6));
      throw Object.assign(new Error(`Not found: ${p}`), { status: 404 });
    }
  }

  if (typeof module !== "undefined" && module.exports) module.exports = Engine;
  else root.CinemagicEngine = Engine;
})(typeof self !== "undefined" ? self : this);
