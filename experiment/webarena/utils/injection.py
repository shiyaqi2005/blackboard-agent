"""Invalid patch injection utilities for WebArena Experiment 2."""
from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, List, Optional


INJECTION_TYPES = [
    "missing_op",
    "replace_missing_path",
    "schema_type_mismatch",
    "invalid_enum",
    "invalid_path_format",
]


def _make_case_id() -> str:
    return str(uuid.uuid4())[:8]


def inject_missing_op(domain_state: dict, **_) -> Optional[List[dict]]:
    """Patch item missing the required ``op`` member."""
    keys = [key for key in domain_state if not key.startswith("_")]
    if not keys:
        return None
    field = keys[0]
    return [{"path": f"/{field}", "value": domain_state[field]}]


def inject_replace_missing_path(domain_state: dict, **_) -> Optional[List[dict]]:
    """Replace a path that does not exist in the current domain state."""
    del domain_state
    return [{"op": "replace", "path": "/nonexistent_field_xyz", "value": "injected"}]


def inject_schema_type_mismatch(domain_state: dict, data_schema: dict, **_) -> Optional[List[dict]]:
    """Write a non-string value into a string-typed schema field."""
    props = data_schema.get("properties", {}) if data_schema else {}
    for field, spec in props.items():
        if spec.get("type") == "string" and field in domain_state:
            return [{"op": "replace", "path": f"/{field}", "value": [1, 2, 3]}]
    for field, value in domain_state.items():
        if isinstance(value, str) and not field.startswith("_"):
            return [{"op": "replace", "path": f"/{field}", "value": {"injected": True}}]
    return None


def inject_invalid_enum(domain_state: dict, data_schema: dict, **_) -> Optional[List[dict]]:
    """Write a value that violates an enum-constrained schema field."""
    props = data_schema.get("properties", {}) if data_schema else {}
    for field, spec in props.items():
        if "enum" in spec and field in domain_state:
            return [{"op": "replace", "path": f"/{field}", "value": "__invalid_enum_value__"}]
    return None


def inject_invalid_path_format(domain_state: dict, **_) -> Optional[List[dict]]:
    """Create a malformed JSON pointer path."""
    keys = [key for key in domain_state if not key.startswith("_")]
    if not keys:
        return None
    field = keys[0]
    return [{"op": "replace", "path": f"no_slash_{field}", "value": "bad"}]


_GENERATORS = {
    "missing_op": inject_missing_op,
    "replace_missing_path": inject_replace_missing_path,
    "schema_type_mismatch": inject_schema_type_mismatch,
    "invalid_enum": inject_invalid_enum,
    "invalid_path_format": inject_invalid_path_format,
}


def generate_invalid_patch(
    injection_type: str,
    domain_state: dict,
    data_schema: Optional[dict] = None,
) -> Optional[List[dict]]:
    """Generate one invalid patch for the given state/schema pair."""
    generator = _GENERATORS.get(injection_type)
    if generator is None:
        raise ValueError(f"Unknown injection type: {injection_type!r}. Valid types: {INJECTION_TYPES}")
    return generator(domain_state=domain_state, data_schema=data_schema or {})


def classify_patch_error(patch_error: str) -> str:
    """Map a raw kernel/jsonpatch error string into a stable category."""
    if not patch_error:
        return ""
    err = patch_error.lower()
    if ("missing" in err and "op" in err) or ("does not contain 'op'" in err) or ("缺少" in err and "op" in err):
        return "json_format_error"
    if (
        "patch apply error" in err
        or "jsonpatch" in err
        or "jsonpointer" in err
        or "can't replace" in err
        or "location must start with /" in err
        or "路径不存在" in err
    ):
        return "json_patch_apply_error"
    if ("type" in err and ("schema" in err or "validation" in err)) or "not of type" in err:
        return "schema_type_error"
    if "enum" in err or "is not one of" in err:
        return "schema_enum_error"
    if "action" in err or "admissible" in err:
        return "invalid_action_error"
    return "unknown_error"


def build_injection_cases(
    captured_states: List[Dict[str, Any]],
    injection_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Create invalid-patch cases from captured runtime states."""
    selected_types = injection_types or INJECTION_TYPES
    cases: List[Dict[str, Any]] = []
    for state_record in captured_states:
        domain_state = state_record.get("domain_state", {})
        data_schema = state_record.get("data_schema", {})
        for injection_type in selected_types:
            patch = generate_invalid_patch(injection_type, domain_state, data_schema)
            if patch is None:
                continue
            cases.append(
                {
                    "case_id": _make_case_id(),
                    "episode_id": state_record.get("episode_id", ""),
                    "gamefile": state_record.get("gamefile", ""),
                    "step_id": state_record.get("step_id", 0),
                    "injection_type": injection_type,
                    "patch": patch,
                    "domain_state_snapshot": copy.deepcopy(domain_state),
                    "data_schema": copy.deepcopy(data_schema),
                }
            )
    return cases
