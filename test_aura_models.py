"""Tests for AURA's selectable Gemini and local Ollama model providers."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aura_brain import AuraBrain
from aura_settings import AuraSettingsManager


class ModelSettingsTests(unittest.TestCase):
    def test_provider_selection_is_validated_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "settings.json"
            settings = AuraSettingsManager(config_path)
            self.assertTrue(settings.set_model_selection("ollama", "qwen2.5-coder:7b"))
            loaded = AuraSettingsManager(config_path)
            self.assertEqual(loaded.config["brain_settings"]["active_provider"], "ollama")
            self.assertEqual(loaded.config["brain_settings"]["active_model"], "qwen2.5-coder:7b")
            self.assertFalse(settings.set_model_selection("copilot", "gpt-4o"))
            self.assertFalse(settings.set_model_selection("gemini", "not-a-supported-model"))

    def test_ollama_chat_maps_tool_calls_into_brain_format(self) -> None:
        response_body = json.dumps({
            "message": {
                "role": "assistant",
                "content": "Running the requested tool.",
                "tool_calls": [{
                    "id": "tool_call_1",
                    "function": {
                        "name": "tool_status",
                        "arguments": {"verbose": True}
                    }
                }]
            }
        }).encode("utf-8")
        brain = AuraBrain(provider="ollama", model="qwen2.5-coder:7b")
        with patch("urllib.request.urlopen", return_value=io.BytesIO(response_body)) as urlopen:
            result = brain._call_api(
                [
                    {"role": "user", "parts": [{"text": "Check status"}]},
                    {"role": "model", "parts": [{
                        "functionCall": {
                            "id": "tool_call_previous",
                            "name": "tool_status",
                            "args": {"verbose": True}
                        }
                    }]},
                    {"role": "user", "parts": [{
                        "functionResponse": {
                            "id": "tool_call_previous",
                            "name": "tool_status",
                            "response": {"output": {"success": True}}
                        }
                    }]}
                ],
                [{"functionDeclarations": [{
                    "name": "tool_status",
                    "description": "Check status",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {"verbose": {"type": "BOOLEAN"}}
                    }
                }]}]
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "qwen2.5-coder:7b")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][2]["tool_calls"][0]["function"]["name"], "tool_status")
        self.assertEqual(payload["messages"][3]["role"], "tool")
        self.assertEqual(payload["messages"][3]["tool_name"], "tool_status")
        self.assertEqual(payload["tools"][0]["function"]["parameters"]["type"], "object")
        parts = result["candidates"][0]["content"]["parts"]
        self.assertEqual(parts[0]["text"], "Running the requested tool.")
        self.assertEqual(parts[1]["functionCall"]["name"], "tool_status")
        self.assertEqual(parts[1]["functionCall"]["args"], {"verbose": True})
        self.assertEqual(parts[1]["functionCall"]["id"], "tool_call_1")


if __name__ == "__main__":
    unittest.main()
