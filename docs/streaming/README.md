# Streaming implementation roadmap

Decision date: 20 October 2026. Branch: `feature/streaming-platform`.

Status: S1-S5D and S6 are implemented; automated candidate checks pass as `0.4.0-rc.1`. On 21 October 2026 the owner supplied **2/2 overall relevance** and general playback sign-off (**"everything works well"**). Detailed source/device/region and public-offering records remain open; S5 stays opt-in. S7 Render deployment is next. The viewer switches sources **manually**. See [candidate evidence](../evaluation/s6/README.md) and [live validation](PLAYBACK_VALIDATION.md).

## Provider decision

Use **CineSrc as the default**, with **VidLink** and **VidSrc .sh** as manually selected alternatives. After both alternatives rejected sandboxed playback, the user explicitly requested standard unsandboxed movie iframes. VidLink has been restored to the selector; player-message origin/window validation remains active. The user confirms the sources now play after sandbox removal; uptime and catalogue-wide availability have not been measured. Keep the remaining research directory as a backlog rather than loading dozens of embeds.

| Candidate | Initial role | Published interface useful to this plan | Validation status |
|---|---|---|---|
| [CineSrc](https://cinesrc.st/docs) | Default source | TMDB addressing, ready/play/error/progress messages, start-position support | User confirms movie playback; full acceptance pending |
| [VidLink](https://vidlink.pro/) | Viewer-selected alternative | TMDB addressing and player/progress messages | User confirms playback after sandbox removal; detailed acceptance pending |
| [VidSrc .sh](https://vidsrc.sh/vidsrc/docs/) | Viewer-selected alternative | TMDB/IMDb addressing and player messages | User confirms playback after sandbox removal; detailed acceptance pending |

If the default candidate fails the initial playback exercise, choose the passing alternative and record the result. Do not keep a nonworking source merely to preserve the planned order. Source availability and content permissions remain separate from this technical selection; use films with an established permission basis for validation.

## Product behavior

1. A viewer opens a movie and selects **Watch movie**.
2. The player loads the default enabled source. **Play trailer** remains a separate action.
3. A visible **Source** selector lists the enabled alternatives. The viewer can change it at any time.
4. A reported failure displays **This source could not play the movie. Choose another source.** The selector stays usable even when the iframe reports nothing.
5. Only a viewer's source-selection action replaces the player. Errors, timeouts and progress messages never select another source automatically.
6. Once progress support ships, manual source changes attempt to retain the last position where the selected provider supports it. Browser autoplay restrictions can still require another Play click.

There is one active movie iframe. Closing the player or opening a different movie disposes its listeners and pending work. A successfully loaded iframe is not treated as proof that the movie played; see [browser iframe event behavior](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe#error_and_load_event_behavior).

## Delivery sequence

| Phase | Deliverable | Dependency | Status |
|---|---|---|---|
| [S1: Source contracts and proof](01-source-foundation.md) | Three adapter contracts, explicit movie identity, playback evidence | Existing v0.3.0 app | Code implemented; live proof pending |
| [S2: Player and manual switching](02-player-and-manual-switching.md) | Watch movie action, player overlay, three-source selector, failure UI | S1 | Code implemented; browser acceptance pending |
| [S3: Personal viewing state](03-progress-and-watchlist.md) | Resume, Continue watching, independent watchlist, position transfer | S2 | Code implemented; browser acceptance pending |
| [S4: Search and catalogue growth](04-search-and-catalogue.md) | Paginated TMDB-backed discovery, metadata cache, broader language coverage | S2; reuse S3 identity conventions | Implemented; API/client checks passed |
| [S5: Viewing-aware recommendations](05-recommendations.md) | Measured viewing, device-local playback eligibility and explanations | S3 and S4 | Implemented as opt-in; evaluation/parity passed |
| [S5A: Dynamic preferences](05a-dynamic-preferences.md) | Apply external likes/dislikes using resolved metadata and honest pending states | S4 and S5 | Implemented; API/static/boot tests and focused desktop/mobile browser checks passed |
| [S5B: Dynamic discovery](05b-dynamic-discovery.md) | Retrieve new recommendation candidates beyond the starter snapshot | S5A | Implemented; deterministic/live API and S5D rendered-browser checks passed |
| [S5C: Scalable ranking](05c-scalable-ranking.md) | Sparse feature/profile scoring and bounded reranking instead of growing global matrices | S5A and S5B | Implemented; tests, benchmark, live API and S5D rendered-browser checks passed |
| [S5D: Dynamic evaluation](05d-dynamic-evaluation.md) | Relevance, parity, browser-flow and resource acceptance; optional embedding decision | S5A-S5C | Accepted with owner relevance 2/2 overall; calibration retained, embeddings deferred |
| [S6: Release readiness and operational checks](06-release.md) | Provider configuration, release-candidate acceptance and regression evidence | S1-S5 and S5A-S5D | Implemented; automated checks and owner functional sign-off recorded; detailed public-release evidence remains open |
| [S7: Render deployment](07-render-deployment.md) | One full-project Render service, hosted acceptance evidence and rollback | S6 | Planned |

**First demo milestone:** S1 + S2. A user can search the existing catalogue, open a movie, and manually try another source. S3 completes resume behavior. S4-S5 establish discovery and viewing signals. S5A-S5D implement and validate dynamic recommendations before S6 release readiness and S7 Render deployment.

The older recommender evaluation/model experiments remain recorded in [ITERATIONS.md](../ITERATIONS.md). Streaming work keeps S1-S7 labels and inserts S5A-S5D between S5 and S6, preserving the existing release/deployment numbering. Decide release versions at implementation time.

## Dynamic recommendation upgrade

Implementation order: **S5 -> S5A -> S5B -> S5C -> S5D -> S6 -> S7**. The current 447-film snapshot remains the starter/offline fallback. The new phases make external likes/dislikes usable, retrieve fresh candidates and score bounded pools as the catalogue evolves. Candidate budgets are per-request limits, not a permanent 447/500-film discovery limit. The existing snapshot builder cap remains until deliberately revisited.

Start with metadata-based features and reuse the existing stack. S5D evaluates relevance and resource costs; semantic embeddings remain an optional follow-on. S5A-S5C are implemented with deterministic, benchmark, API and browser evidence. S5D recorded proxy/live replay, browser walkthrough and popularity calibration; on 21 October the owner rated relevance **2/2 overall**. S6 has automated checks and general owner playback sign-off. Detailed source/device/region and public-offering records remain open; S7 deployment is next.

## Implementation boundaries

Keep FastAPI, vanilla JavaScript and the current recommender. Add small modules for provider definitions, playback lifecycle and viewing-state persistence; do not rewrite the UI framework for this milestone.

S1-S3 should support both the local FastAPI app and the existing static demo. A shared browser-readable registry keeps source definitions consistent. S4's live metadata search needs the backend to keep its API credentials private; the static demo retains snapshot search and identifies that capability clearly.

Module locations:

- `frontend/providers.js`: approved provider definitions, URL builders and message adapters.
- `frontend/player.js`: one-player lifecycle and viewer-driven source changes.
- `frontend/viewing.js`: versioned progress, watchlist and preferred source storage.
- `frontend/preferences.js`: browser-local likes, dislikes and mood, including legacy migration and separate catalogue profiles.
- `backend/catalog.py`: S4 metadata lookup/cache and canonical identity mapping.
- `frontend/catalogue.js`: remote search, capability detection and saved title metadata.
- `backend/recommender.py` and `frontend/engine.js`: coordinated S5 ranking changes where both modes support them.
- `backend/features.py`, `backend/preferences.py` and `frontend/preference-resolver.js`: shared normalization, versioned external feature resolution and device-local feature aggregates. `backend/discovery.py`: S5B bounded candidate retrieval (related titles, taste genres, new releases, starter pools) with background enrichment. `backend/ranking.py`: S5C ranking contract, budgets, rollback switch and the versioned sparse feature cache shared by discovery and external measured viewing.

Movie identity must include its origin. TMDB dataset IDs are TMDB IDs; curated IDs are internal IDs and must never be sent to a provider as though they were TMDB IDs. Resolve an explicit TMDB mapping or show that full-movie playback is unavailable for that record.

## Definition of done

Each phase has checkboxes, affected files, a demo and acceptance criteria in its linked document. Mark a phase done only when its acceptance evidence exists. Deterministic tests use simulated provider messages; live checks verify a small permitted-film set without making third-party network availability a CI dependency.

The recorded suite passes **143 tests**, including external preference, dynamic retrieval, sparse ranking, evaluation and Python/JavaScript parity checks. The Node player/preferences runner has **29 cases** within that suite. S6 additionally records **six browser scenarios** for backend/static desktop/mobile and disabled-source recovery. See [S6 evidence](../evaluation/s6/README.md), [S5 evaluation](../EVALUATION.md) and [S5D review](../evaluation/s5d-review.md). The owner's 21 October relevance rating and general playback sign-off are recorded; detailed source/device/region, explicit autoplay and public-offering evidence remain uncollected. Automated results remain dated 20 October.

## Deferred work

Automatic provider failover, stream extraction/proxying, TV episode navigation, accounts and cross-device sync, subscription billing, and enabling the entire provider directory are outside this roadmap. The source selector and adapter boundary allow additional evaluated providers later.
