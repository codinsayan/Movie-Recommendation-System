/* Device-local recommendation preferences; catalogue IDs never cross profiles. */
(function (root) {
  "use strict";
  const KEY = "cinemagic:preferences:v2";
  const LEGACY_KEY = "cinemagic:v1";
  const sources = ["tmdb", "curated"];
  const ids = (value) => Array.isArray(value)
    ? [...new Set(value.filter((id) => Number.isSafeInteger(id) && id > 0))].slice(-10000) : [];
  function normalize(value = {}) {
    if (!value || typeof value !== "object") value = {};
    const liked = ids(value.liked);
    const loved = new Set(liked);
    return { liked, disliked: ids(value.disliked).filter((id) => !loved.has(id)),
      mood: typeof value.mood === "string" ? value.mood.trim().slice(0, 200) : "" };
  }
  function read(storage, key) {
    try { return JSON.parse(storage?.getItem(key) || "null"); } catch { return null; }
  }

  class PreferenceStore {
    constructor(storage) {
      this.storage = storage;
      this.state = { version: 2, profiles: {}, legacyImported: false };
      const saved = read(storage, KEY);
      if (saved?.version === 2) {
        this.state.legacyImported = saved.legacyImported === true;
        for (const source of sources) {
          if (saved.profiles && Object.hasOwn(saved.profiles, source)) this.state.profiles[source] = normalize(saved.profiles[source]);
        }
      }
      this.legacy = read(storage, LEGACY_KEY);
    }
    persist() {
      try {
        if (!this.storage) return false;
        this.storage.setItem(KEY, JSON.stringify(this.state));
        return true;
      } catch { return false; }
    }
    load(source) {
      if (!sources.includes(source)) throw new TypeError("Unknown preference catalogue");
      if (!Object.hasOwn(this.state.profiles, source)) {
        // The old store had no catalogue identity. Import it once into the
        // active catalogue, then keep the two profiles independent forever.
        const legacy = !this.state.legacyImported && this.legacy && typeof this.legacy === "object" ? this.legacy : {};
        this.state.profiles[source] = normalize(legacy);
        this.state.legacyImported = true;
        this.persist();
      }
      return normalize(this.state.profiles[source]);
    }
    save(source, profile) {
      if (!sources.includes(source)) throw new TypeError("Unknown preference catalogue");
      this.state.profiles[source] = normalize(profile);
      this.state.legacyImported = true;
      return this.persist();
    }
  }
  if (typeof module !== "undefined" && module.exports) module.exports = PreferenceStore;
  root.CinemagicPreferenceStore = PreferenceStore;
})(typeof globalThis !== "undefined" ? globalThis : window);
