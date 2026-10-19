# Iteration plan

Each iteration ships something demoable. Status: ✅ done · 🔄 in progress · ⏳ planned.

## Streaming upgrade: active implementation roadmap

The product work follows [the streaming roadmap](streaming/README.md), with **viewer-controlled manual source switching**. CineSrc is the default, with VidLink and VidSrc available for manual selection. Per the latest user request, movie players use standard cross-origin iframes without the sandbox attribute. S1-S4 code is available as a local preview; live playback/browser acceptance remains pending. See [validation evidence](streaming/PLAYBACK_VALIDATION.md).

| Phase | Planned result |
|---|---|
| [S1](streaming/01-source-foundation.md) | Source adapters, canonical movie IDs and playback validation |
| [S2](streaming/02-player-and-manual-switching.md) | Movie player with a visible manual Source selector |
| [S3](streaming/03-progress-and-watchlist.md) | Resume, Continue watching and an independent watchlist |
| [S4](streaming/04-search-and-catalogue.md) | Implemented: paginated live search and cached remote details; API/client checks passed |
| [S5](streaming/05-recommendations.md) | Viewing-aware recommendations and evaluated ranking changes |
| [S6](streaming/06-release.md) | Deployment and end-to-end release evidence |

S1-S2 form the first demo milestone. The evaluation/model/polish iterations below retain their original numbering and remain future work; relevant tasks are incorporated into S5/S6 without implying those older iterations are complete.

---

## Iteration 1: Working hybrid recommender with a magical UI ✅ (v0.1.0)

**Goal:** an end-to-end app you can demo in class today.

- [x] Curated 60-film catalogue with genres, mood tags, overviews, colour palettes
- [x] Content-based filtering (TF-IDF + cosine)
- [x] Item-item collaborative filtering on a simulated ratings matrix
- [x] Hybrid blending with cold-start / mood / personal modes
- [x] MMR diversity re-ranking
- [x] Natural-language mood search with synonym expansion
- [x] Explanations: "Because you loved…", shared traits, score breakdown
- [x] FastAPI backend serving API + frontend; one-command launcher
- [x] UI: aurora background, 3D-tilt cards, match rings, particle bursts, View Transitions, Taste DNA, modal with "More like this", toasts, keyboard shortcuts, reduced-motion support, responsive
- [x] 15 automated tests (engine + API)
- [x] Docs: README, architecture, algorithm, this plan, changelog

**Demo script:** open the app → click *Mind-bending* → love Inception, Interstellar, Arrival → watch Taste DNA unlock → open a pick and show "Why this pick?" → open *How it works*.

---

## Iteration 2: Netflix-style redesign + real posters ✅ (v0.2.0)

**Goal:** instant recognition. Users should know every film at a glance, in a layout they already know how to use.

- [x] Real posters for all 60 films via the Wikipedia REST API, cached locally (`scripts/fetch_posters.py`)
- [x] Auto-rotating billboard hero built from your top 5 picks
- [x] Horizontal rows: Top Picks, My List, Because you loved X, Top 10, taste-ordered genre rows
- [x] Hover preview cards, match / love / new-pick badges
- [x] Detail modal with "More Like This"; My Taste drawer
- [x] Nav search: live title filter + Enter for mood search
- [x] Poster fallback, row scroll preservation, tests for poster coverage

**Demo script:** open the app → hover a poster and tap ♥ on 3 sci-fi films → watch the billboard, "NEW PICK" badges and "Because you loved…" rows update → open 🧬 My Taste → search "make me cry" + Enter.

## Iteration 3: Real-world data with TMDB ✅ (v0.3.0)

**Goal:** credibility. Real films, real audience signal, real trailers.

- [x] TMDB catalogue builder (most-voted + popular, keywords, cast, director, backdrops, trailers)
- [x] Collaborative filtering from TMDB's recommendation graph (replaces simulated ratings)
- [x] Vote-weighted quality prior; director/cast as content features
- [x] UI: backdrops, Play Trailer, cast/director/runtime, TMDB attribution
- [x] Offline tests + JS parity for the graph engine; sparse static model
- [x] Build the snapshot with a real key (447 films) and review recommendation quality
- [x] Mood search tuned for TMDB keywords; substring-matching bug fixed
- [ ] Tune MMR for mood searches (diversity occasionally pulls in loose matches)
- [ ] Optional: live TMDB search to love films outside the snapshot
- [ ] Optional: MovieLens ratings as a second collaborative signal
- [x] Merge to `main` and redeploy GitHub Pages

## Iteration 4: Measure it ⏳ (v0.4.0)

**Goal:** prove which approach is best, the core of the project report.

- [ ] `evaluate.py`: leave-one-out Hit-Rate@10, NDCG@10, coverage, diversity
- [ ] Compare content-only vs CF-only vs hybrid vs hybrid+MMR; tune weights and λ
- [ ] Results table + charts in `docs/EVALUATION.md`
- [ ] "Lab" panel in the UI: sliders for weights and λ, re-ranking live

## Iteration 5: Smarter models ⏳ (v0.5.0)

- [ ] Matrix factorisation (truncated SVD / ALS) as a third signal
- [ ] Sentence-embedding mood search (e.g. `all-MiniLM-L6-v2`) instead of synonym expansion
- [ ] Implicit feedback: dwell time on a card or opening details counts as a weak like

## Iteration 6: Product polish ⏳ (v1.0.0)

- [ ] User accounts + server-side profiles (SQLite)
- [ ] Shareable "Taste DNA" card (PNG export)
- [ ] Watchlist, "seen it" state
- [ ] Deploy (Render / Railway) with a public demo URL
- [ ] Lighthouse ≥ 95 for accessibility and performance

---

## Backlog / ideas

- Group mode: blend two people's tastes for movie night
- "Surprise me" serendipity slider
- Light theme
