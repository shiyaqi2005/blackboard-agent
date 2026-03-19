"""Run WebArena Experiment 2 schema-guard evaluation."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiment.common.result_writer import ResultWriter
from experiment.common.task_registry import resolve_task_set
from experiment.webarena.core.reference_env import WebArenaReferenceEnv
from experiment.webarena.core.script_env import WebArenaScriptEnv
from experiment.webarena.evaluators.schema_guard_evaluator import (
    SchemaGuardEvaluator,
    compute_schema_guard_metrics,
    flatten_case_results,
)
from experiment.webarena.evaluators.webarena_evaluator import WebArenaEvaluator
from experiment.webarena.systems.blackboard_runner import WebArenaBlackboardRunner
from experiment.webarena.utils.live_readiness import assert_script_browser_ready


def load_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    """Load newline-delimited JSON records."""
    records: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_env(args: argparse.Namespace):
    """Build the requested WebArena backend."""
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


def capture_states_from_task_set(args: argparse.Namespace) -> Dict[str, Any]:
    """Run the structured blackboard WebArena runner and persist captured states."""
    task_set = resolve_task_set(args.task_set_file, limit=args.limit, seed=args.seed)
    task_paths = list(task_set["task_paths"])
    if not task_paths:
        raise ValueError(
            f"Task set resolved zero tasks: {args.task_set_file}. "
            "Use a manifest with existing task configs, such as webarena_debug.json."
        )
    if args.execution_backend == "script_browser":
        assert_script_browser_ready(config_files=task_paths, systems=["blackboard"])

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or "capture_states"
    writer = ResultWriter(
        str(output_dir),
        run_id=run_id,
        system_id="blackboard_capture_states",
        system_family="blackboard",
        env_name="webarena",
    )
    writer.write_config_snapshot(
        {
            "task_set_file": args.task_set_file,
            "task_set": task_set.get("task_set", ""),
            "selection_mode": task_set.get("selection_mode", ""),
            "selection_seed": task_set.get("selection_seed", args.seed),
            "n_tasks": len(task_paths),
            "output_dir": str(output_dir),
            "workflow_mode": args.workflow_mode,
            "execution_backend": args.execution_backend,
            "max_steps": args.max_steps,
            "model_name": args.model_name,
            "capture_states": True,
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

    env = build_env(args)
    runner = WebArenaBlackboardRunner(
        env,
        config={
            "workflow_mode": args.workflow_mode,
            "execution_backend": args.execution_backend,
            "use_local_llm": bool(args.use_local_llm),
            "llm_model": args.model_name,
            "llm_base_url": args.llm_base_url,
            "llm_api_key": args.llm_api_key,
            "llm_timeout": args.llm_timeout,
            "llm_temperature": args.llm_temperature,
        },
    )
    evaluator = WebArenaEvaluator(adapter=runner, result_writer=writer)
    try:
        evaluator.run_batch(
            task_paths,
            run_id=run_id,
            experiment_id="webarena:schema_guard:capture_states",
            model_name=args.model_name,
            max_steps=args.max_steps,
            task_set=str(task_set.get("task_set", "")),
            seed=args.seed,
            capture_states=True,
        )
        summary = evaluator.finalize()
    finally:
        env.close()

    return {
        "task_set": task_set,
        "summary": summary,
        "states_path": str(writer.standard_states_path),
        "episodes_path": str(writer.standard_episodes_path),
        "summary_path": str(writer.standard_summary_path),
        "config_snapshot_path": str(writer.config_snapshot_path),
    }


def parse_args() -> argparse.Namespace:
    default_manifest = _ROOT / "experiment" / "common" / "task_sets" / "webarena_debug.json"
    parser = argparse.ArgumentParser(description="Run WebArena Experiment 2 schema-guard evaluation")
    parser.add_argument("--states-file", default="", help="Optional JSONL file of previously captured states")
    parser.add_argument("--task-set-file", default=str(default_manifest), help="Task-set manifest JSON")
    parser.add_argument("--output-dir", default="outputs/webarena_exp2", help="Directory for outputs")
    parser.add_argument("--run-id", default="capture_states", help="Run identifier used for capture artifacts")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of tasks")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed override")
    parser.add_argument("--max-steps", type=int, default=10, help="Maximum steps per episode")
    parser.add_argument("--workflow-mode", choices=["single_action", "planner_action"], default="planner_action")
    parser.add_argument(
        "--execution-backend",
        choices=["reference_oracle", "script_browser"],
        default="reference_oracle",
        help="Backend used while capturing states",
    )
    parser.add_argument("--model-name", default="webarena_reference", help="Model label written to capture logs")
    parser.add_argument("--use-local-llm", action="store_true", help="Use a local OpenAI-compatible model for action selection while capturing states")
    parser.add_argument("--llm-base-url", default="", help="Optional override for the local OpenAI-compatible base URL")
    parser.add_argument("--llm-api-key", default="", help="Optional override for the local OpenAI-compatible API key")
    parser.add_argument("--llm-timeout", type=float, default=60.0, help="Timeout in seconds for the local model")
    parser.add_argument("--llm-temperature", type=float, default=0.0, help="Sampling temperature for the local model")
    parser.add_argument("--render", action="store_true", help="Render the browser in script_browser mode")
    parser.add_argument("--slow-mo", type=int, default=0, help="Slow down browser actions")
    parser.add_argument(
        "--observation-type",
        choices=["accessibility_tree", "html", "image"],
        default="accessibility_tree",
        help="Observation type for script_browser mode",
    )
    parser.add_argument("--current-viewport-only", action="store_true", help="Only capture the current viewport")
    parser.add_argument("--viewport-width", type=int, default=1280, help="Browser viewport width")
    parser.add_argument("--viewport-height", type=int, default=720, help="Browser viewport height")
    parser.add_argument("--save-trace-enabled", action="store_true", help="Enable Playwright tracing")
    parser.add_argument("--sleep-after-execution", type=float, default=0.0, help="Sleep after each browser action")
    parser.add_argument(
        "--injection-types",
        default="",
        help="Optional comma-separated subset of injection types",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    capture_metadata: Dict[str, Any] = {}
    if args.states_file:
        captured_states = load_jsonl(args.states_file)
        states_path = args.states_file
        print(f"Loaded {len(captured_states)} captured states from {states_path}")
    else:
        capture_metadata = capture_states_from_task_set(args)
        states_path = str(capture_metadata["states_path"])
        if not Path(states_path).is_file():
            raise FileNotFoundError(
                f"State capture did not produce {states_path}. "
                "This usually means the selected task set resolved no runnable tasks."
            )
        captured_states = load_jsonl(states_path)
        print(f"Captured {len(captured_states)} runtime states to {states_path}")

    if not captured_states:
        raise ValueError(
            "Schema-guard evaluation needs at least one captured state, but zero states were loaded."
        )

    injection_types = [item.strip() for item in args.injection_types.split(",") if item.strip()]
    evaluator = SchemaGuardEvaluator(injection_types=injection_types or None)
    results, metrics = evaluator.evaluate_from_states(captured_states)
    metrics = compute_schema_guard_metrics(results)

    metrics_path = output_dir / "schema_guard_metrics.json"
    metrics_payload = {
        "states_path": states_path,
        "n_states": len(captured_states),
        "n_cases": metrics.n_cases,
        "n_by_type": metrics.n_by_type,
        "full": asdict(metrics.full),
        "ablate_c2": asdict(metrics.ablate_c2),
        "c2_on_interception_rate": metrics.c2_on_interception_rate,
        "c2_off_interception_rate": metrics.c2_off_interception_rate,
        "delta_interception_rate": metrics.delta_interception_rate,
        "c2_on_interception_by_type": metrics.c2_on_interception_by_type,
        "c2_off_interception_by_type": metrics.c2_off_interception_by_type,
        "capture_metadata": capture_metadata,
    }
    metrics_path.write_text(json.dumps(metrics_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    cases_path = output_dir / "schema_guard_cases.jsonl"
    rows = flatten_case_results(results)
    with open(cases_path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("\n=== WebArena Schema Guard Evaluation Results ===")
    print(f"Captured states:           {len(captured_states)}")
    print(f"Total cases:              {metrics.n_cases}")
    print(f"C2 on  interception rate: {metrics.c2_on_interception_rate:.3f}")
    print(f"C2 off interception rate: {metrics.c2_off_interception_rate:.3f}")
    print(f"Delta (C2 adds):          {metrics.delta_interception_rate:+.3f}")
    print(f"Metrics saved to:         {metrics_path}")
    print(f"Per-case results saved to:{cases_path}")


if __name__ == "__main__":
    main()
