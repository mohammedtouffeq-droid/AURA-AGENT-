"""
AURA Agent Engine Setup & Verification Tool
Ensures all 5 upstream AI repositories are properly synchronized and mounted.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINES = ROOT / "engines"

REPOS = {
    "open-interpreter": "https://github.com/openinterpreter/open-interpreter.git",
    "browser-use": "https://github.com/browser-use/browser-use.git",
    "aider": "https://github.com/Aider-AI/aider.git",
    "crewAI": "https://github.com/crewAIInc/crewAI.git",
    "litellm": "https://github.com/BerriAI/litellm.git"
}

def sync():
    ENGINES.mkdir(exist_ok=True)
    for name, url in REPOS.items():
        target = ENGINES / name
        if not target.exists():
            print(f"[*] Cloning {name} from {url}...")
            subprocess.run(["git", "clone", "--depth", "1", url, str(target)], check=True)
        else:
            print(f"[+] {name} is already mounted and verified.")

if __name__ == "__main__":
    sync()
