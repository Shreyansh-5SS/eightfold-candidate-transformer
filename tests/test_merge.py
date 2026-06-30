from datetime import datetime, timezone
from src.models import RawRecord
from src.pipeline.merge import merge_records


def _record(source, candidate_key, data):
    return RawRecord(source=source, candidate_key=candidate_key, data=data,
                      fetched_at=datetime.now(timezone.utc).isoformat())


def test_matched_by_email_with_conflicting_phones():
    r1 = _record("recruiter_csv", "a@example.com",
                  {"full_name": "Aarav Sharma", "email": "a@example.com", "phone": "9876543210"})
    r2 = _record("recruiter_csv", "a@example.com",
                  {"full_name": "Aarav Sharma", "email": "a@example.com", "phone": "9123456780"})

    candidates = merge_records([r1, r2])
    assert len(candidates) == 1
    c = candidates[0]
    assert len(c.phones) == 2  # both kept, not overwritten
    assert c.field_confidence["phones"] < 0.9  # conflict penalty applied


def test_github_only_candidate_no_email():
    r = _record("github", None,
                {"full_name": "Octo Cat", "headline": "I build things", "languages": ["Python", "Go"],
                 "github_url": "https://github.com/octocat", "location_raw": "San Francisco, US"})
    candidates = merge_records([r])
    assert len(candidates) == 1
    c = candidates[0]
    assert c.full_name == "Octo Cat"
    assert c.overall_confidence > 0
    assert len(c.skills) == 2


def test_skill_agreement_boosts_confidence():
    r1 = _record("github", None, {"full_name": "Jane Doe", "languages": ["Python"]})
    r2 = _record("github", None, {"full_name": "Jane Doe", "languages": ["py"]})
    candidates = merge_records([r1, r2])
    assert len(candidates) == 1
    skill = next(s for s in candidates[0].skills if s.name == "Python")
    assert "github" in skill.sources
    assert skill.confidence >= 1.0  # capped at 1.0 even after bonus

def test_field_priority_override_changes_phone_order():
    r1 = _record("recruiter_csv", "x@example.com",
                  {"full_name": "Test Person", "email": "x@example.com", "phone": "9876543210"})
    r2 = _record("github", None,
                  {"full_name": "Test Person", "headline": "From GitHub"})
    r2.data["phone"] = "9123456780"  # simulate a phone-bearing unstructured source for the test

    default_candidates = merge_records([r1, r2])
    assert default_candidates[0].phones[0] == "+919876543210"  # recruiter_csv first by default order

    priority_candidates = merge_records([r1, r2], field_priority={"phones": ["github", "recruiter_csv"]})
    assert priority_candidates[0].phones[0] == "+919123456780"  # github now wins