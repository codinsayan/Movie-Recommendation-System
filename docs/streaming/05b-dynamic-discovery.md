# S5B: Dynamic recommendation candidates

Status: planned. Depends on [S5A external preferences](05a-dynamic-preferences.md). Next: [S5C scalable ranking](05c-scalable-ranking.md).

## Outcome

Recommendations can include newly discovered movies outside the original 447-film snapshot. The snapshot becomes a starter/fallback pool rather than a permanent boundary. TMDB retrieves possible candidates; the project's own engine determines their personalized order.

## Work

- [ ] Add cached backend adapters for TMDB movie recommendations and discovery, using fixed upstream endpoints and validated IDs/parameters. Reuse existing timeout, rate-limit, sanitized-error and stale-cache behavior.
- [ ] Gather candidates from several positive preference seeds, preference-informed discovery, relevant new releases, cached titles and the starter snapshot. Do not rely exclusively on the latest like or on popularity.
- [ ] Handle dislike-only and cold-start profiles explicitly: generate a broad starter pool, apply negative preferences, and label the result appropriately.
- [ ] Define source quotas, seed selection, pagination limits, concurrency limits and an initial bounded request pool, tentatively 200-500 unique movies. Verify these budgets during S5D; they are not a cap on the total discoverable catalogue.
- [ ] Deduplicate by canonical identity and exclude explicit likes/dislikes before final selection. Preserve title, original language, metadata language and feature provenance.
- [ ] Refresh new-release discovery on a documented TTL and invalidate changed metadata/features by version. A new release need not wait for a committed snapshot rebuild.
- [ ] Reuse S5A feature normalization for remote candidates. Bound detail enrichment and label incomplete metadata instead of assigning fictional scores or pretending a search summary contains all features.
- [ ] Rank the candidate pool using the current content/related-title/quality signals and the resolved positive/negative profile. Treat TMDB related-title results as an external recommendation signal, not a new user-ratings dataset.
- [ ] Apply supported eligibility rules before the ranking pool is truncated. Unknown streaming availability remains unknown; a recommendation result is not proof of playable video.
- [ ] Integrate dynamic cards with details, Watchlist, playback, taste controls and saved metadata. Make an explicit preference for a newly recommended movie usable through S5A.
- [ ] Abort or reject superseded preference/mood/discovery responses so an older pool cannot overwrite the current banner or rows.
- [ ] Preserve usable cached/snapshot results during upstream failures. Record partial retrieval and stale data honestly; no request should depend on every external source succeeding.
- [ ] Keep live retrieval backend-only. Static mode uses the exported/cached subset and clearly documents its narrower freshness and discovery capabilities.

## Expected files

`backend/catalog.py` or a dedicated retrieval module, `backend/app.py`, `backend/recommender.py`, `frontend/catalogue.js`, `frontend/app.js`, identity/cache/retrieval tests and architecture documentation.

## Acceptance

- [ ] A deterministic TMDB fixture absent from the original catalogue appears as a recommendation, opens details and can be liked/disliked without retraining the snapshot.
- [ ] A newly released fixture becomes eligible after discovery refresh; duplicate pages and overlapping retrieval sources do not duplicate cards.
- [ ] Exact disliked IDs remain excluded across every retrieval source. Similarity penalties do not masquerade as categorical genre bans.
- [ ] Candidate count, upstream calls and concurrency stay within configured budgets even with many saved preferences or many result pages.
- [ ] Missing credentials, empty recommendation endpoints, rate limits, stale cache and partial failures preserve usable fallback results and truthful explanations.
- [ ] Dynamic cards preserve canonical identity and browser-local persistence across refresh. Static mode does not advertise a fresh live pool.

## Sources and demo

Interfaces to verify during implementation: [TMDB recommendations](https://developer.themoviedb.org/reference/movie-recommendations), [discovery](https://developer.themoviedb.org/reference/discover-movie), [details](https://developer.themoviedb.org/reference/movie-details).

Like an external film, retrieve a fresh pool containing another external film, dislike one suggestion, and refresh. Demonstrate bounded retrieval and an upstream-failure fallback. Record retrieval provenance and request counts; live network checks stay separate from deterministic CI.

Commit this iteration as `codinsayan` only, with no co-author trailers.
