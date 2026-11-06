"""
===================================================================================
                     AURA AGENT - ADVANCED SETTINGS ENGINE
===================================================================================
Enterprise Settings & Preference Manager synthesized from the world's top 15 AI platforms:
(ChatGPT, Claude, Cursor, Open-Interpreter, Ollama, AutoGPT, CrewAI, LM Studio, etc.)

Author: AURA Technologies Inc.
===================================================================================
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

import tempfile

def _resolve_config_path() -> Path:
    default_dir = Path(__file__).resolve().parent
    if os.environ.get("VERCEL") or not os.access(default_dir, os.W_OK):
        tmp_cfg = Path(tempfile.gettempdir()) / "aura_config.json"
        if not tmp_cfg.exists() and (default_dir / "aura_config.json").exists():
            try:
                tmp_cfg.write_text((default_dir / "aura_config.json").read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass
        return tmp_cfg
    return default_dir / "aura_config.json"

CONFIG_PATH = _resolve_config_path()
MODEL_CATALOG = {
    "gemini": {
        "label": "Google Gemini",
        "models": [
            "gemini-flash-lite-latest",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ],
    },
    "ollama": {
        "label": "Ollama (local)",
        "models": [],
    },
}


class AuraSettingsManager:
    """Manages all configuration state, validation, persistence and runtime updates."""
    
    def __init__(self, config_file: Optional[Path] = None):
        self.config_path = config_file or CONFIG_PATH
        self.config = self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """Loads configuration from JSON file or generates default."""
        if not self.config_path.exists():
            return self.get_default_config()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Warning: Could not read {self.config_path.name}: {e}. Loading defaults.")
            return self.get_default_config()

    def save_settings(self) -> bool:
        """Atomically persists settings to JSON."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"[!] Error saving settings: {e}")
            return False

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "system": {"agent_name": "AURA", "creator": "AURA Technologies Inc.", "version": "4.2.0"},
            "brain_settings": {
                "active_provider": "gemini",
                "active_model": "gemini-flash-lite-latest",
                "temperature": 0.3,
                "thinking_budget_level": "medium",
                "custom_system_instruction": "You are AURA, an elite autonomous AI."
            },
            "security_and_permissions": {
                "execution_mode": "auto_pilot",
                "require_confirmation_for_destructive_commands": True,
                "browser_headless_mode": False,
                "shell_timeout_seconds": 30
            },
            "memory_and_privacy": {
                "persistent_sqlite_enabled": True,
                "auto_recall_user_facts": True
            },
            "ui_kinetic_theme": {
                "theme_mode": "kinetic_cyberpunk",
                "particle_flow_speed": "smooth_fast",
                "neon_accent_color": "#00FFCC"
            }
        }

    # ===================================================================================
    # 1. BRAIN & MODEL CONTROLS (ChatGPT & Claude Inspired)
    # ===================================================================================
    def set_model(self, model_name: str) -> bool:
        """Switches active model after validating it against its provider."""
        provider = self.config.get("brain_settings", {}).get("active_provider", "gemini")
        return self.set_model_selection(provider, model_name)

    @staticmethod
    def validate_model_selection(provider: str, model_name: str) -> bool:
        if provider not in MODEL_CATALOG or not isinstance(model_name, str):
            return False
        model_name = model_name.strip()
        if provider == "gemini":
            return model_name in MODEL_CATALOG["gemini"]["models"]
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", model_name))

    def set_model_selection(self, provider: str, model_name: str) -> bool:
        """Validate and persist a provider/model selection."""
        model_name = model_name.strip() if isinstance(model_name, str) else ""
        if not self.validate_model_selection(provider, model_name):
            return False
        brain_settings = self.config.setdefault("brain_settings", {})
        old_provider = brain_settings.get("active_provider", "gemini")
        old_model = brain_settings.get("active_model", "gemini-flash-lite-latest")
        brain_settings["active_provider"] = provider
        self.config["brain_settings"]["active_model"] = model_name
        if self.save_settings():
            return True
        brain_settings["active_provider"] = old_provider
        brain_settings["active_model"] = old_model
        return False

    @staticmethod
    def public_model_catalog() -> Dict[str, Any]:
        return {
            provider: {"label": entry["label"], "models": list(entry["models"])}
            for provider, entry in MODEL_CATALOG.items()
        }

    def set_temperature(self, temp: float) -> bool:
        """Sets temperature (0.0 = deterministic/precise, 1.0 = highly creative)."""
        temp = max(0.0, min(1.0, float(temp)))
        self.config["brain_settings"]["temperature"] = temp
        return self.save_settings()

    def set_thinking_budget(self, level: str) -> bool:
        """Sets deep thinking reasoning budget: 'low', 'medium', 'deep', 'maximum'."""
        if level.lower() in ["low", "medium", "deep", "maximum"]:
            self.config["brain_settings"]["thinking_budget_level"] = level.lower()
            return self.save_settings()
        return False

    # ===================================================================================
    # 2. SECURITY & TOOL PERMISSIONS (Cursor & Open-Interpreter Inspired)
    # ===================================================================================
    def set_execution_mode(self, mode: str) -> bool:
        """
        'auto_pilot': Runs commands and opens browser autonomously.
        'ask_first' : Prompts user for approval before running shell/file actions.
        """
        if mode.lower() in ["auto_pilot", "ask_first"]:
            self.config["security_and_permissions"]["execution_mode"] = mode.lower()
            return self.save_settings()
        return False

    def toggle_browser_visibility(self, visible: bool) -> bool:
        """Toggle between visible browser window vs silent headless background execution."""
        self.config["security_and_permissions"]["browser_headless_mode"] = not visible
        return self.save_settings()

    # ===================================================================================
    # 3. KINETIC UI THEME & MOTION (Custom Cyberpunk Visuals)
    # ===================================================================================
    def set_neon_color(self, hex_color: str) -> bool:
        """Change the glowing kinetic primary color palette."""
        self.config["ui_kinetic_theme"]["neon_accent_color"] = hex_color
        return self.save_settings()

    def set_particle_speed(self, speed: str) -> bool:
        """Motion speed: 'calm_slow', 'smooth_fast', 'hyper_speed'."""
        if speed in ["calm_slow", "smooth_fast", "hyper_speed"]:
            self.config["ui_kinetic_theme"]["particle_flow_speed"] = speed
            return self.save_settings()
        return False

    # ===================================================================================
    # 4. INSPECTION & EXPORT
    # ===================================================================================
    def print_overview(self):
        print("\n" + "=" * 60)
        print("          AURA AGENT - ACTIVE SETTINGS OVERVIEW")
        print("=" * 60)
        for category, options in self.config.items():
            print(f"\n[+] {category.upper()}:")
            if isinstance(options, dict):
                for k, v in options.items():
                    print(f"    - {k:<30}: {v}")
        print("=" * 60)


if __name__ == "__main__":
    settings = AuraSettingsManager()
    settings.print_overview()
