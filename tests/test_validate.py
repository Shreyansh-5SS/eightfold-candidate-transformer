from src.pipeline.validate import validate_output


def _config():
    return {
        "fields": [
            {"path": "full_name", "type": "string", "required": True},
            {"path": "emails", "type": "string[]", "required": False},
        ]
    }


def test_valid_record_passes():
    projected = {"full_name": "Aarav Sharma", "emails": ["a@example.com"]}
    ok, errors = validate_output(projected, _config())
    assert ok is True
    assert errors == []


def test_missing_required_field_fails_clearly():
    projected = {"emails": ["a@example.com"]}
    ok, errors = validate_output(projected, _config())
    assert ok is False
    assert len(errors) == 1
    assert "full_name" in errors[0]


def test_wrong_type_fails_clearly():
    projected = {"full_name": "Aarav Sharma", "emails": "not-a-list"}
    ok, errors = validate_output(projected, _config())
    assert ok is False
    assert len(errors) == 1