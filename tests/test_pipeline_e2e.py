from unittest.mock import patch, MagicMock
from src.sources.csv_source import RecruiterCSVSource
from src.sources.github_source import GitHubSource
from src.pipeline.merge import merge_records
from src.pipeline.project import project_candidate
from src.pipeline.validate import validate_output


def _default_config():
    return {
        "fields": [
            {"path": "candidate_id", "type": "string", "required": True},
            {"path": "full_name", "type": "string", "required": True},
            {"path": "emails", "type": "string[]"},
            {"path": "phones", "type": "string[]", "normalize": "E164"},
            {"path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical"},
        ],
        "include_confidence": True,
        "on_missing": "null",
    }


@patch("src.sources.github_source.requests.get")
def test_full_pipeline_produces_valid_output(mock_get):
    user_resp = MagicMock(status_code=200)
    user_resp.json.return_value = {
        "name": "Linus Torvalds", "bio": "Creator of Linux",
        "html_url": "https://github.com/torvalds", "location": "Portland, US",
    }
    repos_resp = MagicMock(status_code=200)
    repos_resp.json.return_value = [{"language": "C"}, {"language": "Shell"}]
    mock_get.side_effect = [user_resp, repos_resp]

    csv_records = RecruiterCSVSource().parse("sample_inputs/recruiter.csv")
    github_records = GitHubSource().parse("https://github.com/torvalds")

    candidates = merge_records(csv_records + github_records)
    config = _default_config()

    outputs = []
    for c in candidates:
        projected = project_candidate(c, config)
        is_valid, errors = validate_output(projected, config)
        assert is_valid, errors
        outputs.append(projected)

    assert len(outputs) > 0
    for o in outputs:
        assert o["candidate_id"]
        assert 0.0 <= o.get("_overall_confidence", 0.0) <= 1.0

    torvalds = next((o for o in outputs if o["full_name"] == "Linus Torvalds"), None)
    assert torvalds is not None
    # merged from both CSV and GitHub -> should have skills from github merge
    assert len(torvalds["skills"]) > 0


@patch("src.sources.github_source.requests.get")
def test_pipeline_survives_missing_and_404_sources(mock_get, tmp_path):
    # malformed CSV: only the broken row
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("name,email,phone,current_company,title\n,,,, \n", encoding="utf-8")

    mock_get.return_value = MagicMock(status_code=404)

    csv_records = RecruiterCSVSource().parse(str(bad_csv))
    github_records = GitHubSource().parse("https://github.com/this-user-does-not-exist-xyz")

    assert csv_records == []
    assert github_records == []

    candidates = merge_records(csv_records + github_records)
    assert candidates == []  # no crash, just empty output

    config = _default_config()
    outputs = [project_candidate(c, config) for c in candidates]
    assert outputs == []