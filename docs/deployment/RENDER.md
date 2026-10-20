# Render deployment runbook

S7 package prepared on 21 October 2026. Cloud service creation and hosted acceptance are separate from local validation; no public URL exists in this repository yet.

## What the owner needs

1. Sign in to [Render](https://dashboard.render.com/) and connect GitHub with access to `codinsayan/Movie-Recommendation-System`.
2. Use the updated `main` branch containing the streaming/S7 work. On 21 October the owner explicitly authorized publishing the feature branch, merging to `main`, and deploying. The deployment configuration now targets `main`; verify the GitHub revision before importing the Blueprint.
3. Have the existing **TMDB API Read Access Token** ready. Enter it privately into Render's `TMDB_READ_ACCESS_TOKEN` secret prompt. Do not put it in chat, GitHub, `render.yaml` or the frontend. This is the long Read Access Token, not an account password. An API-key alternative can be set manually as `TMDB_API_KEY` instead.

No domain, paid disk, account system or separate frontend/backend hosting is required for the planned demo.

## Import the prepared Blueprint

In Render, create a **Blueprint**, connect the repository above, and select **main** as the Blueprint branch. Use the root `render.yaml`. Review the concrete configuration before creating resources:

| Setting | Prepared value |
|---|---|
| Service | One Python Web Service named `cinemagic` |
| Plan / region | Free / Singapore (change before creation if desired) |
| Branch | `main` |
| Root directory | Repository root; leave blank in the dashboard |
| Python | `3.13.5`, selected by `.python-version` |
| Build | `pip install --no-cache-dir -r requirements-runtime.txt && python scripts/export_static.py` |
| Start | `uvicorn app:app --app-dir backend --host 0.0.0.0 --port $PORT --workers 1` |
| Health | `/api/health` |
| Metadata cache | `/tmp/cinemagic/catalogue.sqlite3`, disposable |
| Catalogue / ranking | `tmdb` / `dynamic` |
| Movie sources | `cinesrc,vidlink,vidsrc`, manual selection |
| Automatic redeployment | Off; later deploys are explicit |
| Secret | `TMDB_READ_ACCESS_TOKEN`, prompted privately (`sync: false`) |

The initial Blueprint creation provisions/deploys the service. Disabling automatic redeployment does not turn that initial creation into a dry run. Leave the plan Free; this package creates no database or persistent disk. The service name is a requested name, not a claim that any particular `onrender.com` URL is available.

Wait for the build and health check. Record the resulting HTTPS URL and the deployed **full Git SHA** shown by Render. Confirm that `main` includes the streaming/S7 merge; a page loading alone does not prove it is the full backend.

References checked 21 October 2026: [Blueprint fields/secrets](https://render.com/docs/blueprint-spec), [Python selection](https://render.com/docs/python-version), [FastAPI hosting](https://render.com/docs/deploy-fastapi).

## Verify the actual service

Run from the tested project environment, substituting the real URL and full SHA:

```powershell
python scripts/smoke_deployment.py https://YOUR-SERVICE.onrender.com --expected-commit FULL_40_CHARACTER_SHA --live --wait-seconds 120 --output docs/deployment/hosted-smoke.json
```

`/api/deployment` reports only the public release and Render's commit identity. The checker rejects an unexpected commit, a static HTML fallback in place of the API, a missing/mismatched model export, exposed private paths and failed live search. `--live` checks Batman result pages 1/2, Sintel details/external preference resolution and a dynamic recommendation request with that preference. Partial/unavailable discovery fails the live check even if fallback recommendations remain usable. Use a non-live run to check the documented credential-free snapshot fallback; it does not establish live discovery.

The checker makes metadata/API requests, never loads third-party movie video, extracts streams or modifies a browser profile. It does not create server-side user taste. Its JSON evidence contains public deployment/capability information, not credentials. Keep real failures recorded and retry after fixing their cause; do not replace an unavailable discovery result with a success claim.

Complete the S7.3 browser checklist in [the iteration plan](../streaming/07-render-deployment.md): live search, details, external like/dislike, Watchlist and refresh, manual source changes, close/resume, both viewing switches, mobile/keyboard/fullscreen/captions. Record film/source/browser/device/country and the public origin in [playback validation](../streaming/PLAYBACK_VALIDATION.md). Local owner sign-off does not establish hosted-origin compatibility. Share the **public service URL** in chat for the hosted checks; no login credentials are needed here.

## Restarts and rollback

The Free service can sleep after 15 idle minutes and loses runtime filesystem changes on restart/redeploy/spin-down. The metadata and sparse-feature caches can rebuild. Likes, dislikes, progress and Watchlist remain in the viewer's browser at the same origin. Localhost, GitHub Pages and Render have separate browser storage; this iteration does not migrate profiles between them. See [Render's Free-service behavior](https://render.com/docs/free).

For a source incident, change `CINEMAGIC_PROVIDERS` to the passing subset and restart/redeploy; reload existing tabs. Errors in an active player continue to wait for manual selection. For a ranking incident use `CINEMAGIC_RANKING=snapshot`. Preserve local storage. If the service is Blueprint-managed, update the tracked configuration too so a later sync does not restore the incident setting.

Use Render's deployment history to select a verified working commit/deployment. Confirm the resulting SHA with `/api/deployment` and rerun the smoke check. If dashboard rollback is unavailable for the selected plan/account, use **Manual Deploy -> Deploy a specific commit** when offered, or deploy a reviewed revert commit on the configured branch. Actual account-specific rollback controls and cold-start delay are recorded during S7.3, not assumed from this runbook.

Do not rotate the TMDB credential merely because a derived cache was erased. Change a secret privately if it is actually compromised; never paste its value into logs. No secret is required for the static GitHub Pages demo, which remains available independently.
