"""FastAPI server: JSON API under /api and the static frontend at /."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Path as ApiPath
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from recommender import load_default
from catalog import Catalog, CatalogError

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Cinemagic Recommender", version="0.3.0")
engine = load_default()
catalog = Catalog.from_environment()


def model_ids():
    return {m["tmdb_id"] for m in engine.movies if m.get("source") == "tmdb"}


def catalogue_error(error):
    raise HTTPException(status_code=error.status, detail=error.message,
                        headers={"Retry-After": error.retry_after} if error.retry_after else None)


@app.get("/api/capabilities")
def capabilities():
    return {"catalogue": {"live_search": catalog.configured,
                          "snapshot_source": engine.movies[0].get("source") if engine.movies else None}}


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


class RecommendRequest(BaseModel):
    liked: list[int] = Field(default_factory=list)
    disliked: list[int] = Field(default_factory=list)
    mood: str | None = Field(default=None, max_length=200)
    k: int = Field(default=12, ge=1, le=100)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    return engine.meta()


@app.get("/api/movies")
def movies():
    return engine.movies


@app.post("/api/recommend")
def recommend(req: RecommendRequest):
    return engine.recommend(req.liked, req.disliked, req.mood, req.k)


@app.get("/api/movies/{movie_id}/similar")
def similar(movie_id: int, k: int = 6):
    try:
        return engine.similar(movie_id, k)
    except KeyError:
        raise HTTPException(status_code=404, detail="Movie not found")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
