import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fine_tuning.acord125_pipeline.postprocess import (  # noqa: E402
    apply_field_position_heuristics,
    compute_confidence,
    compute_field_confidence,
    compute_trust_score,
    consistency_check,
    enforce_grounding,
    enforce_schema,
    rule_based_extraction,
    validate_fields,
    validate_json,
    verify_field,
)


def test_validate_json_and_schema():
    raw = '{"agency_name":"ACME","x":"ignored"}'
    data = validate_json(raw)
    assert data is not None
    fixed = enforce_schema(data)
    assert "x" not in fixed
    assert fixed["agency_name"] == "ACME"
    assert fixed["carrier"] is None


def test_enforce_grounding_and_verify_field():
    text = "Agency Name: ACME Insurance\nCarrier: ABC Carrier"
    data = {"agency_name": "ACME Insurance", "carrier": "Wrong Carrier", "contact_name": None}
    grounded = enforce_grounding(data, text, threshold=85.0)
    assert grounded["agency_name"] == "ACME Insurance"
    assert grounded["carrier"] is None
    assert verify_field("agency_name", "ACME Insurance", text, threshold=85.0) == "ACME Insurance"
    assert verify_field("carrier", "Wrong Carrier", text, threshold=85.0) is None


def test_validate_fields_and_confidence():
    text = "Email: a@b.com\nPhone: +1 6305550244"
    data = {
        "agency_name": None,
        "contact_name": None,
        "carrier": None,
        "policy_number": None,
        "email": "invalid-email",
        "phone": "12",
    }
    validated = validate_fields(data)
    assert validated["email"] is None
    assert validated["phone"] is None
    conf = compute_confidence(validated, text)
    assert conf == 0.0


def test_rule_based_extraction_and_trust_score():
    text = "Policy Number: AB1234567\nEmail: x@y.com\nPhone: (630) 555-0244"
    rules = rule_based_extraction(text)
    assert rules["policy_number"] == "AB1234567"
    assert rules["email"] == "x@y.com"
    assert "phone" in rules

    data = {
        "agency_name": None,
        "contact_name": None,
        "carrier": None,
        "policy_number": "AB1234567",
        "email": "x@y.com",
        "phone": "(630) 555-0244",
    }
    trust = compute_trust_score(data, text)
    assert trust > 0.45


def test_consistency_check_nulls_invalid_values():
    text = "Agency Name: ACME Insurance\nCarrier: ACME Insurance"
    data = {
        "agency_name": "ACME Insurance",
        "contact_name": None,
        "carrier": "ACME Insurance",
        "policy_number": "NOT_IN_TEXT_123",
        "email": None,
        "phone": None,
    }
    out = consistency_check(data, text)
    assert out["carrier"] is None
    assert out["policy_number"] is None


def test_field_confidence_and_position_heuristics():
    text = "Agency Name: ACME\n" + ("x" * 200) + "\nCarrier: ABC Carrier"
    data = {
        "agency_name": "ACME",
        "contact_name": None,
        "carrier": "ABC Carrier",
        "policy_number": None,
        "email": None,
        "phone": None,
    }
    conf = compute_field_confidence(data, text)
    assert conf["agency_name"] > 80
    adjusted = apply_field_position_heuristics(data, text, conf)
    assert adjusted["carrier"] <= conf["carrier"]

