"""
===================================================================================
        AURA AUTONOMOUS EXECUTION LOOP & SELF-HEALING ENGINE (STEP 2 CORE)
===================================================================================
Provides a workspace-confined, atomic self-healing execution loop with automatic
rollback on validation failure and zero fake scaffold fallbacks.
===================================================================================
"""

import ast
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from coderx_engine import _atomic_write_bytes, _atomic_write_text

logger = logging.getLogger("AuraAutonomousLoop")
logger.setLevel(logging.INFO)

ROOT_DIR = Path(__file__).resolve().parent
if os.environ.get("VERCEL") or not os.access(ROOT_DIR, os.W_OK):
    WORKSPACE_DIR = Path(tempfile.gettempdir()) / "aura_workspace"
else:
    WORKSPACE_DIR = ROOT_DIR / "workspace"


class AutonomousExecutionLoop:
    """
    Workspace-confined self-healing execution loop with atomic writes and rollback.
    """
    def __init__(self, workspace: Optional[Union[str, Path]] = None):
        self.workspace = Path(workspace) if workspace else WORKSPACE_DIR
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict[str, Any]] = []

    def run_relentless_loop(
        self,
        goal: str,
        target_filename: str,
        code_generator_fn: Callable[[str, Optional[str]], str],
        test_command: Optional[str] = None,
        max_iterations: int = 5,
        allow_custom_command: bool = False,
    ) -> Dict[str, Any]:
        max_iterations = max(1, min(int(max_iterations or 5), 10))
        workspace_root = self.workspace.resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)

        try:
            target_path = (workspace_root / target_filename).resolve()
            rel_filename = target_path.relative_to(workspace_root).as_posix()
        except (OSError, ValueError, TypeError):
            return {
                "success": False,
                "status": "INVALID_TARGET_PATH",
                "error": "Target file must stay inside the configured workspace.",
            }
        if target_path == workspace_root:
            return {
                "success": False,
                "status": "INVALID_TARGET_PATH",
                "error": "Target file must name a file inside the configured workspace.",
            }

        custom_cmd = (test_command or "").strip()
        if custom_cmd:
            if not allow_custom_command:
                return {
                    "success": False,
                    "status": "CUSTOM_COMMAND_FORBIDDEN",
                    "error": "Custom shell test_command requires administrator privileges.",
                }
            from aura_brain import is_safe_command
            safe_ok, safe_reason = is_safe_command(custom_cmd)
            if not safe_ok:
                return {
                    "success": False,
                    "status": "UNSAFE_TEST_COMMAND",
                    "error": safe_reason,
                }

        existed_before = target_path.exists()
        original_bytes: Optional[bytes] = target_path.read_bytes() if existed_before and target_path.is_file() else None

        iteration = 0
        last_error: Optional[str] = None
        start_time = time.time()
        loop_records: List[Dict[str, Any]] = []

        logger.info("[Autonomous Loop] Starting mission: '%s' on '%s'", goal, rel_filename)

        while iteration < max_iterations:
            iteration += 1
            try:
                code_content = code_generator_fn(goal, last_error)
            except Exception as e:
                last_error = f"Code generator raised exception: {e}"
                loop_records.append({
                    "iteration": iteration,
                    "exit_code": -1,
                    "stdout_preview": "",
                    "stderr_preview": last_error[:200],
                    "file": str(target_path),
                })
                continue

            if not isinstance(code_content, str) or not code_content.strip():
                last_error = "Code generator returned empty output."
                loop_records.append({
                    "iteration": iteration,
                    "exit_code": -1,
                    "stdout_preview": "",
                    "stderr_preview": last_error,
                    "file": str(target_path),
                })
                continue

            if rel_filename.endswith(".py"):
                try:
                    ast.parse(code_content)
                except SyntaxError as syn:
                    last_error = f"SyntaxError at line {syn.lineno}: {syn.msg}"
                    loop_records.append({
                        "iteration": iteration,
                        "exit_code": 1,
                        "stdout_preview": "",
                        "stderr_preview": last_error,
                        "file": str(target_path),
                    })
                    continue

            _atomic_write_text(target_path, code_content, encoding="utf-8")

            if custom_cmd:
                is_win = sys.platform == "win32"
                cmd_args = ["powershell", "-NoProfile", "-Command", custom_cmd] if is_win else ["/bin/bash", "-c", custom_cmd]
            elif rel_filename.endswith(".py"):
                cmd_args = [sys.executable, str(target_path)]
            elif rel_filename.endswith(".js"):
                cmd_args = ["node", str(target_path)]
            else:
                if target_path.exists() and target_path.stat().st_size > 0:
                    return {
                        "success": True,
                        "status": "COMPLETED_WITHOUT_ERRORS",
                        "iterations_taken": iteration,
                        "file_path": str(target_path),
                        "code_preview": code_content[:400],
                        "terminal_output": "Static artifact verified non-empty.",
                        "execution_time_sec": round(time.time() - start_time, 2),
                        "loop_records": loop_records,
                    }
                last_error = "Generated artifact was empty."
                continue

            try:
                proc = subprocess.run(
                    cmd_args,
                    cwd=str(workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                exit_code = proc.returncode
                stdout = (proc.stdout or "").strip()
                stderr = (proc.stderr or "").strip()
            except Exception as e:
                exit_code = 1
                stdout = ""
                stderr = str(e)

            loop_records.append({
                "iteration": iteration,
                "exit_code": exit_code,
                "stdout_preview": stdout[:200],
                "stderr_preview": stderr[:200],
                "file": str(target_path),
            })

            if exit_code == 0:
                return {
                    "success": True,
                    "status": "COMPLETED_WITHOUT_ERRORS",
                    "iterations_taken": iteration,
                    "file_path": str(target_path),
                    "code_preview": code_content[:400],
                    "terminal_output": stdout,
                    "execution_time_sec": round(time.time() - start_time, 2),
                    "loop_records": loop_records,
                }

            last_error = f"Exit code {exit_code}\nStderr: {stderr}\nStdout: {stdout}"

        # Rollback broken writes
        try:
            if existed_before and original_bytes is not None:
                _atomic_write_bytes(target_path, original_bytes)
            elif not existed_before and target_path.exists():
                target_path.unlink()
            rolled_back = True
        except OSError:
            rolled_back = False

        return {
            "success": False,
            "status": "MAX_ITERATIONS_REACHED",
            "iterations_taken": iteration,
            "file_path": str(target_path),
            "rolled_back": rolled_back,
            "last_error": last_error,
            "loop_records": loop_records,
        }


# Singleton instance
AURA_LOOP = AutonomousExecutionLoop()
