# S4: Search beyond the snapshot

Status: implemented; offline tests and live API/client verification passed. Rendered-browser acceptance is pending. Depends on S2; reuse [S3](03-progress-and-watchlist.md) movie identities. Next: [S5](05-recommendations.md).

## Outcome

The backend deployment can discover movies outside the existing 447-film snapshot. Search results can open details and playback without immediately rebuilding the entire recommender.

## Work

- [x] Add `backend/catalog.py` and a bounded SQLite cache with schema version 1 and refresh timestamps.
- [x] Add validated canonical TMDB search/detail routes before the static mount, plus `/api/capabilities`.
- [x] Keep credentials on the backend; bound inputs and handle sanitized timeout/auth/rate-limit errors and stale fallback.
- [x] Preserve original titles/languages and detail alternative titles; metadata language stays separate from playback audio.
- [x] Debounce, abort and reject late search responses; keep Enter-to-search-by-mood.
- [x] Add shared remote metadata lookup and remembered metadata for details/playback/watchlist/history.
- [x] Return `in_model` membership, keep the model bounded and omit unsupported personal scores/explanations.
- [x] Show an unavailable state for local similar recommendations on unindexed titles.
- [x] Detect capability separately; static and curated builds use snapshot/saved-title search.
- [x] Keep source selection independent of metadata availability.

## Expected files

`backend/catalog.py`, `backend/app.py`, `scripts/build_tmdb_catalog.py`, `frontend/app.js`, `frontend/viewing.js`, API/cache/search tests, dependency/config changes only as needed.

## Acceptance

- [ ] A remote film absent from the snapshot can be searched, opened, saved and offered to an enabled source without a false personalized score.
- [x] Pagination, stale-response rejection and offline fallback pass API/client tests.
- [x] Public capabilities and errors do not return credentials.
- [x] Static search makes no live capability/search requests in contract tests; existing player tests pass.
- [x] Live searches left the trained snapshot at 447 films; discovery stays separate from similarity matrices.

## Validation evidence (20 October 2026)

- Full pytest suite: **50 passed**, including seven JavaScript catalogue cases and 17 playback/preferences cases invoked through the suite.
- Live search: two pages of **Batman**, 20 results each, nine pages reported.
- Live details: **Sintel**, TMDB **45745**, outside the snapshot (`in_model=false`), with English and Hindi metadata requests.
- Client integration against the local API: remote search/details and saved watchlist metadata restoration all passed.
- Page 501 returned HTTP 422. The model stayed at **447** movies before and after live searches.
- Browser acceptance remains: visually inspect search controls and remote details, select a source for a remote film, save it and refresh. No browser is attached to automation; HTTP/contract evidence does not establish rendered UI behavior.

The updated preview runs at `http://127.0.0.1:8000`. Existing `.env` credentials were used without printing their values. No new credential is currently needed.

## Demo

Find a permitted film outside the snapshot, open its details, select a source and save it. Demonstrate a cached lookup during an upstream failure and the static deployment's snapshot behavior.
