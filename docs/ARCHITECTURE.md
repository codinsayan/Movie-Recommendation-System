# Architecture

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
