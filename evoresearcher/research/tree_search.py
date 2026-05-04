"""Fixed-depth idea tree search helpers."""

from __future__ import annotations

from collections.abc import Callable

from evoresearcher.schemas import ResearchIdea


def build_tree(
    roots: list[ResearchIdea],
    *,
    depth: int,
    expand_fn: Callable[[ResearchIdea, int], list[ResearchIdea]],
) -> tuple[list[ResearchIdea], list[ResearchIdea]]:
    nodes = list(roots)
    frontier = list(roots)
    leaves = list(roots)
    for current_depth in range(1, depth + 1):
        next_frontier: list[ResearchIdea] = []
        for node in frontier:
            children = expand_fn(node, current_depth)
            if children:
                next_frontier.extend(children)
                nodes.extend(children)
        if next_frontier:
            leaves = next_frontier
        frontier = next_frontier
        if not frontier:
            break
    return nodes, leaves
