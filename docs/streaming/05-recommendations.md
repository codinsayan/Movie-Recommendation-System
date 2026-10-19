# S5: Recommendations informed by viewing

Status: planned. Depends on [S3](03-progress-and-watchlist.md) and [S4](04-search-and-catalogue.md). Next: [S6](06-release.md).

## Outcome

The existing hybrid engine recommends movies using explicit taste plus carefully evaluated viewing signals, with honest explanations and optional playback eligibility filtering.

## Work

- [ ] Define a versioned viewing-signal contract shared by API requests and the browser engine. Explicit likes/dislikes remain strongest initially.
- [ ] Treat actual watched duration and repeated viewing as candidate weak signals. Do not use source errors, provider changes or a Play click as movie-preference evidence.
- [ ] Resolve viewed external titles through canonical IDs; titles outside the current model remain history-only until indexed through a bounded refresh process.
- [ ] Keep a bounded active model for the first release. New metadata records do not automatically enlarge all pairwise matrices.
- [ ] Before substantially increasing the active model, retain sparse features/graph neighbours and retrieve a bounded candidate pool, then apply the existing blend, MMR and explanations.
- [ ] Add **Because you watched** while preserving **Because you loved**. Explain the actual signal behind each row.
- [ ] Offer an optional **Verified playback recently** filter only for titles with recorded successful playback evidence and a visible freshness policy. Unknown status remains unknown; a working URL is not sufficient evidence.
- [ ] Apply supported eligibility constraints before final top-k selection and MMR; do not truncate first and return an accidentally empty list.
- [ ] Update Python and browser implementations together where capability overlaps. Document backend-only behavior rather than claiming full parity for unavailable static data.
- [ ] Compare the current engine with the proposed signal blend using a reproducible evaluation protocol and a small human relevance review before shipping new weights.

## Expected files

`backend/recommender.py`, `backend/app.py`, `frontend/engine.js`, `frontend/viewing.js`, `scripts/export_static.py`, `frontend/app.js`, focused parity/ranking tests and `docs/EVALUATION.md`.

## Acceptance

- [ ] Identical supported signals/configurations produce equivalent Python and JavaScript results.
- [ ] Explicit dislikes, completion behavior and source failures are handled independently.
- [ ] The candidate filter can fill top-k where enough eligible candidates exist; explanation text matches the underlying signal.
- [ ] A remote unindexed title does not crash ranking or acquire a fabricated similarity score.
- [ ] The evaluation records dataset provenance, baselines, metrics and limitations. Synthetic ratings and TMDB graph signals are labeled accurately.
- [ ] Larger-catalogue measurements include memory, candidate latency and browser responsiveness before any model-size increase.

## Demo

Show the difference between a film liked explicitly, one watched substantially and one abandoned because of a source error. Demonstrate the corresponding recommendation rows without treating playback problems as dislikes.
