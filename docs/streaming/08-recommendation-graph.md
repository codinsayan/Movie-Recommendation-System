# S8: Your movie taste in 3D

Status: **Planned; no implementation started.** Decision date: **21 October 2026**. Extends the deployed S1–S7 application.

## Agreed scope

The owner's latest preference is a small, presentation-friendly graph **based on movies they have liked**. This supersedes the earlier request to open the full network. Open with **My liked movies**; provide an explicit **Show recommendations** action to expand a selected movie. Do not open the 447-film catalogue graph or grow the scene automatically.

The graph appears inside **How it works**, below the three recommendation-signal cards. It is an interactive 3D scene with depth, orbit and zoom. Its coordinates are a visual arrangement of relationships, not learned embedding dimensions or a model confidence scale.

## Presentation experience

1. Open How it works: a dark graph panel titled **Your movie taste in 3D** displays liked films as glowing nodes connected by supported similarities.
2. Drag to rotate; scroll/pinch to zoom. A visible **Reset view** control restores the camera. Provide touch instructions on phones.
3. Select a node: keep it and its connections bright, fade the rest, and show its title, poster, year, genres and an explanation of each displayed connection in a side panel. On phones the information panel stacks beneath the canvas.
4. Select **Show recommendations**: add a small number of current recommended movies related to that selected like. Show which films were already liked and which are recommended. If the engine has no supported connection for a pick, explain that honestly rather than drawing an invented line.
5. Choose **Back to my likes** to remove the expanded recommendations, or **View movie** to enter the existing details flow. Selecting/dragging nodes does not like a movie or start playback.
6. Optional presentation controls: expand the graph panel, gently orbit the camera, pause motion, and pin a selected film. Automatic orbit is opt-in and disabled for reduced-motion preferences.

Use the current dark/red design: red accent or ring for liked films, a distinct accent plus label/icon for recommendations, and a white outline for the selected film. Keep bodies primarily one colour for a readable small graph. Only selected/nearby nodes receive persistent title labels; every film is also reachable from an accessible movie list. Node size is uniform apart from selection emphasis; it does not silently imply popularity or recommendation confidence.

## What the connections mean

| Relationship | Actual evidence | Display rule |
|---|---|---|
| Story/style similarity | Existing TF-IDF feature vectors over genres, tags, people and overview | Inspectable shared traits and content cosine; no edge solely because both films were liked |
| Audience similarity | Existing collaborative vectors from the TMDB recommendation-neighbour graph | Label as an audience-similarity proxy, not this site's real user watch history |
| Direct TMDB relation | An actual recorded TMDB recommendation link, when present | Separate evidence badge/layer; distinguish it from computed cosine similarity |
| Recommended because of a like | Current ranking result's supported `because`/discovery evidence | Connect only the named/supported seed, preserving evidence availability and explanation floor |
| Quality/diversity pick | Current score breakdown or ranking explanation | Show as a recommendation with its real reason; do not fabricate a seed-to-pick edge |

For indexed pairs, reuse the existing `similar()` relationship formula (0.6 content + 0.4 collaborative similarity) where a combined relationship is shown. This differs from the profile ranking's content/collaborative/quality blend; explain the distinction in the inspector. For external films without collaborative vectors, use and label content-only similarity, with unavailable audience evidence represented as unavailable, not fabricated. Line width is relative within the displayed evidence type, not a calibrated probability.

Keep only a few strongest supported links per node above a documented display threshold. The threshold is a readability choice, separate from the ranking/explanation floor, and must not alter recommendations. Deduplicate reciprocal links; omit self-links. Do not force isolated movies to connect. Keep them visible with “No strong connection in this selection.”

## Existing code we can reuse

- `frontend/app.js`: `openHow()`, `openModal()`, `closeModal()`, `modalEpoch`, liked/disliked state and the current recommendation results.
- `backend/recommender.py` and `frontend/engine.js`: content/collaborative similarities, score breakdowns, shared traits and existing similar-movie behaviour.
- `frontend/preferences.js` and `frontend/preference-resolver.js`: device-local choices, per-film external metadata/features and pending/applied states.
- `backend/preferences.py`, `backend/ranking.py` and `backend/discovery.py`: versioned external features, bounded feature cache and `related_to` provenance.
- `scripts/export_static.py` and the static model: data for the browser/offline mode; do not create a second independently fitted recommendation model.

The committed TMDB snapshot currently has **447 movies / 1,275 undirected direct links**. These counts describe the underlying snapshot, not the default visible scene or the entire live TMDB catalogue. Snapshot SHA256 when inspected: `a23e4a0b654634696ccc76fd5957ab4abf9abe01b161064b832d95a88ceab00c`.

## Proposed technical approach

Use **3d-force-graph**, which provides a vanilla-JavaScript Three.js/WebGL force-directed renderer, orbit controls, selection/highlighting and dynamic data updates. Keep the existing FastAPI/vanilla-JS app. Select and pin a released, compatible distribution during S8A; self-host the bundle with its required licence notices, and load it only when the graph is opened. Do not depend on an unversioned external CDN during the presentation.

Create separate graph-data and graph-view modules, for example `frontend/graph-data.js` and `frontend/taste-graph.js`, with a Python graph helper for backend parity. Proposed backend surface: a bounded `POST /api/graph` for the selected liked-film keys. Keep preferences in request bodies and browser storage; do not introduce accounts or a server-side user database. Exact DTO names are finalized in S8A.

The graph contract should carry:

- Version, dataset, feature/ranking version, view mode and selection identity.
- Nodes with canonical keys (`tmdb:45745` / `curated:…`), display metadata, liked/recommended role and applied/pending/unavailable status.
- Links with source/target keys, evidence type, component scores where available, shared traits and provenance.
- Total/displayed counts, declared truncation, pending metadata and stale-result status.

Build pair evidence only for the selected films using the same features as the engine. Server mode reuses its matrices/cache; static mode uses the exported model and available per-film cached records. No extra full-catalogue similarity matrix, graph database or live catalogue crawl is needed.

For expanded recommendations, reuse the current ranking result and its evidence. If additional explanation fields are needed, add an opt-in bounded graph payload to the **same ranking pass**, rather than independently reranking when How it works opens. Label unavailable live discovery in static mode. Graph output must not change ranked items, scores, likes or viewing signals.

Suggested initial display budgets, subject to the S8A prototype:

| Item | Desktop | Phone |
|---|---|---|
| Liked nodes shown initially | All up to 30 | All up to 15 |
| Extra recommendations for a selected like | Up to 5 | Up to 3 |
| Hard scene budget | 50 nodes / 120 links | 25 nodes / 60 links |
| Visible labels | Selected film and highlighted neighbours | Selected film; details in the panel |

For larger profiles, explicitly show “Showing 30 of N likes” and offer movie search/selection; preserve the owner's full profile and allow access to every liked title. Expansion replaces the previous expanded neighbourhood instead of accumulating nodes indefinitely. A zero-like profile prompts the viewer to like movies; a one-like profile shows that node and an explicit recommendation-expansion action.

External liked films are included even when outside the snapshot. Pending metadata stays visible as pending; reuse bounded S5 feature resolution and caches. Do not issue one unbounded upstream request per edge, infer nonexistent audience data or silently omit unresolved likes. Disliked titles are excluded from expanded recommendations; they are not default liked-graph nodes. Viewing history is not silently added to this likes-based view.

## Delivery phases

| Phase | Deliverable | Acceptance |
|---|---|---|
| **S8A — Graph data and renderer proof** | Versioned bounded liked-graph contract; shared evidence rules; local pinned-renderer prototype | Verify known and external liked pairs, missing evidence, exclusions, no self/duplicate links, displayed counts and Python/browser parity where supported. Measure bundle size and a small WebGL scene before committing to effects. Recommendation output remains identical with graph disabled/enabled. |
| **S8B — Interactive liked-movie graph** | Embed graph under How it works; selection, orbit/zoom, reset, legend, movie list/inspector and details navigation | Works for zero/one/many likes and long titles. Correct focus and camera reset. Repeated open/close leaves no animation loop or orphan canvas. Home does not fetch graph libraries. |
| **S8C — Recommendation expansion and dynamic movies** | Explicit small expansion around a selected like using current recommendation evidence; external liked-film support and freshness indicators | A like/dislike change updates the selection/result identity; stale responses cannot repaint a closed/replaced modal. Show unsupported/pending links honestly. Static mode and unavailable upstream paths remain usable. No extra unbounded retrieval or ranking drift. |
| **S8D — Presentation, mobile and release checks** | Expanded presentation view, optional slow orbit, reduced motion, fallback, performance tuning and deployment evidence | Check 320/390px phones, tablet and presentation desktop. Test keyboard/list access, WebGL/context failure and repeated navigation. Verify published exact revision on Render and static Pages, plus a real presentation-device rehearsal. |

**Recommended first milestone:** S8A + S8B. That gives a usable liked-movie graph to present before adding recommendation expansion and presentation polish. Commit each completed phase as **codinsayan**, without co-author trailers, and log observed evidence in `CHANGELOG.md`.

## Mobile, fallback and lifecycle requirements

- Reserve a bounded canvas area and keep page scrolling usable. Enable drag/pinch interaction deliberately; provide an obvious way to leave graph interaction on touch screens.
- The current Three.js WebGL renderer requires WebGL 2. Detect unavailable/lost context and offer a readable connection list or simple 2D focused view with the same evidence; do not leave a blank panel.
- Stop motion while hidden and honour reduced-motion preferences. Cap device pixel ratio, use simple nodes, and avoid loading a poster texture for every node. Start without bloom or animated edge particles; consider them only after measuring presentation hardware.
- `openModal()` / `closeModal()` must dispose graph listeners, pending work and GPU resources. Reuse `modalEpoch`/abort guards so late metadata/library loads cannot recreate a closed scene. Returning from movie details may restore plain camera/selection state, not an abandoned WebGL instance.
- Keep node labels escaped/plain-text. Preserve the existing modal focus boundary, Escape behaviour, source/player cleanup and browser-local profile. Selecting a graph node must never launch an extra movie iframe.

## Suggested presentation walkthrough

Use your existing likes, ideally a small set you can explain. Open How it works → rotate the liked-movie network → select one movie → explain its strongest supported connection → show a few recommendations → inspect the real score/reason → return to the liked graph. Optional slow orbit helps while speaking; pause it when explaining a connection. A temporary labelled demo profile can be added in S8D if useful, without overwriting saved taste.

## Research references

Primary documentation inspected 21 October 2026:

- [3d-force-graph documentation and examples](https://github.com/vasturiano/3d-force-graph): vanilla component, camera controls, highlighting, dynamic updates, pause/resume and image/custom-node options.
- [Upstream package manifest](https://github.com/vasturiano/3d-force-graph/blob/master/package.json): MIT licence and browser distribution entry. Its inspected development manifest reports 1.80.1; resolve an actual released build and dependency compatibility when implementing, rather than treating a development manifest as a pinned release.
- [Three.js WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html): WebGL 2 support, renderer configuration and GPU-resource disposal.

This document is a proposal and phased implementation plan. It adds no renderer, endpoint, dependency, new recommendation model or deployed feature yet.
