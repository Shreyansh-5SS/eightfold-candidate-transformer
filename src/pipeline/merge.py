import logging
import re
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional

from src.models import (
    RawRecord, CanonicalCandidate, Skill, ExperienceEntry,
    Location, Links, ProvenanceEntry,
)
from src.pipeline.normalize import (
    normalize_phone, normalize_country, normalize_skill,
)

logger = logging.getLogger(__name__)

STRUCTURED_SOURCES = {"recruiter_csv", "ats_json"}
UNSTRUCTURED_SOURCES = {"github"}

BASE_RELIABILITY = {**{s: 0.9 for s in STRUCTURED_SOURCES}, **{s: 0.7 for s in UNSTRUCTURED_SOURCES}}
AGREEMENT_BONUS = 0.1
CONFLICT_PENALTY = 0.2


def _norm_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return email.strip().lower()


def _norm_name_key(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return re.sub(r"\s+", " ", name.strip()).lower()


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _field_confidence(sources_contributed: List[str], conflicted: bool = False) -> float:
    if not sources_contributed:
        return 0.0
    base = max(BASE_RELIABILITY.get(s, 0.5) for s in sources_contributed)
    score = base
    if len(set(sources_contributed)) >= 2:
        score += AGREEMENT_BONUS
    if conflicted:
        score -= CONFLICT_PENALTY
    return round(_clamp(score), 2)


def _group_records(raw_records: List[RawRecord]) -> List[List[RawRecord]]:
    """Group raw records into one group per real-world person."""
    email_groups: Dict[str, List[RawRecord]] = {}
    name_groups: Dict[str, List[RawRecord]] = {}
    unkeyed: List[RawRecord] = []

    # pass 1: anything with a candidate_key (email) groups by email
    for r in raw_records:
        if r.candidate_key:
            email_groups.setdefault(r.candidate_key, []).append(r)
        else:
            unkeyed.append(r)

    # build a lookup of normalized name -> email group key, for fallback matching
    name_to_email_key: Dict[str, str] = {}
    for key, group in email_groups.items():
        for r in group:
            name = r.data.get("full_name")
            nk = _norm_name_key(name)
            if nk:
                name_to_email_key[nk] = key

    # pass 2: unkeyed records (e.g. GitHub) match into existing email group by name,
    # else fall back to their own name-keyed group
    for r in unkeyed:
        nk = _norm_name_key(r.data.get("full_name"))
        if nk and nk in name_to_email_key:
            email_groups[name_to_email_key[nk]].append(r)
        elif nk:
            name_groups.setdefault(nk, []).append(r)
        else:
            # no name and no email at all — shouldn't happen since sources filter this,
            # but guard anyway: each becomes its own singleton group
            name_groups.setdefault(str(uuid.uuid4()), []).append(r)

    groups = list(email_groups.values()) + list(name_groups.values())
    logger.info(f"[merge] grouped {len(raw_records)} raw records into {len(groups)} candidates")
    return groups


def _resolve_full_name(group: List[RawRecord]) -> str:
    names = [r.data.get("full_name") for r in group if r.data.get("full_name")]
    if not names:
        return "Unknown"
    return max(names, key=len)


def _resolve_emails(group: List[RawRecord], provenance: List[ProvenanceEntry]) -> List[str]:
    emails = []
    seen = set()
    for r in group:
        raw = r.data.get("email")
        ne = _norm_email(raw)
        if ne and ne not in seen:
            seen.add(ne)
            emails.append(ne)
            provenance.append(ProvenanceEntry(field="emails", source=r.source, method="structured_direct"))
    return emails


def _resolve_phones(group: List[RawRecord], field_conf: Dict[str, float],
                     provenance: List[ProvenanceEntry]) -> List[str]:
    phones = []
    seen = set()
    contributing_sources = []
    for r in group:
        raw = r.data.get("phone")
        if not raw:
            continue
        normalized, ok = normalize_phone(raw)
        if not ok:
            provenance.append(ProvenanceEntry(field="phones", source=r.source, method="failed_normalize"))
            continue
        contributing_sources.append(r.source)
        if normalized not in seen:
            seen.add(normalized)
            phones.append(normalized)
            provenance.append(ProvenanceEntry(field="phones", source=r.source, method="structured_direct"))

    conflicted = len(phones) > 1
    field_conf["phones"] = _field_confidence(contributing_sources, conflicted=conflicted)
    return phones


def _resolve_links_and_location(group: List[RawRecord], field_conf: Dict[str, float],
                                 provenance: List[ProvenanceEntry]) -> (Links, Location):
    links = Links()
    location = Location()
    for r in group:
        if r.source == "github":
            gh_url = r.data.get("github_url")
            if gh_url and not links.github:
                links.github = gh_url
                provenance.append(ProvenanceEntry(field="links.github", source=r.source, method="unstructured_extracted"))
            loc_raw = r.data.get("location_raw")
            if loc_raw and not location.city:
                # location_raw is a free-text string like "Portland, OR" — best-effort split
                parts = [p.strip() for p in loc_raw.split(",")]
                location.city = parts[0] if parts else None
                if len(parts) > 1:
                    country_code, ok = normalize_country(parts[-1])
                    location.country = country_code if ok else None
                    location.region = parts[1] if len(parts) > 2 else None
                provenance.append(ProvenanceEntry(field="location", source=r.source, method="unstructured_extracted"))
                field_conf["location"] = _field_confidence([r.source])
    return links, location


def _resolve_headline(group: List[RawRecord], field_conf: Dict[str, float],
                       provenance: List[ProvenanceEntry]) -> Optional[str]:
    for r in group:
        if r.source in UNSTRUCTURED_SOURCES:
            headline = r.data.get("headline")
            if headline:
                provenance.append(ProvenanceEntry(field="headline", source=r.source, method="unstructured_extracted"))
                field_conf["headline"] = _field_confidence([r.source])
                return headline
    return None


def _resolve_skills(group: List[RawRecord], field_conf: Dict[str, float],
                     provenance: List[ProvenanceEntry]) -> List[Skill]:
    skill_map: Dict[str, Skill] = {}
    for r in group:
        languages = r.data.get("languages") or []
        for raw_skill in languages:
            canon, base_conf = normalize_skill(raw_skill)
            if not canon:
                continue
            if canon in skill_map:
                existing = skill_map[canon]
                if r.source not in existing.sources:
                    existing.sources.append(r.source)
                    existing.confidence = round(_clamp(existing.confidence + AGREEMENT_BONUS), 2)
            else:
                skill_map[canon] = Skill(name=canon, confidence=base_conf, sources=[r.source])
                provenance.append(ProvenanceEntry(field=f"skills[{canon}]", source=r.source, method="unstructured_extracted"))

    skills = list(skill_map.values())
    field_conf["skills"] = _field_confidence(
        list({s for skill in skills for s in skill.sources}) or []
    )
    return skills


def _resolve_experience(group: List[RawRecord], provenance: List[ProvenanceEntry]) -> List[ExperienceEntry]:
    experience = []
    for r in group:
        if r.source in STRUCTURED_SOURCES:
            company = r.data.get("current_company")
            title = r.data.get("title")
            if company or title:
                experience.append(ExperienceEntry(
                    company=company or "Unknown",
                    title=title or "Unknown",
                    start=None, end=None, summary=None,
                ))
                provenance.append(ProvenanceEntry(field="experience", source=r.source, method="structured_direct"))
    return experience


def merge_records(raw_records: List[RawRecord]) -> List[CanonicalCandidate]:
    """Group raw records into one CanonicalCandidate per real person, resolving
    field-level conflicts and attaching provenance + confidence."""
    groups = _group_records(raw_records)
    candidates: List[CanonicalCandidate] = []

    for group in groups:
        provenance: List[ProvenanceEntry] = []
        field_conf: Dict[str, float] = {}

        full_name = _resolve_full_name(group)
        emails = _resolve_emails(group, provenance)
        field_conf["emails"] = _field_confidence([r.source for r in group if r.data.get("email")])
        phones = _resolve_phones(group, field_conf, provenance)
        links, location = _resolve_links_and_location(group, field_conf, provenance)
        headline = _resolve_headline(group, field_conf, provenance)
        skills = _resolve_skills(group, field_conf, provenance)
        experience = _resolve_experience(group, provenance)

        if full_name and full_name != "Unknown":
            field_conf["full_name"] = _field_confidence([r.source for r in group])

        populated_confidences = [v for v in field_conf.values() if v > 0]
        overall_confidence = round(
            sum(populated_confidences) / len(populated_confidences), 2
        ) if populated_confidences else 0.0

        candidate = CanonicalCandidate(
            candidate_id=str(uuid.uuid4()),
            full_name=full_name,
            emails=emails,
            phones=phones,
            location=location,
            links=links,
            headline=headline,
            years_experience=None,
            skills=skills,
            experience=experience,
            education=[],
            provenance=provenance,
            overall_confidence=overall_confidence,
            field_confidence=field_conf,
        )
        candidates.append(candidate)

    logger.info(f"[merge] produced {len(candidates)} canonical candidates")
    return candidates