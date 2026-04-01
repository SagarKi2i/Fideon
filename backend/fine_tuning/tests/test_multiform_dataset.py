import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fine_tuning.acord_form_pipeline.build_multiform_dataset import balance_dataset, validate_sample  # noqa: E402
from fine_tuning.acord_form_pipeline.schema_registry import SCHEMA_REGISTRY  # noqa: E402


def test_balance_dataset():
    s = [
        {"form_type": "acord_25", "messages": [1, 2, {"content": "{}"}]},
        {"form_type": "acord_25", "messages": [1, 2, {"content": "{}"}]},
        {"form_type": "acord_125", "messages": [1, 2, {"content": "{}"}]},
    ]
    out = balance_dataset(s)
    # min group count is 1 => 2 forms * 1 each
    assert len(out) == 2


def test_validate_sample_acord125():
    payload = {k: None for k in SCHEMA_REGISTRY["acord_125"]}
    sample = {
        "form_type": "acord_125",
        "messages": [
            {"role": "system", "content": "x"},
            {"role": "user", "content": "x"},
            {"role": "assistant", "content": json.dumps(payload)},
        ],
    }
    assert validate_sample(sample)

