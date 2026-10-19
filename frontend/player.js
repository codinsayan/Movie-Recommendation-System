/* One active iframe. Only an explicit viewer action selects another source. */
(function (root) {
  "use strict";
  class MoviePlayer {
    constructor({ providers, viewing, eventTarget = root, timers = root, onChange = () => {} }) {
      this.providers = providers;
      this.viewing = viewing;
      this.eventTarget = eventTarget;
      this.timers = timers;
      this.onChange = onChange;
      this.session = null;
      this.generation = 0;
    }

    open(movie, { host, select, status, restart, removeHistory }, startOver = false) {
      this.close();
      const ref = this.providers.reference(movie);
      if (!ref?.tmdbId) throw new TypeError("This movie has no verified TMDB mapping");
      const sources = this.providers.list();
      if (!sources.length) throw new Error("No movie sources are enabled");
      const saved = this.viewing.progress(ref.key);
      if (startOver) this.viewing.removeProgress(ref.key);
      const preferred = this.providers.get(this.viewing.preferredSource) || sources[0];
      const position = startOver || saved.completed ? 0 : saved.position || 0;
      this.session = { movie, ref, host, select, status, restart, removeHistory,
        position, duration: saved.duration || 0, generation: this.generation };
      select.replaceChildren(...sources.map((source) => {
        const option = select.ownerDocument.createElement("option");
        option.value = source.key; option.textContent = source.label;
        return option;
      }));
      this.selectHandler = () => this.selectSource(select.value, true);
      select.addEventListener("change", this.selectHandler);
      this.restartHandler = () => {
        if (!this.session) return;
        this.session.position = 0;
        this.session.forget = false;
        this.viewing.removeProgress(ref.key);
        this.selectSource(select.value, false, true);
        this.onChange();
      };
      restart?.addEventListener("click", this.restartHandler);
      this.removeHandler = () => { this.viewing.removeProgress(ref.key); this.session.forget = true; this.onChange(); this.setStatus("Removed from viewing history."); };
      removeHistory?.addEventListener("click", this.removeHandler);
      this.selectSource(preferred.key, false);
    }

    setStatus(text) { if (this.session) this.session.status.textContent = text; }
    save() {
      const s = this.session;
      if (s && !s.forget && s.position > 0 && s.duration > 0) this.viewing.saveProgress(s.ref.key, s.position, s.duration, s.completed);
    }
    detachFrame() {
      const s = this.session;
      if (!s) return;
      this.timers.clearTimeout(s.timer);
      if (s.handler) this.eventTarget.removeEventListener("message", s.handler);
      s.host.replaceChildren();
      s.frame = null;
    }
    selectSource(key, remember, autoplay = remember) {
      const s = this.session;
      const provider = this.providers.get(key);
      if (!s || !provider) return;
      this.save();
      this.detachFrame();
      s.provider = provider;
      s.select.value = key;
      s.completed = false;
      s.failed = false;
      s.playing = false;
      s.autoplay = autoplay;
      s.playCommandSent = false;
      if (remember) this.viewing.prefer(key);
      const frame = s.host.ownerDocument.createElement("iframe");
      frame.title = `${s.movie.title} — ${provider.label}`;
      frame.allow = "autoplay; fullscreen; picture-in-picture; encrypted-media";
      frame.allowFullscreen = true;
      // These providers reject sandboxed embeds. Use a standard cross-origin
      // iframe as requested; continue validating every incoming player message.
      frame.referrerPolicy = "strict-origin-when-cross-origin";
      frame.src = provider.buildMovieUrl(s.ref.tmdbId, s.position, autoplay);
      s.frame = frame;
      s.host.replaceChildren(frame);
      this.setStatus(autoplay ? `Starting ${provider.label}… If playback stays paused, press Play.` :
        `Press Play in ${provider.label}. If it does not work, choose another source above.`);
      const generation = ++this.generation;
      let lastSaved = 0;
      s.handler = (event) => {
        if (this.session !== s || this.generation !== generation || s.frame !== frame ||
            event.origin !== provider.origin || event.source !== frame.contentWindow) return;
        const normalized = provider.parseMessage(event.data, s.ref.tmdbId);
        if (!normalized) return;
        this.timers.clearTimeout(s.timer);
        if (normalized.type === "error") {
          s.failed = true;
          this.save();
          this.setStatus("This source could not play the movie. Choose another source above.");
        } else if (normalized.type === "playing") {
          s.failed = false;
          s.playing = true;
          s.autoplay = false;
          this.setStatus(`Playing with ${provider.label}. You can change the source at any time.`);
        } else if (normalized.type === "ready" && !s.failed && !s.playing) {
          if (s.autoplay && !s.playCommandSent) {
            s.playCommandSent = true;
            provider.requestPlay(frame);
            this.setStatus(`Starting ${provider.label}… If playback stays paused, press Play.`);
          } else if (!s.autoplay) this.setStatus(`${provider.label} is ready. Press Play to watch.`);
        } else if (normalized.type === "paused" && !s.failed) {
          s.playing = false;
          s.autoplay = false;
          this.save();
          this.setStatus("Paused. Choose another source if you need to.");
        } else if (normalized.type === "progress") {
          if (normalized.playing) {
            s.failed = false;
            s.playing = true;
            s.autoplay = false;
            this.setStatus(`Playing with ${provider.label}. You can change the source at any time.`);
          }
          s.position = normalized.position;
          s.duration = normalized.duration;
          // Completion is a resume/UI state, not an implicit movie rating.
          if (Date.now() - lastSaved >= 5000) { this.save(); lastSaved = Date.now(); }
        } else if (normalized.type === "ended") {
          s.completed = true;
          this.save();
          this.setStatus("Finished. Choose another movie whenever you're ready.");
          this.onChange();
        }
      };
      this.eventTarget.addEventListener("message", s.handler);
      s.timer = this.timers.setTimeout(() => {
        if (this.session === s && this.generation === generation) this.setStatus("Still loading? Press Play, or choose another source above.");
      }, 20000);
    }

    close() {
      const s = this.session;
      if (!s) return;
      this.save();
      this.detachFrame();
      s.select.removeEventListener("change", this.selectHandler);
      s.restart?.removeEventListener("click", this.restartHandler);
      s.removeHistory?.removeEventListener("click", this.removeHandler);
      this.session = null;
      this.generation++;
      this.onChange();
    }
  }
  if (typeof module !== "undefined" && module.exports) module.exports = MoviePlayer;
  root.CinemagicMoviePlayer = MoviePlayer;
})(typeof globalThis !== "undefined" ? globalThis : window);
