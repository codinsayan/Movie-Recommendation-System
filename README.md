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

This is a local implementation preview. The offline player tests pass, and the user has confirmed the sources work with standard cross-origin iframes without the sandbox attribute. Autoplay and the updated source menu still need live browser verification. See [playback validation](docs/streaming/PLAYBACK_VALIDATION.md) for evidence and remaining checks. S4 adds broader live metadata search; S5 adds optional viewing-aware recommendations.

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

Explicit taste retains 90% of the score when this option has qualified signals; viewing contributes at most 10%. Substantial repeat sessions have a capped influence. Likes/dislikes and Taste DNA remain explicit. Viewing outside the trained snapshot stays history-only until a deliberate bounded rebuild indexes that title.

**Top picks: played recently on this device** optionally filters picks using ten measured playing seconds within seven days. Later source errors invalidate that source's record. This is local evidence, not guaranteed availability; ordinary search and browsing remain available when the filter is empty. **Clear viewing history** removes progress and viewing/playback evidence while keeping likes, mood and Watchlist. Both options persist in this browser and work in FastAPI and static mode.

The new blend is opt-in: a small reproducible proxy evaluation found unchanged hit rate and slight NDCG differences, which do not establish real-user improvement. One informal review was broadly positive; broader relevance and rendered-browser acceptance remain pending. See [S5 implementation](docs/streaming/05-recommendations.md) and [evaluation](docs/EVALUATION.md).

## Real-world catalogue (TMDB)

### Live movie search (S4)

The backend app can search beyond the committed snapshot using the same TMDB credential in `.env`. Type a title, wait for results, and choose **Load more** for another page. The **Details language** selector changes metadata; it does not select playback audio. Pressing Enter still searches the recommendation model by mood.

Remote results support details, the movie player and Watchlist. Selected metadata is saved locally so bookmarked movies remain visible after refresh. Titles outside the trained model have no personalized match score or local similar-film recommendations yet; discovery does not enlarge the model.

SQLite caches searches for one hour and details for one day, with stale fallback during upstream failures. The cache is bounded to 5,000 entries and git-ignored. Set `CINEMAGIC_CACHE_PATH` to change its location. Missing credentials or upstream failures leave snapshot browsing available.

GitHub Pages and curated mode retain snapshot/saved-title search. Live search requires FastAPI with the TMDB dataset; curated IDs remain isolated from TMDB IDs.

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

GitHub Pages serves static files only, so the Pages build runs the recommender **in the browser**:

1. `scripts/export_static.py` exports the trained model (TF-IDF vectors, similarity matrices, vocabulary, config) to `frontend/data/model.json` (about 180 KB).
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
  data/movies.json    60-film catalogue (genres, tags, overview, palette, poster)
frontend/
  index.html          page shell (nav, billboard, rows, drawer, modal)
  styles.css          Netflix-style design system + animations
  app.js              state, API calls, rows, billboard, previews, modal
  engine.js           in-browser port of the recommender (GitHub Pages)
  posters/            cached poster images (<id>.jpg)
scripts/
  fetch_posters.py    downloads posters from Wikipedia (re-run to refresh)
  build_tmdb_catalog.py  builds the real-world catalogue from the TMDB API
  export_static.py    exports the trained model to JSON for engine.js
.github/workflows/
  pages.yml           test + export + deploy to GitHub Pages
tests/                engine + API tests (pytest)
docs/                 architecture, algorithm, iteration plan
run.py                one-command launcher
CHANGELOG.md
```

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | liveness check |
| `GET` | `/api/movies` | full catalogue |
| `GET` | `/api/capabilities` | live-search configuration and snapshot origin; no credentials returned |
| `GET` | `/api/search?q=...&page=1&language=en-US` | paginated TMDB discovery; pages 1–500 |
| `GET` | `/api/movies/{id}?language=en-US` | canonical TMDB details, cache status and `in_model` membership |
| `POST` | `/api/recommend` | body `{liked: int[], disliked: int[], mood?: string, k?: 1-100}` → `{mode, items[], taste}` |
| `GET` | `/api/movies/{id}/similar?k=6` | most similar movies |
| `GET` | `/api/meta` | dataset & model stats (used by "How it works") |

Interactive API docs are at `http://127.0.0.1:8000/docs`.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): system design and request flow
- [docs/ALGORITHM.md](docs/ALGORITHM.md): the maths behind the recommendations
- [docs/ITERATIONS.md](docs/ITERATIONS.md): roadmap, iteration by iteration
- [docs/streaming/README.md](docs/streaming/README.md): phased movie playback upgrade with manual source selection
- [docs/STREAMING_PROVIDERS.md](docs/STREAMING_PROVIDERS.md): provider research and verification status
- [CHANGELOG.md](CHANGELOG.md): what changed in each version

## A note on the data

The catalogue is 60 hand-curated films. Posters come from Wikipedia and are used for this educational project. Run `python scripts/fetch_posters.py --force` to re-download them. The ratings matrix behind collaborative filtering is **simulated** (600 synthetic users with Dirichlet-distributed genre tastes, seeded for reproducibility), because real rating data isn't bundled. Swapping in MovieLens is planned for Iteration 2, see [docs/ITERATIONS.md](docs/ITERATIONS.md).
