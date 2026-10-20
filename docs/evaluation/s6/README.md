# S6 release-candidate evidence

Recorded 20 October 2026 on `feature/streaming-platform`; candidate `0.4.0-rc.1`. No hosted deployment.

## Automated results

- `python -m pytest -q --tb=short`: **143 passed**. Includes seven S6 policy/API/export/cache cases; the Node player wrapper now contains 29 cases, including three S6 configuration/permission/missing-bootstrap regressions.
- `python scripts/export_static.py`: model and public playback bootstrap generated successfully; model approximately **1,287 KiB**.
- `node scripts/check_release_browser.cjs --recorded 2026-10-20`: six scenarios passed; see [machine-readable results](browser.json).
- Headless Microsoft Edge on Windows, desktop 1440x900 and emulated mobile 390x844. These are Chromium layout checks, not physical-phone or Safari/Firefox tests.

| Scenario | Result | Evidence |
|---|---|---|
| Backend desktop | Passed | [Player](backend-desktop-player.png), [filters](backend-desktop-filters.png) |
| Backend mobile | Passed | [Player](backend-mobile-player.png), [filters](backend-mobile-filters.png) |
| Static desktop | Passed | [Player](static-desktop-player.png), [filters](static-desktop-filters.png) |
| Static mobile | Passed | [Player](static-mobile-player.png), [filters](static-mobile-filters.png) |
| Restart with all providers disabled | Passed; explicit unavailable state, picks and stored likes retained | [Details](backend-disabled-sources.png) |
| Restart with saved source disabled | Passed; enabled default at next open, resume retained, history removal preserves watchlist | [JSON](browser.json) |

Each desktop/mobile flow checks automatic snapshot search, details, like, Watch, watchlist, error without failover, keyboard source switching, one iframe, wrong-origin/stale-frame rejection, resume/autoplay URL parameters, pause guidance, Escape/focus boundaries, no horizontal overflow, close disposal, refresh persistence, Start over, trailer replacement and recent-playback empty states. Desktop/mobile player screenshots were visually inspected. Backend credentials are empty; static mode falls back after API 404s. Live search and dynamic/external recommendations retain their deterministic tests and previously recorded S4/S5A-S5D evidence.

Movie metadata here is Inception (TMDB 27205); **external movie/trailer frame loads are blocked**. Progress/error messages are synthetic. Black frames are intentional. Results verify the parent application and URL/state contracts, not actual video/audio, native fullscreen, captions, autoplay, redirects or in-player resume accuracy.

## Remaining acceptance

1. **Received 21 October 2026:** owner relevance rating **2/2 overall** in [S5D review](../s5d-review.md). No per-pick or baseline scores supplied.
2. **Received 21 October 2026:** owner replied **"everything works well"** to the requested live-playback exercise. General functional sign-off recorded in [live validation](../../streaming/PLAYBACK_VALIDATION.md). Film actually used, source-specific outcomes, device/browser/country and explicit autoplay result remain unrecorded.
3. Current provider terms and content permission basis before public offering; integration documentation does not establish rights to indexed films.
4. S7 creates the Render service and repeats acceptance at its public HTTPS URL.

S6 implementation, automated checks and owner functional sign-off are recorded. Detailed playback provenance and public-offering/hosted checks remain open; the general responses are not expanded into individual media outcomes or quantitative human metrics.
