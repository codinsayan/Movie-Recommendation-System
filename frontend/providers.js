/* Movie providers: trusted URL builders and normalization of documented events. */
(function (root) {
  "use strict";
  const positiveId = (id) => Number.isSafeInteger(id) && id > 0;
  const seconds = (n) => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 86400;

  function reference(movie) {
    if (!movie || !positiveId(movie.id)) return null;
    const tmdbId = positiveId(movie.tmdb_id) ? movie.tmdb_id : null;
    const source = movie.source === "tmdb" || movie.source === "curated" ? movie.source : null;
    if (!source) return null;
    // Only explicit TMDB identity can be sent to an embed service.
    if (source === "tmdb" && !tmdbId) return null;
    return { key: `${source}:${movie.id}`, source, id: movie.id, tmdbId };
  }

  function progress(position, duration) {
    if (!seconds(position) || !seconds(duration) || duration <= 0 || position > duration + 2) return null;
    return { type: "progress", position: Math.min(position, duration), duration };
  }

  function cineEvent(data) {
    const types = { "cinesrc:ready": "ready", "cinesrc:play": "playing", "cinesrc:pause": "paused",
      "cinesrc:seeking": "seeking", "cinesrc:seeked": "seeked", "cinesrc:ended": "ended", "cinesrc:error": "error" };
    if (data.type === "cinesrc:timeupdate") return progress(data.currentTime, data.duration);
    return types[data.type] ? { type: types[data.type] } : null;
  }

  function linkEvent(data, tmdbId) {
    if (data.type !== "PLAYER_EVENT" || !data.data || typeof data.data !== "object") return null;
    const event = data.data;
    // The current published event schema uses mtmdbId (including that typo).
    const id = event.mtmdbId ?? event.tmdbId;
    if (id != null && String(id) !== String(tmdbId)) return null;
    if (event.mediaType && event.mediaType !== "movie") return null;
    const types = { play: "playing", pause: "paused", seeked: "seeked", ended: "ended" };
    if (event.event === "timeupdate") return progress(event.currentTime, event.duration);
    return types[event.event] ? { type: types[event.event] } : null;
  }

  function srcEvent(data, tmdbId) {
    if (data.type !== "PLAYER_EVENT" || !data.data || typeof data.data !== "object") return null;
    const event = data.data, info = event.player_info;
    if (!info || typeof info !== "object" || info.mediaType !== "movie") return null;
    if (info.tmdb != null && String(info.tmdb) !== String(tmdbId)) return null;
    if (event.player_status === "playing") {
      const update = progress(event.player_progress, event.player_duration);
      return update ? { ...update, playing: true } : null;
    }
    const types = { paused: "paused", completed: "ended", seeked: "seeked" };
    return types[event.player_status] ? { type: types[event.player_status] } : null;
  }

  function makeProvider(key, label, origin, moviePath, resumeParam, parseMessage, documentation, options = {}) {
    return Object.freeze({ key, label, origin, documentation, enabled: true, resume: true, ...options,
      capabilities: Object.freeze({ progress: true, explicitError: key === "cinesrc" }),
      buildMovieUrl(tmdbId, position = 0, autoplay = false) {
        if (!positiveId(tmdbId)) throw new TypeError("A mapped TMDB movie ID is required");
        if (!seconds(position)) throw new TypeError("Invalid playback position");
        const url = new URL(moviePath + tmdbId, origin);
        if (position > 0) url.searchParams.set(resumeParam, String(Math.floor(position)));
        url.searchParams.set("autoplay", key === "vidsrc" ? (autoplay ? "1" : "0") : String(autoplay));
        if (key === "cinesrc" && autoplay) url.searchParams.set("continueprompt", "false");
        return url.href;
      },
      requestPlay(frame) {
        if (key === "cinesrc") frame.contentWindow.postMessage({ type: "cinesrc:command", command: "play", args: [] }, origin);
      },
      parseMessage(data, tmdbId) {
        if (!data || typeof data !== "object" || Array.isArray(data)) return null;
        return parseMessage(data, tmdbId);
      },
    });
  }

  const registry = Object.freeze([
    makeProvider("cinesrc", "CineSrc", "https://cinesrc.st", "/embed/movie/", "t", cineEvent, "https://cinesrc.st/docs"),
    makeProvider("vidlink", "VidLink", "https://vidlink.pro", "/movie/", "startAt", linkEvent, "https://vidlink.pro/"),
    makeProvider("vidsrc", "VidSrc", "https://vidsrc.sh", "/embed/movie/", "startAt", srcEvent, "https://vidsrc.sh/vidsrc/docs/"),
  ]);
  const api = Object.freeze({ version: 1, reference, seconds, list: () => registry.filter((p) => p.enabled),
    all: () => [...registry],
    get: (key) => registry.find((p) => p.key === key && p.enabled) || null });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CinemagicProviders = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
