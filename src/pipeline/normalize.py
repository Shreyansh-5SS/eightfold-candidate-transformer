import logging
import re
from datetime import datetime
from typing import Tuple, Optional

import phonenumbers

logger = logging.getLogger(__name__)


# ---------- Phone ----------

def normalize_phone(raw: Optional[str], default_region: str = "IN") -> Tuple[Optional[str], bool]:
    if not raw or not raw.strip():
        return None, False
    try:
        parsed = phonenumbers.parse(raw.strip(), default_region)
        if not phonenumbers.is_valid_number(parsed):
            return None, False
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return e164, True
    except Exception as e:
        logger.debug(f"[normalize_phone] failed for {raw!r}: {e}")
        return None, False


# ---------- Date ----------

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m",
    "%m/%Y",
    "%m-%Y",
    "%b %Y",     # Jan 2020
    "%B %Y",     # January 2020
    "%Y",
]


def normalize_date(raw: Optional[str]) -> Tuple[Optional[str], bool]:
    if not raw or not raw.strip():
        return None, False
    raw = raw.strip()

    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m"), True
        except ValueError:
            continue

    # bare 4-digit year fallback
    if re.fullmatch(r"\d{4}", raw):
        return f"{raw}-01", True

    logger.debug(f"[normalize_date] unparseable: {raw!r}")
    return None, False


# ---------- Country ----------

_COUNTRY_LOOKUP = {
    "us": "US", "usa": "US", "united states": "US", "united states of america": "US",
    "in": "IN", "india": "IN",
    "uk": "GB", "gb": "GB", "united kingdom": "GB", "britain": "GB",
    "ca": "CA", "canada": "CA",
    "au": "AU", "australia": "AU",
    "de": "DE", "germany": "DE", "deutschland": "DE",
}


def normalize_country(raw: Optional[str]) -> Tuple[Optional[str], bool]:
    if not raw or not raw.strip():
        return None, False
    key = raw.strip().lower()
    if key in _COUNTRY_LOOKUP:
        return _COUNTRY_LOOKUP[key], True
    logger.debug(f"[normalize_country] unknown country string: {raw!r}")
    return None, False


# ---------- Skills ----------

CANONICAL_SKILLS = {
    "js": "JavaScript", "javascript": "JavaScript",
    "ts": "TypeScript", "typescript": "TypeScript",
    "py": "Python", "python": "Python",
    "golang": "Go", "go": "Go",
    "reactjs": "React", "react": "React", "react.js": "React",
    "nodejs": "Node.js", "node": "Node.js", "node.js": "Node.js",
    "k8s": "Kubernetes", "kubernetes": "Kubernetes",
    "ml": "Machine Learning", "machine learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "c++": "C++", "cpp": "C++",
    "c#": "C#", "csharp": "C#",
    "java": "Java",
    "ruby": "Ruby",
    "rust": "Rust",
    "shell": "Shell",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
    "docker": "Docker",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "mongo": "MongoDB", "mongodb": "MongoDB",
    "git": "Git",
    "linux": "Linux",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
}


def normalize_skill(raw: str) -> Tuple[str, float]:
    if not raw or not raw.strip():
        return "", 0.0
    key = raw.strip().lower()
    if key in CANONICAL_SKILLS:
        return CANONICAL_SKILLS[key], 1.0
    return raw.strip().title(), 0.5