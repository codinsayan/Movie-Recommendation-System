# S5C: Scalable profiles and bounded ranking

Status: planned. Depends on [S5A](05a-dynamic-preferences.md) and [S5B](05b-dynamic-discovery.md). Next: [S5D evaluation](05d-dynamic-evaluation.md).

## Outcome

The engine can process an evolving catalogue by encoding new movie metadata and scoring a bounded candidate pool. It no longer needs to append each discovered movie to global dense movie-to-movie matrices or retrain the entire model on every preference change.

## Work

- [ ] Separate candidate retrieval, feature encoding, positive/negative profile construction, scoring and diversity reranking behind explicit versioned contracts.
- [ ] Cache sparse movie representations by canonical ID, metadata version/language and encoder version. A cache miss triggers bounded feature work, not a full-catalogue rebuild.
- [ ] Score the retrieved candidates against the user's positive/negative profile with sparse operations. Maintain supported quality and related-title evidence; normalize weights over available signals without manufacturing collaborative scores for new films.
- [ ] Keep explicit likes/dislikes authoritative. Extend optional S5 measured-viewing signals to resolved external movies using the same canonical representation, preserving their weaker capped influence and the independence of errors/completion.
- [ ] Apply exact exclusions and supported playback-evidence constraints before top-pool selection. Compute MMR similarities only over the bounded reranking pool instead of allocating global N-by-N arrays for all discovered titles.
- [ ] Define and measure budgets for retrieval size, active feature batches, reranking size, cache entries/bytes and request time. A growing cache/catalogue must not silently enlarge the work of each recommendation request.
- [ ] Bound preference-resolution work while preserving a path to apply all saved preferences: reuse cached aggregate/profile information and process pending metadata incrementally. Do not make every click refetch the entire preference history.
- [ ] Specify feature-cache eviction and rebuild behavior. Keep preference IDs and browser state independent of derived-cache eviction; newly missing features become pending and can be rehydrated.
- [ ] Preserve stateless per-device requests and local preference storage unless separately scoped otherwise. A derived movie-feature cache is not a server-side user-account database.
- [ ] Support disposable cache storage for the planned Render demo. Test cold-cache recovery; persistent caching can be selected in S7 without changing canonical identities or the scoring contract.
- [ ] Re-encode incompatible cached features on encoder-version changes. Never mix incompatible vocabularies or embedding dimensions in one profile or compare scores across incompatible feature spaces.
- [ ] Keep a versioned snapshot/static fallback and a practical ranking rollback path. Document exactly which cached external inputs the browser engine can support; live retrieval remains a backend capability.
- [ ] Preserve honest explanations for dynamic sources and score components, including missing-metadata or low-overlap cases. No unrelated film should receive a fabricated "Because you loved" source.

## Expected files

`backend/recommender.py`, feature/retrieval/profile modules as appropriate, `backend/catalog.py`, `backend/app.py`, `scripts/export_static.py`, `frontend/engine.js`, `frontend/preferences.js`, `frontend/viewing.js`, `frontend/app.js`, parity/performance tests and architecture notes.

## Acceptance

- [ ] Adding a candidate or explicit preference requires incremental metadata/feature work and does not allocate or rebuild a global all-discovered-movies similarity matrix.
- [ ] Benchmark a growing cached catalogue with a fixed candidate budget. Record retained memory, cold/warm latency, cache size and request counts; establish limits before raising production budgets.
- [ ] A sufficiently large eligible pool can fill top-k; duplicate IDs, unsupported features and explicit exclusions cannot create misleading cards or inconsistent counts.
- [ ] New explicit and weaker viewing signals stay independent. No-metadata, zero-vector, cache-eviction and all-dislike profiles have documented fallback behavior.
- [ ] Offline/static supported inputs remain deterministic and in Python/JavaScript parity. Unsupported live capability is described rather than imitated with stale data.
- [ ] Reset/removal and schema migration preserve browser-local taste, Watchlist and unrelated viewing history according to their separate controls.

## Demo

Use external likes/dislikes to score a fresh bounded pool, add another newly discovered title, and demonstrate that only its features need resolution. Repeat with a warm cache, an empty cache and an expired feature version; record resource measurements without claiming those tests prove unlimited scale.

Commit this iteration as `codinsayan` only, with no co-author trailers.
