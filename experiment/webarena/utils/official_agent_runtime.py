"""Lazy loaders and helpers for the official WebArena prompt agents."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict

from experiment.webarena.utils.runtime_bootstrap import ensure_placeholder_site_envs, webarena_root


def _webarena_root() -> Path:
    return webarena_root()


def bootstrap_webarena_imports() -> Path:
    """Ensure the local WebArena package root is importable."""
    ensure_placeholder_site_envs()
    root = _webarena_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def ensure_prompt_jsons() -> Path:
    """Materialize official prompt JSON files from raw python definitions if missing."""
    root = bootstrap_webarena_imports()
    raw_dir = root / "agent" / "prompts" / "raw"
    json_dir = root / "agent" / "prompts" / "jsons"
    json_dir.mkdir(parents=True, exist_ok=True)

    for prompt_path in sorted(raw_dir.glob("*.py")):
        module_name = f"agent.prompts.raw.{prompt_path.stem}"
        module = importlib.import_module(module_name)
        output_path = json_dir / f"{prompt_path.stem}.json"
        output_path.write_text(json.dumps(module.prompt, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_dir


def load_official_agent_runtime() -> Dict[str, Any]:
    """Load the official WebArena agent modules lazily."""
    bootstrap_webarena_imports()
    ensure_prompt_jsons()

    from agent.agent import PromptAgent, construct_agent
    from browser_env.actions import ActionTypes
    from browser_env.helper_functions import get_action_description

    return {
        "PromptAgent": PromptAgent,
        "construct_agent": construct_agent,
        "ActionTypes": ActionTypes,
        "get_action_description": get_action_description,
    }
