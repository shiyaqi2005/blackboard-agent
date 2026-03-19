"""Helpers for loading WebArena task configs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class WebArenaTask:
    """Normalized view of one WebArena config file."""

    config_path: str
    task_id: str
    sites: List[str]
    intent: str
    start_url: str
    require_login: bool
    eval_types: List[str]
    action_set_tag: str
    reference_action_sequence: List[str]


def load_task_config(config_path: str | Path) -> Dict[str, Any]:
    """Load one raw WebArena config JSON."""
    resolved_path = Path(config_path).resolve()
    return json.loads(resolved_path.read_text(encoding="utf-8"))


def parse_task(config_path: str | Path) -> WebArenaTask:
    """Parse one WebArena config into a stable task record."""
    resolved_path = Path(config_path).resolve()
    config = load_task_config(resolved_path)
    eval_section = config.get("eval", {})
    reference_sequence = config.get("reference_action_sequence", {})
    task_id = config.get("task_id", resolved_path.stem)
    sites = config.get("sites", [])
    if not isinstance(sites, list):
        sites = []
    eval_types = eval_section.get("eval_types", [])
    if not isinstance(eval_types, list):
        eval_types = []
    action_sequence = reference_sequence.get("action_sequence", [])
    if not isinstance(action_sequence, list):
        action_sequence = []
    action_set_tag = str(reference_sequence.get("action_set_tag", "playwright") or "playwright")
    return WebArenaTask(
        config_path=str(resolved_path),
        task_id=str(task_id),
        sites=[str(site) for site in sites],
        intent=str(config.get("intent", "")),
        start_url=str(config.get("start_url", "")),
        require_login=bool(config.get("require_login", False)),
        eval_types=[str(eval_type) for eval_type in eval_types],
        action_set_tag=action_set_tag,
        reference_action_sequence=[str(action) for action in action_sequence],
    )


def site_group(task: WebArenaTask) -> str:
    """Return the canonical grouping label used for WebArena task sampling."""
    if not task.sites:
        return "unknown"
    return "+".join(task.sites)
