"""Proposal-writing agent."""

from __future__ import annotations

from pydantic import BaseModel

from evoresearcher.llm import LLMClient
from evoresearcher.schemas import EvidenceSynthesis, ReportSections, ResearchBrief, ResearchIdea, SourceNote


class ProposalAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(
        self,
        *,
        brief: ResearchBrief,
        top_ideas: list[ResearchIdea],
        evidence: EvidenceSynthesis,
        sources: list[SourceNote],
        observer=None,
    ) -> ReportSections:
        if observer is not None:
            observer.phase_log("proposal", f"Writing report from {len(top_ideas)} top ideas.")
        report = self.llm.structured(
            ReportSections,
            label="proposal_sections",
            system_prompt=(
                "You are the proposal agent for EvoResearcher. Write a concise proposal/report "
                "that stays within three pages when rendered in a compact article format. "
                "For ML mode, describe experiments as proposals only; do not claim results. "
                "Stay strictly on the user's topic; do not switch to a different model family or benchmark. "
                "If you include equations, use proper LaTeX math delimiters such as $...$ or \\[...\\]. "
                "Never use raw Unicode math symbols like ∈, ≈, Σ, ×, ⊗, π. "
                "Do not emit raw code snippets, class definitions, or unescaped underscores in prose."
            ),
            user_prompt=(
                f"Brief: {brief.model_dump_json(indent=2)}\n"
                f"Top ideas: {[idea.model_dump() for idea in top_ideas]}\n"
                f"Evidence synthesis: {evidence.model_dump_json(indent=2)}\n"
                f"Sources: {[source.model_dump() for source in sources]}\n"
                "Structure the report for a deep research audience and include verifiable references. "
                "If you use math, every formula must compile in LaTeX without manual fixes."
            ),
        )
        self._validate_latex_fragments(report)
        return report

    def _validate_latex_fragments(self, report: ReportSections) -> None:
        joined = "\n".join(
            [
                report.abstract,
                report.problem_and_goal,
                report.evidence_base,
                report.proposed_direction,
                report.plan_or_analysis,
                report.risks_and_limits,
                report.conclusion,
            ]
        )
        if joined.count("$") % 2 != 0:
            raise ValueError("Generated report contains unbalanced inline math delimiters.")
        if joined.count("{") != joined.count("}"):
            raise ValueError("Generated report contains unbalanced braces.")
        forbidden = ("∈", "≈", "Σ", "×", "⊗", "π")
        if any(symbol in joined for symbol in forbidden):
            raise ValueError("Generated report still contains raw Unicode math symbols.")
