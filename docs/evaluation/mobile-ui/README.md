# Mobile UI review — 21 October 2026

Reviewed home, search, movie details, player/source menu, My Taste (top and bottom), and How it works at **320×640, 390×844, 560×844, 768×900 and 1440×900**. Screens were rendered with headless Edge in an isolated temporary browser profile. Movie/trailer frames were blocked; this checks the app layout and controls, not actual media playback or physical-device/Safari behavior.

## Changes

- Phone banners size to their content, keep the title below navigation, and give the primary action a full row. Secondary actions wrap consistently without overlapping the mood strip.
- Moods use a single horizontally scrollable row on phones. Section descriptions wrap below titles; onboarding gives touch instructions instead of hover/keyboard instructions on touch devices.
- Larger phone navigation, details/player actions, source options and close controls; search inputs use 16px text, with space reserved beneath navigation for the expanded search field.
- Smaller movie-detail posters, balanced action rows, two-column related movies, and wrapping metadata/explanation bars.
- My Taste uses the available phone width, a sticky heading/close button, larger checkbox labels, visible remove controls and wrapping footer actions.
- Help cards stack in one readable column. Toasts stay within the phone width, with safe-area spacing at the bottom.

## Verification

- **154 pytest tests passed**, with the existing upstream TestClient deprecation warning.
- **Six browser scenarios passed** in backend/static desktop/mobile modes and provider-disable recovery, including source selection, focus/menu behavior, one-frame lifecycle, URL resume/autoplay requests and likes/watchlist/resume persistence across refresh. [Interaction record](browser.json). Third-party frames were blocked and progress/errors were synthetic.
- **95 geometry checks passed across 35 screen/viewport combinations**: no page or inspected-content horizontal overflow, banner/navigation/mood separation, phone action heights, 16px expanded search text, touch onboarding copy and reachable sticky close controls after scrolling. [Layout record](layout.json).
- The existing browser regression runner supports `--output-dir` so a new run does not overwrite historical S6 evidence. Independent scenarios clear local storage before the new app document boots, then remove that initializer before the refresh exercise; refresh-persistence assertions remain active.

Reproduce the existing browser interaction checks with:

```powershell
node scripts/check_release_browser.cjs --recorded 2026-10-21 --output-dir .s7-local/mobile-regression
```

An initial multi-width screenshot run timed out during a capture; the remaining widths were rerun successfully with explicit viewport captures. A later regression run exposed saved source state carrying between scenarios; the runner now resets storage in the new document before app initialization, rather than clearing an inherited blank document's origin. These were verification-runner issues; no source-selection or persistence behavior was relaxed in the app.

## Reviewed screens

| Screen | Capture |
|---|---|
| Home, 390px | [home.png](home.png) |
| Hosted search after thumbnails load, 390px | [search.png](search.png) |
| Movie details, 320px | [details.png](details.png) |
| My Taste after scrolling, 320px | [taste.png](taste.png) |
| Player/source menu, 390px | [player.png](player.png) |
| Help, 390px | [how.png](how.png) |

## Published deployment

Commit **`6b935301d6776b153d2de8abf825dfc34eaa9fb3`** was published on `fix/mobile-layout` and fast-forwarded to main, authored and committed solely as **codinsayan**. Both [main release checks](https://github.com/codinsayan/Movie-Recommendation-System/actions/runs/39520364596) and [branch release checks](https://github.com/codinsayan/Movie-Recommendation-System/actions/runs/39520364666) succeeded; [Pages deployment](https://github.com/codinsayan/Movie-Recommendation-System/actions/runs/39520364548) succeeded too.

Render deploy **`dep-dbc093jrjlhs73abtbvg`** reached **live** at **05:48:29 IST on 21 October 2026** at **https://cinemagic-trbu.onrender.com**. **74 hosted live checks passed** for that exact revision: [hosted-smoke.json](hosted-smoke.json). The hosted CSS/JavaScript matched the committed files after line-ending normalization; a post-deploy error-level query returned no entries. The service stays Free/Singapore with manual deployment.

All seven screens were also rendered on the hosted origin at **390×844**, with no measured page/content horizontal overflow and the sticky My Taste close control reachable after scrolling. Home, search, loaded movie details and the scrolled profile were visually inspected. [Hosted layout record](hosted-layout.json). The checker waits for live details to finish loading before using movie actions; these captures still block media frames and use an isolated browser profile.

The earlier owner confirmation of live Render playback/refresh persistence remains recorded in [S7 evidence](../../deployment/RENDER_VALIDATION.md). This UI review does not expand that report to other devices or providers.
