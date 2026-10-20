# S7.1 local deployment-package validation

Recorded **21 October 2026**, branch `feature/streaming-platform`, working tree based on acceptance commit `1c0cbee`. The S7.1 implementation commit is recorded in Git history. This document records the original local validation; later service creation and hosted checks are recorded in [Render deployment evidence](RENDER_VALIDATION.md).

| Check | Observed result |
|---|---|
| Fresh environment | Python 3.13.5, isolated `.s7-local/venv`, no system site packages; installed from project requirements |
| Final framework pins | FastAPI 0.156.3, Starlette 1.9.0, Pydantic 2.14.1, Uvicorn 0.54.0 |
| Complete regression suite | **154 passed**, one upstream TestClient deprecation warning about its supported HTTPX adapter |
| Runtime dependency closure | **24 Linux packages resolved**, all exactly pinned; no unpinned transitive packages |
| Linux target | CPython 3.13.5 x86_64 wheels using manylinux 2.28/2.27/2014/2.17 tags; dependency resolution only, not Linux execution |
| Official Blueprint schema | Passed against `https://render.com/schema/render.yaml.json`; SHA256 `8a3fb8da6b4f55fe686fbefa790e011d3dd7895f013f355953c572a21ab6494a` |
| Static export | 447-film TMDB model, approximately 1,287 KiB, and matching public playback bootstrap |
| HTTP startup smoke | Real local Uvicorn on `0.0.0.0:8765`, one worker; health/API/frontend/assets/model/recommendations/private-path checks passed |
| Missing credentials | Both credential environment variables explicitly empty; live-search capability false, snapshot recommendations remain usable; live search explicitly unavailable |
| Local process memory | Approximately 155 MiB working set / 157 MiB peak after smoke on Windows; not a Linux/Render load measurement or a hosting guarantee |
| Remote branch observed | Read-only `git ls-remote`: `3bb0863e49581444e6ff4b72dabf1f383e2cbc55`; older than local S6/S7 work, must be updated before importing Blueprint |

Reviewed HTTP evidence: [local-smoke.json](local-smoke.json). Its deployment commit is deliberately `null`: this is a local working-tree process, not a Render deployment. After publication, GitHub's configured-Python tests, export and exact-revision CLI smoke **passed on Linux** at `0755f8f`; Python 3.12 tests/export and Pages deployment also passed. See [publication evidence](GITHUB_VALIDATION.md). These checks do not establish a Render service or hosted live discovery.

## Why the web runtime changed

The installed S6 environment used Starlette 0.47.3. The maintainer's [file-response Range advisory](https://github.com/Kludex/starlette/security/advisories/GHSA-7f5h-v6xp-fcq8) includes that version and applies to static-file serving used here. S7's locked runtime selects patched framework versions and a current certificate bundle, tested in isolation. The scientific model versions remain NumPy 2.3.2, SciPy 1.16.1 and scikit-learn 1.7.1, preserving the tested fitted-feature behavior. No user's global Python packages were changed.

Runtime resolution used public PyPI metadata/wheels. Render documents [Debian 12 native runtimes](https://render.com/docs/native-runtimes); the wheel check does not substitute for the actual deployment build. [Python selection](https://render.com/docs/python-version) and [Blueprint validation](https://render.com/docs/blueprint-spec) were checked against current primary documentation.

## Follow-up deployment evidence

- The plugin is installed/enabled; its account tools were unavailable in this session, so the authenticated official CLI was used after the owner selected Sayan's Workspace.
- The Free Singapore service is created at **https://cinemagic-trbu.onrender.com**. Initial deployment of main revision `eae92cebecdc48f135ed9e2eb29e135e19501fd4` reached **live**, with Python 3.13.5 and successful pinned-runtime install/export.
- The initial credential-free hosted smoke passed **57 checks**. The owner confirmed private token entry; the token-enabled redeployment reached **live** and passed **74 live HTTPS checks**, including search pagination, external preferences and dynamic discovery. See [the hosted record](RENDER_VALIDATION.md).
- Hosted provider playback, browser-state persistence, actual Linux memory, idle cold start/cache reset and dashboard rollback remain separate acceptance items.

Use [the runbook](RENDER.md) for service settings. Original local evidence remains unchanged; this evidence does not mark all of S7 complete.
