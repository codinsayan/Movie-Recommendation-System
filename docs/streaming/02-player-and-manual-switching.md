# S2: Movie player and manual source switching

Status: code implemented; live/browser acceptance pending. Depends on [S1](01-source-foundation.md). Next: [S3](03-progress-and-watchlist.md). Evidence: [validation record](PLAYBACK_VALIDATION.md).

## Outcome

Users can watch a mapped movie and select another source themselves. The source selector is available throughout playback and on error.

## Work

- [x] Create `frontend/player.js`; integrate it with `frontend/app.js`, `index.html` and `styles.css`.
- [x] Add **Watch movie** to eligible detail views and the appropriate preview/billboard actions. Preserve the separate trailer action and recommendation explanation.
- [x] Add a responsive player overlay containing the title, a labeled Source selector, close control and concise failure/status text. Browser/layout acceptance remains pending.
- [x] Start with the default enabled source. Remembering the viewer's preference is included in the S3 preview.
- [x] On an explicit source selection, dispose the previous iframe and create the selected one. Position transfer is included in the S3 preview.
- [x] On a reported error, show recovery text and keep the existing source selected until the viewer chooses another. A slow player can show a loading hint without changing sources.
- [x] Keep the selector outside the iframe so it is independent of provider telemetry. Show unavailable mapping separately from a playback failure.
- [x] Implement disposal, focus restoration and billboard suspension; rendered-browser verification remains pending.
- [x] Validate message origin, active iframe window, payload shape and player generation. Reject late messages from removed players.
- [x] Load the provider/player scripts in both serving modes without requiring a new backend endpoint.

## Expected files

`frontend/player.js`, `frontend/providers.js`, `frontend/app.js`, `frontend/index.html`, `frontend/styles.css`; focused lifecycle tests and browser checks.

## Acceptance

- [ ] A viewer opens a mapped movie, selects source B, then returns to source A; only one movie iframe exists at each point.
- [x] Simulated source failure updates the message but **does not change the selected provider**. Timers also never change the provider.
- [x] A simulated provider with no telemetry still permits manual selection of another source.
- [x] Frame disposal and delayed-message rejection pass offline lifecycle tests; actual audio/video stop remains a browser check.
- [ ] Keyboard users can operate the selector and close the player. Focus remains usable on mobile and desktop.
- [ ] Existing trailers, likes/dislikes, search, recommendation rows and both serving modes continue working.

## Demo

Search a film in the current snapshot, open Watch movie, simulate a source failure and manually select the alternative. Close the movie and play its trailer. This is the first complete streaming demo milestone.
