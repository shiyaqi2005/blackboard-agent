"""Abstract base evaluator for WebArena experiment runners."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseEvaluator(ABC):
    """Base class for WebArena evaluators."""

    @abstractmethod
    def run_episode(self, config_file: str, **kwargs) -> Dict[str, Any]:
        """Run one task config and return a result record."""
        ...

    def run_batch(self, config_files: List[str], **kwargs) -> List[Dict[str, Any]]:
        """Run one batch of WebArena task configs."""
        return [self.run_episode(config_file, **kwargs) for config_file in config_files]

    def aggregate(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate episode results into summary metrics."""
        from experiment.webarena.evaluators.metrics import compute_summary

        return compute_summary(results)
