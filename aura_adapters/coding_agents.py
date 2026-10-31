"""
===================================================================================
AURA ADAPTER: CODING AGENTS & CODE INTELLIGENCE
===================================================================================
Curated capabilities extracted from:
- Aider-AI/aider (AST Repo-Map & Search/Replace Diff Patcher)
- OpenHands/OpenHands (Action/Observation Event Machine)
- SWE-agent/SWE-agent (Agent-Computer Interface Command Loop)
- continuedev/continue (Inline Diff & Context Engine)
- cline/cline (Sequential Plan-Act Terminal Feedback)
- RooCodeInc/Roo-Code (Tri-Mode Switching: Code/Architect/Ask)
- NousResearch/hermes-agent (Structured XML Tool-Calling Grammar)
===================================================================================
"""
import ast
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


class AiderDiffPatcher:
    """Aider-inspired atomic search/replace block patcher with rollback safety."""
    @staticmethod
    def apply_patch(original_text: str, patch_text: str) -> Tuple[bool, str, str]:
        """
        Parses <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE blocks and applies cleanly.
        """
        pattern = re.compile(r"<<<<<<< SEARCH\r?\n(.*?)\r?\n=======\r?\n(.*?)\r?\n>>>>>>> REPLACE", re.DOTALL)
        matches = list(pattern.finditer(patch_text))

        if not matches:
            return False, original_text, "No valid Aider search/replace blocks found in patch."

        updated = original_text
        applied_count = 0

        for match in matches:
            search_block = match.group(1)
            replace_block = match.group(2)

            if search_block in updated:
                updated = updated.replace(search_block, replace_block, 1)
                applied_count += 1
            else:
                # Try normalized whitespace
                norm_search = "\n".join(line.rstrip() for line in search_block.splitlines())
                norm_updated = "\n".join(line.rstrip() for line in updated.splitlines())
                if norm_search in norm_updated:
                    updated = norm_updated.replace(norm_search, replace_block, 1)
                    applied_count += 1
                else:
                    return False, original_text, f"Search block not found in target file:\n{search_block[:100]}..."

        return True, updated, f"Successfully applied {applied_count} patch blocks."


class AiderASTRepoMapper:
    """Aider-inspired Python AST symbol and repo map extractor."""
    @staticmethod
    def map_file_symbols(file_path: Path) -> Dict[str, Any]:
        if not file_path.exists() or file_path.suffix != ".py":
            return {"file": str(file_path), "symbols": []}

        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8", errors="ignore"))
            classes = []
            functions = []

            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    classes.append({"name": node.name, "methods": methods, "line": node.lineno})
                elif isinstance(node, ast.FunctionDef):
                    functions.append({"name": node.name, "line": node.lineno})

            return {
                "file": str(file_path.name),
                "classes": classes,
                "functions": functions,
                "total_symbols": len(classes) + len(functions)
            }
        except Exception as e:
            return {"file": str(file_path.name), "error": str(e), "symbols": []}


class OpenHandsActionObservationLoop:
    """OpenHands-inspired event-driven action/observation cycle."""
    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def record_action(self, action_type: str, payload: Dict[str, Any]):
        entry = {"event": "action", "type": action_type, "payload": payload}
        self.history.append(entry)
        return entry

    def record_observation(self, observation_type: str, content: Any, status: str = "success"):
        entry = {"event": "observation", "type": observation_type, "content": content, "status": status}
        self.history.append(entry)
        return entry


class SWEAgentACITerminal:
    """SWE-agent-inspired Agent-Computer Interface command generator and viewport cursor."""
    @staticmethod
    def format_aci_view(filepath: str, start_line: int, end_line: int, total_lines: int) -> str:
        return f"[ACI Window: {filepath} | Lines {start_line}-{end_line} of {total_lines}]"

    @staticmethod
    def format_command_prompt(issue_description: str, repo_path: str) -> str:
        return f"""You are an autonomous SWE-bench software engineer operating on {repo_path}.
ISSUE:
{issue_description}
COMMANDS AVAILABLE:
- open_file <path> <start_line> <end_line>
- edit_file <path> <search_block> <replace_block>
- run_test <test_command>
- submit_patch
"""


class RooCodeModeSwitcher:
    """Roo-Code-inspired dynamic cognitive mode selector."""
    MODES = {
        "architect": "System Architecture & High-Level Planning Mode (Read-only analysis, diagram synthesis)",
        "code": "Direct Implementation Mode (Surgical file editing, unit testing, git branching)",
        "ask": "Interactive Pair-Programming & Clarification Mode"
    }

    @classmethod
    def get_mode_prompt(cls, mode: str) -> str:
        return cls.MODES.get(mode.lower(), cls.MODES["code"])


class HermesStructuredXMLParser:
    """NousResearch/hermes-agent-inspired XML tool call parser."""
    @staticmethod
    def parse_tool_call(response_text: str) -> List[Dict[str, Any]]:
        tool_pattern = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)
        matches = tool_pattern.findall(response_text)
        tools = []
        for m in matches:
            try:
                parsed = json.loads(m)
                tools.append(parsed)
            except Exception:
                pass
        return tools
