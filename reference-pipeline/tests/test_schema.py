"""Citation-required is enforced in code, not just asked for in the prompt.

No model calls. Every test here feeds validate_finding the kind of output
a model actually produces and checks that bad output is dropped.
"""

import review


GOOD = {
    "severity": "high",
    "title": "SQL injection",
    "line_start": 59,
    "line_end": 59,
    "evidence": 'sql = "SELECT id, item FROM orders WHERE item LIKE \'%%%s%%\'" % query',
    "explanation": "The search term is formatted into the query.",
    "confidence": "high",
}


def validate(overrides=None, file_path="target-app/models.py", **kwargs):
    candidate = dict(GOOD)
    if overrides:
        candidate.update(overrides)
    return review.validate_finding(candidate, file_path, **kwargs)


def test_a_well_formed_finding_survives():
    result = validate()
    assert result is not None
    assert result["file"] == "target-app/models.py"
    assert result["line_start"] == 59


def test_finding_without_a_line_is_dropped():
    assert validate({"line_start": None}) is None


def test_finding_with_a_zero_line_is_dropped():
    assert validate({"line_start": 0, "line_end": 0}) is None


def test_finding_with_a_string_line_is_dropped():
    assert validate({"line_start": "59"}) is None


def test_finding_without_a_file_is_dropped():
    assert validate(file_path="") is None


def test_finding_without_evidence_is_dropped():
    assert validate({"evidence": "   "}) is None


def test_finding_without_a_title_is_dropped():
    assert validate({"title": ""}) is None


def test_a_bare_string_instead_of_an_object_is_dropped():
    assert review.validate_finding("SQL injection on line 59", "f.py") is None


def test_reversed_line_range_is_repaired():
    result = validate({"line_start": 60, "line_end": 55})
    assert result["line_start"] == 55
    assert result["line_end"] == 60


def test_line_beyond_the_end_of_the_file_is_dropped():
    assert validate({"line_start": 9000, "line_end": 9000}, line_budget=100) is None


def test_line_inside_the_file_is_kept():
    assert validate({"line_start": 59, "line_end": 59}, line_budget=100) is not None


def test_unknown_severity_becomes_info_rather_than_dropping_the_finding():
    result = validate({"severity": "SEVERE"})
    assert result["severity"] == "info"


def test_uppercase_severity_is_normalized():
    assert validate({"severity": "HIGH"})["severity"] == "high"


def test_unknown_confidence_becomes_low():
    assert validate({"confidence": "certain"})["confidence"] == "low"


def test_scanner_reference_is_recorded_when_present():
    result = validate(scanner_refs=["B608"])
    assert result["scanner_ref"] == "B608"
    assert result["id"].startswith("B608:")


def test_scanner_reference_is_null_for_freeform_findings():
    assert validate(scanner_refs=None)["scanner_ref"] is None


def test_multiple_scanner_references_are_joined():
    result = validate(scanner_refs=["B105", "Secret Keyword"])
    assert result["scanner_ref"] == "B105, Secret Keyword"


def test_long_evidence_is_truncated():
    result = validate({"evidence": GOOD["evidence"] + "x" * 2000})
    assert len(result["evidence"]) == 500


def test_evidence_from_another_file_is_dropped():
    """The model read auth.py but filed its quote under models.py."""
    quote = 'if password == "password123":'
    assert validate({"evidence": quote}) is None


def test_evidence_with_copied_line_numbers_still_matches():
    """Models copy the '59: ' prefix from the numbered source they were shown."""
    assert validate({"evidence": "59: " + GOOD["evidence"]}) is not None


def test_evidence_matches_despite_whitespace():
    spaced = "sql   =   " + GOOD["evidence"][len("sql = "):]
    assert validate({"evidence": spaced}) is not None


def test_every_schema_key_is_present_on_a_validated_finding():
    expected = {
        "id", "severity", "title", "file", "line_start", "line_end",
        "evidence", "explanation", "scanner_ref", "confidence",
    }
    assert set(validate()) == expected


def test_severity_and_confidence_vocabularies_match_the_documented_schema():
    assert review.SEVERITIES == ["critical", "high", "medium", "low", "info"]
    assert review.CONFIDENCES == ["high", "medium", "low"]


# --------------------------------------------------- test-code context


def test_files_under_a_tests_directory_are_recognized():
    assert review.looks_like_test_code("target-app/tests/conftest.py")
    assert review.looks_like_test_code("a/b/test/helpers.py")


def test_test_prefixed_and_suffixed_filenames_are_recognized():
    assert review.looks_like_test_code("tests/test_planted_bugs.py")
    assert review.looks_like_test_code("pkg/widget_test.py")
    assert review.looks_like_test_code("conftest.py")


def test_fixture_and_spec_directories_are_recognized():
    assert review.looks_like_test_code("app/fixtures/data.py")
    assert review.looks_like_test_code("app/spec/thing.py")


def test_application_code_is_not_mistaken_for_test_code():
    assert not review.looks_like_test_code("target-app/app.py")
    assert not review.looks_like_test_code("target-app/auth.py")
    assert not review.looks_like_test_code("src/latest/protest.py")


SCANNER = {
    "tool": "Bandit",
    "refs": ["B105"],
    "line": 15,
    "file": "target-app/app.py",
    "message": "Possible hardcoded password.",
}


def test_triage_prompt_carries_the_scanner_facts():
    user = review.build_triage_user(SCANNER, "1: x = 1")
    assert "B105" in user
    assert "line 15" in user
    assert "target-app/app.py" in user
    assert "Numbered source:" in user


def test_application_code_gets_no_test_context_line():
    user = review.build_triage_user(SCANNER, "1: x = 1")
    assert "test or fixture code" not in user


def test_test_code_is_flagged_as_context_for_the_model():
    scanner = dict(SCANNER, file="target-app/tests/conftest.py")
    user = review.build_triage_user(scanner, "1: x = 1")
    assert "test or fixture code" in user


def test_evidence_wrapped_in_escaped_quotes_still_matches():
    """gpt-oss quotes the line as a JSON-escaped string inside the string."""
    wrapped = '"sql = \\"SELECT id, item FROM orders WHERE item LIKE \'%%%s%%\'\\" % query"'
    assert validate({"evidence": wrapped}) is not None


def test_wrapping_does_not_let_other_text_through():
    assert validate({"evidence": '"if password == \\"password123\\":"'}) is None
