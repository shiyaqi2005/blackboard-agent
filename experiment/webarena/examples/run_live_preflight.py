"""Preflight checks for live WebArena script-browser runs."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiment.common.task_registry import preview_task_set, resolve_task_set
from experiment.webarena.utils.live_readiness import collect_script_browser_readiness
from experiment.webarena.utils.task_loader import parse_task


def _check_url(url: str, timeout: float) -> Dict[str, object]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "url": url,
                "ok": True,
                "status": int(getattr(response, "status", 200)),
            }
    except urllib.error.HTTPError as exc:
        return {"url": url, "ok": False, "status": int(exc.code), "error": str(exc)}
    except Exception as exc:  # pragma: no cover - network environment dependent
        return {"url": url, "ok": False, "status": 0, "error": str(exc)}


def parse_args() -> argparse.Namespace:
    default_manifest = _ROOT / "experiment" / "common" / "task_sets" / "webarena_live_debug.json"
    parser = argparse.ArgumentParser(description="Run preflight checks for live WebArena runs")
    parser.add_argument("--task-set-file", default=str(default_manifest), help="Task-set manifest JSON")
    parser.add_argument(
        "--systems",
        default="blackboard,langgraph,autogen,official_prompt",
        help="Comma-separated systems intended for the live run",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of tasks")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed override")
    parser.add_argument("--official-provider", default="openai", help="official_prompt provider")
    parser.add_argument("--official-model-endpoint", default="", help="official_prompt HF endpoint")
    parser.add_argument("--check-urls", action="store_true", help="Attempt HTTP checks against selected start URLs")
    parser.add_argument("--url-timeout", type=float, default=3.0, help="Timeout for optional URL checks")
    return parser.parse_args()


def _preflight_suggestions(*, readiness: Dict[str, object], official_provider: str) -> List[str]:
    suggestions: List[str] = []
    missing_config_files = list(readiness.get("missing_config_files", []))
    if missing_config_files:
        suggestions.append(
            "Generate local WebArena numbered configs after exporting site env vars: `cd /home/syq/Documents/blackboard/webarena && conda run -n blackboard python scripts/generate_test_data.py`."
        )
        smoke_manifest = _ROOT / "experiment" / "common" / "task_sets" / "webarena_script_browser_smoke.json"
        suggestions.append(
            f"For script_browser plumbing smoke before local configs exist, use manifest `{smoke_manifest}`."
        )

    if not bool(readiness.get("playwright_installed", False)):
        suggestions.append(
            "Install Playwright in the `blackboard` env, then install Chromium: `conda run -n blackboard pip install playwright && conda run -n blackboard playwright install chromium`."
        )

    missing_site_envs = list(readiness.get("missing_site_envs", []))
    if missing_site_envs:
        suggestions.append(
            "Export WebArena site env vars for login-required tasks: " + ", ".join(missing_site_envs) + "."
        )

    generation_missing_site_envs = list(readiness.get("config_generation_missing_site_envs", []))
    if missing_config_files and generation_missing_site_envs:
        suggestions.append(
            "Those same site env vars are also required before `scripts/generate_test_data.py` can render local configs."
        )

    missing_provider_requirements = list(readiness.get("missing_provider_requirements", []))
    if missing_provider_requirements:
        if official_provider == "openai":
            suggestions.append("Set `OPENAI_API_KEY` before running `official_prompt`.")
        else:
            suggestions.append(
                "Provide the missing official_prompt runtime parameters: " + ", ".join(missing_provider_requirements) + "."
            )
    return suggestions


def main() -> None:
    args = parse_args()
    systems = [system.strip() for system in args.systems.split(",") if system.strip()]
    preview = preview_task_set(args.task_set_file, limit=args.limit, seed=args.seed)
    config_files = list(preview["task_paths"])
    existing_config_files = list(preview.get("existing_task_paths", []))
    manifest_status = "ok" if not preview.get("missing_task_paths") else "missing_files"
    try:
        task_set = resolve_task_set(args.task_set_file, limit=args.limit, seed=args.seed)
    except Exception as exc:
        task_set = preview
        manifest_error = str(exc)
    else:
        manifest_error = ""

    tasks = [parse_task(config_file) for config_file in existing_config_files]

    readiness = collect_script_browser_readiness(
        config_files=config_files,
        systems=systems,
        official_provider=args.official_provider,
        official_model_endpoint=args.official_model_endpoint,
    )

    site_groups = sorted({"+".join(task.sites) if task.sites else "unknown" for task in tasks})
    login_required = [task.config_path for task in tasks if task.require_login]
    start_urls = []
    seen_urls = set()
    for task in tasks:
        if task.start_url and task.start_url not in seen_urls:
            seen_urls.add(task.start_url)
            start_urls.append(task.start_url)

    report = {
        "task_set_file": str(Path(args.task_set_file).resolve()),
        "task_set": task_set.get("task_set", ""),
        "status": "not_ready",
        "task_manifest_status": manifest_status,
        "task_manifest_error": manifest_error,
        "n_tasks": len(config_files),
        "existing_task_count": len(existing_config_files),
        "systems": systems,
        "site_groups": site_groups,
        "login_required_count": len(login_required),
        "login_required_examples": login_required[:5],
        "readiness": readiness,
        "start_urls": start_urls,
        "suggested_next_steps": _preflight_suggestions(
            readiness=readiness,
            official_provider=args.official_provider,
        ),
    }

    is_ready = (
        manifest_status == "ok"
        and not readiness.get("missing_config_files")
        and not readiness.get("config_parse_errors")
        and bool(readiness.get("playwright_installed", False))
        and not readiness.get("script_runtime_import_error")
        and not readiness.get("official_agent_import_error")
        and not readiness.get("missing_site_envs")
        and not readiness.get("missing_provider_requirements")
    )
    report["status"] = "ready" if is_ready else "not_ready"

    if args.check_urls and existing_config_files:
        report["url_checks"] = [_check_url(url, args.url_timeout) for url in start_urls]

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
