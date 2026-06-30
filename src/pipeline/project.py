import logging
import re
from typing import Any, Dict, List, Optional

from src.models import CanonicalCandidate
from src.pipeline.normalize import normalize_phone, normalize_skill

logger = logging.getLogger(__name__)


class MissingRequiredFieldError(ValueError):
    pass


def _get_path(obj: Any, path: str) -> Any:
    """Resolve a dotted/bracket path against a dict (canonical.to_dict()).
    Supports: plain dots (location.city), array index (emails[0]),
    and array-flatten (skills[].name -> list of .name from every item)."""
    tokens = re.findall(r"[^.\[\]]+|\[\d*\]", path)
    current = obj

    for i, tok in enumerate(tokens):
        if tok == "[]":
            remaining = ".".join(_reconstruct(tokens[i + 1:]))
            if not isinstance(current, list):
                return None
            results = [_get_path(item, remaining) if remaining else item for item in current]
            return results
        elif tok.startswith("[") and tok.endswith("]"):
            idx = int(tok[1:-1])
            if not isinstance(current, list) or idx >= len(current):
                return None
            current = current[idx]
        else:
            if not isinstance(current, dict) or tok not in current:
                return None
            current = current[tok]

    return current


def _reconstruct(tokens: List[str]) -> List[str]:
    # rejoin remaining tokens back into a dotted path string fragment list
    out = []
    for t in tokens:
        if t.startswith("["):
            out[-1] = out[-1] + t if out else t
        else:
            out.append(t)
    return out


def _apply_normalize(value: Any, normalize_kind: Optional[str]) -> Any:
    if not normalize_kind or value is None:
        return value
    if normalize_kind == "E164":
        if isinstance(value, list):
            out = []
            for v in value:
                n, ok = normalize_phone(v)
                if ok:
                    out.append(n)
            return out
        n, ok = normalize_phone(value)
        return n if ok else None
    if normalize_kind == "canonical":
        if isinstance(value, list):
            return [normalize_skill(v)[0] for v in value if v]
        name, _ = normalize_skill(value)
        return name
    return value


def project_candidate(candidate: CanonicalCandidate, config: Dict[str, Any]) -> Dict[str, Any]:
    canonical_dict = candidate.to_dict()
    field_confidence = candidate.field_confidence or {}
    on_missing = config.get("on_missing", "null")
    include_confidence = config.get("include_confidence", False)
    include_provenance = config.get("include_provenance", False)

    output: Dict[str, Any] = {}
    included_field_names = set()

    for field_spec in config.get("fields", []):
        out_path = field_spec["path"]
        source_path = field_spec.get("from", out_path)
        required = field_spec.get("required", False)
        normalize_kind = field_spec.get("normalize")

        value = _get_path(canonical_dict, source_path)

        if normalize_kind:
            value = _apply_normalize(value, normalize_kind)

        is_missing = value is None or value == [] or value == ""

        if is_missing:
            if required and on_missing == "error":
                raise MissingRequiredFieldError(f"Required field '{out_path}' is missing")
            if on_missing == "omit":
                continue
            output[out_path] = None
        else:
            output[out_path] = value

        included_field_names.add(out_path)

        if include_confidence:
            base_field = source_path.split("[")[0].split(".")[0]
            conf = field_confidence.get(base_field)
            if conf is not None:
                output[f"{out_path}_confidence"] = conf

    if include_confidence:
        output["_overall_confidence"] = candidate.overall_confidence

    if include_provenance:
        output["_provenance"] = [
            {"field": p.field, "source": p.source, "method": p.method}
            for p in candidate.provenance
            if any(p.field.startswith(f) for f in included_field_names)
        ]

    return output