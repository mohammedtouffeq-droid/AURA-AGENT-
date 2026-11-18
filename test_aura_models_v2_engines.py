"""Tests for dedicated AURA 2.0, AURA 2.3, and AURA 2.6 model engines, HTTP routes, and Generative UI."""
from __future__ import annotations

import json
import secrets
import shutil
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

import aura_db
import aura_web
from aura_engine_20 import Aura20StudyEngine
from aura_engine_23 import Aura23ArchitectEngine
from aura_engine_26 import Aura26ApexEngine
from aura_models_hub import AURA_MODEL_ROUTER
from aura_web import _resolve_workspace_dir, make_server


class TestAuraThreeEngineModulesUnit(unittest.TestCase):
    def test_catalog_and_lightweight_storage_footprint(self):
        catalog = AURA_MODEL_ROUTER.list_catalog()
        ids = [item["id"] for item in catalog]
        self.assertEqual(ids, ["aura-2.0", "aura-2.3", "aura-2.6"])
        for item in catalog:
            self.assertGreater(item["engine_disk_kb"], 0.5)
        self.assertLess(catalog[0]["total_engines_kb"], 100.0)

    def test_tier_normalization_and_distinct_engine_profiles(self):
        self.assertEqual(AURA_MODEL_ROUTER.normalize_tier("2.0"), "aura-2.0")
        self.assertEqual(AURA_MODEL_ROUTER.normalize_tier("AURA 2.3"), "aura-2.3")
        self.assertEqual(AURA_MODEL_ROUTER.normalize_tier("aura_2.6"), "aura-2.6")
        self.assertIsNone(AURA_MODEL_ROUTER.normalize_tier("unknown-9.9"))

        p20 = Aura20StudyEngine().build_dispatch_plan(999101, "Explain photosynthesis simply")
        self.assertIn("STORYTELLER & STUDY MENTOR", p20.system_framing)
        self.assertEqual(p20.thought_steps, [])
        self.assertAlmostEqual(p20.temperature, 0.55)

        p23 = Aura23ArchitectEngine().build_dispatch_plan(999102, "Hello")
        self.assertIn("DEEP ARCHITECT & CODING STUDIO", p23.system_framing)
        self.assertGreaterEqual(len(p23.thought_steps), 3)
        self.assertAlmostEqual(p23.temperature, 0.2)

        p26 = Aura26ApexEngine().build_dispatch_plan(999103, "Hello")
        self.assertIn("APEX MULTI-AGENT SUPER-BRAIN", p26.system_framing)
        self.assertGreaterEqual(len(p26.thought_steps), 4)
        self.assertIn("aura-chart", p26.system_framing)

        enriched_26 = AURA_MODEL_ROUTER.postprocess_reply("aura-2.6", "Hello", "Ready to build!", p26)
        self.assertIn(":::thought AURA 2.6 Deep Multi-Agent Trace", enriched_26)
        self.assertIn("Phase 1", enriched_26)
        self.assertIn("Ready to build!", enriched_26)

        chart_block = Aura26ApexEngine.build_sample_apex_chart("Latency")
        self.assertIn("```aura-chart", chart_block)
        svg_card = Aura20StudyEngine.build_cartoon_study_svg("Neural Networks")
        self.assertIn("AURA 2.0 STUDY CARD", svg_card)


class TestAuraModelEnginesHttpAndUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)

        cls.user = aura_db.register_user(f"mod_u_{secrets.token_hex(4)}", "ModPass99!")
        cls.token = cls.user["token"]
        cls.uid = cls.user["user"]["id"]

    @classmethod
    def tearDownClass(cls):
        try:
            cls.server.shutdown()
            cls.server.server_close()
        except Exception:
            pass
        shutil.rmtree(_resolve_workspace_dir(cls.uid), ignore_errors=True)

    def _req(self, path: str, method: str = "GET", token: str = "", body: dict | None = None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(f"{self.base}{path}", data=data, headers=headers, method=method)
        return urllib.request.urlopen(req, timeout=8)

    def test_models_catalog_endpoint_and_settings_persistence(self):
        with self._req("/api/models/aura", token=self.token) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["success"])
            self.assertEqual([m["id"] for m in data["models"]], ["aura-2.0", "aura-2.3", "aura-2.6"])

        with self._req(
            "/api/settings",
            method="POST",
            token=self.token,
            body={"aura_model": "aura-2.6"},
        ) as resp:
            saved = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(saved["success"])
            self.assertEqual(saved["active_aura_model"], "aura-2.6")

        with self._req("/api/settings", token=self.token) as resp:
            fetched = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(fetched["active_aura_model"], "aura-2.6")

    def test_chat_dispatch_routes_engines_and_preserves_slash_commands(self):
        captured = {}

        def _fake_think(self_brain, prompt, **kwargs):
            captured["prompt"] = prompt
            captured["temp"] = getattr(self_brain, "temperature", None)
            self_brain.last_tools = []
            return "Full interactive architecture delivered."

        with mock.patch.object(aura_web.AuraBrain, "think_and_act", _fake_think):
            with self._req(
                "/api/chat",
                method="POST",
                token=self.token,
                body={"prompt": "Build an ant simulation", "thread_id": "t_m26", "aura_model": "aura-2.6"},
            ) as resp:
                out = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(out["aura_model"], "aura-2.6")
                self.assertIn("[ENGINE PROFILE: AURA 2.6", captured["prompt"])
                self.assertIn(":::thought AURA 2.6 Deep Multi-Agent Trace", out["reply"])
                self.assertAlmostEqual(captured["temp"], 0.25)

            with self._req(
                "/api/chat",
                method="POST",
                token=self.token,
                body={"prompt": "Teach me recursion quickly", "thread_id": "t_m20", "aura_model": "aura-2.0"},
            ) as resp:
                out2 = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(out2["aura_model"], "aura-2.0")
                self.assertIn("[ENGINE PROFILE: AURA 2.0", captured["prompt"])
                self.assertNotIn(":::thought", out2["reply"])
                self.assertAlmostEqual(captured["temp"], 0.55)

        # Direct /calc command bypasses framing cleanly even under aura-2.6
        with self._req(
            "/api/chat",
            method="POST",
            token=self.token,
            body={"prompt": "/calc 7 * 8", "thread_id": "t_calc", "aura_model": "aura-2.6"},
        ) as resp:
            calc_out = json.loads(resp.read().decode("utf-8"))
            self.assertIn("56", calc_out["reply"])

    def test_frontend_contains_three_engines_and_generative_renderers(self):
        html = (Path(__file__).resolve().parent / "index.html").read_text(encoding="utf-8")
        for marker in (
            'id="auraTierBtn_aura-2.0"',
            'id="auraTierBtn_aura-2.3"',
            'id="auraTierBtn_aura-2.6"',
            "selectAuraModelTier",
            "_buildSafeAuraChartHtml",
            "hydrateInlineVisualCards",
            'id="customWallpaperInput"',
            "handleCustomWallpaperUpload",
            "aura-thought-block",
            "callout-arch",
        ):
            self.assertIn(marker, html, f"Missing UI marker: {marker}")

    def test_casual_greetings_and_image_clarity_regressions(self):
        from aura_brain import AuraBrain
        from aura_engine_base import is_casual_or_greeting_prompt
        from aura_media_engine import PhotorealCameraEngine

        self.assertTrue(is_casual_or_greeting_prompt("yooo"))
        self.assertTrue(is_casual_or_greeting_prompt("yoooo"))
        self.assertFalse(is_casual_or_greeting_prompt("Compare Python vs Rust performance"))

        plan26 = Aura26ApexEngine().build_dispatch_plan(999104, "yooo")
        self.assertIn("CASUAL TURN MODE", plan26.system_framing)

        composed, _ = PhotorealCameraEngine.compose_photoreal_prompt(
            "3 Pixar characters standing in front of Burj Khalifa Dubai sunny sky",
            camera_style="portrait",
        )
        self.assertIn("deep-focus f/8", composed)
        self.assertNotIn("optical bokeh", composed)

        prior_contents = [
            {"role": "model", "parts": [{"text": "![Dubai](/media/generated_images/aura_cinema_123.png)"}]},
            {"role": "user", "parts": [{"text": "pic ko seedha kar aur saaf bhej"}]},
        ]
        self.assertTrue(AuraBrain._should_include_tools_for_contents(prior_contents, tools=[{"name": "tool_generate_image"}]))


if __name__ == "__main__":
    unittest.main()
