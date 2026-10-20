/* Resolve explicit external choices incrementally; preferences themselves stay in PreferenceStore. */
(function (root) {
  "use strict";
  const STORE = "cinemagic:preference-features:v1", TTL = 86400000, CACHE_BYTES = 2 * 1024 * 1024;
  class PreferenceResolver {
    constructor(snapshot, { storage, fetcher, lookup = () => null, onChange = () => {}, clock = () => Date.now() } = {}) {
      this.snapshot = new Set(snapshot.map(m => m.id)); this.source = snapshot[0]?.source;
      this.storage = storage; this.fetcher = fetcher; this.lookup = lookup; this.onChange = onChange; this.clock = clock;
      this.records = new Map(); this.choices = new Map(); this.failures = new Map(); this.attempted = new Set();
      this.inFlight = new Set(); this.storageFailed = false;
      try {
        const saved = JSON.parse(storage?.getItem(STORE) || "null");
        if (saved?.version === 1 && Array.isArray(saved.items)) for (const record of saved.items.slice(-20000)) {
          if (/^tmdb:[1-9]\d*$/.test(record?.key)) this.records.set(record.key, record);
        }
      } catch { /* Features can be rehydrated; saved choices are independent. */ }
    }
    configure(config, { backend = false, localResolve = null } = {}) {
      if (config?.feature_version !== this.config?.feature_version) { this.attempted.clear(); this.failures.clear(); }
      this.config = config?.version === 1 ? config : null; this.backend = backend; this.localResolve = localResolve;
      this.sync(this.liked || [], this.disliked || []);
    }
    compatible(record) {
      if (!this.config || !record || record.version !== 1 || record.feature_version !== this.config.feature_version || record.feature_language !== "en-US") return false;
      if (!["applied", "unavailable"].includes(record.status) || !Array.isArray(record.vector) || record.vector.length > this.config.vocabulary_size) return false;
      const indices = new Set();
      return record.vector.every(pair => {
        if (!Array.isArray(pair) || pair.length !== 2) return false;
        const [i, v] = pair;
        if (!Number.isInteger(i) || i < 0 || i >= this.config.vocabulary_size || !Number.isFinite(v) || v < 0 || v > 1 || indices.has(i)) return false;
        indices.add(i); return true;
      }) && record.movie?.source === "tmdb" && record.key === `tmdb:${record.movie.id}` &&
        typeof record.movie.title === "string" && record.movie.title.length <= 500 &&
        Array.isArray(record.movie.genres) && record.movie.genres.length <= 64 && record.movie.genres.every(t => typeof t === "string" && t.length <= 200) &&
        Array.isArray(record.movie.tags) && record.movie.tags.length <= 24 && record.movie.tags.every(t => typeof t === "string" && t.length <= 200) &&
        Array.isArray(record.taste?.genres) && record.taste.genres.length <= 64 && record.taste.genres.every(t => this.config.genres.includes(t)) &&
        Array.isArray(record.taste?.tags) && record.taste.tags.length <= this.config.vocabulary_size && record.taste.tags.every(t => typeof t === "string" && t.length <= 200) &&
        (record.status !== "applied" || record.vector.some(([, v]) => v > 0));
    }
    sync(liked, disliked) {
      this.liked = [...liked]; this.disliked = [...disliked];
      this.choices = new Map();
      if (this.source === "tmdb") {
        for (const id of this.liked) if (!this.snapshot.has(id)) this.choices.set(`tmdb:${id}`, "liked");
        for (const id of this.disliked) if (!this.snapshot.has(id)) this.choices.set(`tmdb:${id}`, "disliked");
      }
      for (const key of this.attempted) if (!this.choices.has(key)) { this.attempted.delete(key); this.failures.delete(key); }
      this.pump();
    }
    get(id) { return this.records.get(`tmdb:${id}`)?.movie; }
    status(key) {
      const record = this.records.get(key);
      if (this.compatible(record)) return { status: record.status, reason: record.reason, stale: record.stale || this.clock() - record.resolved_at > TTL };
      return this.failures.get(key) || { status: "pending", reason: "Waiting for usable movie metadata." };
    }
    summary() {
      const counts = { applied: 0, pending: 0, unavailable: 0, stale: 0 };
      for (const key of this.choices.keys()) { const info = this.status(key); counts[info.status]++; if (info.stale) counts.stale++; }
      return counts;
    }
    retry() {
      this.attempted.clear(); this.failures.clear();
      for (const [key, record] of this.records) if (record.status === "unavailable") this.records.delete(key);
      this.pump(); this.onChange();
    }
    persist() {
      // Evict inactive derived features first; never delete a saved explicit preference.
      const inactive = [...this.records.keys()].filter(k => !this.choices.has(k));
      for (const key of inactive.slice(0, Math.max(0, this.records.size - 20000))) this.records.delete(key);
      if (!this.storage) { this.storageFailed = true; return; }
      // Leave room for authoritative preferences, Watchlist and history. All active
      // features remain in session; uncached choices rehydrate after a reload.
      const records = [...this.records.values()].reverse();
      const ordered = [...records.filter(r => this.choices.has(r.key)), ...records.filter(r => !this.choices.has(r.key))];
      let bytes = 64, selected = [];
      for (const record of ordered) {
        if (selected.length >= 200) break;
        const json = JSON.stringify(record), size = json.length * 2 + 2;
        if (bytes + size <= CACHE_BYTES) { selected.push(json); bytes += size; }
      }
      for (;;) {
        try { this.storage.setItem(STORE, `{"version":1,"items":[${selected.join(",")}]}`); return; }
        catch {
          this.storageFailed = true;
          if (!selected.length) {
            try { this.storage.removeItem?.(STORE); } catch { /* Storage itself is denied. */ }
            return;
          }
          selected = selected.slice(0, Math.floor(selected.length / 2));
        }
      }
    }
    pump() {
      if (!this.config) return;
      for (const key of this.choices.keys()) {
        if (this.inFlight.size >= 2) break;
        const record = this.records.get(key);
        if (this.inFlight.has(key) || this.attempted.has(key) || this.compatible(record) && !record.stale && this.clock() - record.resolved_at <= TTL) continue;
        this.inFlight.add(key); this.attempted.add(key);
        this.resolve(key).finally(() => { this.inFlight.delete(key); this.pump(); });
      }
    }
    async resolve(key) {
      try {
        const id = Number(key.split(":")[1]);
        const known = this.lookup(id);
        let record;
        if (this.backend) {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 30000);
          try { record = await this.fetcher(`/api/preferences/tmdb/${id}`, { signal: controller.signal }); }
          finally { clearTimeout(timeout); }
        }
        else if (known?.full_details && known.metadata_language === "en-US" && this.localResolve) record = this.localResolve(known);
        else {
          this.failures.set(key, { status: "pending", reason: "Fresh metadata needs the backend app. Your choice is saved." });
          return;
        }
        if (record?.key !== key || !this.compatible(record)) throw Object.assign(Error("Incompatible feature response"), { incompatible: true });
        this.records.delete(key); this.records.set(key, { ...record, resolved_at: this.clock() }); this.failures.delete(key);
        this.persist();
      } catch (error) {
        this.failures.set(key, { status: "unavailable", reason: error.incompatible ? "Feature metadata is incompatible with this model. Reload or retry; your choice is saved." : error.status === 404 ? "Movie metadata was not found. Your choice is saved." : "Metadata is unavailable. Your choice is saved; retry when ready." });
      } finally {
        // Metadata is choice-independent. Only current choices enter payload(), including reversals.
        if (this.choices.has(key)) this.onChange();
      }
    }
    payload() {
      if (!this.config) return null;
      const vector = new Map(), genres = new Map(), tags = new Map(), seeds = [];
      let positive_count = 0, negative_count = 0;
      const add = (map, k, v) => map.set(k, (map.get(k) || 0) + v);
      for (const [key, choice] of this.choices) {
        const record = this.records.get(key);
        if (!this.compatible(record) || record.status !== "applied") continue;
        const w = choice === "liked" ? 1 : -(this.config.dislike_penalty ?? .5);
        if (choice === "liked") positive_count++; else negative_count++;
        record.vector.forEach(([i, value]) => add(vector, i, w * value));
        record.taste.genres.forEach(name => add(genres, name, w));
        record.taste.tags.forEach(name => add(tags, name, w));
        if (choice === "liked") seeds.push({ key, title: record.movie.title, genres: record.movie.genres,
          tags: record.movie.tags, vector: record.vector });
      }
      if (!positive_count && !negative_count) return null;
      const terms = map => [...map].map(([name, weight]) => ({ name, weight }));
      return { version: 1, feature_version: this.config.feature_version, vector: [...vector].filter(([, v]) => v !== 0),
        positive_count, negative_count, genres: terms(genres), tags: terms(tags), seeds: seeds.slice(-2).reverse() };
    }
  }
  if (typeof module !== "undefined" && module.exports) module.exports = PreferenceResolver;
  root.CinemagicPreferenceResolver = PreferenceResolver;
})(typeof globalThis !== "undefined" ? globalThis : window);
