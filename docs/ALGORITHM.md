# The recommendation algorithm

All code lives in [`backend/recommender.py`](../backend/recommender.py).

## 1. Content model (TF-IDF)

Each movie becomes a document:

```
genres ×2 + tags ×2 + overview
```

Genres and tags are repeated so they outweigh plot words. Hyphenated tags such as `mind-bending` are kept as single tokens. `TfidfVectorizer(sublinear_tf=True, stop_words="english")` produces an L2-normalised matrix **X** (movies × terms), so

```
content_sim = X · Xᵀ      (cosine similarity between every pair of movies)
```

**User profile.** Given liked set L, disliked set D and an optional mood query q:

```
p = Σ_{i∈L} X_i  −  0.5 · Σ_{j∈D} X_j  +  1.5 · max(1,|L|) · tfidf(expand(q))
content_score = X · p / ‖p‖
```

## 2. Collaborative model (item-item CF)

A ratings matrix **R** (users × movies, 1–5, 0 = unwatched) is mean-centred per user over watched items. This is *adjusted cosine*, and it removes "generous" vs "harsh" rater bias. Columns are L2-normalised and

```
collab_sim = R̃ᵀ · R̃
collab_score = mean_{i∈L} collab_sim_i − 0.5 · mean_{j∈D} collab_sim_j
```

### Where R comes from

No real rating data is bundled, so `simulate_ratings()` generates a reproducible one (seed 42):

- 600 users, each with a genre taste vector `θ ~ Dirichlet(0.3)`. The low α makes tastes *peaky*, like real people.
- Affinity of user u to movie m = θ_u · (genre one-hot of m, normalised).
- P(watch) = 0.06 + 0.5 · affinity; rating = round(1 + 4·affinity + 0.35·z(critic) + N(0, 0.6)), clipped to 1–5.

The result is about 7.3k ratings and about 80% sparsity, a realistic shape. Iteration 2 replaces this with MovieLens.

### TMDB mode: the recommendation graph

With the TMDB catalogue, **R** is replaced by TMDB's recommendation graph, which is built from real audience behaviour. For every film, TMDB lists the films its viewers also engage with; edges outside the catalogue are dropped. Then:

```
A = I + adjacency (symmetrised: i→j or j→i gives an edge)
C = rows of A, L2-normalised
collab_sim = C · Cᵀ      (cosine = overlap of audience neighbourhoods; direct links count via the self-loops)
```

The scoring formulas above stay the same; only the item vectors change.

## 3. Quality prior

The rating is min-max scaled to [0, 1]. It is a small nudge towards good films and breaks ties. When vote counts are available (TMDB), the rating is first shrunk towards the catalogue mean (IMDb-style Bayesian average):

```
WR = v/(v+m) · R + m/(v+m) · C      v = votes, R = average rating, C = mean rating, m = median votes
```

so a 9.5 with 10 votes cannot outrank an 8.5 with 100k votes.

## 4. Blending

Each signal is min-max scaled over the *candidate* set (unseen movies), then:

| Mode | When | content | collab | quality |
|---|---|---|---|---|
| `popular` | no likes, no mood (cold start) | 0 | 0 | 1 |
| `mood` | mood only | 0.80 | 0 | 0.20 |
| `personal` | at least one like/dislike | 0.55 | 0.35 | 0.10 |

In mood modes, items with `content_score ≤ 0.05` are dropped, so a query never returns unrelated films.

## 5. Diversity: Maximal Marginal Relevance

From the top 3k candidates, items are picked greedily:

```
next = argmax_i  λ · score_i − (1−λ) · max_{s∈selected} content_sim(i, s)      λ = 0.75
```

Without MMR, loving *Inception* returns five near-clones. With MMR the list still matches the user but covers more ground.

## 6. Explanations

For each recommendation r:

- **because**: the liked movie j maximising `content_sim(r,j) + collab_sim(r,j)`, giving "Because you loved *j*", but only when that link is at least `EXPLAIN_FLOOR = 0.03`. Weaker links mean the pick is there for quality or diversity, so it reads "A well-rated pick to widen your taste" instead of naming an unrelated film (S5C).
- **shared**: the intersection of r's and j's genres + tags (plus mood terms r matches).
- **breakdown**: each signal's weighted contribution. The UI shows these as percentages of the total score.
- **match**: a display value `55 + 44 · score / max_score` (55–99), so the best pick in the list reads about 99%.

## 7. Mood expansion

Everyday words are mapped to catalogue vocabulary before TF-IDF, e.g.

```
"make me cry"  → + "emotional bittersweet drama"
"cozy"         → + "cozy heartwarming feel-good whimsical"
"mind bending" → + "mind-bending cerebral twist"
```

Matching is substring-based (`"inspir"` matches *inspiring* and *inspirational*). See `MOOD_SYNONYMS`.

## S5: optional measured-viewing signal

The explicit formulas above remain the default. With **Use viewing history** enabled, a measured title qualifies after both 120 seconds and 30% unique watched coverage. A qualifying session has strength 0.15; substantial repeat sessions can raise this to 0.20 and then 0.25. Seeks, errors, source changes, Play messages and completion flags alone provide no preference evidence.

The new score is `0.90 * existing_score + 0.10 * viewing_part`, where `viewing_part` is the clipped mean of `(strength/0.25) * (0.6*content_similarity + 0.4*collaborative_similarity)` across qualified indexed seeds. It is not min-max scaled, so weak evidence cannot acquire full strength through normalization. Disliked films cannot act as positive seeds or candidates; likes remain the primary explanations and Taste DNA stays explicit. Without qualified opted-in signals the old scores are unchanged.

Canonical eligibility constraints, including optional device-local recent-playback evidence, are applied before normalization, top-3k selection and MMR. Requests add no remote titles to the model. Python and JavaScript return matching scores, explanations and ?Because you watched? rows. [EVALUATION.md](EVALUATION.md) records reproducible proxy comparisons and why the new blend remains experimental.

## Complexity

With n movies, t terms and U users: start-up is O(n·t + U·n + n²); each request is O(n·t + n·|L|), measured on the current 60/447-film catalogues. Runtime feature/similarity matrices are dense; the refresh budget is capped at 500. Sparse exports alone do not make runtime scaling safe for tens of thousands of films.

## Evaluation (planned, Iteration 3)

Offline leave-one-out on the ratings matrix: hide one liked item per user, measure **Hit-Rate@10**, **NDCG@10**, **catalogue coverage** and **intra-list diversity**, comparing content-only, CF-only, hybrid and hybrid+MMR.
