# S6: Deployment and release validation

Status: planned. Depends on [S1-S5](README.md#delivery-sequence).

## Outcome

Release a usable movie discovery/player experience with manual source selection and recorded end-to-end evidence.

## Work

- [ ] Deploy FastAPI and the frontend together for the full live-search experience. Retain GitHub Pages as a clearly scoped snapshot demo if desired.
- [ ] Configure allowed provider/frame origins and required player permissions from the selected registry. Use standard unsandboxed movie embeds per the user's explicit compatibility choice; retain HTTPS, fixed provider origins and incoming message validation.
- [ ] Keep keys server-side and persist the metadata cache appropriately for the selected host. Browser viewing state remains local until a separately planned account feature.
- [ ] Add provider enable/disable configuration. A removed provider disappears from future choices; an active failure shows a message and waits for viewer selection.
- [ ] Check desktop/mobile layout, fullscreen, captions where offered, keyboard/focus behavior, browser autoplay restrictions and player disposal.
- [ ] Add targeted automated tests for lifecycle, source selection and state isolation. Mock external responses/events in CI and keep real-network playback exercises separate.
- [ ] Run the existing recommender/API/parity suite, the new focused checks and static export validation.
- [ ] Record a permitted-film playback matrix for both selected sources, devices, target region, progress transfer and observed failures. Confirm the permission basis and current provider terms for the content offered publicly.
- [ ] Update README, architecture and changelog around the actual shipped capabilities, including static versus backend differences.
- [ ] Document rollback: disable an affected source or revert the player release while retaining the working recommendation site and viewing-state schema compatibility.

## Expected files

Deployment configuration, `.github/workflows/pages.yml` if required, provider configuration, `README.md`, `CHANGELOG.md`, `docs/ARCHITECTURE.md`, and playback-validation evidence created during S1.

## Release acceptance

- [ ] Movie search -> details -> Watch movie -> manual source selection -> close works in the deployed environment.
- [ ] Errors and silent frames leave the selector usable. No error, timeout or hidden retry changes the source automatically.
- [ ] One movie iframe is active; previous movies cannot update the current player's state.
- [ ] Resume/history/watchlist and recommendations behave according to S3/S5 acceptance criteria.
- [ ] Missing sources, unavailable movies and unavailable backend capabilities have clear user-facing states.
- [ ] Existing checks pass and recorded live evidence supports the published feature claims.

## Demo

Search, watch, manually switch, refresh/resume, save a film and inspect a personalized recommendation. Repeat in the static demo and explain its snapshot-search limit. Stop at an explicit unavailable state when every chosen source fails.
