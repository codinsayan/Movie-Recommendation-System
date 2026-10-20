"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const Providers = require("../../frontend/providers.js");
const ViewingStore = require("../../frontend/viewing.js");
const MoviePlayer = require("../../frontend/player.js");
const SourcePicker = require("../../frontend/source-picker.js");
const PreferenceStore = require("../../frontend/preferences.js");

const movie = { id: 45745, tmdb_id: 45745, source: "tmdb", title: "Sintel" };
const memory = () => { const data = new Map(); return { getItem: (k) => data.get(k), setItem: (k, v) => data.set(k, v) }; };

test("a missing browser bootstrap disables frames while identity helpers keep working", () => {
  const fs = require("node:fs"), vm = require("node:vm"), browser = { URL };
  vm.runInNewContext(fs.readFileSync(require.resolve("../../frontend/providers.js"), "utf8"), browser);
  assert.equal(browser.CinemagicProviders.list().length, 0);
  assert.equal(browser.CinemagicProviders.get("cinesrc"), null);
  assert.equal(browser.CinemagicProviders.reference(movie).tmdbId, movie.tmdb_id);
});

test("provider disable rollback preserves local state and only changes future sessions", () => {
  const defaults = Providers.list().map(p => p.key);
  const f = fixture();
  try {
    f.viewing.prefer("vidlink"); f.viewing.toggle("tmdb:45745");
    f.viewing.saveProgress("tmdb:45745", 120, 900);
    f.player.open(movie, f.ui);
    const active = f.player.session.frame;
    Providers.configure(["cinesrc", "vidsrc"]);
    assert.equal(Providers.get("vidlink"), null);
    assert.equal(f.player.session.frame, active, "Configuration never silently replaces an active movie");
    f.player.close(); f.player.open(movie, f.ui);
    assert.equal(f.ui.select.value, "cinesrc");
    assert.deepEqual(f.ui.select.children.map(p => p.value), ["cinesrc", "vidsrc"]);
    assert.equal(f.player.session.position, 120);
    assert.equal(f.viewing.has("tmdb:45745"), true);
    Providers.configure([]);
    f.player.close();
    assert.throws(() => f.player.open(movie, f.ui), /No movie sources/);
    assert.equal(f.ui.host.children.length, 0);
    assert.equal(f.viewing.progress("tmdb:45745").position, 120);
    assert.throws(() => Providers.configure(["untrusted"]), /Unknown/);
    assert.throws(() => Providers.configure(["cinesrc", "cinesrc"]), /duplicate/);
    assert.deepEqual(Providers.list(), []);
  } finally { f.player.close(); Providers.configure(defaults); }
});

test("iframe permissions come from the registry without a sandbox", () => {
  const f = fixture();
  try {
    for (const provider of Providers.list()) {
      f.player.open(movie, f.ui); f.player.selectSource(provider.key, true);
      const frame = f.player.session.frame;
      assert.equal(frame.allow, provider.permissions.join("; "));
      assert.equal(frame.allowFullscreen, true);
      assert.equal(frame.sandbox, undefined);
      assert.equal(new URL(frame.src).origin, provider.origin);
    }
  } finally { f.player.close(); }
});

class Element {
  constructor(tag, document) {
    this.tagName = tag; this.ownerDocument = document; this.children = []; this.handlers = new Map(); this.dataset = {};
    this.contentWindow = { messages: [], postMessage(data, origin) { this.messages.push({ data, origin }); } };
    const classes = new Set();
    this.classList = { toggle: (name, active) => active ? classes.add(name) : classes.delete(name), contains: (name) => classes.has(name) };
  }
  setAttribute(key, value) { this[key] = value; }
  removeAttribute(key) { delete this[key]; }
  replaceChildren(...children) { this.children.forEach((child) => { child.parentElement = null; }); this.children = children; children.forEach((child) => { child.parentElement = this; }); }
  contains(element) { for (let current = element; current; current = current.parentElement) if (current === this) return true; return false; }
  focus() { this.ownerDocument.activeElement = this; }
  addEventListener(type, handler) { if (!this.handlers.has(type)) this.handlers.set(type, new Set()); this.handlers.get(type).add(handler); }
  removeEventListener(type, handler) { this.handlers.get(type)?.delete(handler); }
  dispatch(type, payload) { for (const handler of [...(this.handlers.get(type) || [])]) handler(payload); }
  dispatchEvent(event) { this.dispatch(event.type, event); }
}
function fixture() {
  let now = 1000000, visible = true;
  const document = new Element("document", null);
  document.createElement = (tag) => new Element(tag, document);
  document.defaultView = { Event: class { constructor(type) { this.type = type; } } };
  const ui = Object.fromEntries(["host", "select", "status", "restart", "removeHistory"].map((key) => [key, document.createElement(key)]));
  const eventTarget = document.createElement("window");
  let id = 0;
  const callbacks = new Map();
  const timers = { setTimeout: (callback) => { callbacks.set(++id, callback); return id; }, clearTimeout: (i) => callbacks.delete(i) };
  const storage = memory();
  const viewing = new ViewingStore(storage, () => now);
  const player = new MoviePlayer({ providers: Providers, viewing, eventTarget, timers, now: () => now, isVisible: () => visible });
  const send = (data, override = {}) => eventTarget.dispatch("message", { origin: player.session.provider.origin,
    source: player.session.frame.contentWindow, data, ...override });
  return { player, viewing, ui, document, eventTarget, callbacks, send, storage,
    tick: (ms) => { now += ms; }, visible: (value) => { visible = value; } };
}

test("movie identity never interprets a curated integer as a TMDB ID", () => {
  assert.equal(Providers.reference({ id: 1, source: "curated" }).tmdbId, null);
  assert.equal(Providers.reference({ id: 1 }), null);
  assert.equal(Providers.reference({ id: 1, source: "tmdb" }), null);
  assert.equal(Providers.reference(movie).key, "tmdb:45745");
  assert.equal(Providers.reference({ id: 1, source: "curated", tmdb_id: 45745 }).tmdbId, 45745);
});

test("URL builders validate identity and resume times and keep fixed origins", () => {
  for (const provider of Providers.list()) {
    const url = new URL(provider.buildMovieUrl(45745, 123.9));
    assert.equal(url.origin, provider.origin);
    assert.equal([...url.searchParams.values()].includes("123"), true);
    for (const id of [0, -1, "45745", Infinity, 1.2]) assert.throws(() => provider.buildMovieUrl(id));
    for (const position of [-1, NaN, Infinity, "2", 90000]) assert.throws(() => provider.buildMovieUrl(45745, position));
  }
});

test("provider adapters ignore malformed, unrelated and wrong-movie events", () => {
  const cine = Providers.get("cinesrc"), link = Providers.all().find((p) => p.key === "vidlink");
  for (const data of [null, "message", [], { type: "something-else" }]) assert.equal(cine.parseMessage(data, 45745), null);
  assert.equal(cine.parseMessage({ type: "cinesrc:timeupdate", currentTime: NaN, duration: 10 }), null);
  assert.equal(cine.parseMessage({ type: "cinesrc:timeupdate", currentTime: 100, duration: 10 }), null);
  assert.deepEqual(cine.parseMessage({ type: "cinesrc:error", error: "untrusted text" }), { type: "error" });
  assert.equal(link.parseMessage({ type: "PLAYER_EVENT", data: { event: "play", mtmdbId: 2 } }, 45745), null);
  assert.equal(link.parseMessage({ type: "PLAYER_EVENT", data: { event: "play", mediaType: "tv" } }, 45745), null);
  assert.deepEqual(link.parseMessage({ type: "PLAYER_EVENT", data: { event: "timeupdate", mtmdbId: 45745,
    currentTime: 42, duration: 900 } }, 45745), { type: "progress", position: 42, duration: 900 });
});

test("errors, silent-player timeout and unrelated messages never switch sources", () => {
  const f = fixture(); f.player.open(movie, f.ui);
  const frame = f.player.session.frame;
  const timer = [...f.callbacks.values()][0]; timer();
  assert.match(f.ui.status.textContent, /Still loading/);
  assert.equal(f.player.session.frame, frame);
  f.send({ type: "cinesrc:play" }, { origin: "https://other.example" });
  assert.match(f.ui.status.textContent, /Still loading/);
  f.send({ type: "cinesrc:play" }, { source: {} });
  assert.match(f.ui.status.textContent, /Still loading/);
  f.send({ type: "cinesrc:error" });
  assert.match(f.ui.status.textContent, /Choose another source/);
  assert.equal(f.player.session.frame, frame);
  assert.equal(f.ui.select.value, "cinesrc");
  f.player.close();
});

test("manual switching replaces the single frame, transfers progress and rejects stale callbacks", () => {
  const f = fixture(); f.player.open(movie, f.ui);
  const oldFrame = f.player.session.frame, oldHandler = f.player.session.handler;
  f.send({ type: "cinesrc:timeupdate", currentTime: 123, duration: 900 });
  f.ui.select.value = "vidsrc"; f.ui.select.dispatch("change");
  assert.equal(f.ui.host.children.length, 1);
  assert.notEqual(f.player.session.frame, oldFrame);
  assert.equal(new URL(f.player.session.frame.src).searchParams.get("startAt"), "123");
  assert.equal(new URL(f.player.session.frame.src).searchParams.get("autoplay"), "1");
  assert.equal(f.viewing.preferredSource, "vidsrc");
  const status = f.ui.status.textContent;
  oldHandler({ origin: "https://cinesrc.st", source: oldFrame.contentWindow, data: { type: "cinesrc:error" } });
  assert.equal(f.ui.status.textContent, status);
  assert.equal(f.eventTarget.handlers.get("message").size, 1);
  f.player.close();
  assert.equal(f.ui.host.children.length, 0);
  assert.equal(f.eventTarget.handlers.get("message").size, 0);
  assert.equal(f.callbacks.size, 0);
  assert.equal(f.ui.select.handlers.get("change").size, 0);
});

test("closing then opening another movie isolates progress and callbacks", () => {
  const f = fixture(); f.player.open(movie, f.ui);
  f.send({ type: "cinesrc:timeupdate", currentTime: 100, duration: 900 });
  f.player.open({ ...movie, id: 2, tmdb_id: 2, title: "Other" }, f.ui);
  assert.equal(f.viewing.progress("tmdb:45745").position, 100);
  assert.equal(f.player.session.position, 0);
  f.player.close();
  assert.deepEqual(f.viewing.progress("tmdb:2"), {});
});

test("start over, resume, completion and removing history preserve independent watchlists", () => {
  const f = fixture(); f.viewing.toggle("tmdb:45745");
  f.viewing.saveProgress("tmdb:45745", 120, 900);
  f.player.open(movie, f.ui);
  assert.equal(f.player.session.position, 120);
  f.ui.restart.dispatch("click");
  assert.equal(f.player.session.position, 0);
  assert.equal(new URL(f.player.session.frame.src).searchParams.has("t"), false);
  f.send({ type: "cinesrc:timeupdate", currentTime: 30, duration: 900 });
  f.ui.removeHistory.dispatch("click");
  f.player.close();
  assert.deepEqual(f.viewing.progress("tmdb:45745"), {});
  assert.equal(f.viewing.has("tmdb:45745"), true);
  f.player.open(movie, f.ui, true);
  f.send({ type: "cinesrc:timeupdate", currentTime: 899, duration: 900 });
  f.send({ type: "cinesrc:ended" });
  f.player.close();
  f.player.open(movie, f.ui);
  assert.equal(f.player.session.position, 0);
  f.player.close();
});

test("viewing state survives refresh, validates stored data and fails gracefully without storage", () => {
  const storage = memory(); const first = new ViewingStore(storage, () => 10);
  first.toggle("tmdb:45745"); first.saveProgress("tmdb:45745", 60, 900); first.prefer("vidlink");
  const second = new ViewingStore(storage);
  assert.equal(second.has("tmdb:45745"), true);
  assert.equal(second.preferredSource, "vidlink");
  assert.deepEqual(second.continueKeys(), ["tmdb:45745"]);
  assert.equal(second.saveProgress("tmdb:45745", Infinity, 900), false);
  assert.equal(second.saveProgress("curated:1", 999, 1), false);
  second.clearHistory();
  assert.equal(second.has("tmdb:45745"), true);
  assert.deepEqual(second.continueKeys(), []);
  const denied = new ViewingStore({ getItem: () => { throw Error("denied"); }, setItem: () => { throw Error("denied"); } });
  assert.equal(denied.saveProgress("tmdb:45745", 60, 900), true);
  assert.equal(denied.progress("tmdb:45745").position, 60);
});

test("all three sources use standard unsandboxed frames and honor the saved selection", () => {
  assert.deepEqual(Providers.list().map((p) => p.key), ["cinesrc", "vidlink", "vidsrc"]);
  for (const source of Providers.list()) {
    const f = fixture(); f.viewing.prefer(source.key); f.player.open(movie, f.ui);
    assert.equal(f.ui.select.value, source.key);
    assert.equal(Object.hasOwn(f.player.session.frame, "sandbox"), false);
    // Source/origin validation remains active without iframe sandboxing.
    f.send({ type: "cinesrc:error" }, { origin: "https://other.example" });
    assert.doesNotMatch(f.ui.status.textContent, /could not play/);
    f.player.close();
  }
});

test("VidSrc validates movie identity and forwards its playing heartbeat as progress", () => {
  const f = fixture(); f.player.open(movie, f.ui);
  f.ui.select.value = "vidsrc"; f.ui.select.dispatch("change");
  const data = { type: "PLAYER_EVENT", data: { player_info: { tmdb: 45745, mediaType: "movie" },
    player_status: "playing", player_progress: 42, player_duration: 900 } };
  f.send(data);
  assert.equal(f.player.session.position, 42);
  assert.match(f.ui.status.textContent, /Playing with VidSrc/);
  f.send({ ...data, data: { ...data.data, player_info: { tmdb: 2, mediaType: "movie" }, player_progress: 100 } });
  assert.equal(f.player.session.position, 42);
  f.player.close();
});

test("manual changes and start over request autoplay while initial opening remains opt-in", () => {
  const f = fixture(); f.player.open(movie, f.ui);
  assert.equal(new URL(f.player.session.frame.src).searchParams.get("autoplay"), "false");
  f.send({ type: "cinesrc:timeupdate", currentTime: 60, duration: 900 });
  f.ui.select.value = "vidlink"; f.ui.select.dispatch("change");
  assert.equal(new URL(f.player.session.frame.src).searchParams.get("autoplay"), "true");
  assert.equal(new URL(f.player.session.frame.src).searchParams.get("startAt"), "60");
  f.ui.select.value = "cinesrc"; f.ui.select.dispatch("change");
  const frame = f.player.session.frame;
  assert.equal(new URL(frame.src).searchParams.get("autoplay"), "true");
  assert.equal(new URL(frame.src).searchParams.get("continueprompt"), "false");
  f.send({ type: "cinesrc:ready" });
  assert.deepEqual(frame.contentWindow.messages, [{ data: { type: "cinesrc:command", command: "play", args: [] }, origin: "https://cinesrc.st" }]);
  f.send({ type: "cinesrc:ready" });
  assert.equal(frame.contentWindow.messages.length, 1);
  f.ui.restart.dispatch("click");
  assert.equal(new URL(f.player.session.frame.src).searchParams.get("autoplay"), "true");
  assert.equal(new URL(f.player.session.frame.src).searchParams.has("t"), false);
  f.player.close();
});

function keyEvent(key) {
  return { key, prevented: false, stopped: false, preventDefault() { this.prevented = true; }, stopPropagation() { this.stopped = true; } };
}

test("custom source menu supports keyboard selection and does not reload the selected source", () => {
  const f = fixture(); f.player.open(movie, f.ui);
  const picker = new SourcePicker(f.document.createElement("div"), f.ui.select);
  const initial = f.player.session.frame;
  picker.button.dispatch("keydown", keyEvent("ArrowDown"));
  assert.equal(picker.button["aria-expanded"], "true");
  assert.equal(f.player.session.frame, initial);
  picker.button.dispatch("keydown", keyEvent("ArrowDown"));
  assert.equal(f.ui.select.value, "cinesrc");
  picker.button.dispatch("keydown", keyEvent("Enter"));
  assert.equal(f.ui.select.value, "vidlink");
  assert.equal(picker.value.textContent, "VidLink");
  assert.equal(picker.options[1]["aria-selected"], "true");
  assert.equal(picker.button["aria-expanded"], "false");
  assert.equal(new URL(f.player.session.frame.src).searchParams.get("autoplay"), "true");
  const selectedFrame = f.player.session.frame;
  picker.setOpen(true); picker.choose(1);
  assert.equal(f.player.session.frame, selectedFrame);
  picker.destroy(); f.player.close();
});

test("Escape closes only the source menu, outside clicks dismiss it and cleanup removes listeners", () => {
  const f = fixture(); f.player.open(movie, f.ui);
  const picker = new SourcePicker(f.document.createElement("div"), f.ui.select);
  picker.setOpen(true);
  const escape = keyEvent("Escape"); picker.button.dispatch("keydown", escape);
  assert.equal(escape.stopped, true);
  assert.equal(picker.open, false);
  assert.ok(f.player.session);
  picker.setOpen(true);
  f.document.dispatch("pointerdown", { target: f.document.createElement("div") });
  assert.equal(picker.open, false);
  picker.setOpen(true); picker.button.dispatch("keydown", keyEvent("End"));
  assert.equal(picker.active, 2);
  picker.button.dispatch("keydown", keyEvent("Home"));
  assert.equal(picker.active, 0);
  picker.button.dispatch("keydown", keyEvent("Tab"));
  assert.equal(picker.open, false);
  picker.destroy();
  assert.equal(f.document.handlers.get("pointerdown").size, 0);
  assert.equal(f.document.handlers.get("focusin").size, 0);
  f.player.close();
});

test("taste and mood survive a new browser session independently of viewing history", () => {
  const storage = memory();
  const first = new PreferenceStore(storage);
  assert.equal(first.save("tmdb", { liked: [10, 20], disliked: [30], mood: "cozy and heartwarming" }), true);
  const viewing = new ViewingStore(storage);
  viewing.toggle("tmdb:10"); viewing.saveProgress("tmdb:10", 60, 900); viewing.clearHistory();
  const restored = new PreferenceStore(storage).load("tmdb");
  assert.deepEqual(restored, { liked: [10, 20], disliked: [30], mood: "cozy and heartwarming" });
  assert.equal(new ViewingStore(storage).has("tmdb:10"), true);
  restored.liked.push(40);
  assert.deepEqual(first.load("tmdb").liked, [10, 20]);
});

test("legacy likes migrate once and clearing taste cannot resurrect the old profile", () => {
  const storage = memory(); storage.setItem("cinemagic:v1", JSON.stringify({ liked: [1, 2], disliked: [3] }));
  const upgraded = new PreferenceStore(storage);
  assert.deepEqual(upgraded.load("tmdb"), { liked: [1, 2], disliked: [3], mood: "" });
  assert.deepEqual(new PreferenceStore(storage).load("curated"), { liked: [], disliked: [], mood: "" });
  upgraded.save("tmdb", { liked: [], disliked: [], mood: "" });
  assert.deepEqual(new PreferenceStore(storage).load("tmdb"), { liked: [], disliked: [], mood: "" });
});

test("catalogue profiles stay separate across reloads", () => {
  const storage = memory(), prefs = new PreferenceStore(storage);
  prefs.save("tmdb", { liked: [1], disliked: [5], mood: "space" });
  prefs.save("curated", { liked: [5], disliked: [1], mood: "comedy" });
  const restored = new PreferenceStore(storage);
  assert.deepEqual(restored.load("tmdb"), { liked: [1], disliked: [5], mood: "space" });
  assert.deepEqual(restored.load("curated"), { liked: [5], disliked: [1], mood: "comedy" });
});

test("invalid preferences and denied storage do not crash or corrupt session taste", () => {
  const storage = memory(); storage.setItem("cinemagic:preferences:v2", "{bad JSON");
  const prefs = new PreferenceStore(storage);
  assert.deepEqual(prefs.load("tmdb"), { liked: [], disliked: [], mood: "" });
  prefs.save("tmdb", { liked: [1, 1, "2", -1, NaN], disliked: [1, 3], mood: "  scary  " });
  assert.deepEqual(new PreferenceStore(storage).load("tmdb"), { liked: [], disliked: [1, 3], mood: "scary" });
  const denied = new PreferenceStore({ getItem() { throw Error("denied"); }, setItem() { throw Error("denied"); } });
  assert.equal(denied.save("tmdb", { liked: [1], mood: "space" }), false);
  assert.deepEqual(denied.load("tmdb"), { liked: [1], disliked: [], mood: "space" });
});


function watch(f, seconds = 180, duration = 600) {
  f.send({ type: "cinesrc:play" });
  f.send({ type: "cinesrc:timeupdate", currentTime: 0, duration });
  for (let t = 5; t <= seconds; t += 5) {
    f.tick(5000);
    f.send({ type: "cinesrc:timeupdate", currentTime: t, duration });
  }
}

test("S5 measures unique watched intervals and migrates old resume positions without inferring taste", () => {
  const storage = memory();
  storage.setItem("cinemagic:viewing:v1", JSON.stringify({ version: 1, progress: {
    "tmdb:45745": { position: 599, duration: 600, updatedAt: 10, completed: true }
  }, watchlist: { "tmdb:45745": 10 }, preferredSource: "vidsrc" }));
  const migrated = new ViewingStore(storage);
  assert.equal(migrated.progress("tmdb:45745").position, 599);
  assert.equal(migrated.has("tmdb:45745"), true);
  assert.deepEqual(migrated.signals(), []);
  assert.equal(migrated.request().viewing, null);
  const f = fixture(); f.player.open(movie, f.ui); watch(f);
  assert.deepEqual(f.viewing.signals().map((s) => [s.watched_seconds, s.plays]), [[180, 1]]);
  f.viewing.setOptions({ use_viewing: true, recent_playback_only: true });
  f.player.close();
  const restored = new ViewingStore(f.storage);
  assert.equal(restored.state.version, 2);
  assert.equal(restored.signals()[0].watched_seconds, 180);
  assert.equal(restored.request().viewing.playback[0].provider, "cinesrc");
  assert.equal(restored.options().use_viewing, true);
  assert.equal(restored.options().recent_playback_only, true);
});

test("S5 play clicks, seeks, pauses, background gaps and ended events do not fabricate viewing", () => {
  const f = fixture(); f.player.open(movie, f.ui);
  f.send({ type: "cinesrc:play" });
  f.send({ type: "cinesrc:timeupdate", currentTime: 0, duration: 600 });
  f.tick(5000); f.send({ type: "cinesrc:timeupdate", currentTime: 580, duration: 600 });
  f.send({ type: "cinesrc:seeked" });
  f.tick(5000); f.send({ type: "cinesrc:timeupdate", currentTime: 585, duration: 600 });
  f.send({ type: "cinesrc:pause" });
  f.tick(5000); f.send({ type: "cinesrc:timeupdate", currentTime: 590, duration: 600 });
  f.send({ type: "cinesrc:play" }); f.visible(false);
  f.tick(5000); f.send({ type: "cinesrc:timeupdate", currentTime: 595, duration: 600 });
  f.visible(true); f.player.suspend();
  f.send({ type: "cinesrc:ended" });
  f.player.close();
  assert.deepEqual(f.viewing.signals(), []);
  assert.deepEqual(f.viewing.state.playback, {});
});

test("S5 rapid callbacks, silent gaps and cross-origin messages cannot credit watch duration", () => {
  const f = fixture(); f.player.open(movie, f.ui);
  f.send({ type: "cinesrc:play" });
  for (let t = 0; t <= 500; t += 5) f.send({ type: "cinesrc:timeupdate", currentTime: t, duration: 600 });
  f.tick(60000); f.send({ type: "cinesrc:timeupdate", currentTime: 560, duration: 600 });
  f.tick(5000); f.send({ type: "cinesrc:timeupdate", currentTime: 565, duration: 600 }, { origin: "https://other.example" });
  f.player.close();
  assert.deepEqual(f.viewing.signals(), []);
  assert.deepEqual(f.viewing.state.playback, {});
});

test("S5 replay strength counts substantial sessions and not repeated play events or source changes", () => {
  const f = fixture(); f.player.open(movie, f.ui); watch(f);
  watch(f); // same intervals and same player session
  assert.equal(f.viewing.signals()[0].watched_seconds, 180);
  assert.equal(f.viewing.signals()[0].plays, 1);
  f.ui.select.value = "vidsrc"; f.ui.select.dispatch("change");
  f.ui.select.value = "cinesrc"; f.ui.select.dispatch("change");
  watch(f);
  assert.equal(f.viewing.signals()[0].plays, 1);
  f.player.close(); f.player.open(movie, f.ui); watch(f);
  assert.equal(f.viewing.signals()[0].plays, 2);
  assert.equal(f.viewing.signals()[0].watched_seconds, 180);
  f.player.close();
});

test("S5 source errors invalidate playback evidence without becoming dislikes or erasing measured viewing", () => {
  const f = fixture(); f.player.open(movie, f.ui); watch(f);
  f.viewing.setOptions({ use_viewing: true, recent_playback_only: true });
  const before = f.viewing.signals()[0].watched_seconds;
  f.tick(1); f.send({ type: "cinesrc:error" });
  let evidence = f.viewing.request().viewing.playback[0];
  assert.ok(evidence.failed_at > evidence.verified_at);
  f.tick(5000); f.send({ type: "cinesrc:timeupdate", currentTime: 185, duration: 600 });
  assert.equal(f.viewing.signals()[0].watched_seconds, before);
  watch(f, 10);
  evidence = f.viewing.request().viewing.playback[0];
  assert.ok(evidence.verified_at > evidence.failed_at);
  assert.equal(f.viewing.has("tmdb:45745"), false);
  f.player.close();
});

test("S5 a playing heartbeat supports measured viewing without a separate play message", () => {
  const f = fixture(); f.player.open(movie, f.ui);
  f.ui.select.value = "vidsrc"; f.ui.select.dispatch("change");
  for (let t = 0; t <= 180; t += 5) {
    f.tick(5000);
    f.send({ type: "PLAYER_EVENT", data: { player_info: { tmdb: 45745, mediaType: "movie" },
      player_status: "playing", player_progress: t, player_duration: 600 } });
  }
  assert.equal(f.viewing.signals()[0].watched_seconds, 180);
  assert.ok(f.viewing.state.playback["tmdb:45745"].vidsrc.verified_at);
  f.player.close();
});

test("S5 clearing history during playback cannot resurrect signals, and preserves watchlist and explicit taste", () => {
  const f = fixture(); f.player.open(movie, f.ui); watch(f);
  const prefs = new PreferenceStore(f.storage);
  prefs.save("tmdb", { liked: [45745], disliked: [2], mood: "cozy" });
  f.viewing.toggle("tmdb:45745");
  f.player.forget(true);
  watch(f); f.player.close();
  const restored = new ViewingStore(f.storage);
  assert.deepEqual(restored.signals(), []);
  assert.deepEqual(restored.state.playback, {});
  assert.deepEqual(restored.progress("tmdb:45745"), {});
  assert.equal(restored.has("tmdb:45745"), true);
  assert.deepEqual(new PreferenceStore(f.storage).load("tmdb"), { liked: [45745], disliked: [2], mood: "cozy" });
});

test("S5 denied storage keeps measured evidence in session and does not send history while opted out", () => {
  const store = new ViewingStore({ getItem() { throw Error(); }, setItem() { throw Error(); } });
  store.recordInterval("tmdb:45745", 0, 180, 600, {});
  store.persist();
  assert.equal(store.signals()[0].watched_seconds, 180);
  assert.equal(store.request().viewing, null);
  store.setOptions({ use_viewing: true });
  assert.equal(store.request().viewing.signals.length, 1);
  assert.deepEqual(store.request().viewing.playback, []);
});


test("S5 starting over preserves measured history and allows a substantial replay", () => {
  const f = fixture(); f.player.open(movie, f.ui); watch(f); f.player.close();
  f.player.open(movie, f.ui, true);
  assert.equal(f.player.session.position, 0);
  assert.equal(f.viewing.signals()[0].plays, 1);
  watch(f);
  assert.equal(f.viewing.signals()[0].plays, 2);
  f.ui.restart.dispatch("click");
  assert.equal(f.viewing.signals()[0].plays, 2);
  watch(f);
  assert.equal(f.viewing.signals()[0].plays, 3);
  f.player.close();
});
