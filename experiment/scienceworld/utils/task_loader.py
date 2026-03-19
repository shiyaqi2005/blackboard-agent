"""Helpers for loading ScienceWorld task configs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class ScienceWorldTask:
    """Normalized view of one ScienceWorld task config."""

    config_path: str
    task_id: str
    task_name: str
    variation_idx: int
    simplification_str: str
    split: str
    max_episode_steps: int
    notes: str


def load_task_config(config_path: str | Path) -> Dict[str, Any]:
    """Load one raw ScienceWorld task JSON."""
    resolved_path = Path(config_path).resolve()
    return json.loads(resolved_path.read_text(encoding="utf-8"))


def parse_task(config_path: str | Path) -> ScienceWorldTask:
    """Parse one ScienceWorld config into a stable task record."""
    resolved_path = Path(config_path).resolve()
    config = load_task_config(resolved_path)
    task_id = str(config.get("task_id", resolved_path.stem))
    task_name = str(config.get("task_name", task_id))
    variation_idx = int(config.get("variation_idx", 0))
    simplification_str = str(config.get("simplification_str", "easy") or "")
    split = str(config.get("split", "debug") or "debug")
    max_episode_steps = int(config.get("max_episode_steps", 50))
    notes = str(config.get("notes", "") or "")
    return ScienceWorldTask(
        config_path=str(resolved_path),
        task_id=task_id,
        task_name=task_name,
        variation_idx=variation_idx,
        simplification_str=simplification_str,
        split=split,
        max_episode_steps=max_episode_steps,
        notes=notes,
    )


def task_group(task: ScienceWorldTask) -> str:
    """Return the canonical grouping label for ScienceWorld analysis."""
    return task.task_name
