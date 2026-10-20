# ✦ Cinemagic: a hybrid movie recommender

> *Tell me a feeling. I'll find the film.*

Cinemagic is a movie recommendation system with a Netflix-style UI and real movie posters. Describe a mood in plain English, or tap ♥ / ✕ on films. Every tap re-ranks your picks in milliseconds, and every pick explains **why** it was chosen.

Built as a college project to show the three classic recommender techniques working together:

| Technique | What it captures | Implementation |
|---|---|---|
| **Content-based filtering** | what a movie *is* | TF-IDF over genres, mood tags and plot + cosine similarity |
| **Collaborative filtering** | what *people* co-enjoy | item-item adjusted-cosine over a user × movie ratings matrix |
| **Diversity re-ranking** | avoiding 10 near-identical picks | Maximal Marginal Relevance (MMR) |

**Live demo:** https://codinsayan.github.io/Movie-Recommendation-System/

## Quick start

```bash
pip install -r requirements.txt
python run.py            # starts http://127.0.0.1:8000 and opens your browser
```

Options: `python run.py --no-browser`, `python run.py --reload` (auto-reload while developing).

## Movie playback preview

On the TMDB catalogue, open a movie and choose **Watch movie**. The player offers **CineSrc**, **VidLink**, and **VidSrc** in a visible Source selector. Select another source yourself if playback fails; the app never switches providers automatically. Trailers remain available separately.

Playback positions and your preferred source are saved in this browser when the player reports progress. **Continue Watching**, **Start over**, and a separate **Watchlist** are included. The custom Source menu supports arrow keys, Enter, Escape and outside-click dismissal. Manual source changes request autoplay at the saved position; Start over also requests playback. Browser restrictions or provider behavior may still require pressing Play again.

The curated catalogue needs explicit TMDB mappings before full-film playback can be offered; its local numeric IDs are not sent to streaming providers. The same playback modules are included in the static export.

The local release candidate is **0.4.0-rc.1**. S6 adds configurable sources, shared frame policy and branch/PR release checks. The recorded suite passes 143 tests; desktop/mobile Edge checks pass in backend and static modes. On 21 October 2026 the owner rated recommendation relevance **2/2 overall** and reported **"everything works well"** for the requested playback exercise. Detailed source/device/region evidence, explicit autoplay results and public-offering terms remain unrecorded. See [S6 evidence](docs/evaluation/s6/README.md) and [live playback validation](docs/streaming/PLAYBACK_VALIDATION.md). S7 Render deployment is next and has not been performed.

Set the process environment variable `CINEMAGIC_PROVIDERS=cinesrc,vidsrc` to remove VidLink, then restart the server and reload the page. Order sets the default when no enabled browser preference exists; an explicitly empty value disables movie sources while keeping the recommender/trailers. Unset restores all three. IDs must come from the fixed registry. For static hosting, export with the same environment and publish the new assets. Operational flags use the shell/hosting environment; the TMDB `.env` is separate. [Configuration and rollback examples](docs/streaming/06-release.md#configuration-and-rollback).

Run the tests:

```bash
python -m pytest -q
```

## Remembering this browser

No login is needed to keep your taste. Likes, dislikes and the selected mood are saved in `localStorage` and restored before requesting recommendations. Watchlist, viewing progress and the preferred streaming source also stay in this browser. Refreshing or closing and reopening the browser does not intentionally clear them.

Existing likes from `cinemagic:v1` are migrated once into the active catalogue. TMDB and curated catalogues then keep separate taste profiles so identical numeric IDs cannot change your preferences for unrelated films. Resetting taste does not clear your watchlist or viewing history.

Use the same browser profile and site address when returning: `localhost:8000` and `127.0.0.1:8000` have separate browser storage, as does a deployed site. Clearing site data or ending a private-browsing session can remove saved preferences. If storage writes fail, the app reports that changes are session-only.

## Viewing-aware recommendations (S5)

Open **My Taste** and enable **Use viewing history** to try the experimental blend. After both two minutes and 30% of a film are measured playing, it can inform a **Because you watched** row. Unique watched intervals are measured separately from resume position: seeking, source changes, errors and pressing Play alone are not preference signals. Older saved positions do not acquire viewing evidence automatically.

Explicit taste retains 90% of the score when this option has qualified signals; viewing contributes at most 10%. Substantial repeat sessions have a capped influence. Likes/dislikes and Taste DNA remain explicit. In dynamic backend mode, S5C can use external watched titles once compatible metadata is cached. Static and snapshot rollback modes keep external viewing history without applying it to ranking. S5A resolves explicit external likes/dislikes separately.

**Top picks: played recently on this device** optionally filters picks using ten measured playing seconds within seven days. Later source errors invalidate that source's record. This is local evidence, not guaranteed availability; ordinary search and browsing remain available when the filter is empty. **Clear viewing history** removes progress and viewing/playback evidence while keeping likes, mood and Watchlist. Both options persist in this browser and work in FastAPI and static mode.

The new blend is opt-in: a small reproducible proxy evaluation found unchanged hit rate and slight NDCG differences, which do not establish real-user improvement. One informal review was broadly positive; broader relevance and rendered-browser acceptance remain pending. See [S5 implementation](docs/streaming/05-recommendations.md) and [evaluation](docs/EVALUATION.md).

The recent-playback option is a strict filter, so it can have no eligible picks. In that case the front banner shows clearly labelled **More to discover** suggestions from outside that filter. The filtered row keeps its empty-state explanation. **Show all picks** turns off only the recent-playback filter while preserving your viewing-history preference. If broader suggestions are also unavailable, the banner shows recovery actions instead of going blank or retaining an old movie.

## Real-world catalogue (TMDB)

### Live movie search (S4)

The backend app can search beyond the committed snapshot using the same TMDB credential in `.env`. Matching movies load automatically after a **300 ms typing pause**; no Enter is needed. Search replaces the home banner/rows with a responsive landscape grid, using backdrops where available and showing titles and years. Choose **Load more** for another page, or clear the search with **×** / **Esc** to return home. The **Details language** selector changes metadata; it does not select playback audio. Pressing Enter still searches the recommendation model by mood.

Remote results support details, the movie player and Watchlist. Selected metadata is saved locally so bookmarked movies remain visible after refresh. S5A lets their explicit likes/dislikes influence snapshot recommendations after English feature metadata resolves. Remote titles receive content-based More Like This neighbours from the snapshot without an invented personalized match score. With S5B, the backend also retrieves fresh recommendation candidates (TMDB related titles of your likes, acclaimed films in your taste genres, new releases) and ranks them with the same engine; they carry a Discovered badge. Discovery does not enlarge the model. S5C keeps that work bounded: discovered films are cached as sparse vectors, only the top `min(3k, 300)` candidates are reranked, and watched films outside the snapshot count towards viewing-based picks once their metadata is cached. Set `CINEMAGIC_RANKING=snapshot` to roll back to snapshot-only ranking. S5D calibrated discovered films against the pool they were found in, so a handful of votes no longer outranks well-loved films; see [the evaluation](docs/streaming/05d-dynamic-evaluation.md).

SQLite caches searches for one hour and details for one day, with stale fallback during upstream failures. The cache is bounded to 5,000 entries and git-ignored. Set `CINEMAGIC_CACHE_PATH` to change its location. Missing credentials or upstream failures leave snapshot browsing available.

GitHub Pages and curated mode retain snapshot/saved-title search. Live search requires FastAPI with the TMDB dataset; curated IDs remain isolated from TMDB IDs.

### External likes and dislikes (S5A)

Like or pass a searched movie outside the snapshot and the choice is saved immediately. The backend resolves its full metadata in English and transforms it with the existing fitted TF-IDF model. Resolved likes add content affinity; dislikes apply a softer negative influence and keep exact exclusions. No catalogue rebuild is needed. With a configured backend, recommendations can also include newly discovered films (S5B); the static build keeps the snapshot. More Like This also works for an external movie when its metadata is usable. Because you loved shelves remain independent of the Top Picks playback filter.

Cached external features are restored before the first recommendation request after refresh, so an applied like is not initially replaced by unpersonalized picks.

**My Taste** shows external choices as **applied**, **pending** or **unavailable**, with **Retry metadata** when needed. Unresolved choices stay saved and do not count towards Taste DNA. A bounded cache keeps compatible feature records across refresh separately from preference IDs; evicted or uncached choices resolve again; unavailable feature storage keeps session influence and rehydrates on a later visit. Clearing taste cannot resurrect a removed choice from a late lookup. Metadata display language remains independent of the fixed feature language.

The static app can reuse matching cached features or encode complete cached English details. A fresh movie without compatible metadata stays pending until the backend is available. External inputs have no invented collaborative evidence. See [S5A implementation and evidence](docs/streaming/05a-dynamic-preferences.md).

### Building the snapshot

Cinemagic can run on a real catalogue of about 450 of the most-voted films from [TMDB](https://www.themoviedb.org), with backdrops, trailers, cast, director and keywords:

```bash
cp .env.example .env          # then paste your TMDB API Read Access Token (or v3 API key)
python scripts/build_tmdb_catalog.py      # writes backend/data/tmdb_movies.json (about 1-2 min)
python run.py                              # serves the TMDB catalogue automatically
```

- Get a free key at https://www.themoviedb.org/settings/api. `.env` is git-ignored.
- The snapshot `tmdb_movies.json` is committed, so the app, tests and GitHub Pages never need the key at runtime.
- Collaborative filtering uses **TMDB's recommendation graph** (audience-driven "people also watched") instead of simulated ratings; quality uses an **IMDb-style vote-weighted rating**.
- Switch catalogues with `CINEMAGIC_DATASET=curated` or `CINEMAGIC_DATASET=tmdb` (the default when the snapshot exists).
- Options: `--pages 20` (×20 most-voted films), `--popular-pages 5`, `--min-votes 300`.

> This product uses the TMDB API but is not endorsed or certified by TMDB.

## Deployment (GitHub Pages)

For the full frontend/API/live-discovery application, S7.1 now provides a [Render Blueprint and setup runbook](docs/deployment/RENDER.md). The package pins Python/runtime dependencies, exports the snapshot fallback, and includes a hosted smoke checker with exact Git-revision verification. Local preparation is tested; a Render account, repository connection, published branch and private TMDB secret are still needed. **No Render service URL is claimed yet.** [Local validation](docs/deployment/S7_VALIDATION.md).

GitHub Pages serves static files only, so the Pages build runs the recommender **in the browser**:

1. `scripts/export_static.py` exports the trained model (sparse TF-IDF/content and collaborative vectors, vocabulary and config) to `frontend/data/model.json` (about 1.3 MiB for the TMDB snapshot), plus the public `frontend/playback-config.js`. No credentials are exported.
2. `frontend/engine.js` is a JavaScript port of `backend/recommender.py` that answers the same `/api/*` paths. `tests/test_static_engine.py` checks it gives the same results as Python.
3. `.github/workflows/pages.yml` runs the tests, exports the model and publishes `frontend/` on every push to `main`.

The app uses the in-browser engine automatically on `*.github.io`, or whenever no API server can be reached. Locally, `python run.py` still uses the FastAPI backend.

One-time setup: **Settings → Pages → Build and deployment → Source: GitHub Actions**.

## Features

- 🎬 **Netflix-style layout**: an auto-rotating billboard of your top 5 picks, then horizontal rows (Top Picks for You, My List, *Because you loved X*, Top 10, and genre rows ordered by your taste).
- 🖼️ **Real posters** for every film, cached locally so the app works offline. A gradient + emoji poster appears if an image fails.
- 👆 **Hover previews**: hold over a poster and a card pops out with ⓘ / ♥ / ✕, match %, genres and the reason it was picked.
- 🪄 **Mood search**: type "make me cry" in the nav search and press Enter. Typing alone filters titles live.
- ♥ / ✕ **Live learning**: every tap re-ranks every row; new picks get a "NEW PICK" badge.
- 🧬 **My Taste drawer**: genre affinity bars, vibe tags, confidence ring on the avatar, and your loved/passed lists.
- 💬 **Explainable picks**: "Because you loved Inception", shared traits, and a content / fans-like-you / quality breakdown in the detail view, plus "More Like This".
- ⌨️ **Keyboard**: `/` or `Ctrl K` search · `L` / `D` love/pass focused title · `Enter` details · `Esc` close.
- ♿ Respects `prefers-reduced-motion`; responsive down to phone width; taste persists in `localStorage`.

## Project structure

```
backend/
  app.py              FastAPI app: /api/* + serves the frontend
  recommender.py      the hybrid engine (content + collaborative + MMR)
  discovery.py        S5B bounded retrieval of fresh candidates beyond the snapshot
  ranking.py          S5C ranking contract, budgets, rollback switch, sparse feature cache
  release.py          S6 candidate version, public provider config and frame policy
  data/movies.json    60-film catalogue (genres, tags, overview, palette, poster)
frontend/
  index.html          page shell (nav, billboard, rows, drawer, modal)
  styles.css          Netflix-style design system + animations
  app.js              state, API calls, rows, billboard, previews, modal
  engine.js           in-browser port of the recommender (GitHub Pages)
  provider-registry.json  fixed movie providers, origins and iframe permissions
  playback-config.js  generated static policy; FastAPI serves runtime policy at this path
  posters/            cached poster images (<id>.jpg)
scripts/
  fetch_posters.py    downloads posters from Wikipedia (re-run to refresh)
  build_tmdb_catalog.py  builds the real-world catalogue from the TMDB API
  export_static.py    exports the trained model to JSON for engine.js
  benchmark_ranking.py  S5C offline benchmark: per-request work vs a growing feature cache
  record_dynamic_fixture.py  S5D: records real TMDB discovery pools (needs keys)
  evaluate_dynamic.py   S5D offline evaluation: world proxy, live replay, review sheet
  browser_walkthrough.py  S5D headless-Edge walkthrough of the real UI with timings
  check_release_browser.cjs  S6 isolated desktop/mobile player and rollback checks
.github/workflows/
  pages.yml           test + export + deploy to GitHub Pages
  checks.yml          branch/PR tests, static export and candidate artifact (no deployment)
tests/                engine + API tests (pytest)
docs/                 architecture, algorithm, iteration plan
run.py                one-command launcher
CHANGELOG.md
```

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | liveness check |
| `GET` | `/api/deployment` | public release and validated Render commit SHA, or null locally; no environment/secret dump |
| `GET` | `/api/playback` | public release/provider configuration; no keys |
| `GET` | `/api/movies` | full catalogue |
| `GET` | `/api/capabilities` | live-search configuration and snapshot origin; no credentials returned |
| `GET` | `/api/search?q=...&page=1&language=en-US` | paginated TMDB discovery; pages 1–500 |
| `GET` | `/api/movies/{id}?language=en-US` | canonical TMDB details, cache status and `in_model` membership |
| `POST` | `/api/recommend` | body `{liked: int[], disliked: int[], mood?: string, k?: 1-100}` → `{mode, items[], taste}` |
| `GET` | `/api/movies/{id}/similar?k=6` | most similar movies |
| `GET` | `/api/meta` | dataset & model stats (used by "How it works") |

Interactive API docs are at `http://127.0.0.1:8000/docs`.

## Documentation

- [Dynamic recommendation iterations (S5A-S5D)](docs/streaming/README.md#dynamic-recommendation-upgrade): S5A external likes/dislikes implemented; fresh candidates, scalable ranking and evaluation planned before S6/S7
- [Render deployment iteration (S7)](docs/streaming/07-render-deployment.md): planned full-project hosting, environment settings, public acceptance checks and rollback; deployment has not been performed yet
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): system design and request flow
- [docs/ALGORITHM.md](docs/ALGORITHM.md): the maths behind the recommendations
- [docs/ITERATIONS.md](docs/ITERATIONS.md): roadmap, iteration by iteration
- [docs/streaming/README.md](docs/streaming/README.md): phased movie playback upgrade with manual source selection
- [docs/STREAMING_PROVIDERS.md](docs/STREAMING_PROVIDERS.md): provider research and verification status
- [CHANGELOG.md](CHANGELOG.md): what changed in each version

## A note on the data

The catalogue is 60 hand-curated films. Posters come from Wikipedia and are used for this educational project. Run `python scripts/fetch_posters.py --force` to re-download them. The ratings matrix behind collaborative filtering is **simulated** (600 synthetic users with Dirichlet-distributed genre tastes, seeded for reproducibility), because real rating data isn't bundled. Swapping in MovieLens is planned for Iteration 2, see [docs/ITERATIONS.md](docs/ITERATIONS.md).
