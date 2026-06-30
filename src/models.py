from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class RawRecord:
    """Common output type every source parser returns — one per detected person,
    before normalization/merge."""
    source: str
    candidate_key: Optional[str]   # normalized email if known, else None
    data: Dict[str, Any]
    fetched_at: str


@dataclass
class Skill:
    name: str
    confidence: float
    sources: List[str] = field(default_factory=list)


@dataclass
class ExperienceEntry:
    company: str
    title: str
    start: Optional[str] = None
    end: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class EducationEntry:
    institution: str
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[int] = None


@dataclass
class Location:
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None


@dataclass
class Links:
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: List[str] = field(default_factory=list)


@dataclass
class ProvenanceEntry:
    field: str
    source: str
    method: str  # "structured_direct" | "unstructured_extracted" | "merged_multi_source" | "failed_normalize"


@dataclass
class CanonicalCandidate:
    candidate_id: str
    full_name: str
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    location: Location = field(default_factory=Location)
    links: Links = field(default_factory=Links)
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: List[Skill] = field(default_factory=list)
    experience: List[ExperienceEntry] = field(default_factory=list)
    education: List[EducationEntry] = field(default_factory=list)
    provenance: List[ProvenanceEntry] = field(default_factory=list)
    overall_confidence: float = 0.0

    # internal, not part of output schema — per-field confidence used by project.py
    field_confidence: Dict[str, float] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("field_confidence", None)
        return d