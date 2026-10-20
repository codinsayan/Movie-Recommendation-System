# S7: Full-project deployment on Render

Status: **S7.1 validated; streaming branch published and fast-forward merged into main on 21 October 2026. GitHub release checks and Pages deployment passed.** The owner reports Render/GitHub repository access connected; the Render integration in this session is not installed yet. Service creation, private TMDB secret entry and hosted acceptance remain pending. See [publication evidence](../deployment/GITHUB_VALIDATION.md), [setup runbook](../deployment/RENDER.md) and [package evidence](../deployment/S7_VALIDATION.md).

## Outcome

Deploy the frontend, FastAPI API, dynamic recommendation engine with its starter snapshot, and live TMDB discovery as **one Render Python Web Service under one HTTPS URL**. Movie video continues to load from the selected provider. Keep GitHub Pages as the separately scoped snapshot demo.

Start with Render Free for the college demo. Render documents idle spin-down after 15 minutes, a subsequent startup delay, and loss of local file changes on restart/redeploy/spin-down. This is acceptable for a disposable metadata cache; it is not persistent database hosting. A paid service with a persistent disk is an optional later choice, not a requirement for the demo. Sources checked 20 October 2026: [FastAPI deployment](https://render.com/docs/deploy-fastapi), [free-service limits](https://render.com/docs/free), [persistent disks](https://render.com/docs/disks).

## S7.1: Prepare and validate the deployment package

- [x] `render.yaml` defines one Free Python Web Service at repository root, Singapore, with manual redeployment and no disk/database.
- [x] Blueprint now targets `main` following the owner's explicit authorization to publish and merge the streaming branch on 21 October. `/api/deployment` exposes the public full Render commit SHA for exact hosted verification; confirm the published revision before importing the Blueprint. Original S7.1 validation used the feature branch.
- [x] `.python-version` pins tested Python 3.13.5. `requirements-runtime.txt` pins the full runtime dependency closure; development tools stay in `requirements.txt`. Patched FastAPI/Starlette are validated in a clean environment. Secrets/caches/local validation outputs remain ignored and outside frontend assets.
- [x] Build exports the committed 447-film snapshot and public playback policy without live catalogue fetching. Runtime retrieval/feature hydration remains S5A-S5D.
- [x] Local Uvicorn startup with the same host, one-worker and port configuration passes the real HTTP smoke check, including assets, model parity, recommendations, capabilities, missing-credential fallback and private-path isolation. Linux CI is configured to exercise the literal Blueprint-style CLI after push; an actual Render build is not inferred.
- [x] Clean pinned-runtime regression suite **154 passed**; model/policy export succeeds. Official Render schema validation and Linux wheel resolution pass. [Evidence](../deployment/S7_VALIDATION.md).

Prepared settings; hosted behavior remains to verify:

| Setting | Value |
|---|---|
| Service type | Web Service |
| Runtime | Python |
| Plan | Free demo instance |
| Root directory | Repository root |
| Build command | `pip install --no-cache-dir -r requirements-runtime.txt && python scripts/export_static.py` |
| Start command | `uvicorn app:app --app-dir backend --host 0.0.0.0 --port $PORT --workers 1` |
| Health-check path | `/api/health` |
| Dataset | `CINEMAGIC_DATASET=tmdb` |
| Demo cache path | `CINEMAGIC_CACHE_PATH=/tmp/cinemagic/catalogue.sqlite3` |
| Runtime / region | Python 3.13.5 / Singapore |
| Auto-redeploy | Off; initial Blueprint creation still deploys |

## S7.2: Configure and deploy the service

- [x] Owner reports GitHub connected to Render with access to this repository. Streaming and main were both published at `0755f8f364c7780accc55058e17863a167186ef2`; Blueprint now selects main. The session's separate Render integration remains uninstalled, so service creation is not yet performed.
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

A Render account connected to `codinsayan/Movie-Recommendation-System`, the prepared branch published to GitHub, and the existing TMDB Read Access Token entered privately in Render. No token/password needs to be sent through chat. Free/Singapore is configured; paid storage or custom domains are separate choices. After service creation, provide the public URL and deployed full SHA so hosted checks can run. [Step-by-step setup](../deployment/RENDER.md).

## Completion evidence

A working HTTPS URL and deployed commit; passing build/regression/export/health checks; hosted search/player/state acceptance records; documented free-tier/cache behavior; and a practical rollback procedure. Record what was observed rather than treating configuration files as proof of a successful deployment.

Commit each completed subphase using `codinsayan` as sole author, without co-author trailers. Documentation-only planning does not mark deployment as complete.
