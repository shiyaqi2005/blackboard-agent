"""Shared task-selection logic for ALFWorld experiment entrypoints."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from experiment.alfworld.utils.dataset_sampler import DatasetSampler
from experiment.common.task_registry import resolve_task_set


def select_gamefiles(
    *,
    data_root: str,
    split: str,
    seed: int,
    limit: int = 0,
    gamefiles_file: str = "",
    task_set_file: str = "",
) -> tuple[List[str], Dict[str, Any]]:
    """Resolve ALFWorld gamefiles from a manifest, explicit JSON, or sampler."""
    if task_set_file:
        task_set = resolve_task_set(task_set_file, limit=limit, seed=seed)
        return list(task_set["task_paths"]), {
            "selection_source": "task_set_manifest",
            "task_set_file": str(Path(task_set_file).resolve()),
            "task_set_name": task_set.get("task_set", ""),
            "selection_mode": task_set.get("selection_mode", ""),
            "selection_seed": task_set.get("selection_seed", seed),
            "selection_root_dir": task_set.get("root_dir", ""),
        }

    if gamefiles_file:
        gamefiles = json.loads(Path(gamefiles_file).read_text(encoding="utf-8"))
        if not isinstance(gamefiles, list):
            raise ValueError(f"gamefiles_file must contain a JSON array: {gamefiles_file}")
        if limit > 0:
            gamefiles = gamefiles[:limit]
        return [str(gamefile) for gamefile in gamefiles], {
            "selection_source": "explicit_gamefiles_file",
            "gamefiles_file": str(Path(gamefiles_file).resolve()),
        }

    if not data_root:
        raise ValueError("data_root is required when task_set_file and gamefiles_file are not provided")

    sampler = DatasetSampler(data_root)
    if split == "debug":
        gamefiles = sampler.debug_split(seed=seed)
    elif split == "formal":
        gamefiles = sampler.formal_split(seed=seed)
    else:
        raise ValueError(f"Unsupported ALFWorld split: {split}")
    if limit > 0:
        gamefiles = gamefiles[:limit]
    return gamefiles, {
        "selection_source": "dataset_sampler",
        "data_root": data_root,
        "split": split,
        "selection_seed": seed,
    }
