# S5C: Scalable profiles and bounded ranking

Status: code implemented on `feature/streaming-platform`. Deterministic tests, the offline benchmark and live API checks passed. The rendered browser walkthrough and the S5D relevance/budget evaluation remain pending. Depends on [S5A](05a-dynamic-preferences.md) and [S5B](05b-dynamic-discovery.md). Next: [S5D evaluation](05d-dynamic-evaluation.md).

## Outcome

The engine can work with an evolving catalogue. It encodes new movie metadata and scores a bounded candidate pool. Discovered movies are never appended to global dense movie-to-movie matrices, and no preference change retrains the model.

## Work

- [x] Separate candidate retrieval, feature encoding, positive/negative profile construction, scoring and diversity reranking behind explicit versioned contracts.
- [x] Cache sparse movie representations by canonical ID, metadata version/language and encoder version. A cache miss triggers bounded feature work, not a full-catalogue rebuild.
- [x] Score the retrieved candidates against the user's positive/negative profile with sparse operations. Keep supported quality and related-title evidence. Normalize weights over available signals without manufacturing collaborative scores for new films.
- [x] Keep explicit likes/dislikes authoritative. Extend optional S5 measured-viewing signals to resolved external movies with the same canonical representation, preserving their weaker capped influence and the independence of errors/completion.
- [x] Apply exact exclusions and supported playback-evidence constraints before top-pool selection. Compute MMR similarities only over the bounded reranking pool instead of allocating global N-by-N arrays for all discovered titles.
- [x] Define and measure budgets for retrieval size, active feature batches, reranking size, cache entries/bytes and request time. A growing cache/catalogue must not silently enlarge the work of each recommendation request.
- [x] Bound preference-resolution work while preserving a path to apply all saved preferences. Reuse cached aggregate/profile information and process pending metadata incrementally. Do not make every click refetch the entire preference history.
- [x] Specify feature-cache eviction and rebuild behavior. Keep preference IDs and browser state independent of derived-cache eviction. Newly missing features become pending and can be rehydrated.
- [x] Preserve stateless per-device requests and local preference storage unless separately scoped otherwise. A derived movie-feature cache is not a server-side user-account database.
- [x] Support disposable cache storage for the planned Render demo. Test cold-cache recovery. Persistent caching can be selected in S7 without changing canonical identities or the scoring contract.
- [x] Re-encode incompatible cached features on encoder-version changes. Never mix incompatible vocabularies or embedding dimensions in one profile, and never compare scores across incompatible feature spaces.
- [x] Keep a versioned snapshot/static fallback and a practical ranking rollback path. Document exactly which cached external inputs the browser engine can support. Live retrieval remains a backend capability.
- [x] Preserve honest explanations for dynamic sources and score components, including missing-metadata or low-overlap cases. No unrelated film should receive a fabricated "Because you loved" source.

## Design

### Stages and contracts

The ranking contract is `rank-v2`. It is reported by `/api/capabilities` and in every `/api/recommend` response under `ranking.contract`. Each stage works within the engine's `feature_version`.

| Stage | Where | Input → output |
|---|---|---|
| Retrieval | `discovery.Discovery.candidates` | likes/dislikes/external profile → at most 300 unique candidates and a report |
| Encoding | `ranking.FeatureStore.encode` | candidate metadata → L2-normalised sparse CSR rows in the fitted vocabulary |
| Profile | `Recommender.recommend` | snapshot rows, the S5A external aggregate and mood → one dense vocabulary-length vector |
| Scoring | `Recommender.recommend` | sparse candidate rows · profile, plus related-title evidence, quality and viewing |
| Reranking | `Recommender._mmr` / `_mmr_union` | top `min(3k, 300)` eligible rows → MMR selection of k |

### Feature cache (`backend/ranking.py`)

- **Key:** `(canonical key, metadata language, feature_version)`. Each entry stores a SHA-256 digest of the feature document it was built from. If the digest differs (for example, when a summary is upgraded to full details), the entry is re-encoded instead of reused.
- **Contents:** int32 indices and float64 values only, plus a 256-byte overhead estimate per entry.
- **Bounds:** LRU, capped at **4,000 entries** and **16 MiB**, whichever is reached first.
- **Misses:** encoded in batches of **64** with `vectorizer.transform`. There is no refit and no vocabulary growth.
- **Version changes:** `bind(engine)` drops every vector from another `feature_version`, so incompatible spaces are never mixed or compared.
- **Eviction:** only costs a re-encode from metadata the next time the film appears. Preference IDs, Watchlist and viewing history live in the browser and never depend on this cache.
- **Scope:** the store is shared by discovery and external-viewing encoding. It's in-memory and disposable, and it is not a user database: requests stay stateless per device.

### Scoring

- Discovered rows stay **sparse** end to end. `content = E · profile` is a sparse-dense product.
- MMR builds its pairwise matrix from sparse rows of the bounded pool only. That's at most 300 × 300, and never N × N or pool × vocabulary.
- Redundancy is updated incrementally. Checks against the previous implementation gave identical selections in 30 randomised trials.
- Snapshot pairs still use the exact `content_sim` values, so snapshot-only results are unchanged.
- Each discovered film reports `component_availability`. Collaborative evidence is `false` when TMDB lists it under none of your likes; it's reported as missing, never imputed. Content is `false` for a zero vector, and quality is `false` without votes. The detail panel hides unavailable components and states "no related-title evidence".
- Exclusions (likes, dislikes, measured-viewing titles, `eligible_keys`, the recent-playback filter, the mood relevance floor) are applied **before** the rerank pool is cut, so a large eligible pool can still fill top-k.

### Measured viewing of external films

- Watched TMDB titles outside the snapshot now count when **Use viewing history** is on.
- The backend reads their features from the metadata cache only, for at most **20** of the most recent titles. They're encoded through the feature store and applied with the same S5 contract: the same thresholds, at most 0.25 strength, and the whole implicit part capped at **10%**.
- They give content evidence only, because they have no collaborative row.
- An explicit like or dislike of the same film always wins.
- Uncached titles are reported as `viewing_status.pending` and queued for background detail fetches. They apply on a later refresh and never block a request.
- The Top Picks subtitle says how many watched films are waiting for metadata. The explanation is "Because you watched X" and includes the external key.

### Honest explanations

"Because you loved X" now needs at least **`EXPLAIN_FLOOR = 0.03`** of content + collaborative link to X; for external seeds and discovered films it needs that much content similarity.

Measured on the snapshot, genuine links sit at about 0.04 and above. Below the floor, a pick is there for quality or diversity. Before this change, for example, Toy Story → *The Godfather* (link 0.018, nothing shared) and Parasite → *The Shawshank Redemption* (0.007) were labelled "Because you loved".

Such picks now read **"A well-rated pick to widen your taste"**, and the detail panel shows that reason. TMDB related-title evidence (`evidence: "tmdb-related"`) is unaffected. The same floor is exported to the browser engine, so Python and JavaScript stay in parity.

### Budgets

| Budget | Value | Where |
|---|---|---|
| Retrieval pool | 300 candidates, 4 seeds, ≤ 6–9 source requests, 4 concurrent | `discovery.BUDGET` |
| Background enrichment | 12 per request, 2 workers | `discovery.BUDGET` |
| Encoding batch | 64 documents per vectorizer call | `RANKING_BUDGET["encode_batch"]` |
| Rerank pool | `min(3k, 300)` rows | `RANKING_BUDGET["rerank_pool"]` |
| External viewing | 20 most recent watched titles | `RANKING_BUDGET["external_viewing"]` |
| Feature cache | 4,000 entries / 16 MiB | `RANKING_BUDGET` |
| Metadata cache | 5,000 rows (SQLite, existing) | `Catalog._write` |

Every response includes `ranking` with:
- the contract and mode (`dynamic` or `snapshot`);
- the candidate and eligible counts;
- the rerank pool size;
- the number of viewing and external-viewing signals;
- feature-cache entries, bytes, hits, misses, re-encodes and evictions;
- timing in ms (`total` and `rank`).

The discovery report also gives `timing_ms.retrieve` and `timing_ms.encode`, plus per-request encoding counts.

### Cache storage, failures and rollback

- **Cache file:** `CINEMAGIC_CACHE_PATH` may point at disposable storage.
  - The SQLite schema is written once per process. If the file is deleted, it's recreated on the next access.
  - A locked or damaged file behaves as a cache miss, never a failed request.
  - A whole pool's cached details are read in **one** query (`Catalog.cached_movies`). Warm discovery previously opened about 120 connections and wrote the schema each time.
- **Rollback:** setting `CINEMAGIC_RANKING=snapshot` turns off live candidates and external-viewing features. `/api/capabilities` then reports `dynamic_discovery: false` and `ranking.mode: "snapshot"`, and results are exactly the snapshot ranking. No redeploy of the model is needed.
- **Static/browser engine:**
  - supports the snapshot, S5A external preferences from cached vectors (or complete cached English metadata), measured viewing of *snapshot* films, the recent-playback filter, the explanation floor and the rerank cap;
  - does **not** support live retrieval, discovered candidates or measured viewing of external films. It never sends `discover` and does not imitate them with stale data.

## Acceptance

- [x] Adding a candidate or explicit preference needs only incremental metadata/feature work, and no global all-discovered-movies similarity matrix is allocated or rebuilt. Shown by the test that engine matrix shapes stay unchanged with 300 discovered candidates, by the store reporting only new or changed rows encoded, and by the JS test where a third like fetches only its own features.
- [x] Benchmark a growing cached catalogue with a fixed candidate budget, recording retained memory, cold/warm latency, cache size and request counts (see Evidence).
- [x] A large enough eligible pool fills top-k. Duplicate IDs, unsupported features and explicit exclusions cannot create misleading cards or inconsistent counts. Shown by 100 unique picks from 447 + 300 candidates with likes/dislikes on both sides excluded.
- [x] New explicit and weaker viewing signals stay independent. No-metadata, zero-vector, cache-eviction and all-dislike profiles have documented fallbacks:

  | Case | Fallback |
  |---|---|
  | No metadata | pending, then rehydrated |
  | Zero-vector candidate | ranked on quality only; no reason or content component claimed |
  | Cache eviction | re-encoded from metadata |
  | All dislikes | personal mode, crowd-favourite reason, no "because" |
- [x] Offline/static supported inputs remain deterministic and in Python/JavaScript parity. Unsupported live capability is described rather than imitated with stale data.
- [x] Reset/removal and schema migration preserve browser-local taste, Watchlist and unrelated viewing history according to their separate controls. Shown by the existing S3/S5 tests plus a new JS case: corrupting the derived feature cache, or changing the feature version, leaves likes, the Watchlist and progress untouched.
- [x] Rendered desktop/mobile walkthrough and S5D relevance review, recorded in [S5D](05d-dynamic-evaluation.md). Human ratings are still pending there.

## Evidence (20 October 2026)

**Automated:** `python -m pytest -q` gives **135 passed**. That's 123 earlier tests plus 12 in `tests/test_ranking.py`:
- feature reuse, re-encode and transform equality;
- version isolation;
- entry and byte eviction with rehydration;
- a bounded rerank pool filling top-k without matrix growth;
- constant per-request work as the cache grows;
- the explanation floor;
- zero-vector and all-dislike fallbacks;
- external measured viewing (capped, explained, overridden by a dislike);
- a pending watched title rehydrating without blocking;
- cold disposable-cache recovery;
- snapshot rollback mode;
- a damaged or deleted cache file.

The JS resolver suite has 11 cases, adding the derived-cache independence and incremental-resolution case. The other JS suites pass.

**Benchmark:** `python scripts/benchmark_ranking.py` runs offline against a mock TMDB. It uses one profile (3 likes, k = 100, a 120-film discovery pool), takes the median of 3 runs, and measures peak memory with `tracemalloc` in a separate traced repeat:

| Cached feature entries | Cache after | Cold request | Warm request | Upstream calls (cold/warm) | Encoded (cold/warm) | Rerank pool | Peak memory per warm request |
|---|---|---|---|---|---|---|---|
| 0 | 360 entries, 0.2 MB | 275 ms | 52 ms | 6 / 0 | 120 / 0 | 300 | 2.15 MB |
| 1,000 | 1,360, 0.9 MB | 347 ms | 59 ms | 6 / 0 | 120 / 0 | 300 | 2.15 MB |
| 5,000 | 5,360, 3.8 MB | 281 ms | 60 ms | 6 / 0 | 120 / 0 | 300 | 2.15 MB |
| 20,000 | 20,360, 14.5 MB | 299 ms | 55 ms | 6 / 0 | 120 / 0 | 300 | 2.15 MB |

Per-request work, memory and latency stay flat while the cache grows 20-fold. Cache memory is about 0.7 KB per film. Before S5C, every discovery request built a dense pool × vocabulary matrix (16.9 MB at 300 × 7,395), and MMR built another. The warm request peak was 29 MB with the dense rerank matrix and is now 2.15 MB. The benchmark's 20,000-entry case raises the cache limits on purpose, since the production default is 4,000 entries / 16 MiB.

**Live TMDB (local backend, k = 100, warm):**
- Pixar likes (Toy Story, Up, Coco) gave a pool of 82, with 56 discovered films among the 100 picks, in **0.22–0.32 s** (the first request after a restart is the slowest).
- Inception + Interstellar + The Dark Knight gave a pool of 69 and 48 discovered picks in **0.19–0.21 s**.
- Ranking took 37–85 ms of that. S5B warm requests took 0.4–1.1 s.
- No top-40 pick was left without a "because" for these profiles.

These numbers describe this machine and these budgets. They do not show unlimited scale.

## Demo

1. Like external films and refresh. `ranking.feature_cache.misses` counts only new titles.
2. Like one more discovered film. Only its features are resolved, both server-side and in the browser.
3. Repeat warm: no upstream calls and no encoding.
4. Delete the cache file: results recover, and the cache is rebuilt.
5. Restart with `CINEMAGIC_RANKING=snapshot`: the snapshot ranking is back.

Commit this iteration as `codinsayan` only, with no co-author trailers.
