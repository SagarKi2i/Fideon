"""Verify no ACORD base_doc_id appears in both train and holdout (in-domain rows only)."""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
TRAIN = BACKEND / "runs" / "t.jsonl"
HOLD = BACKEND / "runs" / "h.jsonl"


def main() -> None:
    train_ids: list[str] = []
    hold_ids: list[str] = []

    if not TRAIN.exists():
        print(f"Missing {TRAIN} — run export first.", file=sys.stderr)
        sys.exit(1)
    if not HOLD.exists():
        print(f"Missing {HOLD} — run export first.", file=sys.stderr)
        sys.exit(1)

    with TRAIN.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            bid = row.get("metadata", {}).get("base_doc_id")
            if bid and row.get("metadata", {}).get("category") != "oos":
                train_ids.append(bid)

    with HOLD.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            bid = row.get("metadata", {}).get("base_doc_id")
            if bid and row.get("metadata", {}).get("category") != "oos":
                hold_ids.append(bid)

    overlap = set(train_ids) & set(hold_ids)
    print(f"Train in-domain doc IDs : {len(set(train_ids))}")
    print(f"Holdout in-domain doc IDs: {len(set(hold_ids))}")
    print(f"Contamination            : {overlap if overlap else 'NONE - OK'}")


if __name__ == "__main__":
    main()
