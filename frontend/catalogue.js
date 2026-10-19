/* Remote metadata/search stays separate from the bounded recommendation model. */
(function (root) {
  "use strict";
  const STORE = "cinemagic:catalogue:v1";
  class CatalogueBrowser {
    constructor(snapshot, { fetcher = (...args) => root.fetch(...args), storage, onChange = () => {}, timers = root } = {}) {
      this.snapshot = new Map(snapshot.map((m) => [m.id, m]));
      this.source = snapshot[0]?.source;
      this.records = new Map(); this.saved = new Map(); this.storage = storage;
      this.fetcher = fetcher; this.onChange = onChange; this.timers = timers;
      this.live = false; this.backend = false; this.language = "en-US"; this.seq = 0;
      this.state = { query: "", items: [], page: 0, totalPages: 0, loading: false, error: "", stale: false };
      try {
        const movies = JSON.parse(storage?.getItem(STORE) || "[]");
        if (this.source === "tmdb" && Array.isArray(movies)) for (const movie of movies.slice(-200)) {
          if (movie?.source === "tmdb" && Number.isSafeInteger(movie.id) && movie.id > 0 && movie.tmdb_id === movie.id && typeof movie.title === "string") {
            this.saved.set(movie.id, movie); this.register(movie);
          }
        }
      } catch { /* saved metadata is optional */ }
    }
    register(movie) {
      if (!movie || movie.source !== "tmdb" || !Number.isSafeInteger(movie.id) || movie.id <= 0) return null;
      const old = this.records.get(movie.id);
      // Search summaries should not discard already fetched cast/trailer details.
      const merged = old?.full_details && !movie.full_details && old.metadata_language === movie.metadata_language ? { ...movie, ...old } : { ...old, ...movie };
      merged.in_model = this.snapshot.has(movie.id);
      merged.tags = Array.isArray(merged.tags) ? merged.tags : [];
      merged.genres = Array.isArray(merged.genres) ? merged.genres : [];
      merged.cast = Array.isArray(merged.cast) ? merged.cast : [];
      this.records.set(movie.id, merged);
      return merged;
    }
    get(id) { return this.source === "tmdb" ? this.records.get(id) : null; }
    savedMovies() { return this.source === "tmdb" ? [...this.saved.keys()].map((id) => this.get(id)).filter(Boolean) : []; }
    remember(movie) {
      if (this.source !== "tmdb" || movie?.source !== "tmdb") return;
      const known = this.register(movie);
      if (!known) return;
      this.saved.delete(movie.id); this.saved.set(movie.id, known);
      while (this.saved.size > 200) this.saved.delete(this.saved.keys().next().value);
      try { this.storage?.setItem(STORE, JSON.stringify([...this.saved.values()])); } catch { /* session metadata remains available */ }
    }
    async json(path, signal) {
      const response = await this.fetcher(path, { signal });
      if (!response.ok) throw Object.assign(new Error("Movie search is temporarily unavailable."), { status: response.status });
      return response.json();
    }
    async configure(backend) {
      this.backend = backend;
      if (!backend || this.source !== "tmdb") return;
      try {
        const data = await this.json("/api/capabilities");
        this.live = data.catalogue?.live_search === true;
      } catch { this.live = false; }
      this.onChange();
    }
    setQuery(query, language = this.language) {
      this.timers.clearTimeout(this.timer); this.controller?.abort();
      const seq = ++this.seq;
      this.language = language;
      this.state = { query: query.trim(), items: [], page: 0, totalPages: 0, loading: this.live && !!query.trim(), error: "", stale: false };
      this.onChange();
      if (this.state.loading) this.timer = this.timers.setTimeout(() => this.run(seq, false), 300);
    }
    async run(seq, append) {
      if (seq !== this.seq || !this.state.query || !this.live) return;
      this.controller?.abort(); this.controller = new AbortController();
      this.state.loading = true; this.state.error = ""; this.onChange();
      const page = append ? this.state.page + 1 : 1;
      const params = new URLSearchParams({ q: this.state.query, page: String(page), language: this.language });
      try {
        const data = await this.json(`/api/search?${params}`, this.controller.signal);
        if (seq !== this.seq) return;
        if (!Array.isArray(data.items)) throw Error("Invalid search response");
        const incoming = data.items.map((movie) => this.register(movie)).filter(Boolean);
        const merged = new Map((append ? this.state.items : []).map((movie) => [movie.id, movie]));
        incoming.forEach((movie) => merged.set(movie.id, movie));
        this.state.items = [...merged.values()]; this.state.page = page;
        this.state.totalPages = Math.min(500, Number(data.total_pages) || 0);
        this.state.stale = data.stale === true;
      } catch (error) {
        if (seq !== this.seq) return;
        this.state.error = error.status === 429 ? "Movie search is busy. Try again shortly." : "Live search is unavailable. Showing downloaded or cached matches.";
      } finally {
        if (seq === this.seq) { this.state.loading = false; this.onChange(); }
      }
    }
    more() { if (!this.state.loading && this.state.page < this.state.totalPages) return this.run(this.seq, true); }
    async details(id) {
      const known = this.get(id);
      if (known?.full_details && known.metadata_language === this.language) return known;
      if (!this.backend) return known || this.snapshot.get(id);
      const movie = await this.json(`/api/movies/${id}?language=${encodeURIComponent(this.language)}`);
      if (movie.id !== id || movie.source !== "tmdb") throw Error("Movie identity mismatch");
      const result = this.register(movie); this.remember(result);
      return result;
    }
  }
  if (typeof module !== "undefined" && module.exports) module.exports = CatalogueBrowser;
  root.CinemagicCatalogueBrowser = CatalogueBrowser;
})(typeof globalThis !== "undefined" ? globalThis : window);
