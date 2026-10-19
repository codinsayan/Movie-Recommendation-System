/* Browser-local viewing state. Likes/dislikes remain in their existing store. */
(function (root) {
  "use strict";
  const STORE = "cinemagic:viewing:v1";
  const validKey = (key) => /^(tmdb|curated):[1-9]\d*$/.test(key);
  const finite = (n) => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 86400;
  const validProgress = (position, duration) => finite(position) && finite(duration) && duration > 0 && position <= duration + 2;

  class ViewingStore {
    constructor(storage, now = () => Date.now()) {
      this.storage = storage;
      this.now = now;
      this.state = { version: 1, preferredSource: null, progress: {}, watchlist: {} };
      try {
        const value = JSON.parse(storage?.getItem(STORE) || "null");
        if (value?.version === 1) {
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
        }
      } catch { /* corrupt or unavailable storage: keep session state */ }
    }

    persist() {
      // Bound browser storage without changing which films a viewer likes.
      const recent = Object.entries(this.state.progress).sort((a, b) => b[1].updatedAt - a[1].updatedAt).slice(0, 500);
      this.state.progress = Object.fromEntries(recent);
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
    removeProgress(key) { delete this.state.progress[key]; this.persist(); }
    clearHistory() { this.state.progress = {}; this.persist(); }
  }
  if (typeof module !== "undefined" && module.exports) module.exports = ViewingStore;
  root.CinemagicViewingStore = ViewingStore;
})(typeof globalThis !== "undefined" ? globalThis : window);
