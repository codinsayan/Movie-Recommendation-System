# S5 viewing-signal evaluation

Recorded 20 October 2026. Raw results, runtime versions and snapshot/profile hashes: [s5-results.json](evaluation/s5-results.json).

## Decision

S5 is available **as an opt-in experiment** in My Taste. Existing ranking remains the default. The proxy evaluation found unchanged Hit-Rate@10 and a small NDCG change; this is not evidence of real-user improvement. One informal user review is recorded below; broader relevance review and rendered-browser acceptance remain pending. No new weights were promoted to the default experience.

## Reproduce

```bash
python scripts/evaluate_viewing.py --output docs/evaluation/s5-results.json
python -m pytest tests -q
```

No network or credentials are needed. The script uses the committed 60-film curated dataset and 447-film TMDB snapshot, seed 2026, k=10 and 60 deterministic profiles per dataset. SHA-256 hashes identify the exact input files and profiles. Ranking metrics reproduce for these inputs; timings and memory readings vary by host.

## Protocol and provenance

Each profile supplies one explicit like, one simulated substantially viewed film, and one hidden target. All variants receive the same candidate set, excluding liked and viewed films **before ranking**. We compare quality/popularity, the existing explicit hybrid, and the hybrid with the proposed viewing contribution. Both hybrids use the existing MMR settings.

- **Curated:** users and positive ratings come from the existing seed-42 synthetic ratings generator. Three items rated at least four stars are selected per usable user. Viewing is fabricated. The collaborative model retains the full synthetic ratings matrix; hiding a target from a request is not retraining on a held-out dataset.
- **TMDB:** a viewed film is selected from the committed graph; one graph neighbour becomes the like and another the hidden target. The same graph trains the model. This is a **transductive neighbour-recovery proxy**, with graph overlap/leakage, not an independent test of viewing behaviour. Graph links are not bundled individual ratings or measured local watch sessions.
- All simulated viewing signals use 180 measured seconds out of 600 and one qualifying session. Weights were fixed before inspecting these results; this run does not tune them.

Hit-Rate@10 measures whether the single hidden target appears in the top ten. NDCG@10 discounts it by rank: `1/log2(rank+1)` for one-based rank. Coverage is distinct recommendations divided by catalogue size. Diversity is mean pairwise `1-content_cosine`, excluding the diagonal.

## Results

| Dataset | Variant | HR@10 | NDCG@10 | Coverage | Diversity |
|---|---|---:|---:|---:|---:|
| Curated, 60 films | Popularity | 0.2333 | 0.0995 | 0.2000 | 0.9387 |
| Curated | Explicit hybrid | 0.5000 | 0.2491 | 1.0000 | 0.9127 |
| Curated | Hybrid + viewing | 0.5000 | 0.2503 | 1.0000 | 0.9132 |
| TMDB, 447 films | Popularity | 0.0333 | 0.0100 | 0.0246 | 0.9847 |
| TMDB | Explicit hybrid | 0.6333 | 0.3194 | 0.5705 | 0.9179 |
| TMDB | Hybrid + viewing | 0.6333 | 0.3239 | 0.5705 | 0.9181 |

These small NDCG differences do not establish statistical significance. Both datasets have synthetic viewing profiles, only 60 cases and training/evaluation overlap. The results support exercising the implementation, not claiming a better recommender.

## Signal policy

The player accepts only messages from its active frame and exact provider origin. It measures forward position intervals while playing in a visible tab, with an advancing wall clock, at most 15 seconds between observations and a position delta no greater than `1.25*elapsed + 0.25` seconds. Seeks, pauses, source changes, failures and long silent gaps break observation continuity. Overlapping intervals are merged; scrubbing to the end and an `ended` event cannot fill unwatched gaps. Old S3 resume positions migrate without acquiring viewing evidence.

A title qualifies after **both 120 seconds and 30% of duration** are measured. Further substantial sessions can raise strength from 0.15 to 0.20 to 0.25. Reopening, repeated Play messages and source changes alone cannot increment the count. Measured coverage remains distinct from completion/resume position. Small seeks, speed changes, missing callbacks or a provider falsely reporting playback cannot be ruled out.

With qualified opted-in signals:

```text
viewing_part(i) = clip(mean_s[(strength(s)/0.25) *
                           (0.6*content_similarity(s,i) + 0.4*collaborative_similarity(s,i))], 0, 1)
score(i) = 0.90 * existing_hybrid_score(i) + 0.10 * viewing_part(i)
```

Implicit contribution is bounded to 10%. Dislikes exclude candidates and remove conflicting positive/viewing seeds; explicit likes remain the primary explanation when present. Taste DNA/confidence still describes explicit taste. Unknown viewed films remain history-only. Eligibility is applied before normalization, the top-3k MMR pool and final k. “Because you watched” rows use measured sources and the same eligibility constraints.

## Device-local playback evidence

**Top picks: played recently on this device** requires ten measured playing seconds from a source within seven days. A later error invalidates that source's preceding success. Another source's fresh success may still qualify a film. Future-dated, expired, absent and unknown-provider evidence does not qualify. A URL, iframe load or Play click is insufficient.

This is client-reported evidence, not independent server verification or a guarantee of future playback. The filter affects Top Picks and viewing-based rows; when it has no matches the billboard shows separately labelled broader suggestions, with a Show all picks action; search, Watchlist, Continue Watching, explicit “Because you loved” rows and general catalogue browsing stay available. History is sent to FastAPI only for enabled options; static mode evaluates it in the browser. The API remains stateless. Removing history clears associated viewing/playback evidence, preserving likes, mood and Watchlist.

## Model size and runtime

Active datasets remain 60 and 447 films; discovery never appends to matrices. The snapshot-refresh command now caps requested IDs at **500** and can prioritize selected remote TMDB IDs. Metadata/quality requirements still apply, so a requested ID may be skipped. Review the refresh, rebuild the static export and restart the backend. No snapshot refresh or dataset expansion was performed during S5.

The raw report records Python startup, retained NumPy array bytes, compact export size, and Node startup plus median/p95 latency over 25 k=100 calls. The TMDB arrays occupy approximately **29.8 MiB**; the compact export is approximately **1,286 KiB**. Node records observed heap and array-buffer deltas, not peak resident memory or browser measurements. Garbage collection affects these readings.

Python retains dense feature/similarity matrices; the export ships sparse feature/graph rows and JavaScript reconstructs dense similarities. Raising the 500-film refresh cap requires measurements on the intended larger catalogue, sparse retrieval with a bounded candidate pool, and actual desktop/mobile responsiveness checks. Node timing does not establish browser responsiveness.

## Human review and browser acceptance

For “liked Inception; substantially watched Interstellar,” the TMDB top five are **Now You See Me 2, Tenet, Minority Report, Sicario, Eternal Sunshine of the Spotless Mind**. Curated picks and exact explanations are in the raw report. In [the informal review](evaluation/s5-human-review.json), the user said ?tenet is not there though, but it is pretty relevant.? This is broadly positive feedback on one example, with a discrepancy between the fixed profile and their displayed picks. Tenet exists in the snapshot and fixed-profile results. The local backend was still pre-S5 and was refreshed; the user's current taste/mood was not inspected and may differ. Curated picks have not been reviewed. No browser session is attached for rendered acceptance.

Before default activation, collect judgments from multiple profiles, compare the explicit baseline, inspect weak picks and run a larger independent evaluation. In the browser, verify measured watching creates the row; seeking/error-only sessions do not; options survive refresh; an empty recent filter leaves search available; and clearing history removes its influence. The planned S5A-S5D dynamic-recommendation upgrade precedes S6 release validation and S7 deployment; this report records the implemented snapshot-based S5 baseline.

## Implementation verification

The full regression suite passes **98 tests**. It invokes 26 JavaScript playback/preferences cases and seven catalogue cases, alongside Python ranking, request-validation and curated/TMDB parity checks. Live local API smoke checks passed for viewing-aware results, watched rows, twelve eligible filtered results, empty evidence, invalid contract versions and unindexed history. The active model stayed at 447 films. Static export succeeded. These checks do not verify rendered controls or third-party playback in a browser.

## Empty-filter banner recovery

The follow-up fix keeps strict filtered results separate from broader banner discovery. A second request removes only the recent-playback constraint when filtered results are empty, retaining mood, explicit taste and the viewing-history preference. No unverified film is labelled as recently played. Recovery can disable the filter explicitly; empty/unavailable broader results clear stale movies, backgrounds, dots and rotation timers. Seven JavaScript regression cases exercise the real app closures, including the exported static engine and late-response handling. The full suite now passes 98 tests. These DOM-contract checks do not replace rendered-browser acceptance.
