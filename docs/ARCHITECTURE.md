# Architecture

## S4 discovery alongside the recommendation snapshot

The model still owns a bounded catalogue. `backend/catalog.py` performs live TMDB title search and detail lookup separately; `frontend/catalogue.js` holds discovered metadata without adding it to the model's similarity matrices.

`/api/capabilities` advertises live search without exposing credentials. `/api/search` accepts a bounded title query, page 1–500 and metadata language. `/api/movies/{id}` uses canonical TMDB movie IDs and reports `in_model`. The pre-existing similar/recommend routes continue to use the active model catalogue.

Runtime metadata is cached in git-ignored SQLite storage with schema version 1, refresh timestamps and a 5,000-entry bound. Search TTL is one hour; detail TTL is one day. Existing stale entries can be used during timeouts, rate limits or upstream failures. Errors are sanitized rather than including authenticated request URLs.

The browser debounces and aborts title searches, rejects late responses by sequence, and merges paginated results by TMDB ID. Opening remote details uses a modal generation guard, so an older request cannot replace a newer movie or player. Selected metadata is saved in browser storage for remote Watchlist/Continue Watching cards after reload.

Discovery metadata includes original title/language and, for full details, alternative titles. Metadata language does not select playback audio. TMDB documents [title search](https://developer.themoviedb.org/reference/search-movie) and [movie details](https://developer.themoviedb.org/reference/movie-details).

Remote titles have no fabricated personalized score or local similar-title result before they are indexed. Their explicit likes can be saved, but the current model ignores unknown IDs; recent-like similarity requests are restricted to indexed IDs. Static/curated builds retain snapshot/saved-title search and do not route new discovery endpoints through the static engine.

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
| **Precompute similarity matrices at start-up** | 60×60 matrices are tiny; every request is a few vector ops (< 5 ms). |
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
