# S6: Release readiness and operational checks

Status: planned. Depends on [S1-S5 and the inserted S5A-S5D upgrade](README.md#delivery-sequence). Complete [S5D acceptance](05d-dynamic-evaluation.md) before implementing this phase. Next: [S7 Render deployment](07-render-deployment.md). Hosting setup and final public-URL verification are tracked in S7.

## Outcome

Prepare a tested movie discovery/player release candidate with manual source selection, configurable providers and recorded acceptance evidence for the Render deployment iteration.

## Work

- [ ] Verify FastAPI and the frontend run together as a release candidate. Retain GitHub Pages as a clearly scoped snapshot demo; actual Render deployment is S7.
- [ ] Configure allowed provider/frame origins and required player permissions from the selected registry. Use standard unsandboxed movie embeds per the user's explicit compatibility choice; retain HTTPS, fixed provider origins and incoming message validation.
- [ ] Verify keys stay server-side and the metadata cache accepts a configurable writable path. S7 selects disposable or persistent hosting storage. Browser viewing state remains local until a separately planned account feature.
- [ ] Add provider enable/disable configuration. A removed provider disappears from future choices; an active failure shows a message and waits for viewer selection.
- [ ] Check desktop/mobile layout, fullscreen, captions where offered, keyboard/focus behavior, browser autoplay restrictions and player disposal.
- [ ] Add targeted automated tests for lifecycle, source selection and state isolation. Mock external responses/events in CI and keep real-network playback exercises separate.
- [ ] Run the recommender/API/parity suite, S5A-S5D dynamic-preference/retrieval/scaling checks, focused player checks and static export validation.
- [ ] Record a permitted-film playback matrix for both selected sources, devices, target region, progress transfer and observed failures. Confirm the permission basis and current provider terms for the content offered publicly.
- [ ] Update README, architecture and changelog around the actual shipped capabilities, including static versus backend differences.
- [ ] Document rollback: disable an affected source or revert the player release while retaining the working recommendation site and viewing-state schema compatibility.

## Expected files

Provider configuration, `.github/workflows/pages.yml` if required, `README.md`, `CHANGELOG.md`, `docs/ARCHITECTURE.md`, and playback-validation evidence created during S1. Render-specific deployment files and hosted evidence belong to S7.

## Release acceptance

- [ ] Movie search -> details -> Watch movie -> manual source selection -> close works in the release-candidate environment; repeat against the public Render URL in S7.
- [ ] Errors and silent frames leave the selector usable. No error, timeout or hidden retry changes the source automatically.
- [ ] One movie iframe is active; previous movies cannot update the current player's state.
- [ ] Resume/history/watchlist and recommendations behave according to S3/S5 and S5A-S5D acceptance criteria, including external likes/dislikes and dynamic candidates.
- [ ] Missing sources, unavailable movies and unavailable backend capabilities have clear user-facing states.
- [ ] Existing checks pass and recorded live evidence supports the published feature claims.

## Demo

Search, watch, manually switch, refresh/resume, save a film and inspect a personalized recommendation. Repeat in the static demo and explain its snapshot-search limit. Stop at an explicit unavailable state when every chosen source fails.
