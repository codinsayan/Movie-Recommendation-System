# S5: Recommendations informed by viewing

Status: implemented as an opt-in experiment; automated contracts/parity and reproducible proxy evaluation pass. One informal user relevance review is recorded; broader relevance review and rendered-browser acceptance remain pending. Depends on [S3](03-progress-and-watchlist.md) and [S4](04-search-and-catalogue.md). Next: [S6](06-release.md). Evidence: [evaluation](../EVALUATION.md).

## Outcome

My Taste offers **Use viewing history** and **Top picks: played recently on this device**. Explicit ranking remains the default. FastAPI and the static engine support the same signal contract and scoring policy. No model-size increase was made.

## Work

- [x] Versioned contract: `viewing: {version: 1, signals, playback}`, `use_viewing`, `recent_playback_only`, optional canonical `eligible_keys`. API/browser validation bounds payload sizes and numeric values.
- [x] Measure short forward playing intervals against wall time; merge overlaps and reject seeks, paused/background gaps, source changes, errors and Play-only events as preference evidence.
- [x] Qualify after both two minutes and 30% unique coverage. Count repeated substantial sessions with capped strength; completion remains separate.
- [x] Retain the original blend at 90% and cap viewing at 10%, only when opted in. Dislikes override conflicting positives; Taste DNA reflects explicit taste.
- [x] Resolve canonical IDs within the active model. Remote unindexed titles stay history-only without fabricated scores.
- [x] Add bounded snapshot refresh: at most 500 requested IDs, with optional prioritized remote IDs. Retain sparse exports and the 60/447-film models.
- [x] Add ?Because you watched? beside ?Because you loved,? with honest billboard/detail explanations and a viewing score component.
- [x] Offer device-local recent-playback filtering: seven-day freshness, ten measured playing seconds, provider-specific failure invalidation, and explicit unknown/empty states.
- [x] Filter eligibility before normalization, candidate-pool truncation, MMR and top-k. Search/general browsing remain independent.
- [x] Keep Python/JavaScript in parity on curated and TMDB graph catalogues.
- [x] Reproducibly compare popularity, explicit hybrid and hybrid plus viewing; label synthetic ratings/viewing and graph overlap in [EVALUATION.md](../EVALUATION.md).
- [x] Collect one informal user relevance review: broadly relevant, with Tenet missing from their displayed picks; scope and discrepancy are recorded in the evaluation.
- [ ] Complete broader relevance review and rendered-browser acceptance before default activation. The feature remains opt-in.
- [ ] Before raising the 500-film refresh budget, implement sparse candidate retrieval and measure memory, latency and real browser responsiveness on the larger catalogue. This phase does not raise that budget.

## Acceptance evidence

The full suite passes **97 tests**, including 26 JavaScript playback/preferences cases. Live API smoke checks and static export pass; no rendered browser is attached.

- [x] Signals, scores, explanations, taste and watched rows agree between Python and JavaScript for both datasets.
- [x] Dislikes, errors, completion, unknown IDs, duplicate signals and stale callbacks are handled independently in focused tests.
- [x] Eligibility fills top-k where enough candidates exist; expired/future/failed-only evidence cannot qualify.
- [x] Legacy resume positions acquire no evidence. Storage denial retains session state; history clearing cannot resurrect active-player evidence and preserves explicit taste/watchlists.
- [x] Evaluation records input/profile hashes, seed, metrics, timing and model sizes. HR@10 is unchanged; small NDCG changes do not establish real-user improvement.
- [ ] Browser verification: opt in, watch substantially, inspect the row, refresh, toggle the recent filter, clear history and confirm search remains available.

## Bounded refresh

To intentionally index a discovered ID, rebuild explicitly using the existing TMDB credential:

```bash
python scripts/build_tmdb_catalog.py --max-movies 500 --include-tmdb-id 45745
python scripts/export_static.py
```

Review the snapshot, re-run tests/evaluation and restart FastAPI. Metadata/quality checks still apply; requested IDs may be skipped. No automatic indexing or account synchronization is added. No snapshot refresh was run during S5.

## Demo

Enable viewing history in My Taste. Watch at least two minutes and 30% of a film, close playback and inspect ?Because you watched.? Compare an explicit like and an error-only session. Toggle recent playback, then clear viewing history while retaining taste and Watchlist.
