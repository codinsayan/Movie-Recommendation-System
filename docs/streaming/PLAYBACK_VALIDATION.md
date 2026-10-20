# Playback validation record

Date: 20 October 2026. Branch: `feature/streaming-platform`.

## Implemented preview

CineSrc, VidLink and VidSrc adapters, the player overlay, manual source selector, browser-local progress/preference storage, Continue Watching, independent Watchlist, and explicit catalogue identities are implemented. Source errors and timeouts show recovery text and leave the selected source unchanged.

CineSrc is the default and has user-confirmed movie playback. The user reported sandbox errors from VidLink and VidSrc, then explicitly requested unsandboxed movie embeds. The sandbox attribute has been removed and all three providers are enabled; player-message origin and window checks remain active. The user confirms that the sources now work after this change; detailed autoplay and resume checks remain pending. Playback reports do not establish catalogue-wide availability or content rights.

## Evidence collected

| Check | Result |
|---|---|
| Existing and new pytest suite | 98 passed; includes S5 ranking/eligibility, curated/TMDB parity, catalogue/cache/API checks and preference-restoration integration |
| JavaScript playback contracts | 26 passed using Node's test runner without external network requests, including autoplay, source-menu keyboard behavior, preference migration and persistent local state |
| JavaScript catalogue contracts | Seven passed: pagination, response ordering, language changes, static fallback and remote metadata restoration |
| Live S4 discovery | Batman pages 1/2 returned 20 results each; Sintel (TMDB 45745) details loaded in English/Hindi outside the model; saved metadata restored; model stayed at 447 movies |
| JavaScript syntax | Checked all new modules and `app.js` |
| API smoke check | Healthy; default catalogue returns 447 movies, all with explicit TMDB mappings |
| Static assets | Providers, player, viewing store and app scripts returned HTTP 200 |
| Static export | Generated model includes catalogue identities; existing Python/JS recommendation parity checks passed |
| Live external movie playback | User confirms the sources work after removing the sandbox. Autoplay-on-switch and the redesigned menu require a new browser check. Film IDs, device and detailed resume behavior not yet recorded |
| Desktop/mobile visual and keyboard checks | Pending; no browser is available through the attached browser automation tool |

Tests simulate provider events and a small DOM surface. They verify contract/lifecycle behavior; they do not render a browser or verify a third-party player. S5 now offers opt-in recommendations from measured viewing intervals and a device-local recent-playback filter. See [evaluation](../EVALUATION.md) for the proxy results, informal relevance review and remaining acceptance checks.

## Manual verification to collect

Run `python run.py --no-browser` and open `http://127.0.0.1:8000` in the target browser. Use a film with an established permission basis and record its TMDB ID. For each candidate:

- [ ] Record browser/device, region, film ID, date and permission basis.
- [ ] Confirm the source actually plays video and audio.
- [ ] Confirm the source selector remains visible and usable on failure or a silent frame.
- [ ] Manually change sources and verify that only one player remains active.
- [ ] Verify reported progress resumes after a source change and refresh, where supported.
- [ ] Verify Start over, Remove from history and Watchlist independently.
- [ ] Close playback, open a trailer, and check that the previous movie stops.
- [ ] Check mobile layout, fullscreen, captions, keyboard focus and autoplay behavior.
- [ ] Record ads/redirects, missing callbacks or provider restrictions accurately.

| Candidate | Movie/device/region | Playback | Progress/resume | Notes |
|---|---|---|---|---|
| CineSrc | Film/device details pending | User-confirmed playback | Pending | Default source |
| VidLink | Film/device details pending | User confirms sources work after sandbox removal | Pending | Manually selected alternative |
| VidSrc .sh | Film/device details pending | User confirms sources work after sandbox removal | Pending | Manually selected alternative |

The movie iframe now omits the sandbox attribute following the user's explicit compatibility request. Cross-origin browser isolation still applies; player messages must match the exact configured provider origin and active iframe window. Standard embeds permit provider behavior previously restricted by the sandbox, including popup/navigation behavior subject to browser controls.
