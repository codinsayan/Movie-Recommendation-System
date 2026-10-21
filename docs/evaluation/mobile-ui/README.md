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
| Movie details, 320px | [details.png](details.png) |
| My Taste after scrolling, 320px | [taste.png](taste.png) |
| Player/source menu, 390px | [player.png](player.png) |
| Help, 390px | [how.png](how.png) |

The earlier owner confirmation of live Render playback/refresh persistence remains recorded in [S7 evidence](../../deployment/RENDER_VALIDATION.md). This UI review does not expand that report to other devices or providers.
