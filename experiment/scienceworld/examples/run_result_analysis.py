"""Analyze ScienceWorld system comparison outputs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiment.common.communication_analysis import export_communication_artifacts
from experiment.scienceworld.utils.result_analysis import analyze_ablation_summary, analyze_system_compare_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze ScienceWorld system-compare results")
    parser.add_argument("--summary-path", required=True, help="Path to system_compare_summary.json")
    parser.add_argument(
        "--output-path",
        default="",
        help="Optional explicit output path; defaults to <summary-dir>/system_compare_summary_analysis.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary_path = Path(args.summary_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if "system_summaries" in summary:
        analysis = analyze_system_compare_summary(args.summary_path)
    elif summary.get("summary_type") == "scienceworld_ablation":
        analysis = analyze_ablation_summary(args.summary_path)
    else:
        raise ValueError(f"Unsupported ScienceWorld summary format: {args.summary_path}")
    output_path = (
        Path(args.output_path)
        if args.output_path
        else summary_path.with_name("system_compare_summary_analysis.json")
    )
    output_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Analysis written to: {output_path}")

    group_specs = []
    if "system_summaries" in summary:
        group_specs = [
            {
                "group_type": "system",
                "group_id": system,
                "episodes_path": (
                    system_summary.get("result", {}).get("episodes_path")
                    or system_summary.get("result", {}).get("standard_episodes_path", "")
                ),
            }
            for system, system_summary in summary.get("system_summaries", {}).items()
        ]
    elif summary.get("summary_type") == "scienceworld_ablation":
        group_specs = [
            {
                "group_type": "mode",
                "group_id": mode,
                "episodes_path": (
                    mode_summary.get("result", {}).get("episodes_path")
                    or mode_summary.get("result", {}).get("standard_episodes_path", "")
                ),
            }
            for mode, mode_summary in summary.get("summaries", {}).items()
        ]

    artifacts = export_communication_artifacts(
        output_dir=summary_path.parent,
        env_name="scienceworld",
        group_specs=group_specs,
    )
    print(f"Communication summary written to: {artifacts['summary_path']}")
    print(f"Communication trace written to: {artifacts['trace_path']}")
    print(f"Communication judge records written to: {artifacts['judge_path']}")


if __name__ == "__main__":
    main()
