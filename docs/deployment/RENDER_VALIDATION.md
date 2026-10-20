# S7 Render deployment evidence

Recorded **21 October 2026** (Asia/Kolkata). The owner authorized deployment from `main` on Render Free in Singapore and selected **Sayan's Workspace**.

## Service identity

| Field | Observed value |
|---|---|
| Public origin | https://cinemagic-trbu.onrender.com |
| Dashboard | https://dashboard.render.com/web/srv-dbbvh47f3r2c73fs399g |
| Service ID / name | `srv-dbbvh47f3r2c73fs399g` / `cinemagic` |
| Workspace | Sayan's Workspace |
| Service / runtime | Web service / Python 3.13.5 |
| Compute plan / region | `free` / `singapore` |
| Source branch | `main` |
| Initial source revision | `eae92cebecdc48f135ed9e2eb29e135e19501fd4` |
| Initial deploy ID | `dep-dbbvh4vf3r2c73fs3ba0` |
| Live token-enabled deploy ID | `dep-dbbvi8vf3r2c73fs76hg` |
| Automatic deployment | Off |
| Health-check path | `/api/health` |
| Cache | `/tmp/cinemagic/catalogue.sqlite3`, disposable |

## Access and configuration

The Render plugin was confirmed installed and enabled, but exposed no account operations in this session. The official Render CLI **2.30.0** was downloaded into the ignored local tools directory and its archive digest verified against GitHub release metadata. Browser authorization succeeded. The account/workspace were verified; the workspace initially contained no services, avoiding duplicate creation. `render blueprints validate render.yaml` returned `valid: true` with one planned service.

The service was created directly through the CLI using the committed Blueprint's non-secret build/start commands, health path and environment settings. It is **not attached to a Blueprint**: `render.yaml` remains the reproducible configuration reference. Later configuration changes must be applied to the existing service and reflected in that file; importing a new Blueprint can otherwise create a duplicate service.

Automatic approval review rejected copying the local TMDB token to Render without explicit approval for that secret transfer. That command did not execute. Service creation used no secret. The owner then confirmed entering `TMDB_READ_ACCESS_TOKEN` privately in the service's Environment page with Save only. A second deploy (`dep-dbbvi8vf3r2c73fs76hg`) was triggered for the same exact source revision to activate it. No credential value belongs in this record or chat.

## Observed deployment stages

- Render checked out the exact initial revision above from `main`.
- Build logs selected Python **3.13.5** via `.python-version` and installed the pinned runtime successfully.
- Export produced the **447-film**, approximately **1,287 KiB** browser model.
- Render reported **Build successful** and began the startup/health-check stage.
- Initial deployment reached terminal **live** status at **2026-10-20 23:27:39 UTC** (21 October locally), approximately **87.5 seconds** after it started. This is initial deployment duration, not a measured idle cold-start delay.
- **57 hosted HTTPS checks passed** before token configuration: exact revision, API health, frontend/assets, CSP/bootstrap, snapshot/model parity, explicit recommendation exclusions, honest missing-token search 503, and private paths returning 404. See [hosted-fallback-smoke.json](hosted-fallback-smoke.json).
- Token-enabled deploy `dep-dbbvi8vf3r2c73fs76hg` reached terminal **live** at **2026-10-20 23:29:57 UTC**, approximately **82.3 seconds** after starting. Render deactivated the initial deployment. Both deployments used the exact same source revision; only the privately saved configuration changed.
- **74 hosted live HTTPS checks passed** after redeployment. Live search returned Batman pages 1/2, external Sintel details (`tmdb:45745`) loaded, its preference resolved, explicit seeds remained excluded and dynamic discovery reported **`ok`**, **60 candidates**, **0 failed sources**, and **4 recommendations**. Retrieval took approximately **2,413.8 ms** and feature encoding **7.6 ms** for this request. Candidates were summary-only, with 12 enrichments queued; this is not a fully hydrated-cache or load benchmark. See [hosted-smoke.json](hosted-smoke.json).
- An error-level log query from the second deployment's start through post-smoke returned no entries. This is a bounded observation, not a claim of future uptime.
- Auto-deploy remained **off**, compute **free**, region **singapore**, and branch **main** when rechecked. Subsequent documentation-only commits do not alter the running revision automatically.

## Owner hosted browser confirmation

On **21 October 2026**, the owner was asked to use **https://cinemagic-trbu.onrender.com**, try **Sintel (2010, TMDB 45745)**, like it, refresh, watch and switch sources manually. The owner replied **"Both persistence and playback work"**. This records a passing owner check for the requested hosted flow: the like/recommendations survive refresh and playback/manual switching work. Browser/device/country, individual source results, resume position, autoplay, fullscreen and captions were not supplied. No per-source matrix or storage-survival result across a redeploy is inferred.

## Remaining hosted acceptance

Live metadata search, pagination, external preferences and dynamic ranking passed after private token entry and redeployment. The owner confirmed hosted playback/manual switching and like/recommendation persistence across refresh. Remaining checks in [S7](../streaming/07-render-deployment.md) include detailed player/device behavior, other saved-state fields, storage across a redeploy, cache reset and idle cold start. The configuration redeploy above establishes successful redeployment, but no browser profile was measured across it. API checks alone do not establish media playback; that functional confirmation comes from the owner's hosted report above.

The full pinned-runtime regression suite and Linux CI already passed before deployment; see [package validation](S7_VALIDATION.md) and [GitHub validation](GITHUB_VALIDATION.md). This record does not claim all S7 acceptance checks are complete.
