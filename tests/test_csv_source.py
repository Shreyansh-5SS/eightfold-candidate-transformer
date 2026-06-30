import os
import tempfile
from src.sources.csv_source import RecruiterCSVSource


def test_parses_valid_rows():
    parser = RecruiterCSVSource()
    records = parser.parse("sample_inputs/recruiter.csv")
    # 4 valid rows, 1 skipped
    assert len(records) == 4
    names = [r.data.get("full_name") for r in records]
    assert "Aarav Sharma" in names
    assert "Linus Torvalds" in names


def test_skips_malformed_row():
    csv_content = "name,email,phone,current_company,title\n,,,, \nGood Person,good@example.com,,,,\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        path = f.name
    try:
        parser = RecruiterCSVSource()
        records = parser.parse(path)
        assert len(records) == 1
        assert records[0].data["full_name"] == "Good Person"
    finally:
        os.unlink(path)


def test_missing_file_returns_empty_list():
    parser = RecruiterCSVSource()
    records = parser.parse("sample_inputs/does_not_exist.csv")
    assert records == []