# S7 publication and merge evidence

Recorded **21 October 2026** after the owner explicitly authorized pushing, merging into main and deploying.

## Published code

- Repository: `codinsayan/Movie-Recommendation-System`.
- Both `feature/streaming-platform` and `main` were verified on GitHub at **`0755f8f364c7780accc55058e17863a167186ef2`**.
- Main advanced from `0b6576d` by a fast-forward merge; no conflicts, force push or history rewrite.
- The final configuration commit targets Render at **main**, updates the deployment contract test and enables release checks on main pushes.
- Commit author and committer: **codinsayan <codinsayan2024@gmail.com>**, no co-author trailer.
- Full local pinned-runtime regression suite: **154 passed**, one upstream TestClient deprecation warning.
- `.env`, runtime SQLite and `.s7-local/` validation environments are not tracked or published.

## Remote checks observed

| Workflow | Revision / branch | Observed result |
|---|---|---|
| [Release checks](https://github.com/codinsayan/Movie-Recommendation-System/actions/runs/39513163211) | `0755f8f` / main | Completed, success |
| [Release checks](https://github.com/codinsayan/Movie-Recommendation-System/actions/runs/39513156550) | `0755f8f` / feature/streaming-platform | Completed, success |
| [GitHub Pages](https://github.com/codinsayan/Movie-Recommendation-System/actions/runs/39513163300) | `0755f8f` / main | Build and deployment completed, success |

The release job installed the pinned runtime with Python 3.13.5, ran tests/export/JavaScript checks, started the complete service on Linux, verified the exact revision through `/api/deployment`, and uploaded smoke evidence. The Pages job separately passed its Python 3.12 tests/export and published the static snapshot demo. The existing main-push workflow performed that authorized static deployment; it is not the Render backend deployment.

## Render still pending

The owner reports repository access granted to Render. No browser session is attached here. The Render integration was found and offered, and the owner chose to install/connect it, but its latest confirmed state is **not installed**. No Render API credentials were requested in chat, no secret was copied to GitHub, and no Render resource, deploy ID or public URL is claimed.

After the integration is connected, create the configured Free/Singapore Python service from main, supply the TMDB credential privately, verify its actual deployed SHA, and run the hosted/API/browser checks in [S7](../streaming/07-render-deployment.md). Subsequent documentation commits may advance main beyond this tested code SHA; record the actual service revision rather than assuming it.
