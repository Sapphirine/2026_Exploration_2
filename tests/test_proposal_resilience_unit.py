"""Tests for the P3 robustness fixes in proposal_agent + pdf.

The DRB-II driver only consumes the markdown output. Previously, malformed
LaTeX (unbalanced $, unbalanced braces, raw Unicode math) caused
ProposalAgent._validate_latex_fragments to raise ValueError, aborting the
run before the markdown was emitted. The fix downgrades these to warnings
and makes PDF compilation non-fatal.
"""

from __future__ import annotations

from pathlib import Path

from evoresearcher.agents.proposal_agent import ProposalAgent
from evoresearcher.report.pdf import _compile_pdf, render_outputs
from evoresearcher.schemas import (
    ConstraintProfile,
    ReportSections,
    ResearchBrief,
)


def _bad_report() -> ReportSections:
    return ReportSections(
        title="Test",
        abstract="One $unbalanced math because we have an odd dollar sign here.",
        problem_and_goal="Has unbalanced braces { { } and a raw Unicode π symbol.",
        evidence_base="ok",
        proposed_direction="ok",
        plan_or_analysis="ok",
        risks_and_limits="ok",
        conclusion="ok",
        references=["ref"],
    )


def _good_report() -> ReportSections:
    return ReportSections(
        title="Test",
        abstract="Clean markdown abstract.",
        problem_and_goal="Goal text.",
        evidence_base="Evidence text.",
        proposed_direction="Proposal text.",
        plan_or_analysis="Plan text.",
        risks_and_limits="Risks text.",
        conclusion="Conclusion text.",
        references=["ref-1"],
    )


def test_validator_no_longer_raises_on_bad_latex(caplog):
    """The validator must log warnings, not raise — so the markdown path can complete."""
    agent = ProposalAgent.__new__(ProposalAgent)  # bypass __init__; we only test the method
    with caplog.at_level("WARNING", logger="evoresearcher.agents.proposal_agent"):
        agent._validate_latex_fragments(_bad_report())
    msgs = [r.getMessage() for r in caplog.records]
    assert any("LaTeX issues" in m for m in msgs), f"expected warning, got {msgs}"


def test_validator_silent_on_good_latex(caplog):
    agent = ProposalAgent.__new__(ProposalAgent)
    with caplog.at_level("WARNING", logger="evoresearcher.agents.proposal_agent"):
        agent._validate_latex_fragments(_good_report())
    assert all("LaTeX issues" not in r.getMessage() for r in caplog.records)


def test_render_outputs_writes_markdown_even_if_pdf_fails(tmp_path: Path, monkeypatch, caplog):
    """If PDF compile fails, render_outputs still emits the markdown file."""
    def fake_compile(*, tex_path, pdf_path):
        return False  # simulate failure

    monkeypatch.setattr("evoresearcher.report.pdf._compile_pdf", fake_compile)

    brief = ResearchBrief(
        mode="general",
        user_goal="g",
        reframed_goal="g",
        scope="s",
        deliverable="d",
        time_cutoff="now",
        constraints=ConstraintProfile(),
    )
    artifacts = render_outputs(
        run_dir=tmp_path,
        brief=brief,
        report=_good_report(),
        sources=[],
        top_ideas=[],
        author_line="test",
    )
    md_path = tmp_path / "research_report.md"
    assert md_path.exists() and md_path.read_text().strip()
    assert "markdown_path" in artifacts
    assert "pdf_path" not in artifacts  # PDF was skipped


def test_compile_pdf_returns_false_when_tectonic_missing(tmp_path: Path, monkeypatch, caplog):
    monkeypatch.setattr("shutil.which", lambda name: None)
    tex = tmp_path / "x.tex"
    tex.write_text(r"\documentclass{article}\begin{document}hi\end{document}")
    pdf = tmp_path / "x.pdf"
    with caplog.at_level("WARNING", logger="evoresearcher.report.pdf"):
        ok = _compile_pdf(tex_path=tex, pdf_path=pdf)
    assert ok is False
    assert any("tectonic" in r.getMessage() for r in caplog.records)
