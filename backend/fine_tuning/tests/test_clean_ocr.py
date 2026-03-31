import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fine_tuning.acord125_pipeline.clean_ocr import clean_ocr_text, before_after_example


def test_removes_noise_and_normalizes_labels():
    raw = "AGENCY:\nConvenis Agency\n[object Object]\nPHONE: 630.555.0244"
    out = clean_ocr_text(raw)
    assert "[object Object]" not in out
    assert "Agency Name: Convenis Agency" in out
    assert "Phone: (630) 555-0244" in out


def test_email_lowercase_and_date_normalization():
    raw = "EMAIL: JOHN.DOE@EXAMPLE.COM\nDATE: 03-15-2026"
    out = clean_ocr_text(raw)
    assert "john.doe@example.com" in out
    assert "03/15/2026" in out


def test_before_after_example_helper():
    ex = before_after_example()
    assert "before" in ex and "after" in ex
    assert "Agency Name:" in ex["after"]


def test_prunes_noisy_sections_and_adds_structured_block():
    raw = (
        "AGENCY: Convenis Agency\n"
        "CARRIER: ABC Carrier\n"
        "Attachments: file1.pdf file2.pdf\n"
        "Loss History: many lines\n"
    )
    out = clean_ocr_text(raw)
    assert "Attachments:" not in out
    assert "Loss History:" not in out
    assert "[Structured Fields]" in out

