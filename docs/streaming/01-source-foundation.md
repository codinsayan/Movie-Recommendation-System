# S1: Source contracts and playback proof

Status: code implemented; live provider proof pending. Depends on the existing app. Next: [S2](02-player-and-manual-switching.md). Evidence: [validation record](PLAYBACK_VALIDATION.md).

## Outcome

Establish that the selected candidates can play a small permitted-film set and define how Cinemagic identifies titles and interprets provider events. Choose the initial order from actual evidence.

## Work

- [x] Define a versioned provider registry with key, label, enabled flag, exact allowed origins, documentation URL and supported capabilities.
- [x] Implement CineSrc, VidLink and VidSrc adapters. At the user's explicit request, use standard unsandboxed movie iframes for provider compatibility while keeping message-origin/window validation.
- [x] Give adapters `buildMovieUrl(tmdbId, startSeconds)` and `parseMessage(eventData)` responsibilities. Parsing returns normalized events or ignores unsupported messages.
- [x] Normalize `ready`, `playing`, `paused`, `progress`, `seeking`, `seeked`, `ended` and `error` only when the provider exposes them. Missing capabilities remain unknown.
- [x] Define a canonical reference carrying dataset origin, internal record ID and explicit TMDB ID. Existing TMDB records can derive the TMDB ID from their dataset origin; curated records need a reviewed mapping.
- [ ] Document a small reproducible playback exercise: chosen film IDs, permission basis, browser/device, region, provider, date, play/seek outcome and observed callbacks. Missing titles are recorded rather than counted as success.
- [ ] Verify current no-payment access conditions and embed behavior for the selected sources. Do not label an untested candidate operational.

## Expected files

Create `frontend/providers.js` and focused adapter tests. Extend metadata/export only as needed to make origin explicit. Record live findings in a new `docs/streaming/PLAYBACK_VALIDATION.md` during implementation.

Provider messages are normalized inside the adapter; window/origin validation belongs to the player controller in S2. Do not accept arbitrary domains or user-supplied embed URLs.

## Acceptance

- [x] URL generation accepts a valid mapped TMDB ID and rejects invalid/missing IDs and non-finite resume positions.
- [x] Curated movie ID `1` cannot accidentally become TMDB movie `1`.
- [x] Message fixtures cover valid progress, malformed payloads and unsupported event types.
- [ ] At least one documented playback succeeds on each enabled candidate. A candidate that fails validation stays disabled; a two-source S2 demo requires two passing candidates.
- [ ] Source order and observed limitations are recorded, including differences between documented and observed behavior.

## Demo

Show the same mapped permitted film in each passing candidate and show normalized progress output. No application player UI or automatic switching is required in this phase.
