"""Run fixed-task WebArena comparisons across system families."""
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
from experiment.webarena.systems import (
    WebArenaAutoGenRunner,
    WebArenaBlackboardRunner,
    WebArenaLangGraphRunner,
    WebArenaOfficialPromptRunner,
)
from experiment.webarena.utils.live_readiness import assert_script_browser_ready


def run_system_compare(
    *,
    config_files: List[str],
    systems: List[str],
    output_dir: str,
    run_system_suite,
    workflow_mode: str,
    execution_backend: str,
) -> Dict[str, object]:
    """Run one fixed WebArena task set across multiple system families."""
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
        "execution_backend": execution_backend,
        "task_paths": str(selected_tasks_path),
        "system_summaries": system_summaries,
    }
    summary_path = output_path / "system_compare_summary.json"
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


def run_named_system(
    *,
    args: argparse.Namespace,
    system: str,
    system_output_dir: str,
    config_files: List[str],
    task_set: Dict[str, object],
) -> Dict[str, object]:
    """Run one named system and return compare-compatible metadata."""
    env = build_env(args)
    common_config = {
        "workflow_mode": args.workflow_mode,
        "execution_backend": args.execution_backend,
        "use_local_llm": bool(args.use_local_llm),
        "llm_model": args.model_name,
        "llm_base_url": args.llm_base_url,
        "llm_api_key": args.llm_api_key,
        "llm_timeout": args.llm_timeout,
        "llm_temperature": args.llm_temperature,
    }
    model_name_for_run = args.model_name
    if system == "blackboard":
        runner = WebArenaBlackboardRunner(env, config=common_config)
        run_id = "blackboard_reference"
        experiment_id = "webarena:blackboard"
        system_id = f"blackboard_{args.workflow_mode}"
        system_family = "blackboard"
    elif system == "langgraph":
        runner = WebArenaLangGraphRunner(env, config=common_config)
        run_id = "langgraph_reference"
        experiment_id = "webarena:langgraph"
        system_id = f"langgraph_{args.workflow_mode}"
        system_family = "langgraph"
    elif system == "autogen":
        runner = WebArenaAutoGenRunner(env, config=common_config)
        run_id = "autogen_reference"
        experiment_id = "webarena:autogen"
        system_id = f"autogen_{args.workflow_mode}"
        system_family = "autogen"
    elif system == "official_prompt":
        runner = WebArenaOfficialPromptRunner(
            env,
            config={
                "agent_type": args.official_agent_type,
                "instruction_path": args.official_instruction_path,
                "provider": args.official_provider,
                "model": args.official_model or args.model_name,
                "mode": args.official_mode,
                "temperature": args.official_temperature,
                "top_p": args.official_top_p,
                "context_length": args.official_context_length,
                "max_tokens": args.official_max_tokens,
                "stop_token": args.official_stop_token,
                "max_retry": args.official_max_retry,
                "max_obs_length": args.official_max_obs_length,
                "model_endpoint": args.official_model_endpoint,
                "action_set_tag": "id_accessibility_tree",
                "execution_backend": args.execution_backend,
            },
        )
        run_id = f"official_prompt_{args.official_agent_type}"
        experiment_id = f"webarena:official_prompt:{args.official_agent_type}"
        system_id = f"official_prompt_{args.official_agent_type}"
        system_family = "webarena_prompt"
        model_name_for_run = args.official_model or args.model_name
    else:
        raise ValueError(f"Unsupported WebArena system: {system}")

    writer = ResultWriter(
        system_output_dir,
        run_id=run_id,
        system_id=system_id,
        system_family=system_family,
        env_name="webarena",
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
            "execution_backend": args.execution_backend,
            "max_steps": args.max_steps,
            "model_name": model_name_for_run,
            "render": args.render,
            "slow_mo": args.slow_mo,
            "observation_type": args.observation_type,
            "current_viewport_only": args.current_viewport_only,
            "viewport_width": args.viewport_width,
            "viewport_height": args.viewport_height,
            "save_trace_enabled": args.save_trace_enabled,
            "sleep_after_execution": args.sleep_after_execution,
            "official_agent_type": args.official_agent_type,
            "official_instruction_path": args.official_instruction_path,
            "official_provider": args.official_provider,
            "official_model": args.official_model,
            "official_mode": args.official_mode,
            "official_temperature": args.official_temperature,
            "official_top_p": args.official_top_p,
            "official_context_length": args.official_context_length,
            "official_max_tokens": args.official_max_tokens,
            "official_stop_token": args.official_stop_token,
            "official_max_retry": args.official_max_retry,
            "official_max_obs_length": args.official_max_obs_length,
            "official_model_endpoint": args.official_model_endpoint,
            "use_local_llm": args.use_local_llm,
            "llm_base_url": args.llm_base_url,
            "llm_timeout": args.llm_timeout,
        }
    )
    evaluator = WebArenaEvaluator(adapter=runner, result_writer=writer)
    try:
        evaluator.run_batch(
            config_files,
            run_id=run_id,
            experiment_id=experiment_id,
            model_name=model_name_for_run,
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
        "execution_backend": args.execution_backend,
        "summary": summary,
        "episodes_path": str(writer.episodes_path),
        "standard_episodes_path": str(writer.standard_episodes_path),
        "summary_path": str(writer.summary_path),
        "standard_summary_path": str(writer.standard_summary_path),
    }


def parse_args() -> argparse.Namespace:
    default_manifest = _ROOT / "experiment" / "common" / "task_sets" / "webarena_debug.json"
    parser = argparse.ArgumentParser(description="Compare WebArena systems on fixed sampled task configs")
    parser.add_argument("--task-set-file", default=str(default_manifest), help="Task-set manifest JSON")
    parser.add_argument("--output-dir", default="outputs/webarena_system_compare", help="Directory for outputs")
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
    parser.add_argument(
        "--execution-backend",
        choices=["reference_oracle", "script_browser"],
        default="reference_oracle",
        help="Execution backend used for WebArena plumbing validation",
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
    parser.add_argument(
        "--official-agent-type",
        choices=["prompt", "teacher_forcing"],
        default="prompt",
        help="Official WebArena agent type when systems include official_prompt",
    )
    parser.add_argument(
        "--official-instruction-path",
        default="",
        help="Optional prompt JSON path for official_prompt system",
    )
    parser.add_argument(
        "--official-provider",
        default="openai",
        help="Official WebArena provider when systems include official_prompt",
    )
    parser.add_argument(
        "--official-model",
        default="",
        help="Official WebArena model name; defaults to --model-name when empty",
    )
    parser.add_argument(
        "--official-mode",
        default="chat",
        help="Official WebArena agent mode when systems include official_prompt",
    )
    parser.add_argument("--official-temperature", type=float, default=0.0, help="Official agent temperature")
    parser.add_argument("--official-top-p", type=float, default=0.9, help="Official agent top_p")
    parser.add_argument("--official-context-length", type=int, default=0, help="Official agent context length")
    parser.add_argument("--official-max-tokens", type=int, default=384, help="Official agent max tokens")
    parser.add_argument("--official-stop-token", default=None, help="Official agent optional stop token")
    parser.add_argument("--official-max-retry", type=int, default=1, help="Official agent max parse retry count")
    parser.add_argument(
        "--official-max-obs-length",
        type=int,
        default=1920,
        help="Official agent max observation length before truncation",
    )
    parser.add_argument(
        "--official-model-endpoint",
        default="",
        help="Official agent HF endpoint for huggingface provider",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    systems = [system.strip() for system in args.systems.split(",") if system.strip()]
    task_set = resolve_task_set(args.task_set_file, limit=args.limit, seed=args.seed)
    config_files = list(task_set["task_paths"])
    if not config_files:
        raise ValueError(
            "No WebArena task configs resolved from manifest: "
            f"{args.task_set_file}\n"
            f"Resolved root_dir: {task_set.get('root_dir', '')}\n"
            "This usually means local generated configs are missing under "
            "`webarena/config_files/`.\n"
            "Current fallback manifest that should exist in this repo: "
            "`experiment/common/task_sets/webarena_debug.json`\n"
            "If you want live/formal task configs, generate them first with:\n"
            "  cd /home/syq/Documents/blackboard/webarena\n"
            "  conda run -n blackboard python scripts/generate_test_data.py"
        )

    print(f"Selected {len(config_files)} task configs via manifest: {task_set['manifest_path']}")
    print(f"Systems: {', '.join(systems)}")
    print(f"Workflow mode: {args.workflow_mode}")
    print(f"Execution backend: {args.execution_backend}")
    if "official_prompt" in systems and args.execution_backend != "script_browser":
        raise ValueError("official_prompt requires --execution-backend script_browser")
    if args.execution_backend == "script_browser":
        assert_script_browser_ready(
            config_files=config_files,
            systems=systems,
            official_provider=args.official_provider,
            official_model_endpoint=args.official_model_endpoint,
        )

    def run_system_suite(system: str, system_output_dir: str) -> Dict[str, object]:
        return run_named_system(
            args=args,
            system=system,
            system_output_dir=system_output_dir,
            config_files=config_files,
            task_set=task_set,
        )

    consolidated = run_system_compare(
        config_files=config_files,
        systems=systems,
        output_dir=args.output_dir,
        run_system_suite=run_system_suite,
        workflow_mode=args.workflow_mode,
        execution_backend=args.execution_backend,
    )
    print(f"Selected tasks written to: {Path(args.output_dir) / 'selected_tasks.json'}")
    print(f"Summary written to: {Path(args.output_dir) / 'system_compare_summary.json'}")
    for system in systems:
        summary = consolidated["system_summaries"][system]["result"]["summary"]
        print(
            f"{system}: success_rate={summary.get('success_rate', 0.0):.3f}, "
            f"mean_steps={summary.get('mean_steps', 0.0):.2f}, "
            f"mean_total_tokens={summary.get('mean_total_tokens', 0.0):.1f}"
        )


if __name__ == "__main__":
    main()
