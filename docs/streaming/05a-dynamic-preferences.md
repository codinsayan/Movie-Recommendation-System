# S5A: Likes and dislikes for newly discovered movies

Status: planned. Depends on [S4 discovery](04-search-and-catalogue.md) and [S5 viewing signals](05-recommendations.md). Next: [S5B dynamic discovery](05b-dynamic-discovery.md). This is a design plan; external preferences do not influence the current engine yet.

## Outcome

A like or dislike for a movie outside the trained snapshot becomes an explicit taste input once usable metadata is resolved. The first milestone still ranks the existing snapshot; S5B adds new recommendation candidates. No full retraining is required for each newly rated movie.

## Work

- [ ] Define a versioned preference-resolution contract using canonical movie keys, feature-version identifiers and applied/pending/unavailable states. Preserve existing browser-local profiles and separate curated IDs from TMDB IDs.
- [ ] Save the preference immediately in the browser. Resolve new TMDB IDs through the backend's validated metadata service and cache; never expose the API credential or accept arbitrary upstream URLs.
- [ ] Fetch complete feature metadata rather than treating a search summary as a trained representation. Reuse genres, keywords, overview, director and cast where available.
- [ ] Centralize feature normalization so snapshot and remote titles use the same genre names, keyword/person normalization and weighting. Separate feature language from the viewer's display-language choice.
- [ ] Transform external metadata with the existing fitted TF-IDF vocabulary without refitting the entire catalogue. Explicitly handle missing metadata, unfamiliar words and zero vectors; use measured structured overlap where supported rather than inventing similarity.
- [ ] Build positive and negative taste profiles from resolved explicit preferences. Dislikes exclude the exact film and apply a calibrated similarity penalty; they do not automatically ban its whole genre. A conflicting dislike wins.
- [ ] Use content and quality when collaborative information is unavailable, with honest component availability and weight normalization. Metadata similarity is not individual user-rating evidence.
- [ ] Update Taste DNA, explanations and "Because you loved" sources to include resolved external likes; count unresolved preferences separately instead of claiming they already affect ranking.
- [ ] Bound concurrent metadata requests and per-request work. Keep unresolved preferences pending and process them incrementally; do not silently discard saved preferences to meet a request budget.
- [ ] Deduplicate feature work by canonical ID and feature version. Reject late responses after a preference is removed, reversed or superseded; the final profile must reflect the latest explicit choice.
- [ ] Keep metadata failures separate from taste: retain the preference, show pending/unavailable status and retry through bounded requests. Existing recommendations and playback must remain usable.
- [ ] Define static fallback precisely: use compatible cached metadata and exported feature transforms where available. Unresolved titles stay pending offline; static mode cannot privately fetch fresh TMDB metadata.

## Expected files

`backend/catalog.py`, `backend/recommender.py`, a shared feature/profile module if useful, `backend/app.py`, `frontend/preferences.js`, `frontend/catalogue.js`, `frontend/engine.js`, `frontend/app.js`, static-export configuration and focused preference/parity tests. Keep the existing snapshot as a fallback.

## Acceptance

- [ ] A fixture movie absent from the snapshot changes recommendations after being liked, without a catalogue rebuild or growth of the original similarity matrices.
- [ ] Disliking an external film removes that exact candidate wherever encountered and reduces measured affinity to related candidates without creating a genre-wide exclusion.
- [ ] Unknown IDs, metadata timeouts, missing keywords, new vocabulary and unsupported schema versions have explicit, non-fabricated outcomes.
- [ ] Removing or reversing a preference during lookup cannot resurrect an obsolete taste signal. Multiple external likes/dislikes survive refresh.
- [ ] New explicit inputs remain stronger than S5's optional viewing signal. Source errors, switches and playback failures never become dislikes.
- [ ] Supported Python/browser inputs produce matching profile/scoring behavior. Offline or missing-metadata limitations are visible and documented.
- [ ] Test that the baseline without external preferences remains compatible with existing rankings and browser storage.

## Demo and evidence

Search for a film outside the snapshot, like it, observe its resolution state and changed picks, then dislike or remove it and observe the updated profile. Repeat with an offline lookup and a browser refresh. Record the fixture/live TMDB ID, feature version and before/after ranking; do not claim all metadata lookups always succeed.

Commit this iteration as `codinsayan` only, with no co-author trailers. Complete its acceptance evidence before starting S5B.
