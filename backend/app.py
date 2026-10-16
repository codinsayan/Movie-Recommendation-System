"""FastAPI server: JSON API under /api and the static frontend at /."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from recommender import load_default

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Cinemagic Recommender", version="0.2.0")
engine = load_default()


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
