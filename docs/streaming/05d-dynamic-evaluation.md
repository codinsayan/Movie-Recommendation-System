# S5D: Evaluate and accept dynamic recommendations

Status: planned. Depends on [S5A](05a-dynamic-preferences.md), [S5B](05b-dynamic-discovery.md) and [S5C](05c-scalable-ranking.md). Next: [S6 release readiness](06-release.md), then [S7 Render deployment](07-render-deployment.md).

## Outcome

Validate that external preferences and dynamically discovered movies improve the supported experience, remain resource-bounded and are ready for release checks. Finish this acceptance milestone before implementing S6/S7. Semantic embeddings are an optional measured experiment; they are not a prerequisite for deploying a validated metadata-based system.

## Work

- [ ] Build versioned offline fixtures covering external likes/dislikes, new releases, missing metadata, unfamiliar vocabulary, multiple taste interests, dislike-only profiles and several original/display languages.
- [ ] Compare the current snapshot engine, dynamic-input-only ranking and dynamic retrieval plus bounded ranking. Separate retrieval coverage/recall from ranking quality; use a common candidate pool when comparing scoring methods.
- [ ] Record dataset/fixture provenance, snapshot hashes, feature/encoder versions, seeds and reproducible commands. Label synthetic viewing/ratings and TMDB graph overlap; avoid reporting them as independent real-user evidence.
- [ ] Measure Hit-Rate/NDCG where a valid held-out target exists, catalogue/candidate coverage, diversity, exact-dislike exclusion and explanation fidelity. Record baselines and limitations instead of promising improvement in advance.
- [ ] Collect human relevance feedback on several profiles, including a newly released or niche liked movie and a related disliked movie. Inspect before/after results, negative-preference overreach, popularity bias and missing-feature cases.
- [ ] Benchmark cold/warm request latency, memory, candidate counts, API calls and derived-cache size at representative growth levels. Measure actual browser responsiveness separately from Node timing.
- [ ] Test preference resolution -> changed recommendations -> external candidate details/playback -> like/dislike -> refresh, including cancellation, retries and offline/static fallback.
- [ ] Verify missing metadata keeps the preference saved with an honest pending state. Removing or reversing it during lookup must prevent an obsolete result from returning.
- [ ] Preserve S5 opt-in viewing behavior, the recent-playback filter's evidence rules, labelled broader banner recovery and source selection independent of recommendation failures.
- [ ] Update the user-facing explanation of dynamic inputs/candidates, static limitations, cache refresh and failure states. Retain a documented rollback to the snapshot engine.
- [ ] Record a go/no-go decision for an optional semantic-embedding experiment based on measured vocabulary/meaning limitations, relevance gains, model startup, storage and hosting cost. Keep it deferred if benefits do not justify the added requirements.

## Optional embedding experiment

If the metadata baseline shows a concrete semantic limitation, compare it with a fixed-version sentence encoder on the same fixtures and candidate sets. Measure cold-start/model memory and encoding cost, feature-cache compatibility, multilingual behavior and browser/static implications. Updating an encoder requires a controlled re-encoding strategy; newly rated movies should not retrain it. A vector database or hosted embedding service is not required for the initial bounded metadata implementation.

Do not silently replace the default encoder, invent quality gains or make a new external service necessary before this experiment has a documented result. Track any approved follow-on implementation separately so the tested metadata-based release can proceed to S6/S7.

## Expected files

Evaluation fixtures/scripts, focused ranking/retrieval/parity/integration checks, `docs/EVALUATION.md` or a linked dynamic-evaluation report, `docs/ARCHITECTURE.md`, `README.md`, `CHANGELOG.md`, and completed evidence in S5A-S5C plans.

## Acceptance

- [ ] A usable TMDB movie outside the original snapshot can affect taste and another external movie can become a recommendation, without a snapshot rebuild per interaction.
- [ ] Likes and dislikes for new movies persist, exact exclusions hold, related penalties are calibrated, and explanations identify the real contributing evidence.
- [ ] The selected retrieval/ranking budgets pass documented latency/memory/request checks; cache growth does not create unbounded per-request work.
- [ ] Regression tests and supported Python/browser parity pass, with backend-only capabilities and static limits clearly identified.
- [ ] Human relevance and actual browser-flow results are recorded with failures and limitations. Configuration files or mocked callbacks alone are not live acceptance evidence.
- [ ] Decide whether to retain the metadata baseline or plan a later embedding upgrade. No blanket claim that every movie has complete metadata or guaranteed playback is made.
- [ ] Update the roadmap to make S6 the next implementation phase only after these dynamic-recommendation acceptance records exist.

## Demo and commit

Show a new external like, an external dislike, a new recommendation outside the starter catalogue, a pending metadata lookup and an offline fallback. Compare the same profile with the prior snapshot baseline and record both relevance and resource measurements.

Commit this iteration and each completed implementation phase as `codinsayan` only, without co-author trailers. This planning document does not indicate that the upgrade has been implemented or tested.
