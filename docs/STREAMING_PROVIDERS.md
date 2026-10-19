# Streaming provider directory and failover research

Researched: 20 October 2026. This supplements [the project feasibility assessment](STREAMING_FEASIBILITY.md).

**Current product decision:** the viewer switches sources manually. Follow [the S1-S6 implementation roadmap](streaming/README.md). The automatic failover section below is retained as earlier research and is outside the chosen implementation scope.

## What this list establishes

This is a research directory, not an enabled production source list. It contains **18 candidates with readable published interface information** and **22 additional entries whose current interface could not be verified**. These are domain/service entries, not 40 independently verified servers. Movie playback, India availability, actual price limits, advertising behavior, source independence and distribution permissions were not tested or established.

Some pages explicitly advertise free access; others document public embeds without establishing all access or pricing conditions. Self-published uptime, quality, catalogue size and no-ad claims are not treated as measured facts. A failed research-browser fetch is not evidence that a service is offline.

## Candidates with published interface information

The linked provider pages are the evidence for the claims below. Brand names across different domains are not independently authenticated.

| # | Candidate and source | Published interface / relevance | Free-access evidence and limitations |
|---|---|---|---|
| 1 | [VidLink](https://vidlink.pro/) | TMDB movie/TV embeds; anime IDs; start position; progress and player-event messages | Public embed examples; full commercial terms and limits not established. Page says it scrapes other sites |
| 2 | [VidSrc-branded: vidsrc.sh](https://vidsrc.sh/vidsrc/docs/) | TMDB/IMDb embeds; progress; resume; title availability lookup | Advertises free embeds without signup/key; brand ownership and actual coverage unverified |
| 3 | [CineSrc](https://cinesrc.st/docs) | TMDB embeds; selected server; resume; player commands and explicit error messages | Presented as a free streaming API; premium-source token option also documented |
| 4 | [VidNest](https://vidnest.fun/) | TMDB movies/TV; anime; initial-server selection; start position and progress tracking | Public embed examples; complete fee/ad-free-play conditions not established |
| 5 | [VixSrc](https://vixsrc.to/) | TMDB/IMDb embeds; catalogue list; audio-language parameter; progress events and start position | Public embed examples; complete fee conditions and territorial availability not established |
| 6 | [SuperEmbed / MultiEmbed](https://superembed.stream/) | TMDB/IMDb multi-host player; documents a VIP-player availability check | Explicitly advertises free/no registration; acknowledges its own and upstream popup ads. MultiEmbed is its documented player endpoint, not an extra independent provider |
| 7 | [EmbedWave](https://embedwave.cc/) | TMDB wrapper with selectable upstream sources | Advertises free/no signup/no key/no ads; these claims were not playback-tested |
| 8 | [AutoEmbed: autoembed.app](https://autoembed.app/) | TMDB/IMDb movie/TV embeds and initial-server selection | Advertises free streaming links; actual operation and operator relationship to other AutoEmbed domains unverified |
| 9 | [AutoEmbed: autoembed.co](https://autoembed.co/) | Separate TMDB/IMDb embed routes; describes crawling third-party links | Public auto-embed documentation; complete access terms and relationship to .app unverified |
| 10 | [2Embed-branded: 2embed.stream](https://www.2embed.stream/) | TMDB/IMDb movie/TV embeds and alternate iframe route | Explicitly advertises free use with possible popup ads. Page warns some metadata IDs do not have actual content |
| 11 | [VidAPI](https://vidapi.xyz/) | TMDB/IMDb movie/TV embeds; JSON endpoints marked coming soon | Explicitly advertises free links; do not rely on future JSON APIs |
| 12 | [VidSrc-branded: vidsrc.to](https://vidsrc.to/) | TMDB/IMDb embeds; latest-content lists; subtitle options | Advertises free links. Relationship to other VidSrc operators unverified |
| 13 | [VidSrc-branded: vidsrc.pk](https://vidsrc.pk/) | TMDB/IMDb player, source lists and published API information | Advertises free/no key/no signup. Backend independence unverified |
| 14 | [VidSrc-branded: vidsrc.link](https://vidsrc.link/) | TMDB/IMDb embeds and latest-content API information | Public no-key embed documentation; current playback and operator identity unverified |
| 15 | [VidSrc-branded: vid-src.top](https://vid-src.top/) | TMDB/IMDb movie/TV embed interface | Advertises free embeds; independence from other similarly named sites unverified |
| 16 | [Videasy-branded: videasy.ws](https://videasy.ws/docs.html) | TMDB/IMDb embeds; progress messages; start position | References a custom domain and VidSrc domains in its own documentation. Do not assume it is videasy.net or an independent source pool |
| 17 | [EmbedMaster](https://embedmaster.com/) | IMDb/TMDB player builder; multiple hosts; external API integration | Describes free video hosts and paid ad-free plays. Not established as entirely free for every feature |
| 18 | [VidRock](https://vidrock.net/) | Indexed provider page documents TMDB/IMDb embeds and movie/TV lists | Search-indexed text was readable, but direct opening returned no extractable body. Full access conditions and progress/error behavior need verification |

Do not import all these domains as an automatic priority order. Entries 12-16 in particular may provide less independent coverage than their count suggests. Entries 1-5 have useful published control/event interfaces for a first engineering evaluation; this is a ranking by documentation suitability, not measured playback reliability.

## Additional entries requiring verification

No API paths are invented for these entries. Keep them disabled until their current documentation, free-access terms and actual permitted-film playback are checked.

| # | Entry / domain investigated | Research result |
|---|---|---|
| 19 | VidFast — `vidfast.pro` | Redirected to `vidfast.vc`; no readable documentation extracted |
| 20 | Videasy — `videasy.net` / `player.videasy.net` | Main site/docs requests did not yield usable documentation; do not substitute .ws as proof of identity |
| 21 | VidKing — `vidking.net` | Research-tool request inaccessible |
| 22 | PrimeSrc — `primesrc.me` | Page title identified an embed service; no readable interface documentation extracted |
| 23 | VidZee — `vidzee.wtf` | Page title identified a streaming API; no readable provider documentation extracted |
| 24 | Embed.su — `embed.su` | Retrieval returned 502 |
| 25 | 2Embed — `2embed.cc` | Research-tool request inaccessible; relationship to .stream not verified |
| 26 | MoviesAPI — `moviesapi.club` | Retrieval returned 502 |
| 27 | Vidora — `vidora.su` | Retrieval timed out |
| 28 | VidBinge — `vidbinge.dev` | Research-tool request inaccessible |
| 29 | RiveStream — `rivestream.org` | Retrieval returned 502 |
| 30 | Gomo — `gomo.to` | Retrieval returned 502 |
| 31 | FilmKu — `filmku.stream` | Research-tool request inaccessible |
| 32 | VidPlus — `vidplus.to` | Retrieval timed out |
| 33 | SmashyStream — `smashystream.com` | Research-tool request inaccessible |
| 34 | Frembed — `frembed.cc` | Research-tool request inaccessible; current free-versus-paid terms unresolved |
| 35 | SuperflixAPI — `superflixapi.com` | Research-tool request inaccessible |
| 36 | ezvidapi — `ezvidapi.com` | Search index advertises free multi-provider failover; direct retrieval returned 502 |
| 37 | VidSrc-branded — `vidsrc.su` | Loading page only; no usable interface documentation extracted |
| 38 | VidSrc-branded — `vidsrc.vip` | Retrieval returned 502 |
| 39 | Upstream — `upstream.to` | Homepage and API requests inaccessible; do not confuse with unrelated upstream.so |
| 40 | Vidstream — `vidstream.pro` | Research-tool request inaccessible; generic name also used for other services |

## File hosts are a different category

These services can be useful when you already have authorized files or provider file IDs. Their documented upload APIs do not mean a TMDB ID will automatically locate a movie:

- [VOE](https://voe.sx/api-1-reference-index): authenticated file upload, information, embedding and subtitle management.
- [MixDrop](https://mixdrop.ag/api): upload/remote-upload, file status and returned embed URLs.
- [Streamtape-branded API page](https://strtape.tech/api): file-hosting API and documented player-control integration; confirm the current operator domain before use.
- [FileMoon-branded documentation](https://filemoon.org/en/api-docs): authenticated owned-file management and authorized remote imports. Operator continuity with historical FileMoon domains is not established here.

These hosts are not counted in the 40 catalogue-service entries above. Uploading the same permitted film to independent hosts could provide redundancy, but requires storage/retention planning, title-to-file mapping and checking each host's current free limits.

## Failover design for Cinemagic

### What can and cannot be detected

For cross-origin iframe players, the parent cannot inspect the internal video element or assume that frame navigation means successful playback. MDN explains that iframe `load` fires even when content fails to load and that iframe `error` events are not fired for this purpose. Source: [iframe event behavior](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe#error_and_load_event_behavior).

Use each provider's documented player messages and availability API where available. CineSrc explicitly documents `cinesrc:error`; VidLink, VixSrc, VidNest and the reviewed VidSrc-branded service document playback/progress interfaces. These schemas are different and need individual adapters. A page returning HTTP 200, a catalogue listing, or an availability response alone does not prove segments will play for a particular viewer.

Absence of playback events is ambiguous: the user may not have pressed Play, autoplay may be blocked, or the player may not emit events. For providers with no usable failure contract, provide **Try next source** and describe readiness as unknown. Do not promise fully automatic failure detection for every iframe.

### Proposed controller behavior

1. Resolve a movie's allowed sources by canonical movie ID, region, desired audio and content availability. Prefer sources with recent measured success and usable telemetry; separate full films from trailers.
2. Load one player at a time. After the viewer requests playback, track an attempt ID, selected iframe window and exact permitted message origin. Reject mismatched/stale events and malformed payloads.
3. On a documented fatal playback error, save the last valid progress and choose the next eligible source that has not already been tried. Do not rotate because the user paused, sought, opened captions or reached the end.
4. For confirmed active playback that stalls, use documented buffering/progress information, a grace period and a bounded retry policy. Treat missing telemetry as uncertainty and offer manual switching rather than silently looping.
5. Resume on the new source using its documented start-position parameter when supported. Preserve language preference where possible; do not silently substitute another dub. Different cuts/edits may make timestamps imperfect.
6. Limit automatic source changes, then show the provider selector and an actionable unavailable state. Never preload every embed at once: that can multiply network requests, players and ads.
7. Record per-source, per-region and per-title outcomes. Temporarily avoid repeatedly failing sources and periodically retry after a cooldown. Keep provider-wide failures distinct from a missing single title or a single user's network problem.

Initial configuration suggestions, to tune with permitted-film testing: at most three automatic switches per playback attempt, one pass through eligible sources, and a manual switch always available. These are design defaults, not provider requirements or measured optimal thresholds.

### Evidence required before enabling a source

Record provider key, exact origin, documentation URL, accepted movie-ID type, media types, backend family if known, access terms, target territories, audio/subtitle support, availability-check semantics, error/progress message schema, resume parameter, last documentation review, and last successful playback test. Leave unknown capabilities unknown. A working domain should not be labelled a working film source until actual playback is observed.

Build a small permitted-film evaluation set covering target languages, mobile/desktop browsers and regional connections. Record startup success, startup delay, recoverable/fatal errors, progress callbacks, seek/resume behavior and ad/redirect behavior. Use those results to order sources; a long directory alone is not a reliability strategy.

The existing recommender stays independent: it ranks movies and can filter by measured source availability, while the playback controller handles provider selection and switching. Playback errors should not become negative movie-preference signals.

## Status

Research and design only. No provider has been enabled, no stream extractor or proxy added, and no movie playback or automatic-failover claim has been tested in the application. Content permissions and regional coverage remain unresolved for these catalogue services.
