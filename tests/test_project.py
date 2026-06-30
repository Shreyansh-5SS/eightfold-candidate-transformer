from src.models import CanonicalCandidate, Skill, Location, Links
from src.pipeline.project import project_candidate, MissingRequiredFieldError


def _sample_candidate():
    return CanonicalCandidate(
        candidate_id="abc-123",
        full_name="Aarav Sharma",
        emails=["aarav.sharma@example.com"],
        phones=["+919876543210"],
        location=Location(city="Pune", region=None, country="IN"),
        links=Links(github="https://github.com/aarav"),
        headline="Backend engineer",
        skills=[Skill(name="Python", confidence=1.0, sources=["github"])],
        field_confidence={"full_name": 0.9, "emails": 0.9, "phones": 0.9, "skills": 0.8},
        overall_confidence=0.87,
    )


def test_default_config_produces_all_fields():
    config = {
        "fields": [
            {"path": "full_name", "type": "string", "required": True},
            {"path": "emails", "type": "string[]"},
        ],
        "include_confidence": True,
        "on_missing": "null",
    }
    result = project_candidate(_sample_candidate(), config)
    assert result["full_name"] == "Aarav Sharma"
    assert result["emails"] == ["aarav.sharma@example.com"]
    assert "_overall_confidence" in result


def test_custom_config_renames_and_selects():
    config = {
        "fields": [
            {"path": "primary_email", "from": "emails[0]", "type": "string", "required": True},
            {"path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical"},
        ],
        "on_missing": "null",
    }
    result = project_candidate(_sample_candidate(), config)
    assert result["primary_email"] == "aarav.sharma@example.com"
    assert result["skills"] == ["Python"]
    assert "full_name" not in result


def test_on_missing_omit_drops_field():
    config = {
        "fields": [
            {"path": "headline2", "from": "nonexistent_field", "type": "string", "required": False},
        ],
        "on_missing": "omit",
    }
    result = project_candidate(_sample_candidate(), config)
    assert "headline2" not in result


def test_on_missing_error_raises_for_required():
    config = {
        "fields": [
            {"path": "nope", "from": "nonexistent_field", "type": "string", "required": True},
        ],
        "on_missing": "error",
    }
    try:
        project_candidate(_sample_candidate(), config)
        assert False, "expected MissingRequiredFieldError"
    except MissingRequiredFieldError:
        pass