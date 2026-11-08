"""
===================================================================================
                CODERX: ULTIMATE AUTONOMOUS CODING & REPO ENGINE
===================================================================================
A unified synthesis of coding agent architectures:
1. Model Routing & Gateway: Multi-model router (Gemini header-auth + Local Ollama fallback).
2. Code Intelligence: Native AST Symbol & Repo Mapper.
3. Surgical Code Editing: Aider-style Search/Replace block diff patcher with atomic fsync+replace.
4. Process Execution: Cross-platform subprocess runner with timeout and output caps.
5. Cyclic State Machine: Self-healing execution graph with automatic failure rollback.
===================================================================================
"""

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

ROOT_DIR = Path(__file__).resolve().parent
if os.environ.get("VERCEL") or not os.access(ROOT_DIR, os.W_OK):
    WORKSPACE_DIR = Path(tempfile.gettempdir()) / "aura_workspace"
else:
    WORKSPACE_DIR = ROOT_DIR / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write_text(file_path: Path, content: str, encoding: str = "utf-8") -> None:
    """Writes text to a sibling temporary file, fsyncs, and atomically replaces `file_path`."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=str(file_path.parent),
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tf:
            tmp_path = tf.name
            tf.write(content)
            tf.flush()
            try:
                os.fsync(tf.fileno())
            except OSError:
                pass
        os.replace(tmp_path, str(file_path))
        tmp_path = None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _atomic_write_bytes(file_path: Path, data: bytes) -> None:
    """Writes raw bytes atomically via sibling temp file + os.replace."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=str(file_path.parent),
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tf:
            tmp_path = tf.name
            tf.write(data)
            tf.flush()
            try:
                os.fsync(tf.fileno())
            except OSError:
                pass
        os.replace(tmp_path, str(file_path))
        tmp_path = None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------------
# 1. UNIFIED MODEL ROUTER (Gemini Header Auth + Ollama Fallback)
# ---------------------------------------------------------------------------------
class UnifiedModelRouter:
    """
    Routes between Gemini Cloud API (using header authentication so API keys never
    appear in URLs or logs) and local Ollama.
    """
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434"):
        self.ollama_url = ollama_url
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")

    def is_ollama_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", headers={"User-Agent": "CoderX/1.0"})
            with urllib.request.urlopen(req, timeout=0.3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_ollama_models(self) -> List[str]:
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", headers={"User-Agent": "CoderX/1.0"})
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                data = json.loads(resp.read().decode())
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            return []

    def generate(self, prompt: str, system_prompt: str = "", model_preference: str = "auto") -> str:
        active_key = self.gemini_key or os.environ.get("GEMINI_API_KEY", "")
        if model_preference == "ollama" or (not active_key and self.is_ollama_available()):
            return self._call_ollama(prompt, system_prompt)

        if active_key:
            try:
                return self._call_gemini(prompt, system_prompt, api_key=active_key)
            except Exception as e:
                if self.is_ollama_available():
                    return self._call_ollama(prompt, system_prompt)
                raise RuntimeError(f"Model Router Error: Gemini failed ({e}) and Ollama is not running.")

        if self.is_ollama_available():
            return self._call_ollama(prompt, system_prompt)

        raise RuntimeError("No active LLM provider found: Please provide GEMINI_API_KEY or start Ollama.")

    def _call_gemini(self, prompt: str, system_prompt: str = "", api_key: Optional[str] = None) -> str:
        key = api_key or self.gemini_key or os.environ.get("GEMINI_API_KEY", "")
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        full_content = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        payload = {
            "contents": [{"role": "user", "parts": [{"text": full_content}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": key,
                "Connection": "close",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _call_ollama(self, prompt: str, system_prompt: str = "", model: str = "qwen2.5-coder") -> str:
        models = self.list_ollama_models()
        if models and model not in models:
            model = models[0]

        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Connection": "close"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")


# ---------------------------------------------------------------------------------
# 2. CODEBASE AST & REPO MAPPER
# ---------------------------------------------------------------------------------
class CodebaseAstMapper:
    @staticmethod
    def parse_python_file(file_path: Path) -> Dict[str, Any]:
        symbols = {"classes": {}, "functions": [], "imports": []}
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for name in node.names:
                        symbols["imports"].append(name.name)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = [a.arg for a in node.args.args]
                    symbols["functions"].append({"name": node.name, "line": node.lineno, "args": args})
                elif isinstance(node, ast.ClassDef):
                    methods = []
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            m_args = [a.arg for a in item.args.args]
                            methods.append({"name": item.name, "line": item.lineno, "args": m_args})
                    symbols["classes"][node.name] = {"line": node.lineno, "methods": methods}
        except Exception as e:
            symbols["parse_error"] = str(e)
        return symbols

    @staticmethod
    def parse_generic_file(file_path: Path) -> Dict[str, Any]:
        symbols = {"functions": [], "classes": []}
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            fn_matches = re.finditer(
                r"(?:function\s+([a-zA-Z0-9_$]+)|const\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)",
                content,
            )
            for m in fn_matches:
                name = m.group(1) or m.group(2)
                if name:
                    symbols["functions"].append({"name": name})
            cls_matches = re.finditer(r"class\s+([a-zA-Z0-9_$]+)", content)
            for m in cls_matches:
                symbols["classes"].append({"name": m.group(1)})
        except Exception:
            pass
        return symbols

    @classmethod
    def generate_repo_map(cls, target_dir: Path, max_files: int = 40) -> str:
        lines = [f"# Codebase Symbol Map: {target_dir.name}"]
        count = 0
        skip_dirs = {".git", "node_modules", "__pycache__", "venv", ".gemini", "engines", "dist", "build"}
        if not target_dir.exists():
            return "\n".join(lines)

        for root, dirs, files in os.walk(str(target_dir)):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            for f in sorted(files):
                if count >= max_files:
                    lines.append("... (+ more files)")
                    return "\n".join(lines)
                p = Path(root) / f
                rel = p.relative_to(target_dir)
                if p.suffix == ".py":
                    syms = cls.parse_python_file(p)
                    cls_strs = [f"{k}({', '.join(m['name'] for m in v['methods'][:4])})" for k, v in syms["classes"].items()]
                    fn_strs = [f"{fn['name']}()" for fn in syms["functions"][:6]]
                    lines.append(f"- `{rel}`: Classes[{', '.join(cls_strs)}] Funcs[{', '.join(fn_strs)}]")
                    count += 1
                elif p.suffix in (".js", ".ts", ".html"):
                    syms = cls.parse_generic_file(p)
                    fn_strs = [f"{fn['name']}()" for fn in syms["functions"][:5]]
                    lines.append(f"- `{rel}`: Funcs[{', '.join(fn_strs)}]")
                    count += 1
        return "\n".join(lines)


# ---------------------------------------------------------------------------------
# 3. SURGICAL DIFF PATCHER (Atomic Temp-File + os.replace)
# ---------------------------------------------------------------------------------
class AiderDiffPatcher:
    BLOCK_REGEX = re.compile(
        r"<<<<<<< SEARCH\r?\n((?:(?!=======\r?\n)[\s\S])*)\r?\n=======\r?\n((?:(?!>>>>>>> REPLACE)[\s\S])*)\r?\n>>>>>>> REPLACE"
    )

    @classmethod
    def apply_patch_string(
        cls,
        file_path: Path,
        patch_text: str,
        workspace_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Applies one or more SEARCH/REPLACE blocks atomically to `file_path`."""
        resolved_target = file_path.resolve()
        if workspace_root is not None:
            try:
                resolved_target.relative_to(workspace_root.resolve())
            except ValueError:
                return {"success": False, "error": "Target file escapes workspace boundary."}

        if not resolved_target.exists() or not resolved_target.is_file():
            return {"success": False, "error": f"File does not exist: {file_path}"}

        original_content = resolved_target.read_text(encoding="utf-8", errors="replace")
        blocks = list(cls.BLOCK_REGEX.finditer(patch_text or ""))

        if not blocks:
            return {"success": False, "error": "No valid <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE blocks found."}

        new_content = original_content
        applied_count = 0

        for match in blocks:
            search_block = match.group(1)
            replace_block = match.group(2)

            if search_block in new_content:
                new_content = new_content.replace(search_block, replace_block, 1)
                applied_count += 1
                continue

            norm_search = "\n".join([line.rstrip() for line in search_block.splitlines()])
            norm_content_lines = [line.rstrip() for line in new_content.splitlines()]
            norm_content = "\n".join(norm_content_lines)

            if norm_search in norm_content:
                idx = norm_content.index(norm_search)
                start_line = norm_content[:idx].count("\n")
                search_line_count = norm_search.count("\n") + 1
                orig_lines = new_content.splitlines(keepends=True)
                orig_lines[start_line:start_line + search_line_count] = [replace_block + "\n"]
                new_content = "".join(orig_lines)
                applied_count += 1
            else:
                return {
                    "success": False,
                    "applied_count": applied_count,
                    "error": f"Search target not found in file:\n{search_block[:150]}...",
                }

        if resolved_target.suffix == ".py":
            try:
                ast.parse(new_content)
            except SyntaxError as syn_err:
                return {
                    "success": False,
                    "error": f"Patch aborted: Resulting code contains Python SyntaxError at line {syn_err.lineno}: {syn_err.msg}",
                }

        _atomic_write_text(resolved_target, new_content, encoding="utf-8")
        return {"success": True, "applied_count": applied_count, "bytes_written": len(new_content)}


# ---------------------------------------------------------------------------------
# 4. SUBPROCESS RUNNER (Direct Argv Execution Preferred; Bounded Output & Timeout)
# ---------------------------------------------------------------------------------
class TerminalSandboxRunner:
    """
    Cross-platform subprocess runner with timeout and bounded stdout/stderr capture.
    Note: This is a timeout-bounded subprocess runner, NOT an OS container/VM sandbox.
    """
    MAX_OUTPUT_CHARS = 32768

    @classmethod
    def execute(
        cls,
        command: Union[str, List[str]],
        cwd: Optional[Path] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        work_dir = (cwd or WORKSPACE_DIR).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        safe_timeout = max(1, min(int(timeout), 60))
        start = time.time()

        if isinstance(command, list):
            shell_cmd = [str(part) for part in command]
        else:
            is_win = sys.platform == "win32"
            shell_cmd = ["powershell", "-NoProfile", "-Command", command] if is_win else ["/bin/bash", "-c", command]

        try:
            proc = subprocess.run(
                shell_cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=safe_timeout,
            )
            elapsed = time.time() - start
            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": (proc.stdout or "").strip()[:cls.MAX_OUTPUT_CHARS],
                "stderr": (proc.stderr or "").strip()[:cls.MAX_OUTPUT_CHARS],
                "duration_sec": round(elapsed, 3),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {safe_timeout} seconds.",
                "duration_sec": safe_timeout,
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": str(e)[:cls.MAX_OUTPUT_CHARS],
                "duration_sec": round(time.time() - start, 3),
            }


# ---------------------------------------------------------------------------------
# 5. CYCLIC STATE MACHINE ENGINE WITH AUTOMATIC ROLLBACK
# ---------------------------------------------------------------------------------
class CoderXStateGraph:
    """
    Cyclic multi-step state graph executing:
    ANALYZE -> MAP_SYMBOLS -> CODE/PATCH -> SYNTAX_CHECK -> EXECUTE -> [IF ERROR: SELF_HEAL] -> FINALIZE
    Restores original file state if validation does not succeed within `max_iterations`.
    """
    def __init__(self, workspace: Path = WORKSPACE_DIR):
        self.workspace = Path(workspace)
        self.router = UnifiedModelRouter()
        self.patcher = AiderDiffPatcher()
        self.runner = TerminalSandboxRunner()

    def run(
        self,
        goal: str,
        target_filename: str,
        test_command: str = "",
        max_iterations: int = 5,
        allow_custom_command: bool = False,
    ) -> Dict[str, Any]:
        start_time = time.time()
        max_iterations = max(1, min(int(max_iterations or 5), 10))
        workspace_root = self.workspace.resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)
        try:
            target_path = (workspace_root / target_filename).resolve()
            target_filename = target_path.relative_to(workspace_root).as_posix()
        except (OSError, ValueError, TypeError):
            return {
                "success": False,
                "status": "INVALID_TARGET_PATH",
                "error": "Target file must stay inside the configured CoderX workspace.",
            }
        if target_path == workspace_root:
            return {
                "success": False,
                "status": "INVALID_TARGET_PATH",
                "error": "Target file must name a file inside the configured CoderX workspace.",
            }

        custom_cmd = (test_command or "").strip()
        if custom_cmd:
            if not allow_custom_command:
                return {
                    "success": False,
                    "status": "CUSTOM_COMMAND_FORBIDDEN",
                    "error": "Custom shell test_command requires administrator privileges.",
                }
            try:
                from aura_brain import is_safe_command
                safe_ok, safe_reason = is_safe_command(custom_cmd)
                if not safe_ok:
                    return {
                        "success": False,
                        "status": "UNSAFE_TEST_COMMAND",
                        "error": safe_reason,
                    }
            except Exception as e:
                return {
                    "success": False,
                    "status": "UNSAFE_TEST_COMMAND",
                    "error": f"Command safety check failed: {e}",
                }

        # Snapshot original state for clean rollback on validation failure
        existed_before = target_path.exists()
        original_bytes: Optional[bytes] = target_path.read_bytes() if existed_before and target_path.is_file() else None

        history = []
        last_error = None
        repo_map = CodebaseAstMapper.generate_repo_map(workspace_root)

        try:
            for iteration in range(1, max_iterations + 1):
                prompt = self._build_prompt(goal, target_filename, target_path, repo_map, last_error, iteration)

                try:
                    raw_response = self.router.generate(
                        prompt,
                        system_prompt="You are CoderX, the world's most disciplined autonomous software engineer.",
                    )
                except Exception as e:
                    last_error = f"Model generation error: {e}"
                    history.append({"iteration": iteration, "stage": "MODEL_INFERENCE", "error": last_error})
                    continue

                code = self._clean_code_fences(raw_response)

                if target_filename.endswith(".py"):
                    try:
                        ast.parse(code)
                    except SyntaxError as syn:
                        last_error = f"SyntaxError at line {syn.lineno}: {syn.msg}"
                        history.append({"iteration": iteration, "stage": "SYNTAX_CHECK", "error": last_error})
                        continue

                _atomic_write_text(target_path, code, encoding="utf-8")

                if custom_cmd:
                    exec_spec: Union[str, List[str]] = custom_cmd
                elif target_filename.endswith(".py"):
                    exec_spec = [sys.executable, str(target_path)]
                elif target_filename.endswith(".js"):
                    exec_spec = ["node", str(target_path)]
                else:
                    # Non-executable asset (e.g. .md/.json/.html/.txt): verify non-empty write
                    if target_path.exists() and target_path.stat().st_size > 0:
                        return {
                            "success": True,
                            "status": "COMPLETED_WITHOUT_ERRORS",
                            "iterations_taken": iteration,
                            "target_file": str(target_path),
                            "code_preview": code[:300],
                            "terminal_output": "Static file verified non-empty.",
                            "duration_sec": round(time.time() - start_time, 2),
                            "history": history,
                        }
                    last_error = "Generated file was empty."
                    history.append({"iteration": iteration, "stage": "FILE_VERIFY", "error": last_error})
                    continue

                run_result = self.runner.execute(exec_spec, cwd=workspace_root)
                history.append({
                    "iteration": iteration,
                    "exit_code": run_result["exit_code"],
                    "stdout": run_result["stdout"][:200],
                    "stderr": run_result["stderr"][:200],
                })

                if run_result["success"]:
                    return {
                        "success": True,
                        "status": "COMPLETED_WITHOUT_ERRORS",
                        "iterations_taken": iteration,
                        "target_file": str(target_path),
                        "code_preview": code[:300],
                        "terminal_output": run_result["stdout"],
                        "duration_sec": round(time.time() - start_time, 2),
                        "history": history,
                    }

                last_error = (
                    f"Terminal exit code {run_result['exit_code']}\n"
                    f"Stderr: {run_result['stderr']}\n"
                    f"Stdout: {run_result['stdout']}"
                )
        finally:
            pass

        # Rollback broken or unverified file writes so workspace stays clean
        rolled_back = self._rollback_target(target_path, existed_before, original_bytes)

        return {
            "success": False,
            "status": "MAX_ITERATIONS_REACHED",
            "iterations_taken": max_iterations,
            "target_file": str(target_path),
            "rolled_back": rolled_back,
            "last_error": last_error,
            "history": history,
        }

    @staticmethod
    def _rollback_target(target_path: Path, existed_before: bool, original_bytes: Optional[bytes]) -> bool:
        try:
            if existed_before and original_bytes is not None:
                _atomic_write_bytes(target_path, original_bytes)
                return True
            if not existed_before and target_path.exists():
                target_path.unlink()
                return True
            return True
        except OSError:
            return False

    def _build_prompt(
        self,
        goal: str,
        filename: str,
        path: Path,
        repo_map: str,
        last_error: Optional[str],
        iteration: int,
    ) -> str:
        base = f"""Mission Goal: {goal}
Target File: {filename}
Current Iteration: {iteration}

{repo_map}
"""
        if last_error:
            base += f"""
CRITICAL: Previous attempt failed with the following error:
{last_error}

Fix all issues completely so that the code runs with 0 errors. Output ONLY the raw executable code, no markdown commentary.
"""
        else:
            base += "\nWrite the complete, production-ready code. Output ONLY the raw executable code."
        return base

    @staticmethod
    def _clean_code_fences(raw_code: str) -> str:
        if "```" not in raw_code:
            return raw_code.strip()
        lines = raw_code.splitlines()
        cleaned = []
        for l in lines:
            if l.startswith("```"):
                continue
            cleaned.append(l)
        return "\n".join(cleaned).strip()


# Singleton Instances
CODERX = CoderXStateGraph()
ROUTER = UnifiedModelRouter()
AST_MAPPER = CodebaseAstMapper()
PATCHER = AiderDiffPatcher()
RUNNER = TerminalSandboxRunner()

if __name__ == "__main__":
    print("[*] CODERX Autonomous Coding Engine initialized.")
    print(f"[*] Ollama Available: {ROUTER.is_ollama_available()}")
    print(f"[*] Repo Map Test:\n{AST_MAPPER.generate_repo_map(ROOT_DIR, max_files=5)}")
