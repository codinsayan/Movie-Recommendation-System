# S6: Release readiness and operational checks

Status: **implemented and automated checks passed; project-owner functional sign-off received 21 October 2026**. Candidate: `0.4.0-rc.1`. S5D received an overall relevance rating of **2/2**; the requested live-playback exercise received **"everything works well"**. Detailed source/device/region evidence and public-offering terms remain unrecorded. No final release, tag, push or deployment is implied. Next: [S7 Render deployment](07-render-deployment.md).

## Outcome

Prepare a tested movie discovery/player release candidate with manual source selection, configurable providers and recorded acceptance evidence for the Render deployment iteration.

## Work

- [x] FastAPI and frontend run together as `0.4.0-rc.1`. GitHub Pages stays a snapshot demo; actual Render deployment is S7.
- [x] One checked-in `frontend/provider-registry.json` defines fixed HTTPS origins, paths, documentation and player permissions. Backend CSP headers and static-bootstrap CSP meta use the enabled registry. Unsandboxed embeds and exact message origin/window/generation checks remain.
- [x] Keys stay server-side. The configured cache path is tested with an actual SQLite write/read. Browser viewing state remains local; hosting storage is S7.
- [x] Provider enable/disable/order configuration; removed choices disappear after restart/reload. Active failures wait for viewer selection. All-disabled and removed-saved-source states preserve browser data.
- [x] Desktop/mobile Chromium layout, keyboard/focus, autoplay requests/pause guidance and disposal checked. Native fullscreen, captions and real autoplay remain in the live matrix below.
- [x] Targeted policy/API/export/cache/rollback tests and player lifecycle/state-isolation contracts; CI mocks external responses/events. Real-network exercises remain separate.
- [x] Full recommender/API/parity/dynamic/scaling/player/static suite: **143 passed**. Static model/policy export succeeds. Six rendered-browser scenarios pass; [evidence and screenshots](../evaluation/s6/README.md).
- [ ] Record a permitted-film playback matrix for both selected sources, devices, target region, progress transfer and observed failures. Confirm the permission basis and current provider terms for the content offered publicly.
- [x] Updated README, architecture and changelog, including static/backend differences and actual acceptance limits.
- [x] Documented provider disable, snapshot-ranking and code rollback without deleting browser storage.
- [x] Record S5D human relevance acceptance: **2/2 overall** on 21 October 2026 in [the review sheet](../evaluation/s5d-review.md); individual ratings were not supplied.

## Expected files

Provider configuration, `.github/workflows/pages.yml` if required, `README.md`, `CHANGELOG.md`, `docs/ARCHITECTURE.md`, and playback-validation evidence created during S1. Render-specific deployment files and hosted evidence belong to S7.

## Release acceptance

- [x] Search -> details -> Watch -> manual selection -> close works in local backend and static candidates; repeat against the public Render URL in S7.
- [x] Error/timeout tests leave the selector usable and never switch automatically. Real-browser checks cover error recovery; deterministic tests also cover silent timeouts.
- [x] One movie iframe; stale or wrong-origin messages cannot alter the active player.
- [x] Automated state/recommendation contracts cover S3/S5/S5A-S5D, external preferences and dynamic candidates. New DOM checks cover refresh, Start over, trailer replacement and history/watchlist independence. Owner relevance and general playback sign-off received 21 October; detailed media-resume provenance remains unrecorded.
- [x] Explicit missing-source/unavailable-title states; snapshot fallback/backend capability messaging remains covered.
- [ ] Existing checks pass and recorded live evidence supports the published feature claims.

## Demo

Search, watch, manually switch, refresh/resume, save a film and inspect a personalized recommendation. Repeat in the static demo and explain its snapshot-search limit. Stop at an explicit unavailable state when every chosen source fails.

## Configuration and rollback

Operational flags are **process environment variables**, not entries read from the private TMDB `.env`. PowerShell examples:

```powershell
# Remove VidLink from new choices after server restart and browser reload.
$env:CINEMAGIC_PROVIDERS = 'cinesrc,vidsrc'
python run.py --no-browser

# Static demo: export with the same environment, then publish frontend/.
python scripts/export_static.py

# Snapshot-only recommender rollback; stored choices are retained.
$env:CINEMAGIC_RANKING = 'snapshot'
```

Unset `CINEMAGIC_PROVIDERS` restores CineSrc, VidLink and VidSrc in that order. An explicitly empty value disables movie playback while retaining recommendations, search, details and trailers. Unknown/duplicate IDs or arbitrary URLs fail startup. The first enabled entry is the default unless the browser has an enabled saved preference. A removed saved source falls back at the **next open**, retaining its position. Configuration never silently replaces an active movie. Restart the server and reload existing tabs; configuration is not pushed into open tabs. Static hosting needs a new export.

Some PowerShell versions remove empty environment variables. A portable all-disabled example is:

```powershell
python -c "import os,uvicorn; os.environ['CINEMAGIC_PROVIDERS']=''; uvicorn.run('app:app',app_dir='backend',host='127.0.0.1',port=8000)"
```

`/api/playback` and `/playback-config.js` expose only public policy. HTML/scripts revalidate; the backend policy bootstrap is `no-store`. `frontend/playback-config.js` is the generated, committed default for a plain static checkout. Edit the registry and regenerate with `python scripts/export_static.py`. The export includes model and public policy, never `.env` or SQLite. Static frame restrictions use a bootstrap CSP meta element; the backend additionally sends the same policy as an HTTP header. This constrains frames created by the app, not a provider's internal player implementation.

Disable an affected source first. For a complete player rollback, serve a previously verified code revision and re-export its static assets; **do not delete browser storage**. S6 changes no viewing schema-2 records under `cinemagic:viewing:v1`, preference-v2 profiles, identities or feature contracts. Dynamic ranking rollback is `CINEMAGIC_RANKING=snapshot`; unsupported external choices remain pending under existing contracts. Metadata SQLite remains a derived schema-1 cache; `CINEMAGIC_CACHE_PATH` selects its writable location. S7 decides hosting storage.

## Reproduce verification

```powershell
python -m pytest -q
python scripts/export_static.py
node scripts/check_release_browser.cjs --recorded 2026-10-20
```

Browser checks need Node 22+ with global WebSocket and installed Edge/Chrome/Chromium (`CHROMIUM_PATH` override). They start isolated localhost servers on 8126/8127, use a temporary browser profile, empty credentials, and block external movie/trailer frames. Results/screenshots go to `docs/evaluation/s6/`. Close conflicting test servers first. CI runs deterministic tests, export and syntax checks; the installed-browser exercise is recorded separately. New live retrieval was not repeated for this policy change; prior S5D evidence remains linked.

**Acceptance update, 21 October 2026:** S5D overall human relevance acceptance and S6 general playback sign-off are recorded. The owner reported no playback problems. The detailed film/source/device/region matrix, explicit actual-autoplay result and current provider terms/permission checks remain unrecorded in [live validation](PLAYBACK_VALIDATION.md); the general reply is not converted into fabricated individual passes. These remain limits on final public-release acceptance. No Render files or hosted results were added; S7 is the next implementation phase.
