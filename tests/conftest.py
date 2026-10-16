import os

# Tests assert on the hand-curated 60-film catalogue (stable ids, offline).
# TMDB-specific behaviour is covered with fixtures in test_tmdb.py.
os.environ["CINEMAGIC_DATASET"] = "curated"
