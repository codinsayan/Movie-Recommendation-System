# Cinemagic: movie playback feasibility and upgrade plan

Research date: 20 October 2026. Branch: `feature/streaming-platform`, created from `main` at `0b6576d`.

**Implementation plan:** [streaming implementation roadmap](streaming/README.md). The latest user decision is manual source selection, with CineSrc as the default and VidLink/VidSrc as alternatives. CineSrc playback is user-confirmed. Movie iframes are now unsandboxed at the user's request after the other two sources rejected sandboxed playback; revalidation is pending. Earlier automatic-switching proposals are not part of the current scope.

## Recommendation

Cinemagic can become a movie discovery and watching website while retaining its hybrid recommender. Start with a broad metadata catalogue, a smaller verified collection playable inside the site, and regional provider links for other titles. Offer separate **Watch here** and **Where to watch** actions so users can tell what is actually playable.

This research did not establish a legitimate, unrestricted, free integration supplying every commercial movie. Content availability, permission to embed, territory, language, and licence dates are separate constraints. A video hosting service also does not supply a movie catalogue or its distribution rights.

The current milestone is analysis and planning. This branch adds this report; application behavior has not been changed.

## What the code currently supports

| Area | Observed implementation | Consequence for the upgrade |
|---|---|---|
| API | `backend/app.py`: FastAPI serves metadata, recommendations, similar titles, health and model stats, then the frontend | Keep this application and add provider, playback and progress services |
| UI | `frontend/app.js`: vanilla JavaScript, movie modal, search, taste controls and YouTube trailer iframe | Reuse the existing interface; add a dedicated movie player and availability states |
| Catalogue | Committed TMDB snapshot has **447 movies**, all with trailer IDs; curated fallback has **60** | These are metadata and trailer references, not full-film sources; trailer IDs were counted, not individually playback-tested |
| Search | `buildRows()` searches loaded titles, tags and genres, displaying at most 30 results per row | Add paginated server search and on-demand metadata ingestion for titles outside the snapshot |
| Ranking | TF-IDF content, TMDB recommendation graph or simulated ratings, vote-weighted quality, MMR diversity | Keep the ranking signals and add availability constraints and viewing events |
| Persistence | Likes and dislikes are stored in browser `localStorage`; the API is stateless | Add durable profiles, watchlists and progress for cross-device use |
| Delivery | GitHub Pages exports model vectors and computes full similarity matrices in the browser | Keep a static demo if useful; a production API is needed for secrets, accounts and partner integrations |
| Catalogue builder | Samples most-voted/popular films, requests English metadata, filters by minimum votes, lacks stored original-language/region fields | Expand discovery and preserve original titles, languages, alternate titles and country metadata |

The TMDB graph is a useful recommendation signal, but it is not collaborative filtering trained on this application's own viewers. The curated fallback uses 600 synthetic users. Explain these distinctions in the project report.

### Scale and identity issues to address early

`backend/recommender.py` creates dense `content_sim` and `collab_sim` matrices. `frontend/engine.js` reconstructs both through `gram()`. Their space requirement grows quadratically: at 100,000 titles, those two float64 matrices alone require approximately **160 GB** in decimal units, before graph and feature storage. The content feature matrix is also densified, and graph construction starts with a dense identity matrix.

For a large catalogue, keep sparse features and graph neighbours, retrieve a bounded candidate set, and calculate similarity only for candidates. Preserve MMR and explanations at the final ranking stage. Expanding the JSON snapshot alone will not solve catalogue scale.

Curated IDs and TMDB IDs currently share the same integer shape, while tastes persist independently of the active dataset. Use an internal movie key plus explicit external IDs, and version or migrate saved preferences. Provider matching should use verified external IDs rather than title-only matching.

## Streaming source research

### The requested sites

Direct research-browser requests to `https://net77.cc/home` and `https://movies2watch.tv` returned retrieval errors. This does **not** establish that either site is offline. Their current player behavior, backend servers, ownership and licensing could not be verified.

Search results also contained similarly named mirrors and promotional pages. Those are insufficient evidence of a site's identity, content rights or permission to integrate. No verified developer agreement or supported playback API for the two requested domains was established in this research. Treat their suitability as unresolved; do not make them a core project dependency on that evidence.

Likewise, a generic movie iframe service accepting TMDB IDs is not evidence that its catalogue is licensed. Before adopting any source, establish who provides the films, what integration is permitted, which territories are covered, and how availability and playback events work. This is a provider-selection requirement, not a claim that a particular unverified site has been legally adjudicated.

### Practical alternatives

| Source | Free viewing / cost distinction | Playback inside Cinemagic | Assessment |
|---|---|---|---|
| Internet Archive | Many films are freely accessible; rights must be checked per item and target territory | Archive documents an embedded player | Good for a curated collection; never assume every upload is public domain |
| Official rights-holder YouTube uploads | Viewing may be free and ad-supported; eligibility varies by video | Supported through the YouTube player when embedding is enabled | Useful for approved full films; keep trailers and full films as separate source types |
| Blender open movies | Selected films have explicit reuse licences | Can provide a documented demonstration film using a permitted source | Strong first demo: *Sintel* has a first-party CC BY 3.0 statement; preserve credits and required attribution |
| Plex | Free ad-supported viewing exists; partner terms are separate | A **draft** AVOD partner guide describes direct playback | Potential later partnership; not a ready, anonymous, free embed API |
| Tubi | Consumer viewing is free and ad-supported | A generally available third-party playback integration was not established here | Use verified regional watch links unless separately authorized; do not assume India coverage |
| TMDB / JustWatch availability | Metadata access and commercial terms are separate from movie viewing | Supplies availability information, not full-film streams | Add regional discovery and provider links alongside playable sources |
| Cloudflare Stream | Paid storage/delivery; does not license films | Hosts video you have permission to distribute | Suitable if hosting your own licensed library; unnecessary for an embed-only first version |

Internet Archive documents embedding, but also explicitly says it cannot guarantee uploader-provided rights information. Preserve evidence for each chosen film rather than importing an entire collection as cleared content. Sources: [embedding guide](https://archivesupport.zendesk.com/hc/en-us/articles/360018377531-Movies-and-Videos-Tips-Troubleshooting), [rights guidance](https://archivesupport.zendesk.com/hc/en-us/articles/360017808151-Movies-and-Videos-A-Basic-Guide).

YouTube's player API supports playback state and progress integration; embedding can be disabled by the owner. A working embed is not sufficient evidence that an uploader owns the film. Prefer verified rights-holder channels and retain the official player. Sources: [IFrame API](https://developers.google.com/youtube/iframe_api_reference), [Sintel licence statement](https://durian.blender.org/about/).

Plex's proposed integration requires partner credentials, server-side authentication, supported DRM playback, ads and timeline reporting. Its page is explicitly marked as a draft for feasibility review. Access, India coverage and commercial terms require confirmation with Plex before implementation. Sources: [partner guide](https://catalogs-docs.plex.tv/avod-direct-playback-partner-guide/), [consumer catalogue FAQ](https://support.plex.tv/articles/frequently-asked-questions-vod/).

Tubi explains its ad-supported model. Its international support page reviewed here lists several markets but does not list India. This is a reason to verify target-market availability, not a guarantee about every future country rollout. Sources: [free viewing explanation](https://tubitv.com/help-center/About-Tubi/articles/4409975158043), [international support](https://tubitv.com/help-center/About-Tubi/articles/4409969055259.).

TMDB's watch-provider endpoint returns country-specific streaming, rental and purchase availability. It requires JustWatch attribution and returns a TMDB watch-page URL rather than full provider deep links. Separately, TMDB describes its API as free for attributed non-commercial use and directs commercial projects to its sales team. Sources: [watch providers](https://developer.themoviedb.org/reference/movie-watch-providers), [API FAQ](https://developer.themoviedb.org/docs/faq).

Cloudflare Stream currently lists storage at $5 per 1,000 minutes of capacity per month, purchased in blocks, and delivery at $1 per 1,000 minutes. As an illustration, 1,000 complete views of a 120-minute movie mean 120,000 delivered minutes, or $120 in delivery at that rate, before storage and other project costs. This is an estimate, not a quotation or content-licensing cost. Source: [Stream pricing](https://developers.cloudflare.com/stream/pricing/).

## Proposed application design

Keep FastAPI and the current frontend for the first version. A framework rewrite is not required to add playback.

Use SQLite for a local prototype, with a migration path to PostgreSQL for hosted accounts and concurrent users. Model these separately:

- **Movies:** internal ID, TMDB/external IDs, titles, original language, genres, cast, year and metadata refresh time.
- **Playback sources:** movie ID, provider ID, provider asset ID, embed/hosted/partner/link mode, full-film/trailer type, audio/subtitle languages, territory and availability window, attribution and rights evidence, last check and health status.
- **User state:** profile, likes/dislikes, watchlist, progress and playback events. Keep resume position separate from preference strength.

Suggested endpoints, to implement in a later milestone:

- `GET /api/search?q=...&page=...`: paginated movie discovery with language and genre filters.
- `GET /api/movies/{id}/availability?region=IN`: verified playback options and external provider availability.
- `POST /api/playback/sessions`: validate the source and availability; return an approved embed or short-lived playback configuration.
- `PUT /api/me/progress/{movie_id}`: save resume position and actual watched duration.
- Extend `POST /api/recommend` with region, languages and a `watch_here_only` option.

Public embeds can load directly from their provider. Keep provider secrets and partner signing on the backend. For hosted films, deliver video from storage/CDN rather than routing all video bytes through FastAPI. Only resolve approved provider assets; avoid an arbitrary user-supplied URL proxy.

The player should handle fullscreen, captions where provided, loading/error states, source expiry and resume. Implement progress using the chosen player's supported API. An arbitrary cross-origin iframe does not let the parent app inspect playback position; Archive progress support must be verified before promising resume for that source. External provider links cannot reliably report movie completion to Cinemagic.

## Recommendations over playable movies

1. Discover candidate titles using the existing content and graph signals.
2. Apply region, licence window, language and playback-health eligibility **before selecting the final top-k**. Filtering an already truncated recommendation list can leave too few results.
3. Blend the existing relevance signals with carefully evaluated viewing signals, then apply diversity ranking and explanations.
4. Keep explicit likes/dislikes strongest initially. Completion and repeat viewing can be weak positive signals; clicking Play or briefly abandoning a buffering video should not automatically become a like/dislike.
5. Add **Recommended and playable now**, **Continue watching**, and **Because you watched** rows. Label external availability separately from in-site playback.

Retain the existing explanations. Evaluate ranking quality with impressions and actual viewing events, not only clicks. Progress should use watched intervals as well as playhead position so seeking to the end is not treated as watching the whole film.

## Delivery milestones

1. **Playback proof:** add one clearly licensed demonstration film, a source registry, Watch here button and player error handling. Validate actual playback on desktop and mobile.
2. **Discovery:** add regional watch-provider lookup, caching, required attribution, broader search and explicit unavailable states. Default to India only as a stated product assumption, and allow region selection.
3. **Personal viewing:** durable progress, separate watchlists, optional accounts and availability-aware recommendation filtering. Verify that watched signals improve results before giving them substantial weight.
4. **Catalogue growth:** multilingual discovery, scheduled source refresh, sparse candidate retrieval and database-backed pagination. Add partner catalogues only after access and terms are confirmed.

For the college project, the strongest first scope is searchable movie discovery plus a verified free-to-watch collection, with the recommender ranking that collection and linking out for other films. This delivers real playback without promising universal commercial-film coverage.

## Follow-up: VidSrc-style embed services

The requested category is a **catalogue embed service**: an app supplies a TMDB/IMDb ID and receives a third-party player. This differs from a file host, which needs an uploaded video or a provider-specific file ID. Research below checks published documentation, not successful movie playback, licensing, uptime or geographic coverage.

| Service / exact domain reviewed | Published capabilities or observed result | Evidence limits |
|---|---|---|
| VidSrc-branded `vidsrc.sh` | Advertises free movie/TV iframe embeds with TMDB/IMDb IDs, no key/signup, subtitle controls, resume position, progress events and an availability lookup | Documentation was retrievable; brand ownership across similarly named domains and content rights were not independently verified |
| VidLink `vidlink.pro` | Documents movie/TV embeds using TMDB IDs, anime via MyAnimeList IDs, customization, resume position and progress/player events | Its page explicitly describes scraping other websites; this does not establish distribution rights, catalogue completeness or reliable playback |
| EmbedWave `embedwave.cc` | Advertises a free, no-signup TMDB embed wrapper with selectable upstream sources and no ads | Those are provider claims; advertising behavior and independence of upstream sources were not tested |
| Videasy-branded `videasy.ws` | Documents TMDB/IMDb iframe playback, subtitles, start position and progress messages | Its own text refers to a custom domain and official VidSrc domains; do not assume this is the operator of `videasy.net` or an independent backup |
| VidFast `vidfast.pro` | Request redirected to `vidfast.vc`; research browser extracted no documentation | Insufficient evidence to verify its current integration features |
| Upstream `upstream.to` | Homepage and API-documentation request were inaccessible to the research tool | Current API, upload workflow and pricing remain unverified; do not confuse this domain with the separate `upstream.so` multistreaming product |
| Vidstream `vidstream.pro` | Homepage was inaccessible to the research tool | A generic player label such as Vidstream does not uniquely identify an operator or supported API |

Sources: [VidSrc-branded documentation](https://vidsrc.sh/vidsrc/docs/), [VidLink documentation](https://vidlink.pro/), [EmbedWave](https://embedwave.cc/), [Videasy-branded documentation](https://videasy.ws/docs.html). These are self-published descriptions, not independent endorsements.

For this codebase, TMDB-addressed embeds fit the existing 447-film metadata snapshot technically. Keep the recommender independent of the playback provider, with a provider adapter, separate full-film/trailer actions, a visible provider selector and explicit playback failure states. Validate progress messages against the selected iframe's origin, window and expected payload before saving them. Similar branding or multiple player domains does not prove independent underlying servers.

No source in this follow-up was established as providing rights-cleared access to all commercial films. Before public deployment, establish permission for the films and territories being offered. The next engineering evaluation would need actual permitted-film playback checks on the intended devices and region, plus checks for ads/redirects, subtitle/audio coverage, availability accuracy and working progress callbacks.

The expanded [provider directory and failover research](STREAMING_PROVIDERS.md) records 18 candidates with published interface information, 22 additional entries requiring verification, file-host distinctions, and a proposed playback switching controller.

## Validation

Existing suite: **36 passed**, including API behavior, recommendation behavior, metadata normalization and Python/JavaScript parity. The initial sandboxed runs hit temporary-directory access errors; the complete suite passed outside that restriction using:

```powershell
python -m pytest -q -p no:cacheprovider --basetemp D:\Projects\Recommender_Sytem_College\.test-tmp-streaming-audit --tb=short
```

These tests validate the existing application. They do not establish full-film playback, provider rights, production scalability or end-to-end browser behavior. No production streaming integration has been implemented or playback-tested in this milestone.
