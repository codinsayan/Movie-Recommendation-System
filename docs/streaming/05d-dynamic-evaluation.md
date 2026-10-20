# S5D: Evaluate and accept dynamic recommendations

Status: **accepted at the project-owner review level on 21 October 2026**. Offline proxy, live-fixture replay, resource benchmark and rendered-browser walkthrough are recorded. The owner rated the proposed recommendation sets **2/2 overall**; no per-pick or baseline ratings were supplied. One calibration change was adopted; embeddings stay deferred. See [the review record](../evaluation/s5d-review.md). Depends on S5A-S5C. [S6](06-release.md) is implemented; [S7 Render deployment](07-render-deployment.md) is next.

## Outcome

This milestone checks three things: that external preferences and dynamically discovered movies improve the supported experience, that they stay resource-bounded, and that they're ready for release checks. Semantic embeddings were an optional measured experiment, and the decision below is to defer them.

## Work

- [x] Build versioned offline fixtures covering external likes/dislikes, new releases, missing metadata, unfamiliar vocabulary, multiple taste interests, dislike-only profiles and several original/display languages.
- [x] Compare the current snapshot engine, dynamic-input-only ranking, and dynamic retrieval plus bounded ranking. Separate retrieval coverage/recall from ranking quality, and use a common candidate pool when comparing scoring methods.
- [x] Record dataset/fixture provenance, snapshot hashes, feature/encoder versions, seeds and reproducible commands. Label synthetic viewing/ratings and TMDB graph overlap, and don't report them as independent real-user evidence.
- [x] Measure Hit-Rate/NDCG where a valid held-out target exists, plus catalogue/candidate coverage, diversity, exact-dislike exclusion and explanation fidelity. Record baselines and limitations instead of promising improvement in advance.
- [ ] Collect human relevance feedback on several profiles, including a newly released or niche liked movie and a related disliked movie. Inspect before/after results, negative-preference overreach, popularity bias and missing-feature cases. *The automated inspection is done (see Findings). The [review sheet](../evaluation/s5d-review.md) is waiting for human ratings.*
- [x] Benchmark cold/warm request latency, memory, candidate counts, API calls and derived-cache size at representative growth levels. Measure actual browser responsiveness separately from Node timing.
- [x] Test preference resolution -> changed recommendations -> external candidate details/playback -> like/dislike -> refresh, including cancellation, retries and offline/static fallback.
- [x] Verify that missing metadata keeps the preference saved with an honest pending state, and that removing or reversing it during lookup prevents an obsolete result from returning. Covered by the S5A resolver tests, the S5C pending-viewing test and the derived-cache JS test.
- [x] Preserve S5 opt-in viewing behavior, the recent-playback filter's evidence rules, labelled broader banner recovery, and source selection independent of recommendation failures. The S5/S5A suites are unchanged and pass.
- [x] Update the user-facing explanation of dynamic inputs/candidates, static limitations, cache refresh and failure states. Keep a documented rollback to the snapshot engine.
- [x] Record a go/no-go decision for an optional semantic-embedding experiment.

## How to reproduce

```bash
python scripts/record_dynamic_fixture.py     # needs TMDB keys; re-records docs/evaluation/s5d-live-fixture.json
python scripts/evaluate_dynamic.py           # offline; writes s5d-results.json and s5d-review.md
python scripts/benchmark_ranking.py          # offline S5C resource benchmark
python run.py --no-browser &                 # then:
python scripts/browser_walkthrough.py        # headless Edge; writes s5d-browser.json and screenshots
python -m pytest -q
```

The evaluation records hashes for the snapshot and fixture, plus the feature version, seed 2026, the policy definitions and the runtime versions, in [s5d-results.json](../evaluation/s5d-results.json). Ranking metrics reproduce exactly for these inputs; timings vary by host.

## Part 1: world proxy (offline)

**Protocol.**
- The 447-film snapshot is split into a **312-film starter** catalogue, which trains the engine, and a **135-film external "world"**.
- A fake TMDB serves the world through the real `Discovery` code. Related titles come from the bundled TMDB graph; discovery uses genre/vote/date filters.
- 80 profiles each like one starter film and one external film. The hidden target is a graph neighbour of the external like.
- **The edge from the external like to the target is removed** from related-title responses, so retrieval must reach the target some other way.
- Half the profiles also dislike an unrelated external film.

**Limitation:** the graph also trains the starter engine. This is a *transductive proxy with graph overlap*, not independent user evidence.

Results for 80 profiles at k = 10:

| Variant | HR@10 (46 starter targets) | NDCG@10 (starter) | HR@10 (34 world targets) | NDCG@10 (world) | HR@10 all | NDCG@10 all | Recall | Coverage | Diversity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A: snapshot engine (external like unusable) | 0.696 | 0.353 | 0 | 0 | 0.400 | 0.203 | 0.575 | 0.512 | 0.928 |
| B: dynamic inputs (S5A) | 0.696 | **0.445** | 0 | 0 | 0.400 | 0.256 | 0.575 | 0.537 | 0.929 |
| C: dynamic retrieval + bounded ranking | 0.652 | 0.398 | **0.382** | **0.240** | **0.538** | **0.331** | **0.800** | **0.635** | 0.924 |

**Recall** is whether the target was in the candidate pool at all. A and B can only reach starter films.

- **B vs A:** using the external like raises NDCG for reachable targets by 26%.
- **C vs B:** retrieval makes 34 previously unreachable targets reachable and finds 38% of them in the top 10. That costs a few starter hits, because discovered films compete for the same 10 slots. Overall HR goes from 0.400 to 0.538 and NDCG from 0.256 to 0.331.
- **Missing metadata:** when every world candidate is a summary (no keywords or cast), world-target HR falls from 0.382 to 0.206. Full-detail enrichment matters, which is why S5B warms details in the background.
- **Unfamiliar vocabulary:** an external like whose metadata uses no known words is marked `unavailable` in all 80 cases, and B correctly falls back to A. C still reaches world targets through that like's related titles (HR 0.294).
- In every scenario: **0 exact-dislike violations** and **0 explanations naming a film outside the profile**.

**Calibration policies on C's common pool** (same retrieved candidates, different scoring), HR@10 / NDCG@10 over all 80 profiles:

| Policy | Full metadata | Summary-only candidates |
|---|---|---|
| S5B snapshot prior | 0.525 / 0.328 | 0.488 / 0.303 |
| Pool prior | 0.525 / 0.328 | 0.488 / 0.303 |
| **Pool prior + related confidence** (adopted) | **0.538 / 0.331** | 0.488 / 0.303 |
| Vote floor 100 | 0.525 / 0.328 | 0.488 / 0.303 |
| Pool prior + confidence + floor 50 | 0.538 / 0.331 | 0.488 / 0.303 |

In the proxy, world films are as popular as starter films, so the policies are statistically indistinguishable here. The proxy shows that the calibration does **no harm** to held-out accuracy, not that it helps.

## Part 2: live replay

[s5d-live-fixture.json](../evaluation/s5d-live-fixture.json) holds real TMDB pools recorded on 20 October 2026 through the production discovery code: 12 profiles and 367 unique discovered films, all with full details.

The profiles are:
- Pixar;
- Nolan;
- a single niche like (Parasite);
- romance;
- horror;
- multi-interest (Toy Story + The Dark Knight + The Notebook);
- a related dislike (like Inception, dislike Interstellar);
- an external like and an external dislike (Primer / Transformers: Revenge of the Fallen);
- non-English originals (Burning, ko; Shoplifters, ja);
- a brand-new release (*Street Fighter*, 2026);
- dislike-only;
- cold start.

There's no ground-truth target, so this part measures side effects. Values are means over profiles of the top 20 picks.

| Policy | Discovered in top 10 | Median votes of discovered picks | Picks < 100 votes | Picks < 300 votes | Mean rating | Diversity (top 10) | Dislike violations | Invalid "because" |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S5B snapshot prior | 47.5% | 1,171 | 5.8% | 17.5% | 7.34 | 0.935 | 0 | 0 |
| Pool prior | 44.2% | 1,169 | 6.3% | 17.1% | 7.38 | 0.939 | 0 | 0 |
| **Pool prior + related confidence** | 37.5% | **2,116** | 3.8% | **11.7%** | **7.50** | **0.944** | 0 | 0 |
| Vote floor 100 | 47.5% | 1,386 | 0% | 12.9% | 7.37 | 0.937 | 0 | 0 |
| Pool prior + confidence + floor 50 | 37.5% | 2,116 | 2.5% | 10.8% | 7.51 | 0.943 | 0 | 0 |

### Findings

- **Popularity mis-calibration (fixed).** S5B shrank discovered films towards the *snapshot's* prior (median 13,370 votes, mean rating 7.49). The snapshot is a curated set of acclaimed films, so a film with 56 votes was treated as average-for-the-acclaimed. On top of that, every TMDB-related title got a full direct-link collaborative score. For Parasite, 15 of the top 20 were discovered with a median of 305 votes (*The Middle Man*: 56 votes).
- **Adopted fix: `DISCOVERY_POLICY = pool prior + related confidence`.**
  - A discovered film's quality is also estimated against the mean rating and median votes of the pool it was retrieved with, and the **lower** of the two estimates is kept. The calibration can only remove flattery, never boost a film.
  - Its related-title evidence is scaled by `votes / (votes + pool median votes)`.
  - It's soft: niche films can still win on strong content match, and there's no hard floor.
  - On live pools it cuts picks under 300 votes from 17.5% to 11.7%, nearly doubles the median votes of discovered picks (1,171 → 2,116), raises mean rating (7.34 → 7.50) and diversity, and keeps a 37.5% discovered share.
  - The extra floor-50 variant changes little, so no hard floor was added.
  - A first version used the pool prior on its own. Because it mixed a smaller prior with the snapshot's, it boosted thin-vote films in cold start (*Michael (2026)* outranked *The Godfather*). Keeping the lower estimate made cold-start picks identical to S5B.
  - Examples: Pixar's *Rock Dog* moves from #4 to #9 and *Blue's Big City Adventure* leaves the top 10; for Parasite, *The Middle Man*, *Good News* and *Somewhere in Queens* give way to *American Psycho*, *The Wolf of Wall Street* and *Falling Down*.
- **Arthouse profile.** Likes of Burning + Shoplifters still get low-vote arthouse picks (*Female Prisoner Scorpion: Jailhouse 41*, 121 votes). That may be correct for this taste; it's flagged for human review.
- **Negative preferences.** No exact-dislike violations in any profile or policy. The related-dislike profile (like Inception, dislike Interstellar) still gets Nolan/sci-fi picks other than Interstellar: dislikes act as a similarity penalty, not a genre ban.
- **Explanation fidelity.** 83% of top-20 picks have a "because". None names a film outside the profile, and every `tmdb-related` explanation matches the film's retrieval provenance.

### Vocabulary and the embedding decision

Across the 367 real discovered films, measured against the fitted TF-IDF vocabulary:
- **70%** of their feature tokens are in the vocabulary (median per film);
- they have a median of **23** non-zero features, against 40 for snapshot films;
- **0** have no features, and **3** have fewer than 10;
- original languages: 308 en, 31 ja, 12 ko, plus es/fr/pt/de/zh. Features always use English metadata, so non-English originals are represented through their English overviews;
- all 5 resolved external preferences applied, with a median of 31 features.

**Decision: defer embeddings (no-go for now).** The vocabulary gap is real: discovered films carry about half the features of snapshot films. But it causes no failures, retrieval already finds 80% of proxy targets, and the main relevance problem found was popularity calibration, not meaning. A sentence encoder would add a model download and memory at startup, a re-encoding strategy, and a browser/static mismatch, with no measured relevance problem it would solve. Revisit if human review shows topical misses that share no words, or if the proportion of tokens outside the vocabulary grows.

## Part 3: rendered browser walkthrough

[s5d-browser.json](../evaluation/s5d-browser.json) is a headless Microsoft Edge run that drives the real UI.

- **Seeded likes:** Toy Story, Up and Coco.
- **Instrumentation:** an injected probe records every fetch, including aborted ones, and main-thread long tasks.

**Backend:**
- **Boot:** Top Picks render with 4 Discovered badges and the line "includes 55 newly discovered films" (1.2 s).
- **Details:** opening *Rock Dog* shows the discovery provenance and "Because you loved: Coco", with a Watch button.
- **Like from details:** the film leaves Top Picks in **0.36 s** (server 0.21 s).
- **Watch:** opens a CineSrc frame for that TMDB ID. This shows playback routing only, not that the film plays.
- **Dislike** of *Rock Dog 2*: it leaves Top Picks in **0.33 s**.
- **Three rapid toggles in 80 ms:** debounced into **one** request; the final state is liked and absent from picks.
- **Main-thread blocking:** at most **79 ms** (4 long tasks).
- **On a cold network:** the same like and dislike took 1.2 s and 2.6 s, because new seeds trigger TMDB retrieval over a flaky connection.

**Static build:** Top Picks render with **no** Discovered badges. A like re-ranks in the browser engine in **0.27 s**, with at most 136 ms of blocking.

**Screenshots:**
- [desktop](../evaluation/screens/s5d-discovered-details-desktop.png) and [mobile](../evaluation/screens/s5d-discovered-details-mobile.png) details windows for a discovered film.
- The phone layout was rendered in a true 390 px frame, because headless Edge enforces a window of about 500 px. The layout wraps correctly with no clipping.

**Offline and rollback fallbacks:**
- Discovery failure, missing credentials, stale cache, a damaged or deleted cache file, and snapshot rollback mode are covered by deterministic tests (S5B/S5C).
- During this milestone the live network itself was intermittently cutting TLS connections to TMDB. The app degraded to `partial` discovery reports rather than failing requests, and the recorder needed retries.

## Resources

See [S5C evidence](05c-scalable-ranking.md#evidence-20-october-2026). Per-request work is flat as the feature cache grows from 0 to 20,000 entries: 120 films encoded cold / 0 warm, 6 / 0 upstream calls, a 300-row rerank pool, a 2.15 MB request peak and about 55 ms warm. The S5D calibration adds two vector operations over the pool and no measurable cost.

## Acceptance

- [x] A usable TMDB movie outside the original snapshot can affect taste, and another external movie can become a recommendation, without a snapshot rebuild per interaction. Shown by proxy variant C, the live fixture and the browser walkthrough.
- [x] Likes and dislikes for new movies persist, exact exclusions hold, related penalties are calibrated, and explanations identify the real contributing evidence.
- [x] The selected retrieval/ranking budgets pass documented latency/memory/request checks, and cache growth does not create unbounded per-request work.
- [x] Regression tests and supported Python/browser parity pass (**136 passed**, plus the JS suites), with backend-only capabilities and static limits clearly identified.
- [x] Human relevance and browser-flow results recorded with limitations: the owner supplied an overall **2/2** on 21 October 2026; the earlier browser flow is recorded. Per-pick and baseline ratings remain uncollected; no human comparison metric is inferred. See [review record](../evaluation/s5d-review.md).
- [x] Decide whether to keep the metadata baseline or plan a later embedding upgrade: **keep the metadata baseline**; embeddings are deferred. No blanket claim of complete metadata or guaranteed playback is made.
- [x] Roadmap reflects the recorded human review. S6 implementation was explicitly requested before this response arrived; its functional sign-off is now recorded separately. S7 is the next implementation phase.

Commit this iteration as `codinsayan` only, without co-author trailers.
