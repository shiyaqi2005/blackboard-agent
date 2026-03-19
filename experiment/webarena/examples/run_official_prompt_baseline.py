"""Run the official WebArena prompt baseline through the experiment scaffold."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiment.webarena.examples.run_system_compare import run_named_system, run_system_compare
from experiment.common.task_registry import resolve_task_set


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the official WebArena prompt baseline")
    parser.add_argument(
        "--task-set-file",
        default=str(_ROOT / "experiment" / "common" / "task_sets" / "webarena_script_browser_smoke.json"),
    )
    parser.add_argument("--output-dir", default="outputs/webarena_prompt_baseline")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--agent-type", choices=["prompt", "teacher_forcing"], default="prompt")
    parser.add_argument("--instruction-path", default="")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default="gpt-3.5-turbo")
    parser.add_argument("--mode", default="chat")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--context-length", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=384)
    parser.add_argument("--stop-token", default=None)
    parser.add_argument("--max-retry", type=int, default=1)
    parser.add_argument("--max-obs-length", type=int, default=1920)
    parser.add_argument("--model-endpoint", default="")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--slow-mo", type=int, default=0)
    parser.add_argument("--observation-type", choices=["accessibility_tree", "html", "image"], default="accessibility_tree")
    parser.add_argument("--current-viewport-only", action="store_true")
    parser.add_argument("--viewport-width", type=int, default=1280)
    parser.add_argument("--viewport-height", type=int, default=720)
    parser.add_argument("--save-trace-enabled", action="store_true")
    parser.add_argument("--sleep-after-execution", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    cli_args = parse_args()
    args = argparse.Namespace(
        task_set_file=cli_args.task_set_file,
        output_dir=cli_args.output_dir,
        systems="official_prompt",
        workflow_mode="single_action",
        execution_backend="script_browser",
        limit=cli_args.limit,
        seed=cli_args.seed,
        max_steps=cli_args.max_steps,
        model_name=cli_args.model,
        render=cli_args.render,
        slow_mo=cli_args.slow_mo,
        observation_type=cli_args.observation_type,
        current_viewport_only=cli_args.current_viewport_only,
        viewport_width=cli_args.viewport_width,
        viewport_height=cli_args.viewport_height,
        save_trace_enabled=cli_args.save_trace_enabled,
        sleep_after_execution=cli_args.sleep_after_execution,
        official_agent_type=cli_args.agent_type,
        official_instruction_path=cli_args.instruction_path,
        official_provider=cli_args.provider,
        official_model=cli_args.model,
        official_mode=cli_args.mode,
        official_temperature=cli_args.temperature,
        official_top_p=cli_args.top_p,
        official_context_length=cli_args.context_length,
        official_max_tokens=cli_args.max_tokens,
        official_stop_token=cli_args.stop_token,
        official_max_retry=cli_args.max_retry,
        official_max_obs_length=cli_args.max_obs_length,
        official_model_endpoint=cli_args.model_endpoint,
    )

    task_set = resolve_task_set(args.task_set_file, limit=args.limit, seed=args.seed)
    config_files = list(task_set["task_paths"])
    consolidated = run_system_compare(
        config_files=config_files,
        systems=["official_prompt"],
        output_dir=args.output_dir,
        run_system_suite=lambda system, system_output_dir: run_named_system(
            args=args,
            system=system,
            system_output_dir=system_output_dir,
            config_files=config_files,
            task_set=task_set,
        ),
        workflow_mode=args.workflow_mode,
        execution_backend=args.execution_backend,
    )

    summary = consolidated["system_summaries"]["official_prompt"]["result"]["summary"]
    print(f"Selected {len(config_files)} task configs via manifest: {task_set['manifest_path']}")
    print(f"Selected tasks written to: {Path(args.output_dir) / 'selected_tasks.json'}")
    print(f"Summary written to: {Path(args.output_dir) / 'system_compare_summary.json'}")
    print(f"Summary metrics: {summary}")


if __name__ == "__main__":
    main()
