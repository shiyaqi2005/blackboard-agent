"""WebArena evaluator."""
from __future__ import annotations

import json
import uuid
from typing import Any, Callable, Dict, Optional

from experiment.webarena.evaluators.base_evaluator import BaseEvaluator


class WebArenaEvaluator(BaseEvaluator):
    """Run WebArena episodes and persist results via a shared writer."""

    def __init__(self, adapter, result_writer=None, token_callback: Optional[Callable] = None):
        self.adapter = adapter
        self.result_writer = result_writer
        self.token_callback = token_callback

    def run_episode(
        self,
        config_file: str = "",
        run_id: str = "",
        experiment_id: str = "",
        episode_id: str = "",
        model_name: str = "",
        max_steps: int = 30,
        task_set: str = "",
        seed: int = 0,
        **kwargs,
    ) -> Dict[str, Any]:
        """Run one WebArena episode and optionally write it out immediately."""
        if not episode_id:
            episode_id = str(uuid.uuid4())[:8]

        result = self.adapter.run_episode(
            config_file=config_file,
            max_steps=max_steps,
            episode_id=episode_id,
            run_id=run_id,
            experiment_id=experiment_id,
            model_name=model_name,
            token_callback=self.token_callback,
            task_set=task_set,
            seed=seed,
            **kwargs,
        )
        if config_file and not result.get("config_file"):
            result["config_file"] = config_file
        if task_set and not result.get("task_set"):
            result["task_set"] = task_set
        if seed and not result.get("seed"):
            result["seed"] = seed

        if self.result_writer is not None:
            self.result_writer.write_episode(result)
        return result

    def finalize(self) -> Dict[str, Any]:
        """Compute and write a summary from all written episodes."""
        if self.result_writer is None:
            return {}
        episodes = []
        path = self.result_writer.episodes_path
        if path.exists():
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        episodes.append(json.loads(line))
        summary = self.aggregate(episodes)
        self.result_writer.write_summary(summary)
        return summary
