"""Run WebArena Experiment 3 context-slicing ablation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiment.common.result_writer import ResultWriter
from experiment.common.task_registry import resolve_task_set
from experiment.webarena.core.reference_env import WebArenaReferenceEnv
from experiment.webarena.core.script_env import WebArenaScriptEnv
from experiment.webarena.evaluators.webarena_evaluator import WebArenaEvaluator
from experiment.webarena.systems.blackboard_runner import WebArenaBlackboardRunner
from experiment.webarena.utils.live_readiness import assert_script_browser_ready


def run_context_ablation(
    *,
    config_files: List[str],
    output_dir: str,
    run_mode,
    workflow_mode: str,
    execution_backend: str,
) -> Dict[str, object]:
    """Run one fixed WebArena task set across multiple C4 modes."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    selected_tasks_path = output_path / "selected_tasks.json"
    selected_tasks_path.write_text(json.dumps(config_files, ensure_ascii=False, indent=2), encoding="utf-8")

    summaries: Dict[str, Dict[str, object]] = {}
    for mode in ("full", "ablate_c4"):
        mode_output_dir = output_path / mode
        result = run_mode(mode, str(mode_output_dir))
        summaries[mode] = {
            "mode": mode,
            "mode_output_dir": str(mode_output_dir),
            "result": result,
        }

    consolidated = {
        "summary_type": "context_ablation",
        "modes": ["full", "ablate_c4"],
        "n_tasks": len(config_files),
        "workflow_mode": workflow_mode,
        "execution_backend": execution_backend,
        "task_paths": str(selected_tasks_path),
        "summaries": summaries,
    }
    summary_path = output_path / "context_ablation_summary.json"
    summary_path.write_text(json.dumps(consolidated, ensure_ascii=False, indent=2), encoding="utf-8")
    return consolidated


def build_env(args: argparse.Namespace):
    """Build the configured WebArena backend environment."""
    if args.execution_backend == "reference_oracle":
        return WebArenaReferenceEnv()
    return WebArenaScriptEnv(
        headless=not args.render,
        slow_mo=args.slow_mo,
        observation_type=args.observation_type,
        current_viewport_only=args.current_viewport_only,
        viewport_width=args.viewport_width,
        viewport_height=args.viewport_height,
        save_trace_enabled=args.save_trace_enabled,
        sleep_after_execution=args.sleep_after_execution,
    )


def run_named_mode(
    *,
    args: argparse.Namespace,
    mode: str,
    mode_output_dir: str,
    config_files: List[str],
    task_set: Dict[str, object],
) -> Dict[str, object]:
    """Run one context-slicing mode and return compare-compatible metadata."""
    env = build_env(args)
    use_context_slicing = mode != "ablate_c4"
    runner = WebArenaBlackboardRunner(
        env,
        config={
            "workflow_mode": args.workflow_mode,
            "execution_backend": args.execution_backend,
            "use_context_slicing": use_context_slicing,
            "use_local_llm": bool(args.use_local_llm),
            "llm_model": args.model_name,
            "llm_base_url": args.llm_base_url,
            "llm_api_key": args.llm_api_key,
            "llm_timeout": args.llm_timeout,
            "llm_temperature": args.llm_temperature,
        },
    )
    run_id = mode
    writer = ResultWriter(
        mode_output_dir,
        run_id=run_id,
        system_id=f"blackboard_{mode}",
        system_family="blackboard",
        env_name="webarena",
    )
    writer.write_config_snapshot(
        {
            "mode": mode,
            "use_context_slicing": use_context_slicing,
            "task_set_file": args.task_set_file,
            "task_set": task_set.get("task_set", ""),
            "selection_mode": task_set.get("selection_mode", ""),
            "selection_seed": task_set.get("selection_seed", args.seed),
            "n_tasks": len(config_files),
            "output_dir": mode_output_dir,
            "workflow_mode": args.workflow_mode,
            "execution_backend": args.execution_backend,
            "max_steps": args.max_steps,
            "model_name": args.model_name,
            "render": args.render,
            "slow_mo": args.slow_mo,
            "observation_type": args.observation_type,
            "current_viewport_only": args.current_viewport_only,
            "viewport_width": args.viewport_width,
            "viewport_height": args.viewport_height,
            "save_trace_enabled": args.save_trace_enabled,
            "sleep_after_execution": args.sleep_after_execution,
        }
    )
    evaluator = WebArenaEvaluator(adapter=runner, result_writer=writer)
    try:
        evaluator.run_batch(
            config_files,
            run_id=run_id,
            experiment_id=f"webarena:context_ablation:{mode}",
            model_name=args.model_name,
            max_steps=args.max_steps,
            task_set=str(task_set.get("task_set", "")),
            seed=args.seed,
        )
        summary = evaluator.finalize()
    finally:
        env.close()

    return {
        "mode": mode,
        "summary": summary,
        "episodes_path": str(writer.episodes_path),
        "standard_episodes_path": str(writer.standard_episodes_path),
        "summary_path": str(writer.summary_path),
        "standard_summary_path": str(writer.standard_summary_path),
        "config_snapshot_path": str(writer.config_snapshot_path),
    }


def parse_args() -> argparse.Namespace:
    default_manifest = _ROOT / "experiment" / "common" / "task_sets" / "webarena_debug.json"
    parser = argparse.ArgumentParser(description="Run WebArena Experiment 3 context-slicing ablation")
    parser.add_argument("--task-set-file", default=str(default_manifest), help="Task-set manifest JSON")
    parser.add_argument("--output-dir", default="outputs/webarena_context_ablation", help="Directory for outputs")
    parser.add_argument(
        "--workflow-mode",
        choices=["single_action", "planner_action"],
        default="planner_action",
        help="Workflow shape used by the blackboard system",
    )
    parser.add_argument(
        "--execution-backend",
        choices=["reference_oracle", "script_browser"],
        default="reference_oracle",
        help="Execution backend used for the ablation run",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of tasks")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed override for the task manifest")
    parser.add_argument("--max-steps", type=int, default=10, help="Maximum steps per episode")
    parser.add_argument("--model-name", default="webarena_reference", help="Model label written to logs")
    parser.add_argument("--use-local-llm", action="store_true", help="Use a local OpenAI-compatible model for action selection")
    parser.add_argument("--llm-base-url", default="", help="Optional override for the local OpenAI-compatible base URL")
    parser.add_argument("--llm-api-key", default="", help="Optional override for the local OpenAI-compatible API key")
    parser.add_argument("--llm-timeout", type=float, default=60.0, help="Timeout in seconds for the local model")
    parser.add_argument("--llm-temperature", type=float, default=0.0, help="Sampling temperature for the local model")
    parser.add_argument("--render", action="store_true", help="Render the browser for script_browser backend")
    parser.add_argument("--slow-mo", type=int, default=0, help="Slow down the browser by the specified amount")
    parser.add_argument(
        "--observation-type",
        choices=["accessibility_tree", "html", "image"],
        default="accessibility_tree",
        help="Observation type for script_browser backend",
    )
    parser.add_argument(
        "--current-viewport-only",
        action="store_true",
        help="Only use the current viewport observation in script_browser backend",
    )
    parser.add_argument("--viewport-width", type=int, default=1280, help="Viewport width for script_browser backend")
    parser.add_argument("--viewport-height", type=int, default=720, help="Viewport height for script_browser backend")
    parser.add_argument("--save-trace-enabled", action="store_true", help="Enable Playwright tracing")
    parser.add_argument("--sleep-after-execution", type=float, default=0.0, help="Sleep after each browser action")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    task_set = resolve_task_set(args.task_set_file, limit=args.limit, seed=args.seed)
    config_files = list(task_set["task_paths"])
    if not config_files:
        raise ValueError(
            f"Task set resolved zero tasks: {args.task_set_file}. Use a manifest with existing task configs."
        )
    if args.execution_backend == "script_browser":
        assert_script_browser_ready(config_files=config_files, systems=["blackboard"])

    consolidated = run_context_ablation(
        config_files=config_files,
        output_dir=args.output_dir,
        run_mode=lambda mode, mode_output_dir: run_named_mode(
            args=args,
            mode=mode,
            mode_output_dir=mode_output_dir,
            config_files=config_files,
            task_set=task_set,
        ),
        workflow_mode=args.workflow_mode,
        execution_backend=args.execution_backend,
    )
    print(
        "Context ablation summary written to: "
        f"{Path(args.output_dir) / 'context_ablation_summary.json'}"
    )
    print(f"Ran modes: {', '.join(consolidated['modes'])}")


if __name__ == "__main__":
    main()
