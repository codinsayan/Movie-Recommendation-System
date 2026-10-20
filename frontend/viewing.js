/* Browser-local viewing state. Likes/dislikes remain in their existing store. */
(function (root) {
  "use strict";
  const STORE = "cinemagic:viewing:v1";
  const validKey = (key) => /^(tmdb|curated):[1-9]\d*$/.test(key);
  const finite = (n) => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 86400;
  const validProgress = (position, duration) => finite(position) && finite(duration) && duration > 0 && position <= duration + 2;
  const providers = new Set(["cinesrc", "vidlink", "vidsrc"]);
  const policy = Object.freeze({ minSeconds: 120, minFraction: .30, freshnessMs: 7 * 24 * 60 * 60 * 1000 });
  const coverage = (intervals) => intervals.reduce((sum, [a, b]) => sum + b - a, 0);
  function merge(intervals, from, to, duration) {
    if (!validProgress(from, duration) || !validProgress(to, duration) || to <= from || from >= duration) return intervals;
    const result = [];
    const bounded = [...intervals, [from, to]].map(([a, b]) => [Math.min(a, duration), Math.min(b, duration)]).filter(([a, b]) => b > a);
    for (const pair of bounded.sort((a, b) => a[0] - b[0])) {
      const last = result[result.length - 1];
      if (last && pair[0] <= last[1]) last[1] = Math.max(last[1], pair[1]);
      else result.push([...pair]);
    }
    // Keep the largest measured intervals when storage must be bounded; never fill gaps.
    return result.sort((a, b) => (b[1] - b[0]) - (a[1] - a[0])).slice(0, 200).sort((a, b) => a[0] - b[0]);
  }

  class ViewingStore {
    constructor(storage, now = () => Date.now()) {
      this.storage = storage;
      this.now = now;
      this.state = { version: 2, preferredSource: null, progress: {}, watchlist: {}, evidence: {}, playback: {},
        options: { use_viewing: false, recent_playback_only: false } };
      try {
        const value = JSON.parse(storage?.getItem(STORE) || "null");
        if (value?.version === 1 || value?.version === 2) {
          if (typeof value.preferredSource === "string") this.state.preferredSource = value.preferredSource;
          for (const [key, item] of Object.entries(value.progress || {})) {
            if (validKey(key) && item && validProgress(item.position, item.duration) && Number.isFinite(item.updatedAt)) {
              this.state.progress[key] = { position: Math.min(item.position, item.duration), duration: item.duration,
                updatedAt: item.updatedAt, completed: item.completed === true };
            }
          }
          for (const [key, time] of Object.entries(value.watchlist || {})) {
            if (validKey(key) && Number.isFinite(time)) this.state.watchlist[key] = time;
          }
          if (value.version === 2) {
            for (const [key, item] of Object.entries(value.evidence || {}).slice(0, 500)) {
              if (!validKey(key) || !item || !finite(item.duration) || item.duration <= 0 || !Number.isFinite(item.updated_at)) continue;
              let intervals = [];
              for (const pair of (Array.isArray(item.intervals) ? item.intervals : []).slice(0, 200)) {
                if (Array.isArray(pair) && pair.length === 2) intervals = merge(intervals, pair[0], pair[1], item.duration);
              }
              this.state.evidence[key] = { intervals, duration: item.duration, updated_at: item.updated_at,
                plays: Number.isInteger(item.plays) ? Math.max(0, Math.min(3, item.plays)) : 0 };
            }
            for (const [key, sources] of Object.entries(value.playback || {}).slice(0, 500)) {
              if (!validKey(key) || !sources || typeof sources !== "object") continue;
              for (const [provider, item] of Object.entries(sources)) {
                if (!providers.has(provider) || !item) continue;
                if (![item.verified_at, item.failed_at].every((n) => Number.isFinite(n) && n >= 0)) continue;
                (this.state.playback[key] ||= {})[provider] = { verified_at: item.verified_at, failed_at: item.failed_at };
              }
            }
            this.state.options.use_viewing = value.options?.use_viewing === true;
            this.state.options.recent_playback_only = value.options?.recent_playback_only === true;
          }
        }
      } catch { /* corrupt or unavailable storage: keep session state */ }
    }

    persist() {
      // Bound browser storage without changing which films a viewer likes.
      const recent = Object.entries(this.state.progress).sort((a, b) => b[1].updatedAt - a[1].updatedAt).slice(0, 500);
      this.state.progress = Object.fromEntries(recent);
      this.state.evidence = Object.fromEntries(Object.entries(this.state.evidence).sort((a, b) => b[1].updated_at - a[1].updated_at).slice(0, 500));
      this.state.playback = Object.fromEntries(Object.entries(this.state.playback).sort((a, b) =>
        Math.max(...Object.values(b[1]).map((v) => Math.max(v.verified_at, v.failed_at))) -
        Math.max(...Object.values(a[1]).map((v) => Math.max(v.verified_at, v.failed_at)))).slice(0, 500));
      try { this.storage?.setItem(STORE, JSON.stringify(this.state)); } catch { /* session-only */ }
    }
    progress(key) { return validKey(key) ? { ...this.state.progress[key] } : {}; }
    saveProgress(key, position, duration, completed = false) {
      if (!validKey(key) || !validProgress(position, duration)) return false;
      this.state.progress[key] = { position: Math.min(position, duration), duration,
        updatedAt: this.now(), completed: completed === true };
      this.persist();
      return true;
    }
    prefer(source) { this.state.preferredSource = source; this.persist(); }
    get preferredSource() { return this.state.preferredSource; }
    has(key) { return Object.hasOwn(this.state.watchlist, key); }
    toggle(key) {
      if (!validKey(key)) return false;
      if (this.has(key)) delete this.state.watchlist[key];
      else this.state.watchlist[key] = this.now();
      this.persist();
      return this.has(key);
    }
    watchlistKeys() { return Object.keys(this.state.watchlist).sort((a, b) => this.state.watchlist[b] - this.state.watchlist[a]); }
    continueKeys() {
      return Object.entries(this.state.progress).filter(([, p]) => p.position >= 10 && !p.completed && p.position < p.duration - 10)
        .sort((a, b) => b[1].updatedAt - a[1].updatedAt).map(([key]) => key);
    }
    recordInterval(key, from, to, duration, run) {
      if (!validKey(key) || !validProgress(from, duration) || !validProgress(to, duration) || to <= from) return false;
      let item = this.state.evidence[key];
      if (!item || Math.abs(item.duration - duration) > 2) item = { intervals: [], duration, plays: 0 };
      item.intervals = merge(item.intervals, from, to, duration);
      item.duration = duration;
      item.updated_at = this.now();
      this.state.evidence[key] = item;
      if (run.duration !== duration) { run.intervals = []; run.credited = false; run.duration = duration; }
      run.intervals = merge(run.intervals || [], from, to, duration);
      if (!run.credited && coverage(run.intervals) >= Math.max(policy.minSeconds, duration * policy.minFraction)) {
        run.credited = true;
        item.plays = Math.min(3, item.plays + 1);
      }
      return coverage(item.intervals) >= Math.max(policy.minSeconds, duration * policy.minFraction);
    }
    recordPlayback(key, provider, failed = false) {
      if (!validKey(key) || !providers.has(provider)) return;
      const item = (this.state.playback[key] ||= {})[provider] ||= { verified_at: 0, failed_at: 0 };
      item[failed ? "failed_at" : "verified_at"] = this.now();
      this.persist();
    }
    signals() {
      return Object.entries(this.state.evidence).map(([key, item]) => ({ key, duration: item.duration,
        watched_seconds: coverage(item.intervals), plays: Math.max(1, item.plays), updated_at: item.updated_at }))
        .filter((s) => s.watched_seconds >= Math.max(policy.minSeconds, s.duration * policy.minFraction))
        .sort((a, b) => b.updated_at - a.updated_at || (a.key < b.key ? -1 : 1)).slice(0, 500);
    }
    options() { return { ...this.state.options }; }
    setOptions(options) {
      for (const key of ["use_viewing", "recent_playback_only"]) if (typeof options[key] === "boolean") this.state.options[key] = options[key];
      this.persist();
    }
    request() {
      const options = this.options();
      if (!options.use_viewing && !options.recent_playback_only) return { ...options, viewing: null };
      const playback = Object.entries(this.state.playback).flatMap(([key, sources]) =>
        Object.entries(sources).map(([provider, evidence]) => ({ key, provider, ...evidence })));
      return { ...options, viewing: { version: 1, signals: options.use_viewing ? this.signals() : [],
        playback: options.recent_playback_only ? playback : [] } };
    }
    restartProgress(key) { delete this.state.progress[key]; this.persist(); }
    removeProgress(key) {
      delete this.state.progress[key]; delete this.state.evidence[key]; delete this.state.playback[key]; this.persist();
    }
    clearHistory() { this.state.progress = {}; this.state.evidence = {}; this.state.playback = {}; this.persist(); }
  }
  ViewingStore.policy = policy;
  if (typeof module !== "undefined" && module.exports) module.exports = ViewingStore;
  root.CinemagicViewingStore = ViewingStore;
})(typeof globalThis !== "undefined" ? globalThis : window);
