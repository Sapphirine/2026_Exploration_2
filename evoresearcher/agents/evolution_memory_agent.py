"""Evolution Memory Agent."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from evoresearcher.memory.store import JSONMemoryStore
from evoresearcher.schemas import EvidenceSynthesis, MemoryEntry, ReportSections, ResearchBrief, ResearchIdea


class EvolutionMemoryAgent:
    def __init__(
        self,
        *,
        ideation_memory: JSONMemoryStore,
        proposal_memory: JSONMemoryStore,
    ):
        self.ideation_memory = ideation_memory
        self.proposal_memory = proposal_memory

    def run(
        self,
        *,
        brief: ResearchBrief,
        top_idea: ResearchIdea,
        evidence: EvidenceSynthesis,
        report: ReportSections,
        observer=None,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        ideation_entry = MemoryEntry(
            entry_id=f"idea-{uuid4().hex[:8]}",
            kind="promising_direction",
            summary=top_idea.title,
            goal=brief.reframed_goal,
            details=f"{top_idea.summary}\nMethod: {top_idea.method_outline}",
            tags=[brief.mode, "tree-search", "ema"],
            created_at=now,
        )
        proposal_entry = MemoryEntry(
            entry_id=f"proposal-{uuid4().hex[:8]}",
            kind="proposal_pattern",
            summary=report.title,
            goal=brief.reframed_goal,
            details=(
                f"Evidence findings: {'; '.join(evidence.findings[:3])}\n"
                f"Direction: {report.proposed_direction[:500]}"
            ),
            tags=[brief.mode, "proposal", "ema"],
            created_at=now,
        )
        self.ideation_memory.add(ideation_entry)
        self.proposal_memory.add(proposal_entry)
        if observer is not None:
            observer.phase_log("memory", "EMA wrote ideation and proposal memories.")
        return {
            "ideation_entry": ideation_entry.model_dump(),
            "proposal_entry": proposal_entry.model_dump(),
        }
