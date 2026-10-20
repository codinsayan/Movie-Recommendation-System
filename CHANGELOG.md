# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Status as of 2026-10-21

This section records implemented streaming work on `feature/streaming-platform` through S6. S6 assigns candidate version **0.4.0-rc.1**; it is not a final release, tag or deployment. The earlier S5B-S5D work and this phase have not been pushed by this task. Earlier Iterations 1-3 and static-hosting release history are retained below.

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
| S5B | Dynamic candidate retrieval beyond the snapshot implemented; deterministic, live API and rendered-browser checks passed (browser walkthrough recorded in S5D) |
| S5C | Versioned sparse feature cache, bounded reranking, external measured viewing, explanation floor and rollback implemented; tests, benchmark, live API and rendered-browser checks passed |
| S5D | Evaluation recorded; calibration adopted, embeddings deferred; owner relevance acceptance 2/2 overall on 21 October |
| S6 | Candidate implemented; 143 tests and six browser scenarios passed; owner general playback sign-off received 21 October; detailed public-release evidence remains open |
| S7 | Render planning only; no service created or deployed |

The **447-film TMDB snapshot** (and the separate **60-film curated dataset**) remains the starter and offline pool. With a configured backend, S5B adds up to 300 freshly retrieved candidates per request and S5C ranks them with bounded sparse work; neither enlarges the snapshot model.

**Open items:**
- S5D received **2/2 overall relevance**; no individual profile, per-pick or baseline scores were supplied. See [review record](docs/evaluation/s5d-review.md).
- General playback sign-off received (**"everything works well"**). Detailed film/source/device/region records, explicit autoplay results and public-offering terms remain unrecorded.
- Final candidate acceptance, any separately authorized push/release, then Render deployment (S7).
- The provider set is unchanged: CineSrc, VidLink and VidSrc. No further streaming servers were researched or added.

### S5D/S6 - Owner acceptance follow-up (2026-10-21)

- Recorded the owner's **"2"** response as overall relevance **2/2** for the proposed recommendation sets and accepted S5D at the owner-review level. Left individual pick/baseline cells blank instead of inventing scores or a human comparison metric.
- Recorded **"everything works well"** as general functional sign-off on the requested playback exercise. No film, individual source outcome, browser/device/country, explicit autoplay result or provider-terms approval was inferred.
- Updated the review sheet, S5D/S6 acceptance docs, playback validation, S6 evidence summary, README and roadmap. S7 is next; detailed public-release/hosted evidence remains open.
- Documentation only; no code, model, configuration, automated results, release version, tag, push or deployment changed. The 143-test/six-browser results remain dated 20 October 2026 and were not rerun for this recording update.

### S6 - Release candidate, provider configuration and operational checks (2026-10-20)

Candidate: **0.4.0-rc.1**. Phase: [S6](docs/streaming/06-release.md). Implementation and automated checks complete; final relevance/live-playback acceptance remains open.

- Added `backend/release.py` as the candidate version/public configuration/policy module; FastAPI now reports the candidate version.
- Moved fixed provider labels, HTTPS origins, movie/resume paths, documentation and iframe permissions into `frontend/provider-registry.json`. Event parsing stays in the provider adapters.
- Added ordered `CINEMAGIC_PROVIDERS` process configuration. Unset enables the three sources; an explicitly empty value disables all. Rejects unknown/duplicate IDs and arbitrary URL values at startup.
- Added `/api/playback` and a synchronous `/playback-config.js` route before the static mount. Only public configuration is returned; private TMDB credentials remain server-side.
- Added generated/committed static playback bootstrap and included it before `providers.js`. `export_static.py` now exports policy alongside the browser model. A missing bootstrap disables playback while retaining recommendations.
- Added backend CSP frame origins from enabled entries, `object-src 'none'`, `base-uri 'self'`, `nosniff`, HTML/script revalidation and a `no-store` runtime bootstrap. Static bootstrap applies the same frame restriction through a CSP meta element.
- Player iframe permissions now come from the registry. Unsandboxed playback, exact origin/window/generation validation, one-frame ownership, manual switching and autoplay-on-switch requests remain intact.
- Added explicit all-sources-unavailable text in movie details and Watch handling, preserving recommendation/trailer access.
- Added seven pytest release tests for configuration/defaults/empty/order/errors, allowed origins, API/bootstrap parity, secret/private-file isolation, generated policy consistency and a configured SQLite write/read. Added three Node player cases covering disabled saved sources, local-state retention, all-disabled behavior, registry permissions without a sandbox, and fail-closed behavior if the browser bootstrap is missing.
- Added `.github/workflows/checks.yml`: read-only feature-branch/PR validation, Python/JS parity suite, static export, browser-script syntax checks and a static candidate artifact; no deployment. Existing Pages workflow includes policy through its existing exporter call.
- Added `scripts/check_release_browser.cjs`, an isolated Chromium DOM exercise for backend/static desktop/mobile plus provider-disable restarts. Credentials are empty and third-party movie/trailer frames are blocked; messages are synthetic.
- Browser checks cover debounced snapshot search, details, likes, Watch/watchlist, manual keyboard switching, error recovery without automatic failover, position/autoplay URL parameters, wrong-origin/stale events, focus/menu behavior, no horizontal overflow, refresh persistence, Start over, trailer cleanup, empty recent-playback state, disabled-source recovery and history/watchlist independence.
- Recorded JSON results and inspected screenshots in [S6 evidence](docs/evaluation/s6/README.md). **143 pytest tests** and **six browser scenarios** pass. Model export is approximately 1,287 KiB for the committed TMDB snapshot.
- Corrected the synthetic Sintel player fixture to TMDB ID 45745, matching the planned permitted-film live exercise.
- Documented shell/hosting configuration, static re-export, restart/reload semantics, provider and snapshot-ranking rollback, and browser-state/cache compatibility. Updated README, architecture, roadmap, `.env.example` and playback validation; corrected stale phase statuses and static-model size.
- Rechecked primary provider integration pages and recorded Sintel's attribution-based permission reference for the remaining live matrix. Integration pages do not establish catalogue-wide distribution permission; actual media, device/region, fullscreen/captions/autoplay/resume and provider-terms acceptance remain pending.
- No Render configuration/service, stream extraction, automatic failover, additional providers, login, storage migration, release tag or push was added.

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

### Changelog consolidation (2026-10-20)

Commit: `1b56dad`.

- Consolidated the complete iteration and implementation changelog against Git history and the phase records before S5B began.

### S5B - Dynamic recommendation candidates (2026-10-20)

Commits: `f42497d` (implementation), `8af3455` (docs). Phase: [dynamic discovery](docs/streaming/05b-dynamic-discovery.md).

**Retrieval (`backend/discovery.py`)**
- Bounded retrieval of candidates beyond the 447-film snapshot from four sources:
  - TMDB related titles of up to **4 seed likes**: the two most recent, then likes spread evenly across older history (`select_seeds`);
  - acclaimed films (`vote_average.desc`, at least 1,000 votes, 2 pages) in the **top 2 taste genres**, counted from snapshot likes plus the S5A external profile. The first live run with a most-voted query added zero new titles, because the snapshot already holds them;
  - **new releases** from the last 120 days (`popularity.desc`, at least 50 votes);
  - for cold-start and dislike-only profiles, popular (2 pages, at least 500 votes) and top-rated (at least 3,000 votes) **starter pools**.
- Budgets:
  - a **300**-candidate pool, merged in deterministic submission order;
  - **4** concurrent upstream requests, enforced by a process-wide semaphore shared by all requests;
  - **12** background detail lookups per request on a 2-worker queue, so enrichment never blocks a response. Candidates are labelled `full` or `summary` metadata.
- Exact liked, disliked and snapshot IDs are dropped at merge time, whichever source returned them.
- Each source fails independently. The report is `ok`, `partial` or `unavailable`, stale cache entries are flagged, and the request itself never fails because discovery did.

**Catalogue (`backend/catalog.py`)**
- Added cached `Catalog.related()`, `Catalog.discover()` and `Catalog.cached_movie()`.
  - `discover()` takes allow-listed sort keys, page 1-3, a bounded vote minimum, genres OR-joined, and a validated ISO date.
  - TTLs: related 24 h, discover 6 h, new releases 3 h.
  - List responses are validated as lists. The existing timeout, rate-limit, sanitized-error and stale-cache behaviour is reused.

**Ranking (`backend/recommender.py`)**
- `recommend(extra=...)` scores discovered films alongside the snapshot:
  - content: the fitted TF-IDF vocabulary, with no refit and no matrix growth;
  - collaborative: TMDB related-title evidence, `RELATED_LINK = 0.3` per related seed, calibrated to a direct snapshot-graph link;
  - quality: `quality_of()` on the snapshot's scale.
- MMR runs over the union (`_mmr_union`), and snapshot pairs keep the exact `content_sim`.
- Explanations come from `_extra_explanation`: "Because you loved X" with `evidence: "tmdb-related"`, a content link, an external seed, viewing, "New release that fits your taste", "Discovered for your taste" or "Popular right now".
- The snapshot-only path is unchanged.

**API and frontend**
- `POST /api/recommend` accepts `discover: true` and returns a `discovery` report covering:
  - status, profile, seeds, genres and per-source counts;
  - pool size, enriched, summary-only and queued counts;
  - upstream calls, cache hits, stale flag, failed sources and the number of films recommended.
- `/api/capabilities` reports `dynamic_discovery`.
- The frontend requests discovery only from a configured backend.
  - Discovered films are registered with the catalogue, so details, likes/dislikes (through S5A), Watchlist and playback work.
  - Each refresh uses an `AbortController`, so an older pool can never overwrite newer rows.
  - The UI shows a **Discovered** tile badge, an honest Top Picks subtitle (count, partial or stale notes) and the retrieval sources in the "why" panel.
  - Static mode never sends `discover`.

**Tests and evidence**
- 12 deterministic mock-TMDB tests in `tests/test_discovery.py` (fixture IDs 910000001-910000008): **123 passed**. JS harnesses now provide `AbortController` like browsers.
- Live check: for Inception + Interstellar + The Dark Knight, 5 of the top 12 picks came from outside the snapshot (Batman (1989), Primer, The Electric State, Stargate: Continuum, Batman and Harley Quinn). Latency: 1.9 s cold, 0.4-1.1 s warm after moving enrichment off the request path (it was 4-5 s before).

**Process and operational notes**
- S5B was first built on a separate `feature/s5b-dynamic-discovery` branch. At the user's request it was fast-forwarded into `feature/streaming-platform`, and the extra branch, which was never pushed, was deleted. Branch references in the docs were corrected.
- A user-reported "no discovery in the response" turned out to be a **stale server**. A `run.py` started before S5B still held port 8000, so the new launch failed to bind and the old code kept answering (its `/api/capabilities` had no `dynamic_discovery`). Restarting fixed it. Check what is listening on port 8000 before restarting.
- Superhero profiles discover fewer new films because the snapshot already contains most of them.
- The user chose to keep the existing streaming providers unchanged; no further piracy streaming sources were researched or added.

### S5C - Scalable profiles and bounded ranking (2026-10-20)

Commits: `20ac7f6` (implementation), `713a0c0` (docs). Phase: [scalable ranking](docs/streaming/05c-scalable-ranking.md).

**Contracts, cache and budgets (`backend/ranking.py`)**
- Added:
  - the `rank-v2` contract and the per-request `RANKING_BUDGET`: rerank pool 300, encode batch 64, external viewing 20, feature cache 4,000 entries / 16 MiB;
  - the `CINEMAGIC_RANKING=snapshot` rollback switch;
  - `FeatureStore`, a thread-safe LRU of sparse TF-IDF rows.
- `FeatureStore` behaviour:
  - keyed by canonical ID, metadata language and `feature_version`;
  - re-encodes when the metadata digest changes;
  - drops other feature versions on `bind`;
  - encodes misses in batches;
  - reports hits, misses, re-encodes and evictions.
- `Discovery` uses the shared store, so discovered rows are **sparse CSR** instead of a dense 300 × 7,395 matrix. It reports `timing_ms.retrieve`/`encode` and per-request encoding counts.

**Scoring and reranking**
- MMR builds its pairwise matrix from sparse rows of the bounded pool only, with an exact incremental redundancy update. 30 randomised checks gave identical selections to the previous implementation.
- The rerank pool is `min(3k, 300)`, and exclusions apply before it is cut.
- Measured viewing now includes watched TMDB films **outside the snapshot**:
  - features are read from the cache only, for the 20 most recent titles;
  - they give content-only evidence under the same 10% cap;
  - explicit likes and dislikes win;
  - uncached titles are reported as `viewing_status.pending` and fetched in the background;
  - they add "Because you watched" explanations and rows.
- **Honest explanations:** "Because you loved X" requires `EXPLAIN_FLOOR = 0.03` of link, in Python and the browser engine. Before, Toy Story → *The Godfather* (0.018, nothing shared) and Parasite → *The Shawshank Redemption* (0.007) were labelled as such. Weak-link picks now read "A well-rated pick to widen your taste".
- Discovered films report `component_availability`; missing related-title evidence is stated, never imputed.

**Performance and robustness**
- `Catalog.cached_movies()` reads a whole pool in one query, where warm discovery had opened about 120 SQLite connections and rewritten the schema on each one.
- The schema is written once per process. A deleted cache file is recreated, and a locked or damaged one behaves as a cache miss.
- Every response carries `ranking` diagnostics (contract, mode, candidates, eligible, rerank pool, signals, feature-cache stats, timing). `/api/capabilities` reports `ranking`.
- `requirements.txt` lists `scipy` explicitly.

**Frontend**
- "Because you watched" vs "Because you loved" is now correct in the hover preview and the details side panel.
- The "why" panel shows the pick's reason when no film is named, and states when a discovered film has no related-title evidence.
- The Top Picks subtitle notes watched films waiting for metadata.
- The static export carries `explainFloor` and `rerankPool`.

**Tests and evidence**
- 12 tests in `tests/test_ranking.py`, plus a JS case showing that losing or invalidating derived features never touches taste, Watchlist or viewing, and that new choices resolve incrementally. Two S5B tests that asked for `k=1000` now use `eligible_keys`, because the rerank pool is bounded. **135 passed**.
- `scripts/benchmark_ranking.py`: as the cache grew from 0 to 20,000 entries, per-request work stayed flat.
  - 120 films encoded cold, 0 warm; 6 upstream calls cold, 0 warm;
  - a 300-row rerank pool;
  - a **2.15 MB** request peak, down from 29 MB;
  - about 55 ms warm.
- Live: warm requests dropped from 0.4-1.1 s to 0.2-0.3 s, with 37-85 ms spent ranking. No top-40 pick lacked a reason for the tested profiles.

### S5D - Evaluate and accept dynamic recommendations (2026-10-20)

Commits: `c9bcaed` (implementation), `ab1ee7b` (docs). Phase: [dynamic evaluation](docs/streaming/05d-dynamic-evaluation.md).

**Calibration adopted (`backend/recommender.py`)**
- The problem: S5B shrank discovered films towards the acclaimed snapshot's prior (median 13,370 votes, mean 7.49). That flattered thin-vote titles, and every TMDB-related title got a full direct-link score. With only Parasite liked, 15 of the top 20 were discovered films with a median of about 300 votes; *The Middle Man* had 56.
- The fix: `DISCOVERY_POLICY` = pool prior + related confidence.
  - A discovered film's quality is also estimated against the pool it was retrieved with, and the **lower** of the two estimates is kept, so it is never a boost.
  - Related-title evidence is scaled by `votes / (votes + pool median votes)`.
  - There is no hard vote floor.
- A first, two-way version boosted thin-vote films in cold start (*Michael (2026)* above *The Godfather*). Making it one-directional fixed that, and cold start now matches S5B exactly.
- Results on live pools:
  - picks under 300 votes: 17.5% → 11.7%;
  - median votes of discovered picks: 1,171 → 2,116;
  - mean rating: 7.34 → 7.50;
  - diversity: 0.935 → 0.944;
  - a 37.5% discovered share remains.
- Examples: Pixar's *Rock Dog* moves from #4 to #9 and *Blue's Big City Adventure* leaves the top 10; for Parasite, *The Middle Man*, *Good News* and *Somewhere in Queens* give way to *American Psycho*, *The Wolf of Wall Street* and *Falling Down*.

**Evaluation tooling and results**
- `scripts/record_dynamic_fixture.py` records real TMDB pools through the production `Discovery`, with retries for a flaky network. The fixture is `docs/evaluation/s5d-live-fixture.json`: 12 profiles and 367 films, covering:
  - Pixar, Nolan, a single niche like (Parasite), romance and horror;
  - multi-interest and a related dislike;
  - an external like and external dislike (Primer / Transformers: RotF);
  - non-English originals (Burning, Shoplifters) and a 2026 new release;
  - dislike-only and cold start.
- `scripts/evaluate_dynamic.py` runs offline and writes `s5d-results.json` and `s5d-review.md`.
  - **World proxy:** the snapshot is split into 312 starter and 135 world films, and 80 profiles run with the edge to the held-out target removed. Dynamic retrieval plus bounded ranking reaches recall **0.80** (vs 0.575) and HR@10 **0.538** / NDCG@10 **0.331**. A snapshot engine scores 0.400 / 0.203, and S5A inputs alone 0.400 / 0.256.
  - Summary-only metadata halves world-target hits (0.382 → 0.206). Unfamiliar vocabulary correctly leaves an external like unavailable.
  - 0 dislike violations and 0 invalid explanations in every scenario.
  - It is labelled as a transductive graph proxy, not user evidence.
  - Policies were compared on a common pool; in the proxy they show no harm.
- **Embeddings deferred:** 70% of discovered-film tokens are in the vocabulary, the median is 23 features (40 for snapshot films), and no film has an empty vector. The measured problem was popularity calibration, not meaning.
- `scripts/browser_walkthrough.py` drives the real UI in headless Edge; results are in `s5d-browser.json`.
  - Discovered badges and provenance appear.
  - A like or dislike from details is visible in 0.33-0.36 s warm (1.2-2.6 s on a cold, flaky network).
  - Watch routes to CineSrc by TMDB ID.
  - Rapid toggles are debounced into one request.
  - The main thread blocks for at most 79 ms.
  - The static build shows no discovery and re-ranks in 0.27 s.
  - Headless Edge cannot make a window narrower than about 500 px (it reported 518), so the phone screenshot renders in a true 390 px iframe. Screenshots are in `docs/evaluation/screens/`.
- "How it works" explains discovered films, calibration, caching, failure fallback, static limits and when "Because you loved" appears.
- A new calibration regression test brings the total to **136 passed**, plus the JS suites.
- During this milestone the network intermittently cut TLS connections to TMDB (`UNEXPECTED_EOF`). The app degraded to `partial` discovery reports, as designed.
- **Pending:** human relevance ratings in `docs/evaluation/s5d-review.md`, which shows the S5B vs calibrated top 10 for every profile.

### Research, documentation and plans added (2026-10-20)

Documentation commits: `f032f77`, `bae6b09`, `2fdaadc`.

- Added the [provider research directory](docs/STREAMING_PROVIDERS.md), [streaming feasibility notes](docs/STREAMING_FEASIBILITY.md), phased implementation roadmap and playback evidence/checklist.
- Recorded the user's final preference for **manual** source switching, replacing the earlier automatic-failover proposal. The larger provider list is research/backlog; only the three selected adapters are integrated.
- Added S6 release-readiness planning for provider configuration, operational checks, actual browser/playback evidence, regressions and rollback. S6 implementation remains pending.
- Added S7 Render deployment planning for one FastAPI Web Service serving frontend/API/model, private credentials, build/start/health settings, disposable cache behavior, hosted acceptance and rollback. No Render service has been created or deployed.
- Inserted S5A-S5D before S6/S7 while preserving those labels. (All four have since been implemented; see the entries above.)
- Kept semantic embeddings as an optional measured follow-on, rather than an implemented model or a deployment prerequisite.
- Updated README, architecture, evaluation notes, iteration status, source evidence and changelog alongside completed work. Kept the older Iterations 4-6 plans separate; partial overlapping features do not mark those iterations complete.
- Consolidated this changelog against the existing Git history and phase records, retaining prior release entries, separating planning from implementation, and recording the latest validation limits.

### Implementation commit index

Commits from 2026-10-20 are unreleased streaming-branch work; the earlier versioned history follows this index.

| Date | Commit | Change |
|---|---|---|
| 2026-10-20 | `ab1ee7b` | S5D evaluation, calibration decision and browser evidence (docs) |
| 2026-10-20 | `c9bcaed` | S5D discovery calibration and evaluation tooling |
| 2026-10-20 | `713a0c0` | S5C scalable ranking design, budgets and benchmark (docs) |
| 2026-10-20 | `20ac7f6` | S5C bounded sparse ranking with a versioned feature cache |
| 2026-10-20 | `8af3455` | S5B dynamic discovery design, budgets and evidence (docs) |
| 2026-10-20 | `f42497d` | S5B dynamic candidates beyond the snapshot |
| 2026-10-20 | `1b56dad` | Consolidated iteration and implementation changelog |
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
