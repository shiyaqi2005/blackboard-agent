"""Reference-backed ScienceWorld environment wrapper."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from experiment.scienceworld.utils.task_loader import ScienceWorldTask, parse_task


class _ScienceWorldEnvShim:
    """Minimal ScienceWorld wrapper that avoids the upstream callback-server hang."""

    def __init__(self, *, jar_path: str, cwd: str, env_step_limit: int = 100):
        from py4j.java_gateway import GatewayParameters, JavaGateway, find_jar_path

        py4j_jar = find_jar_path()
        port = self._reserve_port()
        classpath = os.pathsep.join((py4j_jar, jar_path))
        command = [
            "java",
            "-classpath",
            classpath,
            "py4j.GatewayServer",
            "--die-on-broken-pipe",
            str(port),
        ]
        proc = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.PIPE,
            cwd=cwd,
        )
        self._wait_for_port(port, proc)
        self._gateway = JavaGateway(
            gateway_parameters=GatewayParameters(auto_field=True, port=port),
            java_process=proc,
        )
        self.server = self._gateway.jvm.scienceworld.runtime.pythonapi.PythonInterface()
        self.last_step_score = 0
        self.task_name = ""
        self.variation_idx = 0
        self.simplification_str = ""
        self.env_step_limit = env_step_limit
        self.gold_path_generated = False

    @staticmethod
    def _reserve_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @staticmethod
    def _wait_for_port(port: int, proc: subprocess.Popen, timeout_s: float = 20.0) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"ScienceWorld JVM exited early with code {proc.returncode}.")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                try:
                    sock.connect(("127.0.0.1", port))
                    return
                except OSError:
                    time.sleep(0.1)
        raise TimeoutError(f"ScienceWorld JVM did not open port {port} within {timeout_s:.1f}s.")

    def load(self, task_name: str, variation_idx: int = 0, simplification_str: str = "", generateGoldPath: bool = False):
        self.task_name = task_name
        self.variation_idx = variation_idx
        self.simplification_str = simplification_str
        self.server.load(task_name, variation_idx, simplification_str, generateGoldPath)
        self.last_step_score = 0
        self.gold_path_generated = generateGoldPath

    def reset(self) -> Tuple[str, Dict[str, Any]]:
        self.server.reset()
        self.last_step_score = 0
        observation, _, _, info = self.step("look around")
        return observation, info

    def step(self, action_text: str) -> Tuple[str, int, bool, Dict[str, Any]]:
        observation = self.server.step(action_text)
        score = int(round(100 * self.server.getScore()))
        is_completed = bool(self.server.getCompleted())
        num_moves = int(self.server.getNumMoves())
        reward = score - self.last_step_score
        self.last_step_score = score
        if num_moves > self.env_step_limit or score < 0:
            is_completed = True

        info = {
            "moves": num_moves,
            "score": score,
            "reward": reward,
            "look": str(self.server.freeActionLook()),
            "inv": str(self.server.freeActionInventory()),
            "taskDesc": str(self.server.freeActionTaskDesc()),
            "variationIdx": self.variation_idx,
            "taskName": self.task_name,
            "simplificationStr": self.simplification_str,
        }
        return str(observation), reward, is_completed, info

    def get_possible_actions(self) -> List[str]:
        return list(self.server.getPossibleActions())

    def get_gold_action_sequence(self) -> List[str]:
        if self.gold_path_generated:
            return list(self.server.getGoldActionSequence())
        return ["ERROR: Gold path was not generated."]

    def close(self) -> None:
        self._gateway.shutdown()
        if self._gateway.java_process is not None and self._gateway.java_process.poll() is None:
            self._gateway.java_process.stdin.write(b"\n")
            self._gateway.java_process.stdin.flush()


def _load_runtime():
    repo_root = Path(__file__).resolve().parents[3] / "ScienceWorld" / "scienceworld"
    jar_path = repo_root / "scienceworld.jar"
    task_path = repo_root / "tasks.json"
    if not jar_path.is_file() or not task_path.is_file():
        raise RuntimeError(
            "ScienceWorld runtime is not ready. "
            "Expected local assets under /home/syq/Documents/blackboard/ScienceWorld/scienceworld."
        )
    json.loads(task_path.read_text(encoding="utf-8"))
    return {
        "ScienceWorldEnv": lambda envStepLimit=100: _ScienceWorldEnvShim(
            jar_path=str(jar_path),
            cwd=str(repo_root),
            env_step_limit=envStepLimit,
        )
    }


class ScienceWorldReferenceEnv:
    """Wrapper that exposes ScienceWorld through the shared experiment interface."""

    def __init__(
        self,
        *,
        env_step_limit: int = 100,
        runtime: Dict[str, Any] | None = None,
        env_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.runtime = runtime or ({ } if env_factory is not None else _load_runtime())
        self._env_factory = env_factory
        self.env_step_limit = env_step_limit
        self.env = None
        self.current_task: ScienceWorldTask | None = None
        self.reference_actions: List[str] = []
        self.history: List[str] = []
        self.step_index = 0

    def _ensure_env(self):
        if self.env is None:
            if self._env_factory is not None:
                self.env = self._env_factory()
            else:
                env_cls = self.runtime["ScienceWorldEnv"]
                self.env = env_cls(envStepLimit=self.env_step_limit)
        return self.env

    def reset(self, config_file: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Load one ScienceWorld config and return the initial observation."""
        task = parse_task(config_file)
        env = self._ensure_env()
        env.load(
            task.task_name,
            task.variation_idx,
            task.simplification_str,
            generateGoldPath=True,
        )
        observation, info = env.reset()
        self.current_task = task
        gold_actions = list(env.get_gold_action_sequence())
        if gold_actions and str(gold_actions[0]).startswith("ERROR:"):
            gold_actions = []
        self.reference_actions = [str(action) for action in gold_actions]
        self.history = []
        self.step_index = 0
        normalized_observation = self._build_observation(observation, info)
        normalized_info = self._build_info(
            info=info,
            selected_action="",
            expected_action=self.current_expected_action,
            action_matched=True,
            done=False,
        )
        return normalized_observation, normalized_info

    def step(self, action_text: str) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        """Execute one ScienceWorld action."""
        if self.current_task is None:
            raise RuntimeError("Call reset() before step().")
        env = self._ensure_env()
        expected_action = self.current_expected_action
        action_matched = bool(expected_action) and action_text.strip() == expected_action
        observation, reward, done, info = env.step(action_text)
        self.history.append(action_text)
        self.step_index += 1
        normalized_observation = self._build_observation(observation, info)
        normalized_info = self._build_info(
            info=info,
            selected_action=action_text,
            expected_action=expected_action,
            action_matched=action_matched,
            done=bool(done),
        )
        return normalized_observation, float(reward), bool(done), normalized_info

    @property
    def current_expected_action(self) -> str:
        if 0 <= self.step_index < len(self.reference_actions):
            return self.reference_actions[self.step_index]
        return ""

    def close(self) -> None:
        """Close the underlying ScienceWorld environment."""
        if self.env is not None and hasattr(self.env, "close"):
            self.env.close()
        self.env = None
        self.current_task = None

    def _build_observation(self, observation: str, info: Dict[str, Any]) -> Dict[str, Any]:
        task = self.current_task
        if task is None:
            return {}
        possible_actions = []
        if self.env is not None and hasattr(self.env, "get_possible_actions"):
            try:
                possible_actions = list(self.env.get_possible_actions())
            except Exception:
                possible_actions = []
        return {
            "config_file": task.config_path,
            "task_id": task.task_id,
            "task_name": task.task_name,
            "variation_idx": task.variation_idx,
            "simplification_str": task.simplification_str,
            "history": list(self.history),
            "step_index": self.step_index,
            "task_desc": str(info.get("taskDesc", "") or ""),
            "inventory": str(info.get("inv", "") or ""),
            "look": str(info.get("look", "") or ""),
            "observation": str(observation or ""),
            "next_reference_action": self.current_expected_action,
            "remaining_reference_actions": list(self.reference_actions[self.step_index :]),
            "possible_actions": [str(action) for action in possible_actions],
        }

    def _build_info(
        self,
        *,
        info: Dict[str, Any],
        selected_action: str,
        expected_action: str,
        action_matched: bool,
        done: bool,
    ) -> Dict[str, Any]:
        task = self.current_task
        if task is None:
            return {}
        score = float(info.get("score", 0) or 0)
        success = bool(done and score >= 100.0)
        return {
            "config_file": task.config_path,
            "task_id": task.task_id,
            "task_name": task.task_name,
            "variation_idx": task.variation_idx,
            "simplification_str": task.simplification_str,
            "expected_action": expected_action,
            "selected_action": selected_action,
            "action_matched": action_matched,
            "score": score,
            "reward": float(info.get("reward", 0) or 0),
            "moves": int(info.get("moves", 0) or 0),
            "done": done,
            "success": success,
            "stop_reason": "reference_completed" if done else "running",
            "progress_rate": score / 100.0,
        }
