"""ScriptBrowserEnv-backed WebArena environment wrapper."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from experiment.webarena.core.reference_env import extract_stop_answer
from experiment.webarena.utils.task_loader import WebArenaTask, parse_task
from experiment.webarena.utils.runtime_bootstrap import ensure_placeholder_site_envs, webarena_root


def _load_runtime() -> Dict[str, Any]:
    import sys

    ensure_placeholder_site_envs()
    root = webarena_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from browser_env import ScriptBrowserEnv, create_id_based_action, create_playwright_action
    from browser_env.actions import ActionTypes

    return {
        "ScriptBrowserEnv": ScriptBrowserEnv,
        "create_id_based_action": create_id_based_action,
        "create_playwright_action": create_playwright_action,
        "ActionTypes": ActionTypes,
    }


def _load_evaluator_router():
    import sys

    ensure_placeholder_site_envs()
    root = webarena_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from evaluation_harness.evaluators import evaluator_router

    return evaluator_router


def _normalize_legacy_eval_schema(config: Dict[str, Any]) -> bool:
    """Translate legacy example config eval fields into the official schema."""
    eval_section = config.get("eval", {})
    if not isinstance(eval_section, dict):
        return False
    reference_answers = eval_section.get("reference_answers")
    if not isinstance(reference_answers, list):
        return False
    answers = [str(answer) for answer in reference_answers if str(answer).strip()]
    if not answers:
        eval_section["reference_answers"] = {}
        return True
    if len(answers) == 1:
        eval_section["reference_answers"] = {"exact_match": answers[0]}
        return True
    eval_section["reference_answers"] = {"must_include": answers}
    return True


class WebArenaScriptEnv:
    """Wrapper that executes actions in the official WebArena browser environment."""

    def __init__(
        self,
        *,
        headless: bool = True,
        slow_mo: int = 0,
        observation_type: str = "accessibility_tree",
        current_viewport_only: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        save_trace_enabled: bool = False,
        sleep_after_execution: float = 0.0,
        runtime: Dict[str, Any] | None = None,
    ) -> None:
        self.runtime = runtime or _load_runtime()
        ScriptBrowserEnv = self.runtime["ScriptBrowserEnv"]
        self.env = ScriptBrowserEnv(
            headless=headless,
            slow_mo=slow_mo,
            observation_type=observation_type,
            current_viewport_only=current_viewport_only,
            viewport_size={"width": viewport_width, "height": viewport_height},
            save_trace_enabled=save_trace_enabled,
            sleep_after_execution=sleep_after_execution,
        )
        self.current_task: WebArenaTask | None = None
        self.reference_actions: List[str] = []
        self.history: List[str] = []
        self.step_index = 0
        self.trajectory: List[Any] = []
        self.evaluator = None
        self._temp_artifacts: List[str] = []

    def reset(self, config_file: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Load one WebArena task config and return the initial observation."""
        prepared_config_file = self._prepare_config_file(config_file)
        task = parse_task(prepared_config_file)
        observation, info = self.env.reset(options={"config_file": prepared_config_file})
        self.current_task = task
        self.reference_actions = list(task.reference_action_sequence)
        self.history = []
        self.step_index = 0
        self.trajectory = [{"observation": observation, "info": info}]
        evaluator_router = self.runtime.get("evaluator_router") or _load_evaluator_router()
        self.evaluator = evaluator_router(prepared_config_file)
        normalized_observation = self._build_observation(observation, info)
        normalized_info = self._build_info(
            info=info,
            selected_action="",
            expected_action=self.current_expected_action,
            action_matched=True,
            done=False,
            score=0.0,
        )
        return normalized_observation, normalized_info

    def step(self, action_text: str) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        """Execute one action string in ScriptBrowserEnv."""
        if self.current_task is None:
            raise RuntimeError("Call reset() before step().")

        action = self._parse_action(action_text)
        expected_action = self.current_expected_action
        action_matched = bool(expected_action) and action_text.strip() == expected_action
        ActionTypes = self.runtime["ActionTypes"]
        self.trajectory.append(action)

        if int(action["action_type"]) == int(ActionTypes.STOP):
            score = self._evaluate()
            self.history.append(action_text)
            self.step_index += 1
            done = True
            info = {
                "page": getattr(self.env, "page", None),
                "fail_error": "",
                "observation_metadata": {},
            }
            normalized_observation = self._build_observation({}, info)
            normalized_info = self._build_info(
                info=info,
                selected_action=action_text,
                expected_action=expected_action,
                action_matched=action_matched,
                done=done,
                score=score,
            )
            return normalized_observation, score, done, normalized_info

        next_observation, reward, terminated, truncated, info = self.env.step(action)
        self.trajectory.append({"observation": next_observation, "info": info})
        self.history.append(action_text)
        self.step_index += 1
        done = bool(terminated or truncated)
        score = 0.0
        normalized_observation = self._build_observation(next_observation, info)
        normalized_info = self._build_info(
            info=info,
            selected_action=action_text,
            expected_action=expected_action,
            action_matched=action_matched,
            done=done,
            score=score,
        )
        return normalized_observation, float(reward), done, normalized_info

    @property
    def current_expected_action(self) -> str:
        if 0 <= self.step_index < len(self.reference_actions):
            return self.reference_actions[self.step_index]
        return ""

    def close(self) -> None:
        """Close the underlying browser env."""
        self.env.close()
        self.current_task = None
        for path in self._temp_artifacts:
            if os.path.isdir(path):
                for root, dirs, files in os.walk(path, topdown=False):
                    for file_name in files:
                        os.remove(os.path.join(root, file_name))
                    for dir_name in dirs:
                        os.rmdir(os.path.join(root, dir_name))
                os.rmdir(path)
        self._temp_artifacts = []

    def _parse_action(self, action_text: str) -> Dict[str, Any]:
        if self.current_task is None:
            raise RuntimeError("No active task.")
        action_set_tag = self.current_task.action_set_tag
        if action_set_tag == "playwright":
            return self.runtime["create_playwright_action"](action_text)
        if action_set_tag == "id_accessibility_tree":
            return self.runtime["create_id_based_action"](action_text)
        raise ValueError(f"Unsupported WebArena action_set_tag: {action_set_tag}")

    def _evaluate(self) -> float:
        if self.current_task is None or self.evaluator is None:
            return 0.0
        page = getattr(self.env, "page", None)
        client = self.env.get_page_client(page) if page is not None else None
        return float(
            self.evaluator(
                trajectory=self.trajectory,
                config_file=self.current_task.config_path,
                page=page,
                client=client,
            )
        )

    def _prepare_config_file(self, config_file: str) -> str:
        """Refresh storage_state cookies for login-required tasks before reset."""
        with open(config_file, encoding="utf-8") as handle:
            config = json.load(handle)
        normalized = _normalize_legacy_eval_schema(config)
        storage_state = str(config.get("storage_state", "") or "").strip()
        if not storage_state and not normalized:
            return config_file

        temp_dir = tempfile.mkdtemp(prefix="webarena_config_")
        self._temp_artifacts.append(temp_dir)

        if storage_state:
            cookie_file_name = os.path.basename(storage_state)
            get_site_comb_from_filepath, renew_comb = self._login_helpers()

            site_comb = get_site_comb_from_filepath(cookie_file_name)
            renew_comb(site_comb, auth_folder=temp_dir)
            refreshed_storage_state = os.path.join(temp_dir, cookie_file_name)
            if not os.path.exists(refreshed_storage_state):
                raise RuntimeError(f"Auto-login did not create expected cookie file: {refreshed_storage_state}")
            config["storage_state"] = refreshed_storage_state
        temp_config_path = os.path.join(temp_dir, os.path.basename(config_file))
        with open(temp_config_path, "w", encoding="utf-8") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
        return temp_config_path

    def _login_helpers(self):
        get_site_comb_from_filepath = self.runtime.get("get_site_comb_from_filepath")
        renew_comb = self.runtime.get("renew_comb")
        if get_site_comb_from_filepath is not None and renew_comb is not None:
            return get_site_comb_from_filepath, renew_comb

        import sys

        ensure_placeholder_site_envs()
        root = webarena_root()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from browser_env.auto_login import get_site_comb_from_filepath as official_get_site_comb_from_filepath
        from browser_env.auto_login import renew_comb as official_renew_comb

        return official_get_site_comb_from_filepath, official_renew_comb

    def _build_observation(self, observation: Dict[str, Any], info: Dict[str, Any]) -> Dict[str, Any]:
        task = self.current_task
        if task is None:
            return {}
        text_observation = ""
        if isinstance(observation, dict):
            text_observation = str(observation.get("text", "") or "")
        page = info.get("page", None)
        page_url = getattr(page, "url", "")
        return {
            "config_file": task.config_path,
            "task_id": task.task_id,
            "sites": list(task.sites),
            "intent": task.intent,
            "start_url": task.start_url,
            "require_login": task.require_login,
            "action_set_tag": task.action_set_tag,
            "eval_types": list(task.eval_types),
            "history": list(self.history),
            "step_index": self.step_index,
            "next_reference_action": self.current_expected_action,
            "remaining_reference_actions": list(self.reference_actions[self.step_index :]),
            "page_url": page_url,
            "text_observation": text_observation,
            "raw_observation": observation,
            "raw_info": info,
        }

    def _build_info(
        self,
        *,
        info: Dict[str, Any],
        selected_action: str,
        expected_action: str,
        action_matched: bool,
        done: bool,
        score: float,
    ) -> Dict[str, Any]:
        task = self.current_task
        if task is None:
            return {}
        fail_error = str(info.get("fail_error", "") or "")
        if done:
            stop_reason = "official_evaluator"
        elif fail_error:
            stop_reason = "action_error"
        else:
            stop_reason = "running"
        return {
            "config_file": task.config_path,
            "task_id": task.task_id,
            "sites": list(task.sites),
            "intent": task.intent,
            "action_set_tag": task.action_set_tag,
            "expected_action": expected_action,
            "selected_action": selected_action,
            "action_matched": action_matched,
            "fail_error": fail_error,
            "done": done,
            "stop_reason": stop_reason,
            "progress_rate": float(score),
            "success": bool(done and score >= 1.0),
            "stop_answer": extract_stop_answer(selected_action) if selected_action else "",
            "reference_stop_answer": extract_stop_answer(self.reference_actions[-1]) if self.reference_actions else "",
            "page_url": getattr(info.get("page", None), "url", ""),
        }
