"""Readiness checks for live WebArena script-browser runs."""
from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from experiment.webarena.core.script_env import _load_runtime
from experiment.webarena.utils.official_agent_runtime import load_official_agent_runtime


REQUIRED_SITE_ENV_VARS = [
    "SHOPPING",
    "SHOPPING_ADMIN",
    "REDDIT",
    "GITLAB",
    "MAP",
    "WIKIPEDIA",
    "HOMEPAGE",
]


def _inspect_config_files(config_files: Iterable[str]) -> Dict[str, Any]:
    config_list = [str(path) for path in config_files]
    existing_config_files: List[str] = []
    missing_config_files: List[str] = []
    parse_errors: List[Dict[str, str]] = []
    login_required_examples: List[str] = []
    login_required_count = 0

    for config_file in config_list:
        path = Path(config_file).resolve()
        if not path.is_file():
            missing_config_files.append(str(path))
            continue
        existing_config_files.append(str(path))
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            parse_errors.append({"config_file": str(path), "error": str(exc)})
            continue
        if bool(config.get("require_login", False)) or str(config.get("storage_state", "") or "").strip():
            login_required_count += 1
            if len(login_required_examples) < 5:
                login_required_examples.append(str(path))

    return {
        "config_files": config_list,
        "existing_config_files": existing_config_files,
        "missing_config_files": missing_config_files,
        "parse_errors": parse_errors,
        "login_required_count": login_required_count,
        "login_required_examples": login_required_examples,
    }


def _discover_local_config_inventory() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    config_root = repo_root / "webarena" / "config_files"
    example_files = sorted(str(path.resolve()) for path in (config_root / "examples").glob("*.json") if path.is_file())
    generated_files = sorted(
        str(path.resolve())
        for path in config_root.glob("*.json")
        if path.is_file() and re.fullmatch(r"\d+\.json", path.name)
    )
    raw_template = config_root / "test.raw.json"
    rendered_template = config_root / "test.json"
    return {
        "config_root": str(config_root.resolve()),
        "example_config_files": example_files,
        "generated_config_files": generated_files,
        "raw_template_exists": raw_template.is_file(),
        "rendered_template_exists": rendered_template.is_file(),
    }


def collect_script_browser_readiness(
    *,
    config_files: Iterable[str],
    systems: Iterable[str],
    official_provider: str = "",
    official_model_endpoint: str = "",
) -> Dict[str, Any]:
    """Collect readiness information for a live WebArena script_browser run."""
    system_list = [str(system) for system in systems]
    config_report = _inspect_config_files(config_files)
    config_list = list(config_report["config_files"])
    missing_site_envs = [name for name in REQUIRED_SITE_ENV_VARS if not os.environ.get(name, "").strip()]
    playwright_installed = importlib.util.find_spec("playwright") is not None
    inventory = _discover_local_config_inventory()

    missing_provider_requirements: List[str] = []
    if "official_prompt" in system_list:
        provider = official_provider.strip() or "openai"
        if provider == "openai" and not os.environ.get("OPENAI_API_KEY", "").strip():
            missing_provider_requirements.append("OPENAI_API_KEY")
        if provider == "huggingface" and not official_model_endpoint.strip():
            missing_provider_requirements.append("official_model_endpoint")

    login_required_count = int(config_report["login_required_count"])
    execution_missing_site_envs = missing_site_envs if login_required_count > 0 else []
    script_runtime_import_error = ""
    official_agent_import_error = ""
    try:
        _load_runtime()
    except Exception as exc:
        script_runtime_import_error = str(exc)
    if "official_prompt" in system_list:
        try:
            load_official_agent_runtime()
        except Exception as exc:
            official_agent_import_error = str(exc)

    return {
        "config_count": len(config_list),
        "existing_config_count": len(config_report["existing_config_files"]),
        "missing_config_count": len(config_report["missing_config_files"]),
        "existing_config_files": config_report["existing_config_files"],
        "missing_config_files": config_report["missing_config_files"],
        "config_parse_errors": config_report["parse_errors"],
        "login_required_count": login_required_count,
        "login_required_examples": config_report["login_required_examples"],
        "site_envs_required_for_execution": bool(login_required_count > 0),
        "systems": system_list,
        "playwright_installed": playwright_installed,
        "script_runtime_import_error": script_runtime_import_error,
        "official_agent_import_error": official_agent_import_error,
        "missing_site_envs": execution_missing_site_envs,
        "config_generation_missing_site_envs": missing_site_envs,
        "missing_provider_requirements": missing_provider_requirements,
        "local_config_inventory": inventory,
    }


def assert_script_browser_ready(
    *,
    config_files: Iterable[str],
    systems: Iterable[str],
    official_provider: str = "",
    official_model_endpoint: str = "",
) -> None:
    """Raise a clear error when the live WebArena backend is not ready."""
    report = collect_script_browser_readiness(
        config_files=config_files,
        systems=systems,
        official_provider=official_provider,
        official_model_endpoint=official_model_endpoint,
    )
    issues: List[str] = []
    if report["config_count"] <= 0:
        issues.append("No task configs were selected.")
    missing_configs = report["missing_config_files"]
    if missing_configs:
        issues.append(
            "Selected task configs are missing: " + ", ".join(missing_configs[:5]) + (" ..." if len(missing_configs) > 5 else "")
        )
    parse_errors = report["config_parse_errors"]
    if parse_errors:
        preview = ", ".join(
            f"{item['config_file']}: {item['error']}" for item in parse_errors[:3]
        )
        issues.append("Selected task configs could not be parsed: " + preview)
    if not report["playwright_installed"]:
        issues.append("Python package 'playwright' is not installed in the active environment.")
    runtime_import_error = str(report.get("script_runtime_import_error", "") or "").strip()
    if runtime_import_error:
        issues.append("WebArena script runtime import failed: " + runtime_import_error)
    official_agent_import_error = str(report.get("official_agent_import_error", "") or "").strip()
    if official_agent_import_error:
        issues.append("WebArena official agent import failed: " + official_agent_import_error)
    missing_site_envs = report["missing_site_envs"]
    if missing_site_envs:
        issues.append("Missing WebArena site env vars: " + ", ".join(missing_site_envs))
    missing_provider = report["missing_provider_requirements"]
    if missing_provider:
        issues.append("Missing official_prompt provider requirements: " + ", ".join(missing_provider))

    if issues:
        raise RuntimeError(
            "WebArena script_browser backend is not ready:\n- " + "\n- ".join(issues)
        )
