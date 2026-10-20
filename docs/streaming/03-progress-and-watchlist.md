# S3: Resume, Continue watching and watchlist

Status: code implemented; live/browser acceptance pending. Depends on [S2](02-player-and-manual-switching.md). Next: [S4](04-search-and-catalogue.md). Evidence: [validation record](PLAYBACK_VALIDATION.md).

## Outcome

Viewing state survives refresh, manual source changes can resume where supported, and saving a movie is independent of liking it.

## Work

- [x] Create `frontend/viewing.js` with versioned, browser-local storage and namespaced movie identities; unknown schema versions start a fresh viewing session without touching taste.
- [x] Store preferred provider, position, duration, update time and completion state. Resume state stays independent; S5 adds measured watched-interval evidence for opt-in ranking.
- [x] Save valid progress periodically, on pause and before disposing a player; handle storage failure without interrupting playback.
- [x] On manual source change, snapshot the last valid position before disposal and pass it through the new adapter's supported resume parameter.
- [ ] If the next source cannot resume, say that playback will restart. Do not promise exact continuity across different film cuts or audio editions.
- [x] Add Resume/Start over choices, Continue watching and remove-from-history actions.
- [x] Add a separate Watchlist action and row; keep the existing love-based My List behavior.
- [x] Keep taste, watchlist and individual history removal separate. Accounts and cross-device sync remain deferred.
- [x] Persist catalogue-specific likes/dislikes and mood in browser storage; migrate existing likes once and restore taste before the first recommendation request. Show an actual storage-write failure as session-only state.

## Expected files

`frontend/viewing.js`, `frontend/player.js`, `frontend/providers.js`, `frontend/app.js`, relevant markup/styles and persistence tests.

## Acceptance

- [ ] Refresh restores the correct movie's last position and preferred enabled source.
- [ ] Choosing another source transfers a valid timestamp where supported. A disabled preference falls back to the default when opening a player, without replacing an already active source automatically.
- [x] Reject negative/non-finite times and implausible durations; validate incoming numeric values before storage.
- [ ] Pause, seek and background-tab inactivity do not create false completion events or movie dislikes.
- [ ] Scrubbing to the end does not count as watching the whole movie. History may record the end position while preference strength uses watched intervals.
- [ ] Watchlist changes do not implicitly like/dislike films. History deletion does not erase taste.
- [x] Storage denial/corruption falls back to session-only state in offline tests.

## Demo

Watch part of a film, manually change sources, refresh and resume. Save a different film to Watchlist without liking it, then clear viewing history while retaining taste preferences.
