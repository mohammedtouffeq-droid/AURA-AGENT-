"""
===================================================================================
                     AURA AGENT - AUTONOMOUS BRAIN ENGINE
===================================================================================
Real-time LLM Brain powered by Google Gemini Next-Gen Model Suite.
Implements native Tool Calling & ReAct Execution Loop to control the laptop.
Author: Mohammed Touffeq & Antigravity
===================================================================================
"""

import os
import sys
import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional

# Load configuration from .env safely
def load_env() -> Dict[str, str]:
    env_path = Path(__file__).resolve().parent / ".env"
    config = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    return config

ENV = load_env()
API_KEY = ENV.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-3.1-flash-lite"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"


# ===================================================================================
# 1. REAL HARDWARE & OS TOOLS (The Hands of AURA)
# ===================================================================================
def tool_execute_shell(command: str) -> Dict[str, Any]:
    """Executes native PowerShell command on Windows."""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "success": res.returncode == 0,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def tool_open_browser(url: str) -> Dict[str, Any]:
    """Opens a website in the default web browser."""
    import webbrowser
    try:
        webbrowser.open(url)
        return {"success": True, "action": "opened_browser", "url": url}
    except Exception as e:
        return {"success": False, "error": str(e)}

def tool_write_file(filepath: str, content: str) -> Dict[str, Any]:
    """Creates or overwrites a file on disk."""
    try:
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"success": True, "file": filepath, "bytes_written": len(content)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def tool_read_file(filepath: str) -> Dict[str, Any]:
    """Reads content of a file from disk."""
    try:
        p = Path(filepath)
        if not p.exists():
            return {"success": False, "error": f"File {filepath} not found"}
        content = p.read_text(encoding="utf-8", errors="ignore")
        return {"success": True, "file": filepath, "content": content[:2000]}
    except Exception as e:
        return {"success": False, "error": str(e)}


AVAILABLE_TOOLS = {
    "tool_execute_shell": tool_execute_shell,
    "tool_open_browser": tool_open_browser,
    "tool_write_file": tool_write_file,
    "tool_read_file": tool_read_file
}

GEMINI_TOOLS_DECLARATION = [{
    "functionDeclarations": [
        {
            "name": "tool_execute_shell",
            "description": "Execute a native Windows PowerShell command to inspect system, run scripts, manage apps, or check processes.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "command": {"type": "STRING", "description": "The exact PowerShell command to run."}
                },
                "required": ["command"]
            }
        },
        {
            "name": "tool_open_browser",
            "description": "Open a website URL in the user's web browser.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "url": {"type": "STRING", "description": "The full web URL (e.g. https://www.google.com)."}
                },
                "required": ["url"]
            }
        },
        {
            "name": "tool_write_file",
            "description": "Create or write code, documents, or data into a file on the computer.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "filepath": {"type": "STRING", "description": "File path to write."},
                    "content": {"type": "STRING", "description": "The full file content."}
                },
                "required": ["filepath", "content"]
            }
        },
        {
            "name": "tool_read_file",
            "description": "Read file content from the computer.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "filepath": {"type": "STRING", "description": "File path to read."}
                },
                "required": ["filepath"]
            }
        }
    ]
}]


# ===================================================================================
# 2. AUTONOMOUS BRAIN ORCHESTRATOR
# ===================================================================================
class AuraBrain:
    def __init__(self):
        self.api_key = API_KEY
        self.model = MODEL_NAME
        self.history: List[Dict[str, Any]] = []

    def _call_api(self, contents: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        payload = {"contents": contents}
        if tools:
            payload["tools"] = tools

        req = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Connection": "close"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def think_and_act(self, user_prompt: str, max_turns: int = 5) -> str:
        """Runs the ReAct loop: Prompt -> Thought -> Tool Execution -> Final Response."""
        self.history.append({"role": "user", "parts": [{"text": user_prompt}]})

        for turn in range(max_turns):
            try:
                data = self._call_api(self.history, GEMINI_TOOLS_DECLARATION)
            except Exception as e:
                return f"[AURA Error]: Could not communicate with Brain: {e}"

            candidate = data.get("candidates", [{}])[0]
            model_turn = candidate.get("content", {})
            parts = model_turn.get("parts", [])

            # Check if Gemini called tools
            tool_calls = [p["functionCall"] for p in parts if "functionCall" in p]

            if not tool_calls:
                # No more tools called; Gemini completed the response
                reply_texts = [p["text"] for p in parts if "text" in p]
                final_reply = "\n".join(reply_texts).strip()
                self.history.append(model_turn)
                return final_reply

            # CRITICAL: Append exact model turn (with thoughtSignature preserved) to history
            self.history.append(model_turn)

            # Execute all tool calls
            function_responses = []
            for call in tool_calls:
                func_name = call.get("name")
                args = call.get("args", {})
                call_id = call.get("id", "call_default")
                print(f"[*] AURA Brain executing tool: {func_name}({args})")
                
                tool_func = AVAILABLE_TOOLS.get(func_name)
                if tool_func:
                    result = tool_func(**args)
                else:
                    result = {"error": f"Unknown tool: {func_name}"}

                function_responses.append({
                    "functionResponse": {
                        "name": func_name,
                        "response": {"output": result},
                        "id": call_id
                    }
                })

            # Feed tool execution results back to Gemini Brain
            self.history.append({"role": "user", "parts": function_responses})

        return "[AURA]: Maximum thinking turns reached."


if __name__ == "__main__":
    brain = AuraBrain()
    print("[*] AURA Autonomous Brain Online.")
    test_instruction = "Check what is my computer hostname using tool_execute_shell"
    response = brain.think_and_act(test_instruction)
    print("\n[AURA Response]:")
    print(response)
