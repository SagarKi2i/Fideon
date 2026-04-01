import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fine_tuning.acord125_pipeline.ocr_extract import _estimate_text_quality, detect_template  # noqa: E402


def test_template_detection():
    t = "COMMERCIAL INSURANCE APPLICATION\nACORD 125"
    assert detect_template(t) == "acord_125"
    assert detect_template("random document") == "unknown"


def test_text_quality_estimator():
    good = "Agency Name: ACME\nCarrier: ABC\nPolicy Number: AB1234567\nEmail: x@y.com"
    bad = "@@@ ### !!!"
    assert _estimate_text_quality(good) > _estimate_text_quality(bad)
