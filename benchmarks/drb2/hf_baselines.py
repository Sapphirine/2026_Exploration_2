"""Stage HF baseline reports (Perplexity-Research, Qwen-3-Max-DeepResearch) for re-grading.

The HF dataset `muset-ai/DeepResearch-Bench-II-Dataset` ships PDFs across two
`label` classes but has an empty README, so we cannot assume a schema. This
script has three subcommands so we can fail fast at the cheapest step:

  probe   -- print the dataset schema and one sample row per label class. ~30s.
  match   -- given a candidate field name (e.g. `task_id` or `filename`), build
             a mapping from pilot idx -> HF row index. Prints the mapping for
             review without touching the filesystem.
  extract -- download + text-extract the matched rows for our pilot indices and
             write them to DeepResearch-Bench-II/report/{perplexity_research,
             qwen3_max}/idx-{N}.md so evaluate_with_deepseek.py can grade them.

Run order at "go" time:

    pip install datasets pypdf
    python benchmarks/drb2/hf_baselines.py probe
    # inspect output, pick the field that exposes the task id, then:
    python benchmarks/drb2/hf_baselines.py match  --id-field <FIELD>
    python benchmarks/drb2/hf_baselines.py extract --id-field <FIELD>
    python benchmarks/drb2/evaluate_with_deepseek.py --label perplexity_research
    python benchmarks/drb2/evaluate_with_deepseek.py --label qwen3_max
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRB2_REPO = REPO_ROOT.parent / "DeepResearch-Bench-II"
PILOT_JSON = REPO_ROOT / "benchmarks" / "drb2" / "pilot_tasks.json"
TASKS_JSONL = DRB2_REPO / "tasks_and_rubrics.jsonl"

DATASET_NAME = "muset-ai/DeepResearch-Bench-II-Dataset"
LABEL_TO_DIR = {
    "Perplexity-Research": "perplexity_research",
    "Qwen-3-Max-DeepResearch": "qwen3_max",
}


def load_pilot_indices() -> list[int]:
    return [entry["idx"] for entry in json.loads(PILOT_JSON.read_text())]


def load_pilot_lookup() -> dict[int, dict]:
    """Pilot idx -> task object from tasks_and_rubrics.jsonl. Useful for matching by id/title."""
    pilot_idx = set(load_pilot_indices())
    out: dict[int, dict] = {}
    with TASKS_JSONL.open() as fh:
        for line in fh:
            obj = json.loads(line)
            if int(obj["idx"]) in pilot_idx:
                out[int(obj["idx"])] = obj
    return out


def cmd_probe(_: argparse.Namespace) -> None:
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("Missing dependency: pip install datasets")
    print(f"[probe] loading {DATASET_NAME} (first 5 rows)...")
    ds = load_dataset(DATASET_NAME, split="train[:5]")
    print(f"[probe] features: {ds.features}")
    print(f"[probe] columns: {ds.column_names}")
    print(f"[probe] first row keys: {list(ds[0].keys())}")
    print()
    for i, row in enumerate(ds):
        printable = {k: ("<bytes>" if isinstance(v, (bytes, bytearray)) else v) for k, v in row.items()}
        print(f"[probe] row[{i}] = {json.dumps(printable, indent=2, default=str)[:1200]}")
        print("---")
    print("[probe] now load full split to count per-label rows")
    full = load_dataset(DATASET_NAME, split="train")
    if "label" in full.column_names:
        from collections import Counter

        print(f"[probe] label distribution: {Counter(full['label'])}")
    print(f"[probe] total rows: {len(full)}")


def _candidate_idx_from_value(v) -> int | None:
    """Best-effort coercion of a row field into a DRB-II idx int."""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v)
    # Look for digit-runs that match plausible DRB-II indices.
    matches = re.findall(r"(?<!\d)(\d{1,3})(?!\d)", s)
    for m in matches:
        i = int(m)
        if 0 <= i <= 200:
            return i
    return None


def _build_match_table(full, id_field: str, by_id: dict[str, int] | None):
    """Return list of (pilot_idx, label, row_index) for hits."""
    pilot_idx = set(load_pilot_indices())
    hits: list[tuple[int, str, int]] = []
    for row_index, row in enumerate(full):
        label = row.get("label")
        target_dir = LABEL_TO_DIR.get(label)
        if target_dir is None:
            continue
        raw = row.get(id_field)
        if by_id is not None and raw in by_id:
            idx = by_id[raw]
        else:
            idx = _candidate_idx_from_value(raw)
        if idx is None or idx not in pilot_idx:
            continue
        hits.append((idx, label, row_index))
    return hits


def cmd_match(args: argparse.Namespace) -> None:
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("Missing dependency: pip install datasets")
    full = load_dataset(DATASET_NAME, split="train")
    print(f"[match] field='{args.id_field}', total rows={len(full)}")

    by_id: dict[str, int] | None = None
    if args.via_task_id:
        # If the field stores DRB-II "id" strings (e.g. "task27+"), map id -> idx.
        by_id = {}
        with TASKS_JSONL.open() as fh:
            for line in fh:
                obj = json.loads(line)
                if "id" in obj:
                    by_id[obj["id"]] = int(obj["idx"])
        print(f"[match] using id->idx map ({len(by_id)} entries)")

    hits = _build_match_table(full, args.id_field, by_id)
    pilot = sorted(load_pilot_indices())
    print(f"[match] hits: {len(hits)} / expected {len(pilot)*2}")
    by_label: dict[str, dict[int, int]] = {}
    for idx, label, row_index in hits:
        by_label.setdefault(label, {})[idx] = row_index
    for label in LABEL_TO_DIR:
        cov = by_label.get(label, {})
        missing = [i for i in pilot if i not in cov]
        print(f"  {label}: {len(cov)}/{len(pilot)} matched. Missing: {missing}")
    if any(len(by_label.get(l, {})) < len(pilot) for l in LABEL_TO_DIR):
        sys.exit(1)


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("Missing dependency: pip install pypdf")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception as exc:
            parts.append(f"[extraction error: {exc}]")
    return "\n\n".join(p for p in parts if p.strip())


def cmd_extract(args: argparse.Namespace) -> None:
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("Missing dependency: pip install datasets")
    full = load_dataset(DATASET_NAME, split="train")

    by_id: dict[str, int] | None = None
    if args.via_task_id:
        by_id = {}
        with TASKS_JSONL.open() as fh:
            for line in fh:
                obj = json.loads(line)
                if "id" in obj:
                    by_id[obj["id"]] = int(obj["idx"])
    hits = _build_match_table(full, args.id_field, by_id)

    pdf_field = args.pdf_field
    written: list[Path] = []
    for idx, label, row_index in hits:
        row = full[row_index]
        target_dir = DRB2_REPO / "report" / LABEL_TO_DIR[label]
        target_dir.mkdir(parents=True, exist_ok=True)
        pdf_obj = row.get(pdf_field)
        if pdf_obj is None:
            print(f"[extract] WARN: idx={idx} label={label}: field '{pdf_field}' is missing")
            continue
        # HF Audio/Image/binary fields commonly come back as dicts with 'bytes'.
        if isinstance(pdf_obj, dict) and "bytes" in pdf_obj:
            pdf_bytes = pdf_obj["bytes"]
        elif isinstance(pdf_obj, (bytes, bytearray)):
            pdf_bytes = bytes(pdf_obj)
        else:
            print(f"[extract] WARN: idx={idx} label={label}: unsupported pdf field type {type(pdf_obj)}")
            continue
        text = _extract_pdf_text(pdf_bytes)
        if not text.strip():
            print(f"[extract] WARN: idx={idx} label={label}: empty extraction")
        out_path = target_dir / f"idx-{idx}.md"
        out_path.write_text(text, encoding="utf-8")
        written.append(out_path)
        print(f"[extract] wrote {out_path.relative_to(REPO_ROOT.parent)} ({len(text)} chars)")
    print(f"[extract] {len(written)} files written")


def main() -> None:
    parser = argparse.ArgumentParser(description="HF baseline staging for DRB-II re-grading.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("probe", help="Print HF dataset schema and per-label distribution.")

    p_match = sub.add_parser("match", help="Build pilot idx -> HF row mapping.")
    p_match.add_argument("--id-field", required=True, help="Row field that exposes the task id/idx.")
    p_match.add_argument(
        "--via-task-id",
        action="store_true",
        help="Treat the field as DRB-II 'id' strings (e.g. task27+) and lookup idx via tasks_and_rubrics.jsonl.",
    )

    p_extract = sub.add_parser("extract", help="Download and extract pilot baseline PDFs to report dirs.")
    p_extract.add_argument("--id-field", required=True)
    p_extract.add_argument("--pdf-field", required=True, help="Row field that holds the PDF bytes.")
    p_extract.add_argument("--via-task-id", action="store_true")

    args = parser.parse_args()
    {"probe": cmd_probe, "match": cmd_match, "extract": cmd_extract}[args.cmd](args)


if __name__ == "__main__":
    main()
