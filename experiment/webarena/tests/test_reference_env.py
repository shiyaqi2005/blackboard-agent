"""Tests for the offline WebArena reference environment."""
from __future__ import annotations

import json

from experiment.webarena.core.reference_env import WebArenaReferenceEnv, extract_stop_answer


def _write_config(path, *, task_id: int = 1, site: str = "reddit") -> None:
    path.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "sites": [site],
                "intent": "open the target page",
                "start_url": "http://example.com",
                "require_login": False,
                "eval": {"eval_types": ["string_match"]},
                "reference_action_sequence": {
                    "action_sequence": [
                        "page.get_by_role('link', name='Forums').click()",
                        "page.stop('done')",
                    ]
                },
            }
        ),
        encoding="utf-8",
    )


def test_extract_stop_answer_reads_stop_payload():
    assert extract_stop_answer("page.stop('done')") == "done"
    assert extract_stop_answer('page.stop("final answer")') == "final answer"
    assert extract_stop_answer("page.click('x')") == ""


def test_reference_env_tracks_progress_and_success(tmp_path):
    config_path = tmp_path / "task.json"
    _write_config(config_path)

    env = WebArenaReferenceEnv()
    observation, info = env.reset(str(config_path))

    assert observation["task_id"] == "1"
    assert observation["next_reference_action"].startswith("page.get_by_role")
    assert info["expected_action"].startswith("page.get_by_role")

    observation, reward, done, info = env.step("page.get_by_role('link', name='Forums').click()")
    assert reward == 1.0
    assert done is False
    assert info["action_matched"] is True
    assert observation["next_reference_action"] == "page.stop('done')"

    observation, reward, done, info = env.step("page.stop('done')")
    assert reward == 1.0
    assert done is True
    assert info["success"] is True
    assert info["progress_rate"] == 1.0
