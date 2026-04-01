"""
Convert training/eval datasets to strict JSON outputs for staging fine-tuning.

Usage:
  python -m fine_tuning.prepare_staging_data --dataset fine_tuning/dataset_mixed.json
  python -m fine_tuning.prepare_staging_data --eval-seen fine_tuning/eval_seen.json --eval-paraphrased fine_tuning/eval_paraphrased.json --eval-oos fine_tuning/eval_oos.json
  python -m fine_tuning.prepare_staging_data --all
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        return data["data"]
    raise ValueError(f"Expected a JSON list in {path}")


def _normalize_output(output: Any, *, is_oos: bool) -> str:
    raw = "" if output is None else str(output).strip()
    if raw:
        try:
            parsed = json.loads(raw)
            return json.dumps(parsed, ensure_ascii=False)
        except Exception:
            pass

    if is_oos:
        payload = {
            "in_scope": False,
            "refusal_reason": "out_of_scope",
            "message": raw or "This question is outside the scope of the document.",
        }
    else:
        payload = {
            "in_scope": True,
            "extracted_text": raw,
        }
    return json.dumps(payload, ensure_ascii=False)


def _convert_file(path: Path, *, is_oos: bool) -> tuple[int, int]:
    rows = _load_json_list(path)
    changed = 0
    for row in rows:
        old = row.get("output", "")
        new = _normalize_output(old, is_oos=is_oos)
        if old != new:
            row["output"] = new
            changed += 1
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(rows), changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare strict JSON staging datasets")
    parser.add_argument("--dataset", default=None, help="Path to training dataset JSON")
    parser.add_argument("--eval-seen", default=None, help="Path to seen eval JSON")
    parser.add_argument("--eval-paraphrased", default=None, help="Path to paraphrased eval JSON")
    parser.add_argument("--eval-oos", default=None, help="Path to out-of-scope eval JSON")
    parser.add_argument("--all", action="store_true", help="Convert default dataset + eval files under fine_tuning/")
    args = parser.parse_args()

    targets: list[tuple[Path, bool]] = []
    if args.all:
        targets.extend(
            [
                (Path("fine_tuning/dataset_mixed.json"), False),
                (Path("fine_tuning/eval_seen.json"), False),
                (Path("fine_tuning/eval_paraphrased.json"), False),
                (Path("fine_tuning/eval_oos.json"), True),
            ]
        )
    if args.dataset:
        targets.append((Path(args.dataset), False))
    if args.eval_seen:
        targets.append((Path(args.eval_seen), False))
    if args.eval_paraphrased:
        targets.append((Path(args.eval_paraphrased), False))
    if args.eval_oos:
        targets.append((Path(args.eval_oos), True))

    if not targets:
        raise SystemExit("No targets provided. Use --all or pass explicit file paths.")

    for path, is_oos in targets:
        p = path.resolve()
        if not p.exists():
            print(f"SKIP (missing): {p}")
            continue
        total, changed = _convert_file(p, is_oos=is_oos)
        print(f"UPDATED {p} rows={total} changed={changed}")


if __name__ == "__main__":
    main()

