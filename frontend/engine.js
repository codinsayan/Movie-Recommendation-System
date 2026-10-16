/* In-browser port of backend/recommender.py for the static (GitHub Pages) build.
 * Loads the model exported by scripts/export_static.py and answers the same
 * API paths as the FastAPI server. Kept in lock-step with Python by
 * tests/test_static_engine.py.
 */
(function (root) {
  "use strict";

  const TOKEN = /\b[a-z0-9][a-z0-9-]+\b/g;

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
    recommend(liked = [], disliked = [], mood = null, k = 12) {
      const L = this.indices(liked), D = this.indices(disliked);
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
      [...L, ...D].forEach((i) => (candidates[i] = false));

      let weights, mode;
      if (!L.length && !D.length && !mood) { weights = { content: 0, collab: 0, quality: 1 }; mode = "popular"; }
      else if (mood && !L.length) { weights = cfg.moodWeights; mode = "mood"; }
      else { weights = cfg.weights; mode = "personal"; }

      const parts = { content: minmax(content, candidates), collab: minmax(collab, candidates), quality: minmax(this.quality, candidates) };
      const score = new Float64Array(n);
      for (let i = 0; i < n; i++) score[i] = 0 + weights.content * parts.content[i] + weights.collab * parts.collab[i] + weights.quality * parts.quality[i];
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
        }
        if (moodTerms.size) shared = sortedStrings(new Set([...shared, ...[...this.tokenSets[idx]].filter((t) => moodTerms.has(t))]));
        const reason = because ? `Because you loved ${because.title}` : mood ? `Matches “${mood}”` : "A crowd favourite to get you started";
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
      return { mode, items, taste: this.tasteProfile(L, D) };
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
        return this.recommend(body?.liked, body?.disliked, body?.mood, k);
      }
      const sim = p.match(/^\/api\/movies\/(\d+)\/similar$/);
      if (sim) return this.similar(Number(sim[1]), Number(url.searchParams.get("k") || 6));
      throw Object.assign(new Error(`Not found: ${p}`), { status: 404 });
    }
  }

  if (typeof module !== "undefined" && module.exports) module.exports = Engine;
  else root.CinemagicEngine = Engine;
})(typeof self !== "undefined" ? self : this);
