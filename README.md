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

Run the tests:

```bash
python -m pytest -q
```

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
| `POST` | `/api/recommend` | body `{liked: int[], disliked: int[], mood?: string, k?: 1-100}` → `{mode, items[], taste}` |
| `GET` | `/api/movies/{id}/similar?k=6` | most similar movies |
| `GET` | `/api/meta` | dataset & model stats (used by "How it works") |

Interactive API docs are at `http://127.0.0.1:8000/docs`.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): system design and request flow
- [docs/ALGORITHM.md](docs/ALGORITHM.md): the maths behind the recommendations
- [docs/ITERATIONS.md](docs/ITERATIONS.md): roadmap, iteration by iteration
- [CHANGELOG.md](CHANGELOG.md): what changed in each version

## A note on the data

The catalogue is 60 hand-curated films. Posters come from Wikipedia and are used for this educational project. Run `python scripts/fetch_posters.py --force` to re-download them. The ratings matrix behind collaborative filtering is **simulated** (600 synthetic users with Dirichlet-distributed genre tastes, seeded for reproducibility), because real rating data isn't bundled. Swapping in MovieLens is planned for Iteration 2, see [docs/ITERATIONS.md](docs/ITERATIONS.md).
