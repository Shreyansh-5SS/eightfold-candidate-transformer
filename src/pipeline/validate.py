import logging
from typing import Any, Dict, List, Tuple

from jsonschema import validate as js_validate, ValidationError

logger = logging.getLogger(__name__)

_TYPE_MAP = {
    "string": "string",
    "number": "number",
    "boolean": "boolean",
    "object": "object",
    "array": "array",
    "string[]": "array",
}


def _build_schema(config: Dict[str, Any]) -> Dict[str, Any]:
    properties = {}
    required = []

    for field_spec in config.get("fields", []):
        path = field_spec["path"]
        field_type = field_spec.get("type", "string")
        json_type = _TYPE_MAP.get(field_type, "string")

        # allow null since on_missing="null" can legitimately populate nulls
        properties[path] = {"type": [json_type, "null"]}

        if field_spec.get("required"):
            required.append(path)

    schema = {
        "type": "object",
        "properties": properties,
        "required": required,
        # don't forbid extra keys — confidence/provenance keys are appended dynamically
        "additionalProperties": True,
    }
    return schema


def validate_output(projected: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    schema = _build_schema(config)
    try:
        js_validate(instance=projected, schema=schema)
        return True, []
    except ValidationError as e:
        msg = f"{e.message} (at path: {list(e.path)})"
        logger.warning(f"[validate] validation failed: {msg}")
        return False, [msg]
    except Exception as e:
        msg = f"unexpected validation error: {e}"
        logger.warning(f"[validate] {msg}")
        return False, [msg]