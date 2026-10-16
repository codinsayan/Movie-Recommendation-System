# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased] (branch `feature/tmdb`, Iteration 3: real-world data)

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
