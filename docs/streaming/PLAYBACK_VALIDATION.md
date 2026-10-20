# Playback validation record

Date: 20 October 2026. Branch: `feature/streaming-platform`.

## Implemented preview

CineSrc, VidLink and VidSrc adapters, the player overlay, manual source selector, browser-local progress/preference storage, Continue Watching, independent Watchlist, and explicit catalogue identities are implemented. Source errors and timeouts show recovery text and leave the selected source unchanged.

CineSrc is the default and has user-confirmed movie playback. The user reported sandbox errors from VidLink and VidSrc, then explicitly requested unsandboxed movie embeds. The sandbox attribute has been removed and all three providers are enabled; player-message origin and window checks remain active. The user confirms that the sources now work after this change; detailed autoplay and resume checks remain pending. Playback reports do not establish catalogue-wide availability or content rights.

## Evidence collected

| Check | Result |
|---|---|
| Existing and new pytest suite | S6: 143 passed, including external preferences, dynamic retrieval, sparse ranking, evaluation, curated/TMDB parity, cache/API and release-policy checks |
| JavaScript playback contracts | S6: 29 passed within the pytest wrapper, including autoplay requests, keyboard behavior, local state, provider-disable rollback, permissions and missing bootstrap; no external video dependency |
| JavaScript catalogue contracts | Seven passed: pagination, response ordering, language changes, static fallback and remote metadata restoration |
| Live S4 discovery | Batman pages 1/2 returned 20 results each; Sintel (TMDB 45745) details loaded in English/Hindi outside the model; saved metadata restored; model stayed at 447 movies |
| JavaScript syntax | Checked all new modules and `app.js` |
| API smoke check | Healthy; default catalogue returns 447 movies, all with explicit TMDB mappings |
| Static assets | Providers, player, viewing store and app scripts returned HTTP 200 |
| Static export | Generated model includes catalogue identities; existing Python/JS recommendation parity checks passed |
| Live external movie playback | Prior user confirmation after sandbox removal; actual autoplay/resume and film/device/region details still pending. The menu's parent-app DOM behavior passes S6 checks |
| Desktop/mobile visual and keyboard checks | S6: real headless Edge at 1440x900 and 390x844, backend/static modes; six scenarios pass including provider disable/recovery. [JSON/screenshots](../evaluation/s6/README.md). Actual media frames deliberately blocked |

Deterministic player tests simulate provider events and a small DOM surface. S6 separately renders the real parent app in headless Edge using blocked media frames and synthetic messages. Neither establishes actual third-party media playback. S5 offers opt-in recommendations from measured viewing intervals and a device-local recent-playback filter. See [evaluation](../EVALUATION.md) for proxy results, informal relevance review and remaining checks.

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

## S6 live-media acceptance matrix

The S6 browser exercise uses Inception **metadata only**, blocked provider frames and synthetic events. It does not establish playback. For live checks, use **Sintel (2010), TMDB 45745**, subject to availability, and retain the full credit scroll. Blender Foundation publishes Sintel under CC BY 3.0 and specifies the attribution/credit conditions on its [Sharing page](https://durian.blender.org/sharing/) and [About page](https://durian.blender.org/about/). This permission reference applies to that film, not the rest of an embed provider's catalogue. The player unit fixture was corrected to the same canonical ID in S6.

| Source | Film | Browser/device/country/date | Audio/video | Switch/refresh resume | Actual autoplay | Native fullscreen/captions | Failures/redirects | Permission/provider terms |
|---|---|---|---|---|---|---|---|---|
| CineSrc | Sintel 45745, planned | Pending | Prior informal playback confirmation; film unspecified | Pending | Pending | Pending | Pending | Film reference above; provider/content offering terms pending |
| VidLink | Sintel 45745, planned | Pending | Prior informal playback confirmation; film unspecified | Pending | Pending | Pending | Pending | Film reference above; provider/content offering terms pending |
| VidSrc | Sintel 45745, planned | Pending | Prior informal playback confirmation; film unspecified | Pending | Pending | Pending | Pending | Film reference above; provider/content offering terms pending |

Primary-source documentation checked 20 October 2026: [CineSrc integration](https://cinesrc.st/docs) and [VidLink integration](https://vidlink.pro/) were retrievable. The [VidSrc documentation URL](https://vidsrc.sh/vidsrc/docs/) could not be retrieved through the research tool in this run; this is not evidence of a provider outage. Consulted integration pages describe embeds, not proof of distribution permission for every indexed title. Current terms/permission acceptance remains open, as do actual fullscreen/captions, region/device behavior and the S5D human relevance review. No final public-release claim is made from the automated checks.
