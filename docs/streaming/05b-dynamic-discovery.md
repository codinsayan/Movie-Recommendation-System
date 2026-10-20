   # S5B: Dynamic recommendation candidates

Status: code implemented on `feature/streaming-platform`; deterministic and live API checks passed. Rendered-browser review and the S5D budget/relevance evaluation remain pending. Depends on [S5A external preferences](05a-dynamic-preferences.md). Next: [S5C scalable ranking](05c-scalable-ranking.md).

## Outcome

Recommendations can include newly discovered movies outside the original 447-film snapshot. The snapshot becomes a starter/fallback pool rather than a permanent boundary. TMDB retrieves possible candidates; the project's own engine determines their personalized order.

## Work

- [x] Add cached backend adapters for TMDB movie recommendations and discovery, using fixed upstream endpoints and validated IDs/parameters. Reuse existing timeout, rate-limit, sanitized-error and stale-cache behavior.
- [x] Gather candidates from several positive preference seeds, preference-informed discovery, relevant new releases, cached titles and the starter snapshot. Do not rely exclusively on the latest like or on popularity.
- [x] Handle dislike-only and cold-start profiles explicitly: generate a broad starter pool, apply negative preferences, and label the result appropriately.
- [x] Define source quotas, seed selection, pagination limits, concurrency limits and an initial bounded request pool, tentatively 200-500 unique movies. Verify these budgets during S5D; they are not a cap on the total discoverable catalogue.
- [x] Deduplicate by canonical identity and exclude explicit likes/dislikes before final selection. Preserve title, original language, metadata language and feature provenance.
- [x] Refresh new-release discovery on a documented TTL and invalidate changed metadata/features by version. A new release need not wait for a committed snapshot rebuild.
- [x] Reuse S5A feature normalization for remote candidates. Bound detail enrichment and label incomplete metadata instead of assigning fictional scores or pretending a search summary contains all features.
- [x] Rank the candidate pool using the current content/related-title/quality signals and the resolved positive/negative profile. Treat TMDB related-title results as an external recommendation signal, not a new user-ratings dataset.
- [x] Apply supported eligibility rules before the ranking pool is truncated. Unknown streaming availability remains unknown; a recommendation result is not proof of playable video.
- [x] Integrate dynamic cards with details, Watchlist, playback, taste controls and saved metadata. Make an explicit preference for a newly recommended movie usable through S5A.
- [x] Abort or reject superseded preference/mood/discovery responses so an older pool cannot overwrite the current banner or rows.
- [x] Preserve usable cached/snapshot results during upstream failures. Record partial retrieval and stale data honestly; no request should depend on every external source succeeding.
- [x] Keep live retrieval backend-only. Static mode uses the exported/cached subset and clearly documents its narrower freshness and discovery capabilities.

## Design

### Retrieval (`backend/discovery.py`)

| Source | Endpoint | When | Per-request budget | Cache TTL |
|---|---|---|---|---|
| `related` | `/movie/{id}/recommendations` | each seed like | up to **4 seeds**, page 1 | 24 h |
| `taste` | `/discover/movie`, top 2 taste genres (OR), `vote_average.desc`, ≥1000 votes | any positive like | **2 pages** | 6 h |
| `new_release` | `/discover/movie`, released in the last **120 days**, `popularity.desc`, ≥50 votes | always | 1 page | **3 h** |
| `starter` | `/discover/movie` popular (≥500 votes) ×2 pages + top rated (≥3000 votes) | cold-start / dislike-only | 3 pages | 6 h |

- **Seeds:** the two most recent likes, then likes spread evenly across older history (`select_seeds`). Snapshot and external TMDB likes both qualify.
- **Taste genres:** counted from liked snapshot films plus the S5A external profile's positive genres.
- **Taste discovery** asks for *acclaimed* rather than *most-voted* films, because the snapshot already holds the most-voted ones. In the first live run, a most-voted query added zero new titles.
- **Pool:** at most **300** unique candidates. The merge follows task submission order, so it's deterministic. Exact liked, disliked and snapshot IDs are dropped at merge time, whichever source returned them.
- **Concurrency:** **4** upstream requests at once, enforced process-wide by one semaphore shared by all requests.
- **Failures:** each source fails independently. The report says `ok`, `partial` or `unavailable`. Stale cache entries are used and flagged. The request itself never fails because discovery did.
- **Enrichment:** full cached details are used immediately. Up to **12** missing details per request go to a 2-worker background queue, so they never block the response. Candidates are marked `features: "full"` or `"summary"` (a summary has no keywords or cast).

### Ranking (`Recommender.recommend(extra=...)`)

Discovered films are encoded with the **fitted** TF-IDF vocabulary. There's no refit and no growth of the snapshot matrices. Each candidate is scored alongside the snapshot:

```
content  = cos(candidate TF-IDF vector, taste profile)                     (same profile as snapshot films)
collab   = RELATED_LINK · (#seed likes that TMDB lists it under) / #likes   RELATED_LINK = 0.3
quality  = snapshot's vote-weighted rating formula and scale, clipped to [0, 1]
viewing  = 0.6 · content similarity to measured-viewing films (S5 opt-in)
```

`RELATED_LINK` is calibrated to a typical direct link in the snapshot's recommendation graph: 2 / (degree + 1) with an average degree of about 6. That lets a TMDB related title compete with graph neighbours without dominating them. All signals are min-max scaled over the union of snapshot and discovered candidates, then blended with the existing weights.

MMR runs over the union. Snapshot pairs use the exact `content_sim` values, so snapshot-only behaviour is unchanged. Explanations give the evidence that retrieved the film: "Because you loved X" when TMDB lists it as related to X (`evidence: "tmdb-related"`), otherwise the closest liked film by content, an external seed, viewing, "New release that fits your taste", or "Popular right now".

### API and client

- `POST /api/recommend` takes `discover: true`. The response then includes `discovery`: status, profile, seeds, genres, per-source counts, pool, `enriched`/`summary_only`/`enrich_queued`, upstream calls, cache hits, stale and failed sources, and how many discovered films were recommended.
- `GET /api/capabilities` reports `catalogue.dynamic_discovery`.
- The client requests discovery only from a configured backend. It registers discovered cards with the catalogue browser, so details, Watchlist, likes and dislikes (via S5A) and the player all work.
- A newer refresh aborts the older request, and late responses are ignored.
- The Top Picks subtitle states discovery status honestly. Tiles show a **Discovered** badge, and the detail "why" panel names the retrieval sources and labels summary-only ranking.
- Static mode (GitHub Pages) never sends `discover`, so it keeps the exported snapshot.

## Acceptance

- [x] A deterministic TMDB fixture absent from the original catalogue appears as a recommendation, opens details and can be liked/disliked without retraining the snapshot.
- [x] A newly released fixture becomes eligible after discovery refresh; duplicate pages and overlapping retrieval sources do not duplicate cards.
- [x] Exact disliked IDs remain excluded across every retrieval source. Similarity penalties do not masquerade as categorical genre bans.
- [x] Candidate count, upstream calls and concurrency stay within configured budgets even with many saved preferences or many result pages.
- [x] Missing credentials, empty recommendation endpoints, rate limits, stale cache and partial failures preserve usable fallback results and truthful explanations.
- [x] Dynamic cards preserve canonical identity and browser-local persistence across refresh. Static mode does not advertise a fresh live pool.
- [ ] Rendered desktop/mobile browser walkthrough of discovered cards (badge, details, like, Watch) and S5D relevance/budget review.

## Evidence (20 October 2026)

**Automated:** `python -m pytest -q` gives **123 passed**. That's the 111 existing tests plus 12 in `tests/test_discovery.py`, which use a mock TMDB and no network. They cover:
- a discovered fixture recommended with `tmdb-related` evidence, opening details and resolving as an S5A preference;
- de-duplication across related, taste and repeated pages;
- dislike exclusion across sources, without a genre ban;
- seed, pool, enrichment and concurrency budgets (30 likes still give 4 seed calls and a peak concurrency of 4 or less);
- 429/5xx partial failure with snapshot fallback;
- missing credentials leaving results unchanged;
- stale-cache fallback;
- the 3-hour new-release refresh;
- cold-start and dislike-only profiles;
- an external like seeding its own related titles;
- unchanged snapshot-only output.

The existing Python/JavaScript parity tests still pass, so the snapshot path is byte-compatible. The JavaScript harnesses now provide `AbortController`, as browsers do.

**Live TMDB (local backend):** likes of Inception, Interstellar and The Dark Knight gave a pool of 69. Sources: related 49, taste 12, new release 10. **5 of the top 12 picks** were outside the snapshot: Batman (1989), Stargate: Continuum, Batman and Harley Quinn, The Electric State and Primer, each explained by its seed. Pixar likes gave 5 of 12 discovered films; cold start gave a 14-film starter/new-release pool.

Latency after moving enrichment to the background:

| Request | Time |
|---|---|
| Cold, 2 likes | 1.9 s (4 upstream) |
| Same profile, warm | 0.8 s |
| Next like | 1.1 s |
| Next like, warm | 0.4 s (0 upstream) |

**Findings for S5D:**
- TMDB related titles include some low-vote films (e.g. StarDog and TurboCat for a Pixar profile), and quality is only 10% of the score. Evaluate a vote floor or a higher quality weight for discovered candidates.
- Match percentages stay relative to the best pick in each response.

## Sources and demo

Interfaces used: [TMDB recommendations](https://developer.themoviedb.org/reference/movie-recommendations), [discovery](https://developer.themoviedb.org/reference/discover-movie), [details](https://developer.themoviedb.org/reference/movie-details).

Demo:
1. Like an external film and refresh: the pool contains other external films.
2. Dislike one suggestion: it disappears from every source.
3. Watch the Top Picks subtitle for the discovery count and partial/stale notes.
4. Stop the network or remove the key: the snapshot remains.

Commit this iteration as `codinsayan` only, with no co-author trailers.
