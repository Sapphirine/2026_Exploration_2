"""Unit tests for the two ablation flags on ResearchAgent.

A_TREE (`expansion_blind=True`): expansion drops the review-guided refine-vs-alt
structure; tree leaves carry `relation_to_parent` values from the blind branch.

A_ELO (`skip_elo=True`): tournament is replaced by total_score sort, no matches
emitted, and leaf elo_ratings remain at the default starting value.
"""

from pathlib import Path

import pytest

from evoresearcher.agents.research_agent import ResearchAgent
from evoresearcher.config import AppConfig
from evoresearcher.memory.store import JSONMemoryStore
from evoresearcher.schemas import ConstraintProfile, ResearchBrief


class FakeLLMBlind:
    """LLM stub that asserts the blind expansion path is used and returns child_a/child_b."""

    def __init__(self):
        self.expansion_calls: list[str] = []

    def structured(self, model, *, label, system_prompt, user_prompt, temperature=0.2):
        name = model.__name__
        if name == "RootIdea":
            return model(
                title="Root",
                summary="Root summary.",
                method_outline="Root method.",
                evidence_use="Root evidence.",
                risks=[],
            )
        if name == "IdeaReview":
            return model(
                novelty=7.0,
                feasibility=7.0,
                relevance=7.0,
                clarity=7.0,
                weakest_dimension="clarity",
                feedback="ok",
            )
        if name == "BlindIdeaExpansion":
            self.expansion_calls.append(label)
            assert "Parent weakest dimension" not in user_prompt
            assert "Parent review feedback" not in user_prompt
            return model(
                child_a={
                    "title": "Blind A",
                    "summary": "Blind A summary.",
                    "method_outline": "Blind A method.",
                    "evidence_use": "Blind A evidence.",
                    "risks": [],
                },
                child_b={
                    "title": "Blind B",
                    "summary": "Blind B summary.",
                    "method_outline": "Blind B method.",
                    "evidence_use": "Blind B evidence.",
                    "risks": [],
                },
            )
        if name == "IdeaExpansion":
            raise AssertionError("Review-guided IdeaExpansion must not be invoked when expansion_blind=True.")
        if name == "PairwiseJudgement":
            return model(winner_id="idea-2", rationale="x")
        if name == "EvidenceSynthesis":
            return model(findings=[], tensions=[], opportunities=[])
        if name == "SearchPlan":
            return model(queries=[])
        raise AssertionError(f"Unexpected model request: {name}")


class FakeLLMSkipElo:
    """LLM stub that asserts no PairwiseJudgement call happens when skip_elo=True."""

    def structured(self, model, *, label, system_prompt, user_prompt, temperature=0.2):
        name = model.__name__
        if name == "RootIdea":
            return model(
                title="Root",
                summary="s",
                method_outline="m",
                evidence_use="e",
                risks=[],
            )
        if name == "IdeaReview":
            # Give children different total_scores so the sort order is well-defined.
            if "idea-2" in label:
                scores = (9.0, 9.0, 9.0, 9.0)  # mean 9.0 -> winner
            elif "idea-3" in label:
                scores = (5.0, 5.0, 5.0, 5.0)
            else:
                scores = (7.0, 7.0, 7.0, 7.0)
            return model(
                novelty=scores[0],
                feasibility=scores[1],
                relevance=scores[2],
                clarity=scores[3],
                weakest_dimension="clarity",
                feedback="ok",
            )
        if name == "IdeaExpansion":
            return model(
                refine_weak_dimension_child={
                    "title": "Refine",
                    "summary": "s",
                    "method_outline": "m",
                    "evidence_use": "e",
                    "risks": [],
                    "relation_to_parent": "refine_weak_dimension",
                },
                alternative_direction_child={
                    "title": "Alt",
                    "summary": "s",
                    "method_outline": "m",
                    "evidence_use": "e",
                    "risks": [],
                    "relation_to_parent": "alternative_direction",
                },
            )
        if name == "PairwiseJudgement":
            raise AssertionError("Elo tournament must not be invoked when skip_elo=True.")
        if name == "EvidenceSynthesis":
            return model(findings=[], tensions=[], opportunities=[])
        if name == "SearchPlan":
            return model(queries=[])
        raise AssertionError(f"Unexpected model request: {name}")


def build_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        workspace_dir=tmp_path,
        outputs_dir=tmp_path / "outputs",
        memory_dir=tmp_path / "memory",
        author_line="Test",
        deepseek_api_key="test",
        deepseek_model="test-model",
        deepseek_base_url="https://example.com",
        search_enabled=False,
        tree_depth=1,
        branching_factor=2,
    )


def _brief() -> ResearchBrief:
    return ResearchBrief(
        mode="general",
        user_goal="Goal",
        reframed_goal="Goal",
        scope="test",
        deliverable="proposal",
        time_cutoff="now",
        constraints=ConstraintProfile(),
    )


def test_default_flags_are_off(tmp_path: Path):
    """Smoke test: defaults preserve today's behavior."""
    config = build_config(tmp_path)
    config.ensure_directories()
    agent = ResearchAgent(
        config,
        FakeLLMSkipElo(),  # any non-blind LLM stub works
        JSONMemoryStore(config.memory_dir / "ideation.json"),
        JSONMemoryStore(config.memory_dir / "proposal.json"),
    )
    assert agent.expansion_blind is False
    assert agent.skip_elo is False


def test_blind_expansion_uses_blind_schema(tmp_path: Path):
    config = build_config(tmp_path)
    config.ensure_directories()
    fake = FakeLLMBlind()
    agent = ResearchAgent(
        config,
        fake,
        JSONMemoryStore(config.memory_dir / "ideation.json"),
        JSONMemoryStore(config.memory_dir / "proposal.json"),
        expansion_blind=True,
    )
    result = agent.run(_brief())
    assert len(result.idea_tree) == 3
    assert len(result.leaf_ideas) == 2
    assert fake.expansion_calls, "Blind expansion path was never invoked"
    relations = {idea.relation_to_parent for idea in result.leaf_ideas}
    assert relations == {"blind_child_a", "blind_child_b"}
    assert {idea.title for idea in result.leaf_ideas} == {"Blind A", "Blind B"}


def test_skip_elo_replaces_tournament_with_score_sort(tmp_path: Path):
    config = build_config(tmp_path)
    config.ensure_directories()
    agent = ResearchAgent(
        config,
        FakeLLMSkipElo(),
        JSONMemoryStore(config.memory_dir / "ideation.json"),
        JSONMemoryStore(config.memory_dir / "proposal.json"),
        skip_elo=True,
    )
    result = agent.run(_brief())
    assert result.elo_matches == []
    # Leaf elo ratings unchanged from default starting value.
    assert all(idea.elo_rating == result.leaf_ideas[0].elo_rating for idea in result.ranked_ideas)
    # Sort order should follow total_score (descending).
    scores = [idea.total_score for idea in result.ranked_ideas]
    assert scores == sorted(scores, reverse=True)
    # idea-2 was given the higher score in FakeLLMSkipElo, so it should be on top.
    assert result.ranked_ideas[0].idea_id == "idea-2"


def test_flags_are_independent(tmp_path: Path):
    """Both flags True should activate both branches without interaction."""
    config = build_config(tmp_path)
    config.ensure_directories()

    class FakeLLMBoth(FakeLLMBlind):
        def structured(self, model, *, label, system_prompt, user_prompt, temperature=0.2):
            if model.__name__ == "PairwiseJudgement":
                raise AssertionError("skip_elo=True must suppress PairwiseJudgement.")
            return super().structured(
                model,
                label=label,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )

    agent = ResearchAgent(
        config,
        FakeLLMBoth(),
        JSONMemoryStore(config.memory_dir / "ideation.json"),
        JSONMemoryStore(config.memory_dir / "proposal.json"),
        expansion_blind=True,
        skip_elo=True,
    )
    result = agent.run(_brief())
    assert result.elo_matches == []
    assert {idea.relation_to_parent for idea in result.leaf_ideas} == {"blind_child_a", "blind_child_b"}
