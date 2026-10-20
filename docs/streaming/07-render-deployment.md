# S7: Full-project deployment on Render

Status: planned; next implementation phase. Depends on [S6 release readiness](06-release.md), following [S5A-S5D](README.md#dynamic-recommendation-upgrade). S1-S5D and S6 code are implemented; S6 automated checks pass as `0.4.0-rc.1`. On 21 October 2026 the owner rated relevance 2/2 overall and reported that the requested playback exercise works well. Detailed source/device/region evidence and public-offering terms remain unrecorded. No Render configuration, service or hosted verification has been created yet.

## Outcome

Deploy the frontend, FastAPI API, dynamic recommendation engine with its starter snapshot, and live TMDB discovery as **one Render Python Web Service under one HTTPS URL**. Movie video continues to load from the selected provider. Keep GitHub Pages as the separately scoped snapshot demo.

Start with Render Free for the college demo. Render documents idle spin-down after 15 minutes, a subsequent startup delay, and loss of local file changes on restart/redeploy/spin-down. This is acceptable for a disposable metadata cache; it is not persistent database hosting. A paid service with a persistent disk is an optional later choice, not a requirement for the demo. Sources checked 20 October 2026: [FastAPI deployment](https://render.com/docs/deploy-fastapi), [free-service limits](https://render.com/docs/free), [persistent disks](https://render.com/docs/disks).

## S7.1: Prepare and validate the deployment package

- [ ] Add a `render.yaml` Blueprint for one Python Web Service. Keep the repository root as the working directory so backend data and frontend assets are both included.
- [ ] Choose an explicitly tested deployment branch/commit. The current streaming work is on `feature/streaming-platform`; selecting an older `main` must not silently deploy the pre-streaming project.
- [ ] Specify a supported Python version, reproducible runtime dependencies and required build steps. Keep model/data files and frontend assets in the deploy; exclude credentials, local caches and development artifacts.
- [ ] Include the committed starter snapshot and compatible browser export. Do not fetch a live catalogue during build. Runtime dynamic retrieval/feature caching uses the private TMDB credential, S5A-S5D contracts and measured resource budgets.
- [ ] Validate startup with the hosting command below, not the localhost-only `python run.py` launcher. Verify `/api/health`, `/`, static assets, recommendation routes and catalogue capabilities.
- [ ] Run the current full regression suite and static export. Record the tested commit and results before deployment.

Planned settings, to be verified during implementation:

| Setting | Value |
|---|---|
| Service type | Web Service |
| Runtime | Python |
| Plan | Free demo instance |
| Root directory | Repository root |
| Build command | `pip install -r requirements.txt && python scripts/export_static.py` |
| Start command | `uvicorn app:app --app-dir backend --host 0.0.0.0 --port $PORT` |
| Health-check path | `/api/health` |
| Dataset | `CINEMAGIC_DATASET=tmdb` |
| Demo cache path | `CINEMAGIC_CACHE_PATH=/tmp/cinemagic/catalogue.sqlite3` |

## S7.2: Configure and deploy the service

- [ ] Connect the GitHub repository to the user's Render account and select the tested deployment branch/commit.
- [ ] Configure the existing `TMDB_READ_ACCESS_TOKEN` as a Render secret, or use `TMDB_API_KEY` instead. Never place credential values in the Blueprint, commit, build output or frontend export.
- [ ] Configure dataset, cache path and the provider settings established in S6. Keep the chosen provider order and manual switching behavior.
- [ ] Deploy and record the service URL, deployed commit, plan, Python version, region and deployment date. Verify that the deployed commit includes S1-S5, accepted S5A-S5D work, S6 and the empty-filter banner fix.
- [ ] Check build/startup logs and health checks. Confirm that the recommender fits the selected instance and that live search can reach TMDB without exposing credentials in errors.
- [ ] Keep the free-instance cache disposable. If persistent caching is deliberately selected later, attach a paid-service disk and set the cache path inside its mount; preserve the cache schema and test restart recovery.

Browser profiles are still stored locally. Redeploying at the same origin should preserve them, but localhost, GitHub Pages and the Render URL have separate storage. A new Render URL will start with a new device profile; no account migration or cross-device synchronization is introduced.

## S7.3: Verify the public deployment and document recovery

- [ ] Verify the public HTTPS URL serves the actual API and all scripts/styles/posters. Confirm the TMDB token and `.env` are not exposed as public assets.
- [ ] Search for an unindexed movie, load another result page, open details, save to Watchlist and refresh. Confirm live capabilities and cached fallback match S4.
- [ ] Run search -> details -> Watch movie -> manually choose another source -> close. Record provider/device/region/film evidence in [PLAYBACK_VALIDATION.md](PLAYBACK_VALIDATION.md); local playback reports do not establish hosted-origin compatibility.
- [ ] Verify only one player is active and errors/timeouts leave source selection to the viewer. Check fullscreen/captions where supported, autoplay restrictions, desktop/mobile layout and keyboard/focus behavior on the deployed origin.
- [ ] Verify device-local likes, mood, Watchlist, resume and S5 options survive refresh and a redeploy at the same origin. External preferences must resolve and influence dynamic ranking under S5A-S5D. Old resume positions must not become fabricated viewing signals.
- [ ] Verify both S5 switches with no qualifying evidence: the strict Top Picks row explains the empty result, the banner offers labelled broader suggestions, and Show all picks disables only the recent-playback filter.
- [ ] Verify missing credentials and upstream failures preserve snapshot recommendations and honest discovery error states.
- [ ] Exercise a free-instance cold start and cache reset. Record the observed startup delay; an erased metadata/feature cache must not erase browser-local preference IDs or Watchlist. Exercise bounded feature rehydration and honest pending states for external preferences.
- [ ] Document rollback to a known-good Render deployment/commit and provider-disable recovery using S6 configuration. Preserve browser storage compatibility and keep the snapshot demo usable.
- [ ] Update the README with the verified public URL, actual service settings, deployment evidence and known limitations. Mark this iteration complete only after these hosted checks pass.

## Expected files

`render.yaml`, Python/runtime dependency configuration as needed, `.env.example`, deployment smoke checks, `README.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`, this iteration and the live validation record. Change `run.py` only if necessary; local development must keep working.

## Required inputs at implementation time

A Render account connected to the GitHub repository, the selected deployment branch/commit, and the existing TMDB credential configured privately in Render. Free hosting is the planned starting point; a paid plan/disk or custom domain is a separate deployment choice.

## Completion evidence

A working HTTPS URL and deployed commit; passing build/regression/export/health checks; hosted search/player/state acceptance records; documented free-tier/cache behavior; and a practical rollback procedure. Record what was observed rather than treating configuration files as proof of a successful deployment.

Commit each completed subphase using `codinsayan` as sole author, without co-author trailers. Documentation-only planning does not mark deployment as complete.
