# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Status as of 2026-10-20

This section records the implemented streaming work on `feature/streaming-platform` through `2d590cd`. These changes have not been assigned a new release version or deployed to Render. The versioned entries below retain the earlier Iterations 1-3 and static-hosting release history.

| Iteration | Implementation and validation status |
|---|---|
| Iteration 1 / v0.1.0 | Original hybrid recommender, API, curated dataset and first UI implemented |
| Iteration 2 / v0.2.0 | Poster cache and Netflix-style redesign implemented |
| v0.2.1 | Browser engine, Python/JavaScript parity and GitHub Pages workflow implemented |
| Iteration 3 / v0.3.0 | TMDB snapshot, graph recommendations, quality prior, trailers and visual polish implemented |
| S1 | Source adapters and canonical identities implemented; detailed provider playback proof remains incomplete |
| S2 | Movie player, manual source switching, custom selector and autoplay requests implemented; broader live playback acceptance remains incomplete |
| S3 | Device-local viewing state, independent Watchlist and persistent taste implemented; detailed live resume acceptance remains incomplete |
| S4 | Live search, remote details, metadata caching and landscape search gallery implemented |
| S5 | Opt-in measured-viewing recommendations and recent-playback filtering implemented; proxy evaluation and parity passed; broader relevance review remains open |
| S5A | External explicit preferences, related snapshot movies and refresh/filter fixes implemented; focused desktop/mobile Chrome checks passed |
| S5B | Dynamic candidate retrieval beyond the snapshot implemented; deterministic and live API checks passed; browser review pending |
| S5C-S5D, S6, S7 | Planning documents added; these phases have not been implemented |

The active recommendation candidates remain the **447-film TMDB snapshot**, with the separate **60-film curated dataset** retained. Search can discover other movies, and S5A can use their resolved explicit preferences, without automatically adding them to the recommendation candidate pool.

### S1 - Source adapters and movie identity (2026-10-20)

Implementation commit: `59853c9`. Phase: [source foundation](docs/streaming/01-source-foundation.md).

- Added `frontend/providers.js` with CineSrc, VidLink and VidSrc .sh adapters, labels, enabled flags, fixed embed origins, documentation references and provider capabilities.
- Added validated movie URL construction using explicit TMDB IDs, supported resume parameters and provider-specific player options.
- Added provider-message parsing and normalized playback events where supported; malformed payloads and unsupported events are ignored.
- Added canonical references containing catalogue origin, internal ID and explicit TMDB mapping. Curated IDs cannot be mistaken for unrelated TMDB IDs.
- Included dataset origin and explicit TMDB identities in loaded movies, catalogue-builder output, API responses and browser-model exports.
- Added offline identity, URL-builder and message-fixture checks. Missing mappings produce an unavailable state rather than a fabricated movie URL.

### S2 - Player, source selection and compatibility (2026-10-20)

Implementation commit: `a813113`; application integration shipped in `658ad76`. Phase: [player and manual switching](docs/streaming/02-player-and-manual-switching.md).

- Added `frontend/player.js` and the responsive movie-player overlay with title, source selector, status/recovery text, close control and player host.
- Added Watch movie actions to mapped movie details, previews and billboard flows while retaining separate trailer actions and recommendation explanations.
- Selected CineSrc as the default, with VidLink and VidSrc available as manually chosen alternatives; an enabled saved preference can be used when opening a player.
- Kept one active movie iframe. Manual changes save progress, dispose the previous frame/listeners and create the selected source; closing or opening another film invalidates stale callbacks.
- Validated player-message origin, active iframe window, payload/movie identity and session generation before accepting provider events.
- Kept the source selector outside the embed and usable when telemetry is missing. Errors and silent-player timeouts show recovery text and never switch providers automatically.
- Added `frontend/source-picker.js`: a dark menu with a red selected state, shared SVG icons, highlighted options, ARIA selection/expanded state, keyboard navigation, Enter/Space selection, Home/End, Escape, Tab and outside-click dismissal.
- Selecting the already active source closes the menu without reloading the player; destroying the menu removes its listeners.
- Added autoplay requests when manually changing sources or choosing Start over, preserving the saved position where supported. Initial player opening remains opt-in; CineSrc also receives its play command after ready when autoplay was requested.
- Changed movie embeds to standard cross-origin iframes without `sandbox` after the user reported VidLink/VidSrc sandbox errors and explicitly requested that compatibility change. Origin/window validation remains active; all three adapters are enabled.
- Added focus restoration, billboard suspension during overlays, disposal and separate movie/trailer handling.
- User feedback confirms the sources play after sandbox removal. This does not complete the per-film/provider/device matrix, autoplay-on-switch or live resume checks in [playback validation](docs/streaming/PLAYBACK_VALIDATION.md).

### S3 - Device-local viewing state and taste persistence (2026-10-20)

Implementation commit: `658ad76`. Phase: [progress and watchlist](docs/streaming/03-progress-and-watchlist.md).

- Added `frontend/viewing.js` with versioned browser storage for preferred source, canonical movie keys, progress position, duration, update time and completion state.
- Saved validated progress periodically, on pause and before player disposal; saved again on page-hide/visibility changes. Invalid/non-finite times and implausible durations are rejected.
- Transferred a valid position into a newly selected provider's supported resume URL. Exact continuity across providers or film editions is not claimed.
- Added Resume/Start over behavior, Continue Watching, removal of individual history and a separate Watchlist action/row.
- Kept Watchlist, love-based My List, explicit dislikes, mood and viewing history independent. Saving to Watchlist does not like a movie; clearing history does not reset taste or Watchlist.
- Added `frontend/preferences.js` and `cinemagic:preferences:v2`: likes, dislikes and mood persist without login and restore before recommendations. Migrated legacy `cinemagic:v1` likes once.
- Kept TMDB and curated taste profiles separate, preventing numeric-ID collisions. Preferences are local to the browser profile and site origin; accounts and cross-device synchronization were not added.
- Added validation and graceful handling for corrupt/denied storage. Taste write failures show a session-only warning; reset cannot re-import cleared legacy likes.
- Added player/preferences integration tests covering switching, stale events, history separation, local restoration, migration and denied storage.

### S4 - Live discovery and metadata cache (2026-10-20)

Implementation commit: `3bb0863`. Phase: [search and catalogue](docs/streaming/04-search-and-catalogue.md).

- Added `backend/catalog.py` and private TMDB-backed discovery beside the bounded recommender, keeping credentials on the server.
- Added `/api/capabilities`, validated `/api/search?q=...&page=...&language=...` and `/api/movies/{id}?language=...` routes before the static mount.
- Added title-query validation, canonical-ID validation, pagination through pages 1-500, metadata-language selection and explicit `in_model` membership.
- Preserved original title/language, alternative titles, genres, keywords, overview, artwork, runtime, cast, director and trailer metadata where available. Metadata language does not select playback audio.
- Added a versioned SQLite metadata cache capped at 5,000 entries: search TTL one hour, detail TTL one day, language-specific keys, refresh timestamps and stale fallback.
- Added bounded upstream timeouts and sanitized authentication, rate-limit, not-found and malformed-response handling. Credentials are not returned in public capabilities or errors.
- Added `frontend/catalogue.js` for remote records, pagination, deduplication, remembered metadata and capability detection. Search summaries do not overwrite fuller compatible details.
- Added a 300 ms typing debounce, cancellation of earlier searches, sequence-based rejection of late responses, loading/empty/error states, Retry search and Load more.
- Supported remote details, playback, taste controls, Watchlist and restored saved-title metadata without appending discovered movies to model matrices.
- Kept static/curated search scoped to snapshot and saved metadata rather than pretending a browser-only deployment can privately call TMDB.
- Initially showed unindexed similar-title lookup as unavailable; S5A later adds content-based snapshot neighbours without creating a new candidate catalogue.
- Recorded initial validation: 50 pytest tests passed; Batman pages 1/2 returned 20 results each; Sintel (`tmdb:45745`) details loaded in English/Hindi outside the model; page 501 returned HTTP 422. The model stayed at 447 films.

### S4 follow-up - Landscape search gallery (2026-10-20)

Commit: `add890c`.

- Replaced the search carousel among home recommendations with a dedicated results view. A nonempty query hides the billboard, moods, onboarding and ordinary rows.
- Added landscape artwork using backdrops where available, poster/gradient fallbacks, visible titles/years and the existing movie/taste interactions.
- Added a responsive grid with six columns on wide desktop layouts and two on phones, retaining the app's dark/red visual design.
- Added a clear-search button, search/result association, focus styling and narrow-screen search positioning. Clear, Escape and navigation restore home browsing without resetting taste.
- Kept automatic 300 ms fetching, metadata-language selection, pagination, retry and Enter-to-search-by-mood. Composition input waits for the completed text.
- Removed the previous 30-title cap from static search results; all matching local titles can appear. Live results remain paginated.
- Made row-scroll restoration tolerate a search grid without a horizontal scroller; entering search resets page scroll once rather than on every keystroke.
- Added five interaction cases for automatic fetching, clear/stale-response behavior, pagination failures, static matching/escaping and composition/Escape.
- Recorded 99 passing pytest tests and updated HTTP-served assets. A live `spider` query returned 20 movies, 17 with backdrops. Later S5A browser checks exercised the gallery when opening Sintel.

### S5 - Opt-in viewing-aware recommendations (2026-10-20)

Implementation commit: `36da399`. Phase: [viewing-aware recommendations](docs/streaming/05-recommendations.md). Results: [evaluation](docs/EVALUATION.md), [raw report](docs/evaluation/s5-results.json) and [informal review](docs/evaluation/s5-human-review.json).

- Added a version-1 viewing request contract with measured signals, provider playback evidence, opt-in flags and optional canonical eligibility keys; Python/browser validation bounds payloads and numeric values.
- Measured short forward-playing intervals against wall time in a visible tab; merged overlaps and broke continuity on seeks, pause/background gaps, source changes, errors and implausible progress.
- Required both 120 measured seconds and 30% unique coverage before a movie contributes a viewing signal. Substantial repeat sessions raise strength from 0.15 to 0.20 to 0.25; repeated Play events alone do not count.
- Kept resume/completion separate from measured coverage. Old resume positions, scrubbing to the end, iframe loads, play clicks and source errors do not manufacture watched time or dislikes.
- Added Use viewing history as an opt-in experiment. Qualified viewing contributes at most 10%; the explicit baseline retains 90%, and explicit dislikes override conflicting positives.
- Added Because you watched rows, a viewing score component and corresponding explanations while keeping Taste DNA/confidence based on explicit taste.
- Added Top picks: played recently on this device. Qualification requires ten measured playing seconds within seven days, with provider-specific error invalidation; expired, future or absent playback evidence does not qualify.
- Applied recommendation eligibility before normalization, top-pool truncation, MMR and top-k. Search, Watchlist and general catalogue browsing remain available when strict picks are empty.
- Migrated viewing storage from schema 1 to 2 without inferring evidence from old progress. Clearing history during active playback cannot resurrect forgotten evidence and preserves likes, mood and Watchlist.
- Retained stateless API requests and device-local options/evidence; viewing history is included only for enabled options. Unknown unindexed viewed titles stay history-only.
- Kept Python and JavaScript scoring, explanations, signals and rows in parity on both curated and TMDB catalogues.
- Added an explicit snapshot-refresh budget of at most 500 requested IDs with optional prioritized TMDB IDs. No dataset enlargement or snapshot rebuild was performed.
- Added reproducible proxy evaluation with fixed profiles/seed, provenance hashes, popularity/explicit/viewing comparisons, HR@10, NDCG@10, coverage/diversity and runtime/model-size measurements.
- Recorded unchanged HR@10 and small NDCG differences on synthetic/overlapping evaluation data; these do not establish real-user quality gains. Recorded one broadly positive user review and the reported Tenet discrepancy. The feature remains opt-in pending broader review.
- Recorded 98 passing pytest tests, including 26 JavaScript playback/preferences cases and seven catalogue cases, plus live local API and static-export checks. The active model remained 447 films.

### S5 follow-up - Empty-filter banner recovery (2026-10-20)

Commit: `11fb898`.

- Fixed a blank front banner when recent-playback filtering has no eligible picks.
- Retained the strict Top Picks empty state while requesting broader banner suggestions with only the recent-playback constraint removed; mood, explicit taste and the viewing-history preference remain.
- Labelled broader suggestions More to discover, without presenting them as recently verified playback.
- Added Show all picks recovery, which turns off only the recent-playback filter.
- Cleared stale banner movies, backgrounds, poster, dots and rotation timers when neither strict nor broader picks exist; added recovery actions.
- Rejected late broader responses after filter changes and kept fallback failures usable.
- Added seven regression cases using real app closures and the exported static engine; recorded a passing 98-test suite at that checkpoint.

### S5B - Dynamic recommendation candidates (2026-10-20)

Branch: `feature/streaming-platform`. Phase: [dynamic discovery](docs/streaming/05b-dynamic-discovery.md).

- Added `backend/discovery.py`: bounded retrieval of candidates beyond the 447-film snapshot from TMDB related titles of up to 4 seed likes (most recent plus spread across history), acclaimed films in the top 2 taste genres, new releases from the last 120 days, and popular/top-rated starter pools for cold-start and dislike-only profiles.
- Added cached `Catalog.related()`, `Catalog.discover()` (allow-listed parameters only) and `Catalog.cached_movie()`; TTLs are 24 h related, 6 h discover, 3 h new releases. They reuse the existing timeout, rate-limit, sanitized-error and stale-cache behaviour.
- Budgets: 300-candidate pool, 4 concurrent upstream requests process-wide, 12 background detail lookups per request. Detail enrichment never blocks a response; candidates are labelled `full` or `summary` metadata.
- `Recommender.recommend(extra=...)` ranks discovered films alongside the snapshot: fitted TF-IDF content (no refit, no matrix growth), TMDB related-title evidence as the collaborative signal (`RELATED_LINK = 0.3`, calibrated to a direct snapshot-graph link), and quality on the snapshot's scale. MMR and explanations cover the union; the snapshot-only path is unchanged.
- Exact liked/disliked IDs are excluded across every source; dislikes stay a similarity penalty, not a genre ban.
- `POST /api/recommend` accepts `discover: true` and returns a `discovery` report (status ok/partial/unavailable, sources, pool, enrichment, upstream calls, cache hits, stale). `/api/capabilities` reports `dynamic_discovery`. Upstream failures never fail the request.
- Frontend: requests discovery only from a configured backend; registers discovered films so details, likes/dislikes (S5A), Watchlist and playback work; aborts superseded refreshes; shows a **Discovered** badge, an honest Top Picks status line and retrieval sources in the "why" panel. Static mode is unchanged.
- Tests: 12 deterministic mock-TMDB tests in `tests/test_discovery.py` (**123 passed** in total). JS harnesses provide `AbortController` like browsers.
- Live check: for Inception + Interstellar + The Dark Knight, 5 of the top 12 picks came from outside the snapshot (e.g. Batman (1989), Primer, The Electric State). Latency: 1.9 s cold, 0.4-1.1 s warm.

### S5A - External likes/dislikes and feature resolution (2026-10-20)

Implementation commit: `cadd680`. Phase and evidence: [dynamic preferences](docs/streaming/05a-dynamic-preferences.md).

- Added `backend/features.py`, `backend/preferences.py` and `frontend/preference-resolver.js` for resolved preferences on movies outside the snapshot.
- Saved the explicit choice immediately, then retrieved complete English feature metadata through the validated private `/api/preferences/tmdb/{id}` endpoint. Display metadata language remains independent.
- Shared genre normalization, keyword/person slugs and weighted document construction between snapshot and external features; retained byte-equivalent feature documents for the existing datasets.
- Created feature-version identifiers from the schema/language, fitted vocabulary/IDF and snapshot documents; exposed compatible metadata through API capabilities/meta and browser exports.
- Transformed metadata with the existing fitted TF-IDF vocabulary, without fitting again, adding movie IDs or expanding similarity matrices. Unseen terms are ignored; zero-usable-feature movies are unavailable rather than assigned fictional similarity.
- Added a version-1 `external_preferences` contract: signed sparse aggregate, resolved positive/negative counts, supported genre/tag weights and up to two positive explanation seeds.
- Validated versions, finite values, dimensions, duplicate indices/terms, counts and active seed identities. Removed/reversed preferences cannot be reintroduced by late metadata.
- Added resolved external likes/dislikes to positive/negative content profiles, Taste DNA, confidence and Because you loved rows. Unresolved choices are counted separately rather than represented as already applied.
- Normalized available scoring weights; external metadata supplies content evidence rather than invented collaborative ratings. Marked unavailable score components and retained S5's 10% viewing cap.
- Made dislikes win conflicting imported preferences. Kept exact exclusions and a softer similarity penalty rather than a genre-wide ban.
- Added Applied, Pending, Unavailable and stale-feature states, per-title feedback, Retry metadata, missing-title placeholders and honest storage/version error messages.
- Hydrated at most two choices concurrently in the client with 30-second fetch limits; serialized server hydration and reused a 512-record feature LRU plus the existing metadata cache.
- Stored derived features separately in `cinemagic:preference-features:v1`. Capped the persistent feature cache at 200 records and 2 MiB of estimated UTF-16 storage, shrinking further on quota failures; active uncached features remain usable in session and rehydrate after reload.
- Preserved preference IDs when feature storage fails or entries are evicted; retained a bounded inactive session cache. Made the existing 10,000-per-side preference limit visible for new choices and bounded API lists accordingly.
- Added compatible offline/static reuse of cached vectors or complete cached English metadata; fresh/incompatible titles remain pending when private backend lookup is unavailable.
- Added negative-only, missing-vocabulary/keywords, unavailable metadata, storage denial, cache eviction, retry, version mismatch, stale response and Python/browser transform/ranking checks.
- Recorded 109 passing pytest tests at the feature checkpoint, ten resolver lifecycle cases, static export and live Sintel resolution: 24 nonzero English features, no model growth and changed personalized picks. Client-store reconstruction checks passed; later user feedback exposed the full-app issues fixed below.

### S5A follow-up - Restore personalized picks and related movies (2026-10-20)

Commit: `2d590cd`.

- Investigated user feedback that Sintel remained Applied after refresh while recommendations appeared to revert and similar films were missing. The explicit like was saved; full-app startup and shelf filtering were incomplete.
- Configured/restored cached external features before the first recommendation request after reload, removing the initial unpersonalized request. Added a five-second metadata deadline, usable pending fallback and contract-configuration retry.
- Kept external Because you loved shelves independent of Top Picks mood/playback eligibility, matching indexed shelves; explicit liked/disliked candidates remain excluded. A viewing-based Odyssey shelf does not replace or relabel the Sintel shelf.
- Extended `/api/movies/{id}/similar` to resolve external TMDB titles through the bounded feature service and return content-based snapshot neighbours, with validated IDs and `k` from 1 to 30.
- Added matching Python/browser external-similarity methods and enabled More Like This in external movie details. Static mode uses compatible cached vectors or complete English metadata; empty/unavailable outcomes stay explicit.
- Kept movie/overlay generation checks so late similar-title responses cannot replace a newer dialog; filtered explicit dislikes from displayed related cards.
- Added two real app-bootstrap regression cases: delayed feature configuration across two boots and metadata-timeout recovery. Expanded API/parity coverage for direct external similarity and filtered explicit shelves.
- Recorded **111 passing pytest tests** and a successful static export. These are the latest application regression results, not a new run for this documentation update.
- Verified full page loads/reloads in an isolated headless Chrome profile: first request included Sintel's external profile, the same personalized picks survived refresh, and its explicit related shelf remained visible with synthetic The Odyssey history and both viewing switches.
- Verified nine related cards in Sintel's details and visually inspected desktop 1440 x 1000 and mobile 390 x 844 screenshots. The test profile contained synthetic data; user browser storage was not read or changed. Temporary browser artifacts were removed afterward.
- Left broader human relevance, locale/device and live third-party player acceptance visible; these focused checks do not complete every release/deployment requirement.

### Research, documentation and plans added (2026-10-20)

Documentation commits: `f032f77`, `bae6b09`, `2fdaadc`.

- Added the [provider research directory](docs/STREAMING_PROVIDERS.md), [streaming feasibility notes](docs/STREAMING_FEASIBILITY.md), phased implementation roadmap and playback evidence/checklist.
- Recorded the user's final preference for **manual** source switching, replacing the earlier automatic-failover proposal. The larger provider list is research/backlog; only the three selected adapters are integrated.
- Added S6 release-readiness planning for provider configuration, operational checks, actual browser/playback evidence, regressions and rollback. S6 implementation remains pending.
- Added S7 Render deployment planning for one FastAPI Web Service serving frontend/API/model, private credentials, build/start/health settings, disposable cache behavior, hosted acceptance and rollback. No Render service has been created or deployed.
- Inserted S5A-S5D before S6/S7 while preserving those labels. S5A is now implemented; S5B dynamic candidates, S5C scalable ranking and S5D acceptance remain planned.
- Kept semantic embeddings as an optional measured follow-on, rather than an implemented model or a deployment prerequisite.
- Updated README, architecture, evaluation notes, iteration status, source evidence and changelog alongside completed work. Kept the older Iterations 4-6 plans separate; partial overlapping features do not mark those iterations complete.
- Consolidated this changelog against the existing Git history and phase records, retaining prior release entries, separating planning from implementation, and recording the latest validation limits.

### Implementation commit index

All entries below existed before this changelog consolidation. Commits from 2026-10-20 are unreleased streaming-branch work; the earlier versioned history follows this index.

| Date | Commit | Change |
|---|---|---|
| 2026-10-20 | `2d590cd` | S5A refresh ordering, filtered shelves and external related-film fix |
| 2026-10-20 | `cadd680` | S5A resolved external preferences |
| 2026-10-20 | `add890c` | Automatic-search landscape gallery |
| 2026-10-20 | `2fdaadc` | S5A-S5D upgrade planning before S6/S7 |
| 2026-10-20 | `bae6b09` | S7 Render deployment plan |
| 2026-10-20 | `11fb898` | Empty recent-playback banner recovery |
| 2026-10-20 | `36da399` | S5 opt-in viewing-aware ranking |
| 2026-10-20 | `3bb0863` | S4 live discovery and metadata cache |
| 2026-10-20 | `658ad76` | S3 viewing/taste persistence and app integration |
| 2026-10-20 | `a813113` | S2 player and custom manual source selector |
| 2026-10-20 | `59853c9` | S1 adapters and explicit identities |
| 2026-10-20 | `f032f77` | Streaming research and phased roadmap |
| 2026-10-16 | `0b6576d` | Merge TMDB feature branch into the v0.3.0 history |
| 2026-10-16 | `55abf64` | v0.3.0 release metadata |
| 2026-10-16 | `73dd67a` | SVG icon system and circular avatar polish |
| 2026-10-16 | `9b2a805` | TMDB snapshot and mood-search tuning |
| 2026-10-16 | `69d8a35` | TMDB builder and real-data engine support |
| 2026-10-16 | `b951a55` | GitHub Pages test/export/deployment workflow |
| 2026-10-16 | `047be1e` | Static in-browser recommendation engine |
| 2026-10-16 | `7e18f44` | Initial README, architecture, algorithm, iteration and changelog docs |
| 2026-10-16 | `a85ba97` | Netflix-style billboard, rows, previews and drawer |
| 2026-10-16 | `03759aa` | Wikipedia poster download/cache |
| 2026-10-16 | `21b46be` | FastAPI recommendation/similarity/statistics endpoints |
| 2026-10-16 | `55f4aa4` | Curated dataset and hybrid recommender |
| 2026-10-16 | `7892761` | Project setup, launcher and dependencies |

Further work and remaining acceptance are tracked in [docs/ITERATIONS.md](docs/ITERATIONS.md) and the [streaming roadmap](docs/streaming/README.md). Planned work above is not a release or deployment claim.

## [0.3.0] - 2026-10-16 (Iteration 3: real-world data with TMDB)

### Added
- `scripts/build_tmdb_catalog.py`: builds a real catalogue (about 450 most-voted + currently popular films) from the TMDB API, with keywords, cast, director, runtime, tagline, poster, backdrop, YouTube trailer and TMDB recommendations. Reads `TMDB_READ_ACCESS_TOKEN` / `TMDB_API_KEY` from the environment or a git-ignored `.env` (`.env.example` provided). Retries on 429, certifi TLS.
- **Graph-based collaborative filtering**: item vectors from TMDB's audience-driven recommendation graph (symmetrised, with self-loops); cosine = shared neighbourhood.
- **Vote-weighted quality** (IMDb-style Bayesian average with the median vote count as prior).
- Director and top cast as content features ("Because you loved Inception · christopher nolan").
- Dataset switch: `CINEMAGIC_DATASET=tmdb|curated` (TMDB is the default when a snapshot exists).
- UI: real backdrops in the billboard, hover previews, modal and "More Like This"; **▶ Play Trailer** (YouTube, privacy-enhanced) in the billboard, previews and modal; tagline, runtime, director and cast in the modal; TMDB attribution.
- `tests/test_tmdb.py` (8 tests, offline): payload normalisation, slugs, trailer choice, graph CF, people explanations, weighted rating, and JS parity on a graph catalogue. `tests/conftest.py` pins the existing tests to the curated dataset.

- **TMDB snapshot** `backend/data/tmdb_movies.json`: 447 films (1957–2026), 1,275 recommendation-graph links (avg. 5.7 neighbours), backdrops and trailers for all 447. 12/12 sampled trailer IDs verified against YouTube.
- Mood synonyms now map everyday words onto TMDB keywords too (`sadness`, `loss-of-loved-one`, `haunted-house`, `psychological-thriller`, …) as well as genres, so mood search works on the real catalogue.

### Changed (visual polish)
- Replaced every emoji and Unicode symbol in the UI with one consistent inline-SVG line-icon set (24px grid, 2px round strokes): mood chips, buttons, badges, arrows, preview actions, drawer, "How it works", toasts and like-burst particles.
- The profile avatar is now a circle centred inside its circular confidence ring (it was a square inside a circle).
- New favicon (red rounded square with a white "C"); ratings use a gold star icon; copy no longer relies on glyphs ("like and pass" instead of ♥/✕).
- Bar animations start with a forced reflow instead of `requestAnimationFrame`, so they also render in headless/background tabs.

### Fixed
- Mood keys matched as raw substrings, so "war" fired inside "heart**war**ming" (a cozy search returned *1917*). Keys now match only at the start of a word, in both Python and JS. A regression test was added.

### Changed
- Static model format v2 ships sparse item vectors (`X`, `C`); the browser computes the similarity matrices on load, keeping `model.json` small for large catalogues.
- Ranking uses a stable sort, so tie order is deterministic and identical in Python and JS.
- Genre and search rows are capped at 30 titles.

## [0.2.1] - 2026-10-16 (GitHub Pages deployment)

### Added
- Live static deployment at https://codinsayan.github.io/Movie-Recommendation-System/.
- `frontend/engine.js`: a JavaScript port of the recommender (TF-IDF mood transform, hybrid blending, MMR, explanations, taste profile, similar movies) that answers the same `/api/*` paths in the browser.
- `scripts/export_static.py`: exports the trained model to `frontend/data/model.json` (about 180 KB).
- `tests/test_static_engine.py`: 11 parity tests checking that the JS and Python engines return identical picks, order, match %, reasons and taste profiles.
- `.github/workflows/pages.yml`: test → export → deploy on every push to `main`.
- "How it works" notes when the app is running fully in the browser.

### Changed
- The frontend uses the in-browser engine automatically on `*.github.io`, or when the API is unreachable.

## [0.2.0] - 2026-10-16 (Iteration 2: Netflix-style redesign)

### Added
- **Real movie posters** for all 60 films, cached locally in `frontend/posters/` (6.9 MB, works offline).
- `scripts/fetch_posters.py`: fetches posters from the Wikipedia REST API (no API key), with title overrides for ambiguous films, HTTP 429 back-off, certifi TLS, and incremental caching.
- **Billboard hero** that auto-rotates through your top 5 picks every 8 s: blurred-poster backdrop with Ken Burns zoom, 3D-tilted poster, green "% Match", "Because you loved…", More Info / Love / Pass buttons, progress dots.
- **Horizontal rows**: Top Picks for You, My List, *Because you loved X* (your two most recent loves), Top 10 Highest Rated (big outlined rank numerals), and genre rows ordered by your Taste DNA.
- **Hover preview cards** that pop out of the row after 450 ms with poster, actions (ⓘ ♥ ✕ ⌄), match, genres and reason.
- Green match badges on tiles, ♥ badges on loved titles, "NEW PICK" badges after re-ranking.
- **Netflix-style detail modal** with blurred header, score breakdown and a "More Like This" grid.
- **My Taste drawer** (🧬 avatar, with a confidence ring) holding Taste DNA, vibe tags, My List / Not for me poster grids, reset and "How it works".
- Expanding nav search: filters titles live, and **Enter conjures recommendations by mood**.
- Onboarding banner with a 3-step progress bar until Taste DNA unlocks.
- Gradient + emoji poster fallback if an image fails to load.
- Tests: every movie has a cached poster; whole-catalogue scoring.

### Changed
- Full visual redesign: `#141414` canvas, red accent, Bebas Neue wordmark, Inter UI.
- `/api/recommend` accepts `k` up to 100, so one call scores the whole catalogue and every tile can show its match.
- Row scroll positions are preserved across live re-ranks; only new rows animate in.
- `requirements.txt` adds `certifi`.

### Removed
- Aurora/glassmorphism theme and the separate Discover grid (replaced by genre rows + search).

## [0.1.0] - 2026-10-16 (Iteration 1)

### Added
- **Recommendation engine** (`backend/recommender.py`)
  - TF-IDF content model over genres, tags and overview (genres/tags weighted ×2).
  - Item-item collaborative filtering with adjusted cosine similarity.
  - Reproducible simulated ratings matrix: 600 users, Dirichlet genre tastes, about 80% sparsity.
  - Hybrid scoring with three modes: `popular` (cold start), `mood`, `personal`.
  - Dislikes act as negative feedback (penalty 0.5).
  - Maximal Marginal Relevance re-ranking (λ = 0.75) for diverse lists.
  - Mood search with everyday-language synonym expansion.
  - Per-pick explanations: `because`, `shared` traits, score `breakdown`, display `match` %.
  - Taste profile: normalised genre weights, top tags, confidence.
- **API** (`backend/app.py`): `/api/health`, `/api/movies`, `/api/recommend`, `/api/movies/{id}/similar`, `/api/meta`, with request validation.
- **Frontend** (`frontend/`)
  - Hero "Oracle" mood input with rotating placeholders and 8 one-tap mood chips.
  - "For you" rail that re-ranks live with View Transitions; animated match rings.
  - Discover grid with genre filters and search.
  - 3D tilt + glare cards, particle bursts on ♥, toasts, aurora background, cursor spotlight.
  - Taste DNA sidebar: 3-step unlock, confidence meter, animated genre bars, tag cloud, editable picks.
  - Detail modal with "Why this pick?" breakdown and "More like this".
  - "How it works" modal with live model stats.
  - Keyboard shortcuts, `localStorage` persistence, reduced-motion support, responsive layout.
- **Data**: 60 curated films with generated gradient + emoji posters (no image assets).
- **Tooling**: `run.py` one-command launcher, `requirements.txt`, 15 pytest tests.
- **Docs**: README, ARCHITECTURE, ALGORITHM, ITERATIONS, CHANGELOG.
