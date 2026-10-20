# S5A: Likes and dislikes for newly discovered movies

Status: code implemented; deterministic/live API/static/boot checks and focused desktop/mobile browser verification passed. Broader user review remains pending. Depends on [S4 discovery](04-search-and-catalogue.md) and [S5 viewing signals](05-recommendations.md). Next: [S5B dynamic discovery](05b-dynamic-discovery.md). Resolved external choices now influence the existing snapshot engine; dynamic recommendation candidates remain S5B work.

## Outcome

A like or dislike for a movie outside the trained snapshot becomes an explicit taste input once usable metadata is resolved. The first milestone still ranks the existing snapshot; S5B adds new recommendation candidates. No full retraining is required for each newly rated movie.

## Work

- [x] Define a versioned preference-resolution contract using canonical movie keys, feature-version identifiers and applied/pending/unavailable states. Preserve existing browser-local profiles and separate curated IDs from TMDB IDs.
- [x] Save the preference immediately in the browser. Resolve new TMDB IDs through the backend's validated metadata service and cache; never expose the API credential or accept arbitrary upstream URLs.
- [x] Fetch complete feature metadata rather than treating a search summary as a trained representation. Reuse genres, keywords, overview, director and cast where available.
- [x] Centralize feature normalization so snapshot and remote titles use the same genre names, keyword/person normalization and weighting. Separate feature language from the viewer's display-language choice.
- [x] Transform external metadata with the existing fitted TF-IDF vocabulary without refitting the entire catalogue. Explicitly handle missing metadata, unfamiliar words and zero vectors; use measured structured overlap where supported rather than inventing similarity.
- [x] Build positive and negative taste profiles from resolved explicit preferences. Dislikes exclude the exact film and apply a calibrated similarity penalty; they do not automatically ban its whole genre. A conflicting dislike wins.
- [x] Use content and quality when collaborative information is unavailable, with honest component availability and weight normalization. Metadata similarity is not individual user-rating evidence.
- [x] Update Taste DNA, explanations and "Because you loved" sources to include resolved external likes; count unresolved preferences separately instead of claiming they already affect ranking.
- [x] Bound concurrent metadata requests and per-request work. Keep unresolved preferences pending and process them incrementally; do not silently discard saved preferences to meet a request budget.
- [x] Deduplicate feature work by canonical ID and feature version. Reject late responses after a preference is removed, reversed or superseded; the final profile must reflect the latest explicit choice.
- [x] Keep metadata failures separate from taste: retain the preference, show pending/unavailable status and retry through bounded requests. Existing recommendations and playback must remain usable.
- [x] Define static fallback precisely: use compatible cached metadata and exported feature transforms where available. Unresolved titles stay pending offline; static mode cannot privately fetch fresh TMDB metadata.

## Expected files

`backend/catalog.py`, `backend/recommender.py`, a shared feature/profile module if useful, `backend/app.py`, `frontend/preferences.js`, `frontend/catalogue.js`, `frontend/engine.js`, `frontend/app.js`, static-export configuration and focused preference/parity tests. Keep the existing snapshot as a fallback.

## Acceptance

- [x] A fixture movie absent from the snapshot changes recommendations after being liked, without a catalogue rebuild or growth of the original similarity matrices.
- [x] Disliking an external film removes that exact candidate wherever encountered and reduces measured affinity to related candidates without creating a genre-wide exclusion.
- [x] Unknown IDs, metadata timeouts, missing keywords, new vocabulary and unsupported schema versions have explicit, non-fabricated outcomes.
- [x] Removing or reversing a preference during lookup cannot resurrect an obsolete taste signal. Multiple external likes/dislikes survive refresh.
- [x] New explicit inputs remain stronger than S5's optional viewing signal. Source errors, switches and playback failures never become dislikes.
- [x] Supported Python/browser inputs produce matching profile/scoring behavior. Offline or missing-metadata limitations are visible and documented.
- [x] Test that the baseline without external preferences remains compatible with existing rankings and browser storage.

- [x] Verify applied Sintel, identical picks after full page reload, the explicit related shelf with both viewing switches, and external More Like This in an isolated rendered desktop/mobile browser.
- [ ] Complete broader user-browser/locale and relevance review; focused headless checks do not establish every device/language combination.

## Demo and evidence

### Implementation evidence (20 October 2026)

- Initial feature commit pytest suite: **109 passed**. Includes ten S5A Python cases and ten JavaScript resolver lifecycle cases. Existing playback, search, viewing and static-engine parity checks still pass. `python scripts/export_static.py` also succeeds.
- Both snapshots' feature documents are byte-equivalent to their prior construction. Representative external preferences change ranks without calling `fit_transform`, adding IDs or growing the existing matrices. Supported external transforms, Taste DNA, negative profiles, explanation sources and ranking match in Python/JavaScript, including weaker viewing signals.
- Browser-store/client contracts cover immediate saves, multiple external choices across reload, two-request concurrency, incremental hydration of 20 choices without truncation, unknown IDs/timeouts, retry, incompatible/zero features, removed/reversed choices, denied feature storage, stale-feature refresh and cache-budget eviction/rehydration of 250 saved choices. These use deterministic client harnesses, not rendered-browser automation.
- Live TMDB/local API: **Sintel (`tmdb:45745`)**, outside the **447**-movie snapshot, resolved **24** nonzero English features as `applied`, with feature version `tfidf-v1-ccf0b832fb0f31b94cf8f219` and non-stale metadata. Before its like, top five were The Shawshank Redemption, The Godfather, Interstellar, The Dark Knight and Pulp Fiction. After its like: How to Train Your Dragon, The Hobbit: An Unexpected Journey, How to Train Your Dragon 2, Avatar Aang: The Last Airbender and Mulan. After its dislike: The Shawshank Redemption, Interstellar, The Godfather, Schindler's List and Inception. This demonstrates influence; it is not a broad human relevance evaluation.
- The real JavaScript resolver and PreferenceStore were exercised against the local HTTP API: pending -> applied, identical picks after constructing new store/resolver objects over retained device storage, changed picks on reversal, and no external aggregate after removal. User browser data was not modified. At that initial checkpoint no browser was attached; follow-up full-browser evidence is recorded below.

### Contracts and limits

`/api/preferences/tmdb/{id}` accepts only validated external TMDB IDs and resolves complete `en-US` metadata using the private catalogue service. Shared normalization and the fitted vocabulary/IDF determine a feature version. Missing vocabulary is unavailable; unfamiliar terms are ignored rather than assigned invented meaning. Derived features are reusable offline only when their version matches. Display metadata language does not affect feature encoding.

`external_preferences` version 1 carries a signed sparse aggregate, resolved positive/negative counts, supported genre/tag weights and up to two positive explanation seeds. No full movie-to-movie matrix is added. Collaborative weight comes only from indexed choices; available weights normalize before S5's optional 10% viewing blend. Explicit dislike wins imported conflicts. Exact disliked IDs remain excluded by the explicit sets; new recommendation candidates and their retrieval-wide exclusion tests belong to S5B.

The client hydrates at most two IDs concurrently; server preference lookups are serialized and reuse a 512-record feature LRU plus the existing bounded metadata cache. A local feature TTL of one day supports refresh/stale fallback. Request feature work is bounded by the fitted vocabulary and two seeds. Existing browser preference limits are 10,000 per side and are visible when reached; metadata jobs process all saved IDs incrementally. The persisted feature cache is capped at 200 records and 2 MiB, reducing further on quota failures; uncached active features stay available in session and rehydrate after refresh. Feature caching never removes explicit IDs. Static mode can encode full cached English details or reuse compatible feature records; unknown fresh titles remain pending. Profile aggregation/cache scaling beyond these bounds remains S5C work.

### Reproduce and browser walkthrough

Run `python -m pytest -q`, `node tests/js/test_preference_resolver.cjs` and `python scripts/export_static.py`. With the configured backend running, search Sintel, like it and inspect My Taste for applied metadata and changed picks. Reverse/remove it during a lookup, retry failed metadata, change display language and refresh. Confirm the rendered status text, Taste DNA and Because you loved row. The focused reload/filter/detail paths now pass the isolated-browser check below; broader user/locale review remains outstanding.

Search for a film outside the snapshot, like it, observe its resolution state and changed picks, then dislike or remove it and observe the updated profile. Repeat with an offline lookup and a browser refresh. Record the fixture/live TMDB ID, feature version and before/after ranking; do not claim all metadata lookups always succeed.

Commit this iteration as `codinsayan` only, with no co-author trailers. Keep broader user/locale review visible alongside the recorded focused browser acceptance. S5B remains planned.


## Refresh and related-film corrections (20 October 2026)

User feedback: Sintel stayed Applied after refresh, but picks appeared to revert and similar movies were absent. An isolated headless Chrome run reproduced an initial recommendation request without restored external features and a missing explicit related shelf when recent-playback eligibility was empty. The movie dialog also explicitly rejected unindexed similar-title lookup.

- Startup now configures/restores cached feature inputs before its first recommendation request. A five-second metadata deadline preserves a usable pending fallback; Retry metadata can reconfigure a failed contract lookup. Preferences remain saved.
- External Because you loved shelves exclude explicit liked/disliked candidates independently of the Top Picks playback/mood filters, matching the existing indexed shelves. Those filters still govern Top Picks; watching The Odyssey cannot relabel or replace the Sintel shelf.
- More Like This resolves an external TMDB movie through the existing feature service and returns content-based snapshot neighbours. Static mode supports compatible cached vectors/full English metadata. No new recommendation candidates, model fit or matrix growth are introduced.
- Full suite: **111 passed**, including two app-bootstrap JavaScript cases for delayed feature configuration across reload and metadata-timeout recovery. API and Python/browser parity checks now cover external direct similarity and the filtered explicit shelf. Static export succeeds.
- Full-page isolated Chrome verification: the first request after reload included Sintel's external profile, and the same first five personalized picks persisted. With synthetic The Odyssey viewing evidence and both viewing switches, strict Top Picks stayed empty while Because you loved Sintel remained visible and the broader banner retained personalized picks. Nine related film cards appeared in Sintel's details. Desktop (1440 x 1000) and mobile (390 x 844) screenshots were visually inspected. The profile contained synthetic test data only; user browser storage was not read or changed.
