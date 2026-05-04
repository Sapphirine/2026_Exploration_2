"""Pairwise Elo ranking for idea candidates."""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations
from math import pow

from evoresearcher.schemas import EloMatch, ResearchIdea


def run_elo_tournament(
    ideas: list[ResearchIdea],
    *,
    judge_fn: Callable[[ResearchIdea, ResearchIdea], tuple[str, str]],
    k_factor: float = 24.0,
) -> tuple[list[ResearchIdea], list[EloMatch]]:
    pool = [idea.model_copy(deep=True) for idea in ideas]
    idea_map = {idea.idea_id: idea for idea in pool}
    matches: list[EloMatch] = []
    for idea_a, idea_b in combinations(pool, 2):
        before_a = idea_a.elo_rating
        before_b = idea_b.elo_rating
        winner_id, rationale = judge_fn(idea_a, idea_b)
        expected_a = 1.0 / (1.0 + pow(10.0, (before_b - before_a) / 400.0))
        expected_b = 1.0 - expected_a
        score_a = 1.0 if winner_id == idea_a.idea_id else 0.0
        score_b = 1.0 - score_a
        idea_a.elo_rating = round(before_a + k_factor * (score_a - expected_a), 2)
        idea_b.elo_rating = round(before_b + k_factor * (score_b - expected_b), 2)
        matches.append(
            EloMatch(
                idea_a_id=idea_a.idea_id,
                idea_b_id=idea_b.idea_id,
                winner_id=winner_id,
                rationale=rationale,
                rating_a_before=before_a,
                rating_b_before=before_b,
                rating_a_after=idea_a.elo_rating,
                rating_b_after=idea_b.elo_rating,
            )
        )
        idea_map[idea_a.idea_id] = idea_a
        idea_map[idea_b.idea_id] = idea_b
    ranked = sorted(
        idea_map.values(),
        key=lambda idea: (-idea.elo_rating, -idea.total_score, idea.idea_id),
    )
    return ranked, matches
