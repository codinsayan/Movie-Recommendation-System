# Architecture

## S6 release candidate and playback policy

FastAPI reports `0.4.0-rc.1`. `backend/release.py` reads the fixed `frontend/provider-registry.json` and the process environment `CINEMAGIC_PROVIDERS`. Unset enables all entries, an empty value disables all, and an ordered subset selects known adapters only. Unknown or duplicate entries fail startup; configuration cannot introduce arbitrary frame URLs. `frontend/providers.js` binds each registry entry to its event adapter, exposes only enabled choices and supplies iframe permissions to `player.js`.

`/playback-config.js` is registered before the static mount. It serves the synchronous, public-only policy before `providers.js` and `app.js`; `/api/playback` exposes the same configuration. The backend sends `frame-src` for self, YouTube privacy-enhanced trailers and enabled registry origins, plus `object-src 'none'` and `base-uri 'self'`. The bootstrap sets the equivalent CSP meta policy for static hosts. `export_static.py` generates a default static bootstrap alongside the model, preserving backend/static provider behavior without copying private metadata keys into assets. If the bootstrap fails to load, provider choices are empty and recommendations still run.

Configuration changes apply after process restart and browser reload (or static re-export). An enabled saved source wins over the configured default; a removed preference falls back at the next open, retaining progress. Existing failures/timeouts never change providers automatically. This is not a live configuration push to an active movie. Standard unsandboxed embeds remain the user's chosen compatibility behavior; message validation remains exact-origin, active-window and generation scoped.

S6 adds no user account, storage migration, metadata-cache schema change or global recommendation-matrix growth. Private TMDB settings stay in the backend; the SQLite cache is disposable and its writable path is configurable. `CINEMAGIC_RANKING=snapshot` retains the earlier ranking rollback. Branch/PR CI runs deterministic tests/export/syntax validation and produces a static artifact without deployment. [S6 acceptance](streaming/06-release.md) and [browser evidence](evaluation/s6/README.md) distinguish automated DOM contracts from pending actual media playback and human relevance acceptance. Render setup remains S7.

## S5 device-reported viewing evidence

`frontend/player.js` measures short visible playing intervals against an injected wall clock. The viewing store merges unique intervals, separates completion/resume position, and credits only substantial repeat sessions. Its internal schema migrates from version 1 to 2 without inferring preference from old resume data. The existing storage key stays stable. Opt-in controls and evidence remain browser-local; only enabled evidence is included in recommendation requests.

The version-1 request contract supplies bounded `signals` and provider-specific `playback` records, plus `use_viewing`, `recent_playback_only` and optional canonical `eligible_keys`. `backend/viewing.py` resolves only indexed identities, rejects invalid/duplicate evidence and evaluates seven-day playback freshness. This is client-reported evidence, not a server playback probe. FastAPI remains stateless.

The Python and JavaScript engines retain 90% of the explicit baseline and add at most 10% from qualified viewing when enabled. Dislikes override positive seeds. Candidate eligibility precedes normalization, top-pool selection and MMR. Responses add `watched_rows`; the UI retains explicit ?Because you loved? rows and shows the actual viewing contribution in explanations. Static exports include the same policy. Unknown remote films never expand matrices during a request.

The builder's explicit refresh budget is at most 500 requested IDs, with selected remote IDs optionally prioritized. The active snapshot remains 447 films. Larger models require sparse candidate retrieval and measured memory/latency/browser responsiveness before raising that cap. See [evaluation](EVALUATION.md) for benchmarks, provenance, limits and pending human/browser checks.

## S4 discovery alongside the recommendation snapshot

The model still owns a bounded catalogue. `backend/catalog.py` performs live TMDB title search and detail lookup separately; `frontend/catalogue.js` holds discovered metadata without adding it to the model's similarity matrices.

`/api/capabilities` advertises live search without exposing credentials. `/api/search` accepts a bounded title query, page 1–500 and metadata language. `/api/movies/{id}` uses canonical TMDB movie IDs and reports `in_model`. The pre-existing similar/recommend routes continue to use the active model catalogue.

Runtime metadata is cached in git-ignored SQLite storage with schema version 1, refresh timestamps and a 5,000-entry bound. Search TTL is one hour; detail TTL is one day. Existing stale entries can be used during timeouts, rate limits or upstream failures. Errors are sanitized rather than including authenticated request URLs.

The browser waits 300 ms after typing stops, aborts earlier title searches, rejects late responses by sequence, and merges paginated results by TMDB ID. While the query is nonempty, search shows a dedicated responsive landscape grid in place of the billboard, moods, onboarding and recommendation rows. Cards use backdrops with poster/gradient fallbacks and retain movie details, taste actions and playback via the shared tile interaction. Clear, Escape and home navigation restore ordinary browsing without changing taste. Static search shows all local matches; live search retains explicit pagination, metadata language and retry states. Opening remote details uses a modal generation guard, so an older request cannot replace a newer movie or player. Selected metadata is saved in browser storage for remote Watchlist/Continue Watching cards after reload.

Discovery metadata includes original title/language and, for full details, alternative titles. Metadata language does not select playback audio. TMDB documents [title search](https://developer.themoviedb.org/reference/search-movie) and [movie details](https://developer.themoviedb.org/reference/movie-details).

Remote titles have no fabricated personalized score before they are indexed. S5A resolves their explicit likes/dislikes into the fitted content space; unknown IDs without usable features stay pending/unavailable. Direct similar-title requests use the existing indexed model or, for external TMDB IDs, resolved English features to find content-based snapshot neighbours. Resolved external likes also receive Because you loved rows from that snapshot. Static/curated builds retain snapshot/saved-title search and do not route new discovery endpoints through the static engine.

## S5A external explicit preferences

`backend/features.py` supplies the shared genre, keyword/person slug and document normalization used by the fitted snapshot and resolved metadata. Existing snapshot feature documents remain unchanged. The feature version hashes the normalization schema, English feature language, fitted vocabulary/IDF and snapshot documents. Bump `FEATURE_SCHEMA` when encoding/normalization changes; cached vectors must not cross feature spaces. The exported contract also supplies the explicit dislike penalty. `/api/meta` and `/api/capabilities` expose the version and vocabulary size, never credentials.

`GET /api/preferences/tmdb/{id}` accepts a validated external movie ID. It retrieves complete English metadata through `Catalog`, uses its one-day detail TTL/stale recovery, and transforms with the existing vectorizer. Zero-vocabulary movies are unavailable rather than assigned invented similarity. A lock serializes upstream preference hydration; a 512-record LRU reuses encoded features by ID, encoder version and metadata update time. No request fits the model, appends movies or grows similarity matrices.

`frontend/preference-resolver.js` hydrates at most two explicit choices at a time, with cancellation-aware 30-second fetch limits and retry states. `cinemagic:preferences:v2` remains authoritative for IDs; `cinemagic:preference-features:v1` stores derived metadata/vectors separately. Local feature freshness is one day; stale compatible features can still contribute while refresh fails. The persistent derived cache holds at most 200 records and 2 MiB of estimated UTF-16 storage, prioritizes active records and shrinks further on quota failures. Other active features stay usable in the session and rehydrate after reload; inactive session records are evicted beyond 20,000 records; failed/quota-limited persistence never deletes explicit choices. Existing per-side 10,000-choice storage limits are enforced visibly for new clicks and bounded by the API.

The version-1 `external_preferences` recommendation contract contains a signed sparse aggregate, positive/negative resolved counts, supported genre/tag weights and up to two recent positive explanation seeds. Request feature work is bounded by the fitted vocabulary plus these seeds, rather than transmitting every external feature record. It is device-reported preference evidence. The API validates dimensions, finite values, duplicates, versions, counts and active seed identities. Removed or reversed choices are omitted/reweighted when constructing the current aggregate; late metadata cannot reinstate an obsolete choice.

The existing engine adds the aggregate to its positive/negative profile. External metadata supplies content evidence; collaborative weight is available only from indexed explicit choices and is normalized accordingly. Unavailable components are marked in explanations. Resolved external genres/tags contribute to Taste DNA; weak S5 viewing still contributes at most 10%. External Because you loved rows use measured content overlap with snapshot candidates and exclude explicit choices independently of Top Picks mood/playback eligibility. The existing similar-title route now resolves external IDs using the same bounded feature service; static mode uses compatible cached vectors or complete English metadata. New recommendation candidates remain out of scope.

The exported model includes the feature contract through `meta`. The browser engine normalizes/encodes compatible complete English metadata and matches Python scoring; cached compatible vectors also work offline. Fresh or incompatible metadata stays pending in static mode. Startup awaits feature-contract configuration before the first recommendation request, with a five-second metadata deadline and a recoverable pending fallback. S5C will optimize catalogue/profile scaling further; this milestone retains the 447-film candidate pool and global snapshot matrices.

## S5B-S5D dynamic candidates and bounded ranking

With a configured backend, `/api/recommend` with `discover: true` runs a versioned pipeline (`rank-v2`):

1. **Retrieval** (`backend/discovery.py`): related titles of up to 4 seed likes, acclaimed films in the top taste genres, recent releases, and starter pools for cold-start or dislike-only profiles. At most 300 candidates and 4 concurrent upstream calls; detail enrichment runs in the background.
2. **Encoding** (`backend/ranking.py` `FeatureStore`): sparse TF-IDF rows in the fitted vocabulary, cached by canonical ID, language and `feature_version`.
3. **Profile and scoring** (`Recommender.recommend(extra=...)`): the snapshot plus candidates are scored with content, TMDB related-title evidence and quality. Discovered films are calibrated against the pool they were found in (`DISCOVERY_POLICY`, S5D).
4. **Reranking:** MMR over the top `min(3k, 300)` eligible rows only.

The snapshot model never grows. `CINEMAGIC_RANKING=snapshot` rolls back to snapshot-only ranking. The static build never discovers. Evidence: [S5B](streaming/05b-dynamic-discovery.md), [S5C](streaming/05c-scalable-ranking.md), [S5D](streaming/05d-dynamic-evaluation.md).

## Overview

```
┌──────────────────────────── Browser ────────────────────────────┐
│  index.html + styles.css + app.js   (no framework, no build)    │
│                                                                 │
│  state: liked ♥, disliked ✕, mood  ──►  localStorage            │
│        │                                                        │
│        │ POST /api/recommend   (debounced 140 ms, latest wins)  │
└────────┼────────────────────────────────────────────────────────┘
         ▼
┌──────────────────────────── FastAPI (backend/app.py) ───────────┐
│  /api/recommend  /api/movies  /api/movies/{id}/similar  /api/meta│
│  StaticFiles("/") ── serves the frontend from the same origin   │
└────────┼────────────────────────────────────────────────────────┘
         ▼
┌──────────────────── Recommender (backend/recommender.py) ───────┐
│  built once at start-up, then pure in-memory numpy:              │
│   • TF-IDF matrix X           (movies × terms)                  │
│   • content_sim = X·Xᵀ        (movies × movies)                 │
│   • collab_sim (adj. cosine)  (movies × movies)                 │
│   • quality prior             (movies)                          │
│  recommend() = blend → filter → MMR re-rank → explain           │
└─────────────────────────────────────────────────────────────────┘
```

### Static mode (GitHub Pages)

```
CI: pytest ─► export_static.py ─► frontend/data/model.json ─► Pages artifact
Browser: app.js ─► api(path) ─► engine.js (same /api/* routes, no server)
```

`api()` sends requests to `CinemagicEngine.handle()` when the page is served from `*.github.io` or when the FastAPI server is unreachable. The engine works on the *exported* matrices instead of re-training, so the browser does only the per-request maths. Results are identical to Python (enforced by `tests/test_static_engine.py`).

## Design decisions

| Decision | Why |
|---|---|
| **Single origin**: FastAPI serves both API and static frontend | One command to run, no CORS, easy to demo on any laptop. |
| **Vanilla JS, no build step** | Zero tooling to install; the code is readable in a viva. |
| **Fixed snapshot matrices, bounded sparse dynamic ranking** | Startup builds the fixed 60/447-film snapshot; discovered titles use sparse rows and bounded MMR without growing a global matrix. |
| **Stateless API** | The client sends its full taste (liked/disliked/mood) every call. No sessions or DB needed, and it's trivially testable. |
| **Client-side persistence** in `localStorage` | Taste survives a refresh without user accounts. |
| **Debounce + sequence number** on the client | Rapid taps send few requests, and a slow older response can never overwrite a newer one. |
| **View Transitions API** for re-ranking | Cards morph to their new positions instead of flashing, which is the "magic" feeling. Falls back gracefully where unsupported. |

## Request flow: tapping ♥

1. `setTaste()` updates the in-memory sets, saves to `localStorage`, updates pressed states in place, and fires a particle burst.
2. `refresh()` debounces, then in parallel calls `POST /api/recommend` with `k=100` (scores the whole catalogue) and `GET /similar` for your two most recent loves.
3. The server returns `{mode, items, taste}`; each item carries `match`, `reason`, `because`, `shared`, `breakdown`.
4. `renderRows()` rebuilds the rows. It keeps each row's horizontal scroll position, animates only rows that are new, and marks new top picks with "NEW PICK".
5. The billboard switches to the new top 5 (if they changed), the My Taste drawer and avatar ring update, and a toast reports how many picks are new.

## UI layout

```
nav (logo · links · search · 🔮 · 🧬 avatar)
billboard (top 5 picks, rotates every 8 s)
mood chips · onboarding banner (until 3 loves)
rows: [Search results] · Top Picks · My List · Because you loved X/Y · Top 10 · genre rows (taste-ordered)
overlays: hover preview · My Taste drawer · detail modal · toasts
```

## Frontend modules (inside `app.js`)

| Area | Functions |
|---|---|
| Persistence | `load`, `save` |
| API | `api` |
| Rows | `buildRows`, `renderRows`, `rowHTML`, `tileHTML`, `top10TileHTML` |
| Billboard | `setBillboardItems`, `showBillboard` |
| Hover preview | `bindPreview`, `showPreview`, `hidePreview` |
| Drawer | `renderDrawer`, `toggleDrawer` |
| Interactions | `setTaste`, `syncStates`, `conjure`, `bindSearch`, `burst`, `toast` |
| Modal | `openMovie`, `openHow`, `openModal`, `closeModal` |

## Posters

`scripts/fetch_posters.py` finds each film's Wikipedia page through the REST summary endpoint, trying `Title (Year film)`, then `Title (film)`, then `Title`, plus manual overrides. It downloads the lead image into `frontend/posters/<id>.jpg` and writes the path into `movies.json`. Posters are served as static files, so the app needs no network at runtime. If an image fails to load, a global `error` listener swaps in a gradient + emoji poster generated from the movie's `palette`.
