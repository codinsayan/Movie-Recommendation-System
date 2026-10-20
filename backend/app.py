"""FastAPI server: JSON API under /api and the static frontend at /."""
from __future__ import annotations

from pathlib import Path
import time
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Path as ApiPath
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from recommender import load_default
from catalog import Catalog, CatalogError
from discovery import Discovery
from preferences import ExternalProfile, PreferenceFeatures
from ranking import RANKING_BUDGET, RANKING_CONTRACT, FeatureStore, ranking_mode
from release import VERSION, frame_policy, playback_config, playback_script

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Cinemagic Recommender", version=VERSION)
playback = playback_config()  # Fail clearly at startup for misspelled provider IDs.


@app.middleware("http")
async def playback_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = frame_policy(playback)
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Reload must receive current HTML, policy and scripts after a provider rollback.
    if not request.url.path.startswith("/api/") and request.url.path != "/playback-config.js":
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/playback")
def playback_settings():
    return playback


@app.get("/playback-config.js", include_in_schema=False)
def playback_bootstrap():
    return Response(playback_script(playback), media_type="text/javascript", headers={"Cache-Control": "no-store"})


engine = load_default()
catalog = Catalog.from_environment()
preference_features = PreferenceFeatures(engine, catalog)
features = FeatureStore(engine)   # derived, disposable: never a user database
discovery = Discovery(engine, catalog, features=features)


def model_ids():
    return {m["tmdb_id"] for m in engine.movies if m.get("source") == "tmdb"}


def catalogue_error(error):
    raise HTTPException(status_code=error.status, detail=error.message,
                        headers={"Retry-After": error.retry_after} if error.retry_after else None)


@app.get("/api/capabilities")
def capabilities():
    dynamic = ranking_mode() == "dynamic"
    return {"catalogue": {"live_search": catalog.configured, "dynamic_discovery": dynamic and discovery.available,
                          "snapshot_source": engine.movies[0].get("source") if engine.movies else None},
            "ranking": {"contract": RANKING_CONTRACT, "mode": ranking_mode(),
                        "external_viewing": dynamic and engine.movies[0].get("source") == "tmdb"},
            "preferences": engine.meta()["preferences"]}


@app.get("/api/preferences/tmdb/{movie_id}")
def resolve_preference(movie_id: int = ApiPath(ge=1, le=2147483647)):
    if engine.movies[0].get("source") != "tmdb" or movie_id in engine.by_id:
        raise HTTPException(status_code=422, detail="Feature resolution requires an external TMDB movie.")
    try:
        return preference_features.resolve(movie_id)
    except CatalogError as error:
        catalogue_error(error)


@app.get("/api/search")
def search(q: str = Query(min_length=1, max_length=200), page: int = Query(default=1, ge=1, le=500),
           language: str = Query(default="en-US", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")):
    if not q.strip():
        raise HTTPException(status_code=422, detail="Enter a movie title.")
    try:
        return catalog.search(q, page, language, model_ids())
    except CatalogError as error:
        catalogue_error(error)


@app.get("/api/movies/{movie_id}")
def movie_details(movie_id: int = ApiPath(ge=1, le=2147483647),
                  language: str = Query(default="en-US", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")):
    try:
        return catalog.movie(movie_id, language, model_ids())
    except CatalogError as error:
        snapshot = next((m for m in engine.movies if m.get("tmdb_id") == movie_id), None)
        if snapshot and error.status != 404:
            return {**snapshot, "in_model": True, "full_details": True, "cached": True, "stale": True,
                    "metadata_language": "en-US"}
        catalogue_error(error)


MovieKey = Annotated[str, Field(pattern=r"^(tmdb|curated):[1-9]\d*$", max_length=40)]


class ViewedSignal(BaseModel):
    key: MovieKey
    watched_seconds: float = Field(ge=0, le=86400, strict=True, allow_inf_nan=False)
    duration: float = Field(gt=0, le=86400, strict=True, allow_inf_nan=False)
    plays: int = Field(ge=0, le=100, strict=True)
    updated_at: float = Field(default=0, ge=0, strict=True, allow_inf_nan=False)


class PlaybackEvidence(BaseModel):
    key: MovieKey
    provider: Literal["cinesrc", "vidlink", "vidsrc"]
    verified_at: float = Field(default=0, ge=0, strict=True, allow_inf_nan=False)
    failed_at: float = Field(default=0, ge=0, strict=True, allow_inf_nan=False)


class ViewingEvidence(BaseModel):
    version: Literal[1]
    signals: list[ViewedSignal] = Field(default_factory=list, max_length=500)
    playback: list[PlaybackEvidence] = Field(default_factory=list, max_length=1500)

    @field_validator("version", mode="before")
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Unsupported viewing contract version")
        return value


class RecommendRequest(BaseModel):
    liked: list[int] = Field(default_factory=list, max_length=10000)
    disliked: list[int] = Field(default_factory=list, max_length=10000)
    mood: str | None = Field(default=None, max_length=200)
    k: int = Field(default=12, ge=1, le=100)
    viewing: ViewingEvidence | None = None
    use_viewing: bool = Field(default=False, strict=True)
    recent_playback_only: bool = Field(default=False, strict=True)
    eligible_keys: list[MovieKey] | None = Field(default=None, max_length=5000)
    external_preferences: ExternalProfile | None = None
    discover: bool = Field(default=False, strict=True)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    return engine.meta()


@app.get("/api/movies")
def movies():
    return engine.movies


def external_viewing(viewing, liked, disliked):
    """Features for measured viewing outside the snapshot: cache-only, bounded, never blocking.

    Missing metadata is reported as pending and fetched in the background, so a later
    request can apply it. Explicit likes/dislikes are resolved through S5A instead.
    """
    status = {"considered": 0, "applied": 0, "pending": 0, "queued": 0}
    if not viewing or engine.movies[0].get("source") != "tmdb" or ranking_mode() != "dynamic":
        return None, status
    chosen = set(liked) | set(disliked)
    ids = []
    for signal in sorted(viewing["signals"], key=lambda s: -s["updated_at"]):
        source, mid = signal["key"].split(":")
        mid = int(mid)
        if source == "tmdb" and mid not in engine.by_id and mid not in chosen and mid not in ids:
            ids.append(mid)
        if len(ids) >= RANKING_BUDGET["external_viewing"]:
            break
    status["considered"] = len(ids)
    movies, missing = [], []
    known = catalog.cached_movies(ids)
    for mid in ids:
        cached = known.get(mid)
        if cached:
            movies.append({k: v for k, v in cached.items() if k not in ("cached", "updated_at", "stale")})
        else:
            missing.append(mid)
    status["pending"] = len(missing)
    if missing and discovery.available:
        status["queued"] = discovery.queue_details(missing)
    if not movies:
        return None, status
    matrix, _ = features.encode(movies)
    dense = matrix.toarray()
    status["applied"] = len(movies)
    return {f"tmdb:{m['id']}": {"movie": m, "vector": dense[p]} for p, m in enumerate(movies)}, status


@app.post("/api/recommend")
def recommend(req: RecommendRequest):
    external = req.external_preferences.model_dump() if req.external_preferences else None
    started = time.perf_counter()
    try:
        extra, report, viewing_features, viewing_status = None, None, None, None
        viewing = req.viewing.model_dump() if req.viewing else None
        if req.discover and ranking_mode() == "dynamic":
            # Upstream failures never fail the request: the snapshot remains the fallback pool.
            extra, report = discovery.candidates(req.liked, req.disliked, external)
        if req.use_viewing and viewing:
            viewing_features, viewing_status = external_viewing(viewing, req.liked, req.disliked)
        scoring = time.perf_counter()
        diagnostics = {}
        result = engine.recommend(req.liked, req.disliked, req.mood, req.k, viewing=viewing,
                                  use_viewing=req.use_viewing, recent_playback_only=req.recent_playback_only,
                                  eligible_keys=req.eligible_keys, external_preferences=external, extra=extra,
                                  viewing_features=viewing_features, diagnostics=diagnostics)
        done = time.perf_counter()
        if report is not None:
            report["recommended"] = sum(1 for item in result["items"] if item.get("dynamic"))
            result["discovery"] = report
        if viewing_status is not None:
            result["viewing_status"] = viewing_status
        result["ranking"] = {**diagnostics, "mode": ranking_mode(), "feature_cache": features.snapshot(),
                             "timing_ms": {"total": round((done - started) * 1000, 1),
                                           "rank": round((done - scoring) * 1000, 1)}}
        return result
    except ValueError:
        raise HTTPException(status_code=422, detail="External preferences are invalid or use an incompatible feature version.") from None


@app.get("/api/movies/{movie_id}/similar")
def similar(movie_id: int = ApiPath(ge=1, le=2147483647), k: int = Query(default=6, ge=1, le=30)):
    try:
        return engine.similar(movie_id, k)
    except KeyError:
        if engine.movies[0].get("source") != "tmdb":
            raise HTTPException(status_code=404, detail="Movie not found")
        try:
            return engine.similar_external(preference_features.resolve(movie_id), k)
        except CatalogError as error:
            catalogue_error(error)


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
