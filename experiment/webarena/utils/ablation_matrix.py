"""Mode definitions for WebArena ablation experiments."""
from __future__ import annotations

from typing import Dict, Iterable, List


DEFAULT_RUNTIME_MODES = ["full", "ablate_c1", "ablate_c2", "ablate_c3", "ablate_c4", "ablate_c5"]
ALL_MODES = [
    "full",
    "ablate_c1",
    "ablate_c2",
    "ablate_c3",
    "ablate_c4",
    "ablate_c5",
]

_MODE_COMPONENTS = {
    "full": (),
    "ablate_c1": ("C1",),
    "ablate_c2": ("C2",),
    "ablate_c3": ("C3",),
    "ablate_c4": ("C4",),
    "ablate_c5": ("C5",),
}

_MODE_CONFIGS: Dict[str, Dict[str, object]] = {
    "full": {
        "communication_style": "structured",
        "use_schema_validation": True,
        "use_deterministic_kernel": True,
        "use_context_slicing": True,
        "use_architect_agent": True,
    },
    "ablate_c1": {
        "communication_style": "natural_language",
        "use_schema_validation": True,
        "use_deterministic_kernel": True,
        "use_context_slicing": True,
        "use_architect_agent": True,
    },
    "ablate_c2": {
        "communication_style": "structured",
        "use_schema_validation": False,
        "use_deterministic_kernel": True,
        "use_context_slicing": True,
        "use_architect_agent": True,
    },
    "ablate_c3": {
        "communication_style": "structured",
        "use_schema_validation": True,
        "use_deterministic_kernel": False,
        "use_context_slicing": True,
        "use_architect_agent": True,
    },
    "ablate_c4": {
        "communication_style": "structured",
        "use_schema_validation": True,
        "use_deterministic_kernel": True,
        "use_context_slicing": False,
        "use_architect_agent": True,
    },
    "ablate_c5": {
        "communication_style": "structured",
        "use_schema_validation": True,
        "use_deterministic_kernel": True,
        "use_context_slicing": True,
        "use_architect_agent": False,
    },
}


def resolve_ablation_modes(modes: Iterable[str] | None = None) -> List[str]:
    """Resolve a user-provided mode list while preserving canonical order."""
    requested = list(modes or DEFAULT_RUNTIME_MODES)
    unknown = sorted(set(requested) - set(ALL_MODES))
    if unknown:
        raise ValueError(f"Unknown ablation modes: {unknown}. Valid modes: {ALL_MODES}")
    return [mode for mode in ALL_MODES if mode in requested]


def build_ablation_runner_config(mode: str) -> Dict[str, object]:
    """Return WebArena runner configuration deltas for one named ablation mode."""
    if mode not in _MODE_CONFIGS:
        raise ValueError(f"Unknown ablation mode: {mode!r}")
    return dict(_MODE_CONFIGS[mode])


def get_mode_components(mode: str) -> tuple[str, ...]:
    """Return the disabled component IDs for one mode."""
    if mode not in _MODE_COMPONENTS:
        raise ValueError(f"Unknown ablation mode: {mode!r}")
    return _MODE_COMPONENTS[mode]
