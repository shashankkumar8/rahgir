from app.engine.evidence import evidence_completeness, safety_summary


def test_metadata_completeness_is_bounded():
    assert evidence_completeness({}) == 0
    assert evidence_completeness({"name": "x", "historic": "monument"}) > 0
    assert 0 <= evidence_completeness({"name": "x", "historic": "monument"}) <= 1


def test_no_reports_never_means_safe():
    result = safety_summary([])
    assert result["status"] == "insufficient_evidence"
    assert result["label"] == "Insufficient safety data"


def test_unverified_report_does_not_raise_confidence():
    result = safety_summary([{"status": "submitted"}])
    assert result["status"] == "insufficient_evidence"
