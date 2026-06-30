from src.pipeline.normalize import (
    normalize_phone, normalize_date, normalize_country, normalize_skill
)


def test_normalize_phone_indian_no_country_code():
    value, ok = normalize_phone("9876543210", default_region="IN")
    assert ok is True
    assert value.startswith("+91")


def test_normalize_phone_with_country_code():
    value, ok = normalize_phone("+1 415 555 2671", default_region="IN")
    assert ok is True
    assert value.startswith("+1")


def test_normalize_phone_garbage():
    value, ok = normalize_phone("not a phone number at all")
    assert ok is False
    assert value is None


def test_normalize_phone_empty():
    value, ok = normalize_phone("")
    assert ok is False


def test_normalize_date_formats():
    assert normalize_date("2020-05-14") == ("2020-05", True)
    assert normalize_date("05/2020") == ("2020-05", True)
    assert normalize_date("Jan 2020") == ("2020-01", True)
    assert normalize_date("2020") == ("2020-01", True)


def test_normalize_date_garbage():
    value, ok = normalize_date("not a date")
    assert ok is False
    assert value is None


def test_normalize_country_known():
    assert normalize_country("India") == ("IN", True)
    assert normalize_country("usa") == ("US", True)


def test_normalize_country_unknown():
    value, ok = normalize_country("Narnia")
    assert ok is False
    assert value is None


def test_normalize_skill_known_alias():
    name, conf = normalize_skill("js")
    assert name == "JavaScript"
    assert conf == 1.0


def test_normalize_skill_unknown():
    name, conf = normalize_skill("blockchain wizardry")
    assert name == "Blockchain Wizardry"
    assert conf == 0.5