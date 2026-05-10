"""DeepSeek-as-judge replacement for DRB-II's run_evaluation.py.

Uses DeepSeek (text-only) instead of Gemini (multimodal). Reads markdown reports
from DeepResearch-Bench-II/report/<label>/idx-N.md, looks up each idx's task and
rubrics from tasks_and_rubrics.jsonl, prompts DeepSeek with the official three-way
classification template, parses results, and writes one JSON line per (model, idx)
into benchmarks/drb2/results/<label>__deepseek.jsonl in the same shape DRB-II's
aggregate_scores.py expects.

Run from repo root:
    .venv/bin/python benchmarks/drb2/evaluate_with_deepseek.py \
        --label evoresearcher \
        --chunk-size 25
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DRB2_REPO = REPO_ROOT.parent / "DeepResearch-Bench-II"
TASKS_JSONL = DRB2_REPO / "tasks_and_rubrics.jsonl"
RESULTS_DIR = REPO_ROOT / "benchmarks" / "drb2" / "results"

# Same prompt template used by run_evaluation.py, but adapted for text-only
# (DeepSeek does not accept PDF/image attachments).
PROMPT_TEMPLATE = """You will receive an article, a task, and a list of grading rubric items. Your job is to assess whether the article satisfies each rubric item, and provide a THREE-WAY score for EACH rubric item.

Scoring rule per rubric item (strict):
- Score = 1: The article clearly satisfies the rubric item AND the specific supporting sentence(s) do NOT cite any reference listed in "blocked" (match by title/urls). For numerical data, exact values must be explicitly listed and match the rubric.
- Score = 0: The article does NOT mention this rubric item at all.
- Score = -1: The article mentions this rubric item, BUT the supporting sentence(s) cite a blocked reference.

For EACH rubric item, you MUST provide:
1. "score": 1, 0, or -1
2. "reason": A brief explanation
3. "evidence": The specific supporting sentence(s) from the article (empty string if score is 0)

The input format is:
<input_format>
{{
    "task": "...",
    "rubric_items": ["rubric item 1", "rubric item 2", ...],
    "blocked": {{
        "title": "...",
        "authors": ["...", "..."],
        "urls": ["...", "..."]
    }}
}}
</input_format>

Your output MUST strictly follow this JSON format (no extra keys, and the rubric item text MUST match the input EXACTLY):
<output_format>
{{
    "results": [
        {{
            "rubric_item": "rubric item 1",
            "score": 1 or 0 or -1,
            "reason": "brief explanation",
            "evidence": "supporting sentence(s) from the article"
        }}
    ]
}}
</output_format>

CRITICAL: You MUST return results for ALL rubric items in the input, and the "rubric_item" text MUST match the input text EXACTLY (character-level match).

<passage>
{paper}
</passage>
<task_and_rubric>
{rubric}
</task_and_rubric>
Now, please begin your generation"""


def load_tasks() -> dict[int, dict]:
    out: dict[int, dict] = {}
    with TASKS_JSONL.open() as fh:
        for line in fh:
            obj = json.loads(line)
            out[int(obj["idx"])] = obj
    return out


def call_deepseek(api_key: str, model: str, base_url: str, prompt: str, timeout_s: int = 600) -> tuple[str, dict]:
    response = httpx.post(
        base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a strict, deterministic rubric grader. Return only the requested JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        },
        timeout=timeout_s,
    )
    response.raise_for_status()
    body = response.json()
    text = body["choices"][0]["message"]["content"]
    usage = body.get("usage", {})
    return text, usage


FENCED = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_judge_text(text: str) -> dict | None:
    candidates = []
    matches = FENCED.findall(text)
    if matches:
        candidates.append(matches[0])
    candidates.append(text)
    for cand in candidates:
        cand = cand.strip()
        if not cand:
            continue
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass
        # Try trimming to outermost braces.
        m = re.search(r"\{.*\}", cand, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
    return None


def judge_batch(
    *,
    api_key: str,
    model: str,
    base_url: str,
    paper: str,
    task_text: str,
    blocked: dict,
    rubric_items: list[str],
    max_retries: int,
) -> tuple[list[dict] | None, dict]:
    rubric_input = {"task": task_text, "rubric_items": rubric_items, "blocked": blocked}
    rubric_json = json.dumps(rubric_input, ensure_ascii=False, indent=2)
    prompt = PROMPT_TEMPLATE.format(paper=paper, rubric=rubric_json)
    last_usage: dict = {}
    for attempt in range(1, max_retries + 1):
        try:
            raw, usage = call_deepseek(api_key, model, base_url, prompt)
            last_usage = usage
            parsed = parse_judge_text(raw)
            if not parsed or not isinstance(parsed.get("results"), list):
                print(f"  [retry {attempt}/{max_retries}] parse failed")
                continue
            returned_items = [r.get("rubric_item", "") for r in parsed["results"]]
            missing = [item for item in rubric_items if item not in returned_items]
            if missing:
                print(
                    f"  [retry {attempt}/{max_retries}] {len(missing)} rubric items missing from response"
                )
                continue
            return parsed["results"], last_usage
        except httpx.HTTPError as exc:
            print(f"  [retry {attempt}/{max_retries}] HTTP error: {exc}")
            time.sleep(2)
            continue
        except Exception as exc:
            print(f"  [retry {attempt}/{max_retries}] {type(exc).__name__}: {exc}")
            continue
    return None, last_usage


def grade_one(
    *,
    label: str,
    idx: int,
    md_path: Path,
    rubric_content: dict,
    api_key: str,
    model: str,
    base_url: str,
    chunk_size: int,
    max_paper_chars: int,
    max_retries: int,
) -> dict:
    paper = md_path.read_text(encoding="utf-8", errors="ignore")
    if len(paper) > max_paper_chars:
        paper = paper[:max_paper_chars]
    task_text = rubric_content.get("task", "")
    blocked = rubric_content.get("blocked", {}) or {}
    rubric = rubric_content.get("rubric", {}) or {}

    items: list[str] = []
    dim_map: dict[str, str] = {}
    for dim in ("info_recall", "analysis", "presentation"):
        for item in rubric.get(dim, []) or []:
            items.append(item)
            dim_map[item] = dim
    if not items:
        return {"model": label, "idx": idx, "result": {"error": "no rubric items"}}

    batches = [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)] if chunk_size > 0 else [items]

    all_results: list[dict] = []
    total_input = total_output = total_tokens = 0
    for batch_no, batch in enumerate(batches, start=1):
        print(f"  idx={idx} batch {batch_no}/{len(batches)} ({len(batch)} items)")
        results, usage = judge_batch(
            api_key=api_key,
            model=model,
            base_url=base_url,
            paper=paper,
            task_text=task_text,
            blocked=blocked,
            rubric_items=batch,
            max_retries=max_retries,
        )
        if results is None:
            return {
                "model": label,
                "idx": idx,
                "result": {"error": f"batch {batch_no} failed after {max_retries} retries"},
            }
        all_results.extend(results)
        total_input += int(usage.get("prompt_tokens") or 0)
        total_output += int(usage.get("completion_tokens") or 0)
        total_tokens += int(usage.get("total_tokens") or 0)

    scores_by_dim: dict[str, dict[str, dict]] = {
        "info_recall": {},
        "analysis": {},
        "presentation": {},
    }
    for r in all_results:
        item = r.get("rubric_item", "")
        dim = dim_map.get(item)
        if dim is None:
            continue
        scores_by_dim[dim][item] = {
            "score": r.get("score", 0),
            "reason": r.get("reason", ""),
            "evidence": r.get("evidence", ""),
        }

    return {
        "model": label,
        "idx": idx,
        "result": {
            "task": task_text,
            "scores": scores_by_dim,
            "usage_summary": {
                "total_tokens": total_tokens,
                "input_tokens": total_input,
                "output_tokens": total_output,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSeek-as-judge for DRB-II reports.")
    parser.add_argument("--label", required=True, help="Subdir under report/ to grade (e.g. evoresearcher).")
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--max-paper-chars", type=int, default=150000)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--out-suffix", default="deepseek")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY not set in env or .env")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions")

    report_dir = DRB2_REPO / "report" / args.label
    if not report_dir.is_dir():
        raise SystemExit(f"Report dir not found: {report_dir}")

    fname_re = re.compile(r"^idx-(\d+)(?:-.*)?\.(md|txt|html)$", re.IGNORECASE)
    pairs: list[tuple[int, Path]] = []
    for fname in sorted(report_dir.iterdir()):
        m = fname_re.match(fname.name)
        if m:
            pairs.append((int(m.group(1)), fname))
    if not pairs:
        raise SystemExit(f"No report files matched in {report_dir}")
    print(f"[judge] {len(pairs)} report file(s) to grade under label='{args.label}'")

    tasks = load_tasks()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{args.label}__{args.out_suffix}.jsonl"

    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = []
        for idx, md_path in pairs:
            content = tasks.get(idx, {}).get("content")
            if not content:
                print(f"[skip] idx={idx} not in tasks_and_rubrics.jsonl")
                continue
            futures.append(
                pool.submit(
                    grade_one,
                    label=args.label,
                    idx=idx,
                    md_path=md_path,
                    rubric_content=content,
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                    chunk_size=args.chunk_size,
                    max_paper_chars=args.max_paper_chars,
                    max_retries=args.max_retries,
                )
            )
        with out_path.open("w") as fh:
            for fut in as_completed(futures):
                line: dict[str, Any] = fut.result()
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
                fh.flush()
                err = (line.get("result") or {}).get("error")
                if err:
                    print(f"[judge] idx={line['idx']} ERROR: {err}")
                else:
                    counts = {dim: len(v) for dim, v in line["result"]["scores"].items()}
                    print(f"[judge] idx={line['idx']} done; counts={counts}")

    print(f"[judge] wrote {out_path}")


if __name__ == "__main__":
    main()
