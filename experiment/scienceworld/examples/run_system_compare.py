"""Run fixed-task ScienceWorld comparisons across system families."""
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
from experiment.scienceworld.core.reference_env import ScienceWorldReferenceEnv
from experiment.scienceworld.evaluators.scienceworld_evaluator import ScienceWorldEvaluator
from experiment.scienceworld.systems import (
    ScienceWorldAutoGenRunner,
    ScienceWorldBlackboardRunner,
    ScienceWorldLangGraphRunner,
)


def run_system_compare(
    *,
    config_files: List[str],
    systems: List[str],
    output_dir: str,
    run_system_suite,
    workflow_mode: str,
) -> Dict[str, object]:
    """Run one fixed ScienceWorld task set across multiple system families."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    selected_tasks_path = output_path / "selected_tasks.json"
    selected_tasks_path.write_text(json.dumps(config_files, ensure_ascii=False, indent=2), encoding="utf-8")

    system_summaries: Dict[str, Dict[str, object]] = {}
    for system in systems:
        system_output_dir = output_path / system
        system_result = run_system_suite(system, str(system_output_dir))
        system_summaries[system] = {
            "system": system,
            "system_output_dir": str(system_output_dir),
            "result": system_result,
        }

    consolidated = {
        "systems": systems,
        "n_tasks": len(config_files),
        "workflow_mode": workflow_mode,
        "task_paths": str(selected_tasks_path),
        "system_summaries": system_summaries,
    }
    summary_path = output_path / "system_compare_summary.json"
    summary_path.write_text(json.dumps(consolidated, ensure_ascii=False, indent=2), encoding="utf-8")
    return consolidated


def run_named_system(
    *,
    args: argparse.Namespace,
    system: str,
    system_output_dir: str,
    config_files: List[str],
    task_set: Dict[str, object],
) -> Dict[str, object]:
    """Run one named ScienceWorld system and return compare-compatible metadata."""
    env = ScienceWorldReferenceEnv(env_step_limit=args.max_steps)
    common_config = {
        "workflow_mode": args.workflow_mode,
        "execution_backend": "reference_oracle",
        "use_local_llm": bool(args.use_local_llm),
        "llm_model": args.model_name,
        "llm_base_url": args.llm_base_url,
        "llm_api_key": args.llm_api_key,
        "llm_timeout": args.llm_timeout,
        "llm_temperature": args.llm_temperature,
    }
    if system == "blackboard":
        runner = ScienceWorldBlackboardRunner(env, config=common_config)
        run_id = "blackboard_reference"
        experiment_id = "scienceworld:blackboard"
        system_id = f"blackboard_{args.workflow_mode}"
        system_family = "blackboard"
    elif system == "langgraph":
        runner = ScienceWorldLangGraphRunner(env, config=common_config)
        run_id = "langgraph_reference"
        experiment_id = "scienceworld:langgraph"
        system_id = f"langgraph_{args.workflow_mode}"
        system_family = "langgraph"
    elif system == "autogen":
        runner = ScienceWorldAutoGenRunner(env, config=common_config)
        run_id = "autogen_reference"
        experiment_id = "scienceworld:autogen"
        system_id = f"autogen_{args.workflow_mode}"
        system_family = "autogen"
    else:
        raise ValueError(f"Unsupported ScienceWorld system: {system}")

    writer = ResultWriter(
        system_output_dir,
        run_id=run_id,
        system_id=system_id,
        system_family=system_family,
        env_name="scienceworld",
    )
    writer.write_config_snapshot(
        {
            "system": system,
            "task_set_file": args.task_set_file,
            "task_set": task_set.get("task_set", ""),
            "selection_mode": task_set.get("selection_mode", ""),
            "selection_seed": task_set.get("selection_seed", args.seed),
            "n_tasks": len(config_files),
            "output_dir": system_output_dir,
            "workflow_mode": args.workflow_mode,
            "max_steps": args.max_steps,
            "model_name": args.model_name,
        }
    )
    evaluator = ScienceWorldEvaluator(adapter=runner, result_writer=writer)
    try:
        evaluator.run_batch(
            config_files,
            run_id=run_id,
            experiment_id=experiment_id,
            model_name=args.model_name,
            max_steps=args.max_steps,
            task_set=str(task_set.get("task_set", "")),
            seed=args.seed,
        )
        summary = evaluator.finalize()
    finally:
        env.close()

    return {
        "system": system,
        "system_id": system_id,
        "system_family": system_family,
        "workflow_mode": args.workflow_mode,
        "summary": summary,
        "episodes_path": str(writer.episodes_path),
        "standard_episodes_path": str(writer.standard_episodes_path),
        "summary_path": str(writer.summary_path),
        "standard_summary_path": str(writer.standard_summary_path),
    }


def parse_args() -> argparse.Namespace:
    default_manifest = _ROOT / "experiment" / "common" / "task_sets" / "scienceworld_debug.json"
    parser = argparse.ArgumentParser(description="Compare ScienceWorld systems on fixed sampled task configs")
    parser.add_argument("--task-set-file", default=str(default_manifest), help="Task-set manifest JSON")
    parser.add_argument("--output-dir", default="outputs/scienceworld_system_compare", help="Directory for outputs")
    parser.add_argument(
        "--systems",
        default="blackboard,langgraph,autogen",
        help="Comma-separated systems to run",
    )
    parser.add_argument(
        "--workflow-mode",
        choices=["single_action", "planner_action"],
        default="planner_action",
        help="Workflow shape used across systems",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of tasks")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed override for the task manifest")
    parser.add_argument("--max-steps", type=int, default=50, help="Maximum steps per episode")
    parser.add_argument("--model-name", default="scienceworld_reference", help="Model label written to logs")
    parser.add_argument("--use-local-llm", action="store_true", help="Use a local OpenAI-compatible model for action selection")
    parser.add_argument("--llm-base-url", default="", help="Optional override for the local OpenAI-compatible base URL")
    parser.add_argument("--llm-api-key", default="", help="Optional override for the local OpenAI-compatible API key")
    parser.add_argument("--llm-timeout", type=float, default=60.0, help="Timeout in seconds for the local model")
    parser.add_argument("--llm-temperature", type=float, default=0.0, help="Sampling temperature for the local model")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    task_set = resolve_task_set(args.task_set_file, limit=args.limit, seed=args.seed)
    config_files = list(task_set["task_paths"])
    if not config_files:
        raise ValueError(f"Task set resolved zero tasks: {args.task_set_file}")

    systems = [item.strip() for item in args.systems.split(",") if item.strip()]
    consolidated = run_system_compare(
        config_files=config_files,
        systems=systems,
        output_dir=args.output_dir,
        run_system_suite=lambda system, system_output_dir: run_named_system(
            args=args,
            system=system,
            system_output_dir=system_output_dir,
            config_files=config_files,
            task_set=task_set,
        ),
        workflow_mode=args.workflow_mode,
    )
    print(f"System compare summary written to: {Path(args.output_dir) / 'system_compare_summary.json'}")
    print(f"Ran systems: {', '.join(consolidated['systems'])}")


if __name__ == "__main__":
    main()
