/* One active iframe. Only an explicit viewer action selects another source. */
(function (root) {
  "use strict";
  class MoviePlayer {
    constructor({ providers, viewing, eventTarget = root, timers = root, onChange = () => {},
      now = () => Date.now(), isVisible = () => !root.document?.hidden }) {
      this.providers = providers;
      this.viewing = viewing;
      this.eventTarget = eventTarget;
      this.timers = timers;
      this.onChange = onChange;
      this.now = now;
      this.isVisible = isVisible;
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
      if (startOver) this.viewing.restartProgress(ref.key);
      const preferred = this.providers.get(this.viewing.preferredSource) || sources[0];
      const position = startOver || saved.completed ? 0 : saved.position || 0;
      this.session = { movie, ref, host, select, status, restart, removeHistory,
        position, duration: saved.duration || 0, generation: this.generation, evidenceRun: {} };
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
        this.session.evidenceRun = {};
        this.viewing.restartProgress(ref.key);
        this.selectSource(select.value, false, true);
        this.onChange();
      };
      restart?.addEventListener("click", this.restartHandler);
      this.removeHandler = () => { this.forget(); this.setStatus("Removed from viewing history."); };
      removeHistory?.addEventListener("click", this.removeHandler);
      this.selectSource(preferred.key, false);
    }

    setStatus(text) { if (this.session) this.session.status.textContent = text; }
    save() {
      const s = this.session;
      if (s && !s.forget && s.position > 0 && s.duration > 0) this.viewing.saveProgress(s.ref.key, s.position, s.duration, s.completed);
      this.viewing.persist();
    }
    suspend() { if (this.session) this.session.anchor = null; this.save(); }
    forget(all = false) {
      if (all) this.viewing.clearHistory();
      else if (this.session) this.viewing.removeProgress(this.session.ref.key);
      if (this.session) { this.session.forget = true; this.session.anchor = null; }
      this.onChange();
    }
    observe(position, duration) {
      const s = this.session, now = this.now();
      if (!s || s.forget || s.failed || !s.playing || !this.isVisible()) { if (s) s.anchor = null; return; }
      const previous = s.anchor;
      s.anchor = { position, duration, time: now };
      if (!previous || Math.abs(previous.duration - duration) > 2) return;
      const wall = (now - previous.time) / 1000, delta = position - previous.position;
      // Reject seek jumps, long silent gaps, reverse progress and implausible clocks.
      if (!(wall > 0 && wall <= 15 && delta > 0 && delta <= 15 && delta <= wall * 1.25 + .25)) return;
      const before = this.viewing.signals().some((signal) => signal.key === s.ref.key);
      const qualifies = this.viewing.recordInterval(s.ref.key, previous.position, position, duration, s.evidenceRun);
      s.sourceSeconds += delta;
      if (!s.verified && s.sourceSeconds >= 10) {
        s.verified = true;
        this.viewing.recordPlayback(s.ref.key, s.provider.key);
        this.onChange();
      }
      if (!before && qualifies) this.onChange();
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
      s.anchor = null;
      s.sourceSeconds = 0;
      s.verified = false;
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
          s.playing = false;
          s.anchor = null;
          s.sourceSeconds = 0;
          s.verified = false;
          if (!s.forget) this.viewing.recordPlayback(s.ref.key, provider.key, true);
          this.save();
          this.onChange();
          this.setStatus("This source could not play the movie. Choose another source above.");
        } else if (normalized.type === "playing") {
          s.failed = false;
          s.playing = true;
          s.anchor = null;
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
          s.anchor = null;
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
          this.observe(normalized.position, normalized.duration);
          // Completion is a resume/UI state, not an implicit movie rating.
          if (this.now() - lastSaved >= 5000) { this.save(); lastSaved = this.now(); }
        } else if (normalized.type === "ended") {
          s.playing = false;
          s.anchor = null;
          s.completed = true;
          this.save();
          this.setStatus("Finished. Choose another movie whenever you're ready.");
          this.onChange();
        } else if (normalized.type === "seeking" || normalized.type === "seeked") {
          s.anchor = null;
          s.sourceSeconds = 0;
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
