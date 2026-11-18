"""Comprehensive unit, licensing, security, HTTP, and UI checks for AURA Universal Voice Cloud."""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import aura_db
import aura_web
from aura_brain import AuraBrain
from aura_voice_cloud import (
    KokoroOnnxAdapter,
    PiperAdapter,
    VOICE_ORCHESTRATOR,
    audit_voice_hardware,
    build_language_policy_instruction,
    detect_preferred_language,
    prepare_text_for_speech,
)


ROOT_DIR = Path(__file__).resolve().parent


class TestVoiceLanguageAndLicensingUnit(unittest.TestCase):
    def test_english_casual_greetings_never_trigger_hinglish(self):
        self.assertEqual(detect_preferred_language("Yo WhatsApp bro."), "en")
        self.assertEqual(detect_preferred_language("Yo bro, are you listening what I'm saying you?"), "en")
        self.assertEqual(detect_preferred_language("Hello AURA, explain Docker containers."), "en")
        self.assertEqual(detect_preferred_language("bhai kya haal hai aaj batao"), "hi-en")
        self.assertEqual(detect_preferred_language("नमस्ते आप कैसे हैं"), "hi")
        self.assertEqual(detect_preferred_language("నమస్కారం ఎలా ఉన్నారు"), "te")

    def test_offline_brain_never_replies_hinglish_on_english_input(self):
        brain = AuraBrain()
        brain.api_key = ""
        for msg in ("Yo WhatsApp bro.", "Yo bro, are you listening what I'm saying you?", "Hello"):
            out = brain._offline_autonomous_dispatch([{"role": "user", "parts": [{"text": msg}]}], tools=None)
            txt = out["candidates"][0]["content"]["parts"][0]["text"].lower()
            for banned in ("bhai", "haan", "badhiya", "batao", "samjha", "pichhli"):
                self.assertNotIn(banned, txt)

    def test_language_lock_and_speech_text_normalization(self):
        policy = build_language_policy_instruction("en", voice_turn=True)
        self.assertIn("[LANGUAGE LOCK: ENGLISH]", policy)
        self.assertIn("VOICE CALL STYLE", policy)

        dirty = (
            ":::thought Internal Trace\n- step 1\n:::\n"
            "> [!INSIGHT] Revenue grew 25% to ₹500 ($10).\n"
            "```python\nprint('ignore code')\n```\n"
            "Check [docs](https://example.com) now."
        )
        cleaned = prepare_text_for_speech(dirty, "en")
        self.assertNotIn("Internal Trace", cleaned)
        self.assertNotIn("ignore code", cleaned)
        self.assertIn("25 percent", cleaned)
        self.assertIn("500 rupees", cleaned)
        self.assertIn("10 dollars", cleaned)
        self.assertIn("Check docs now.", cleaned)

    def test_license_compliance_blocks_lessac_and_commercial_edge(self):
        piper = PiperAdapter()
        with self.assertRaises(PermissionError):
            piper.synthesize("hello", "en_US-lessac-medium", "en-us", commercial_only=True)

        with patch.object(VOICE_ORCHESTRATOR._adapters["kokoro"], "is_available", return_value=(False, "mocked")), \
             patch.object(VOICE_ORCHESTRATOR._adapters["sapi"], "is_available", return_value=(False, "mocked")):
            art = VOICE_ORCHESTRATOR.synthesize_speech(
                user_id="unit_comm",
                text="Testing commercial strict mode",
                language="en",
                voice_id="male_02",
                engine="auto",
                commercial_only=True,
                allow_silent_ci_fallback=True,
            )
            self.assertNotEqual(art.engine, "edge")
            self.assertTrue(art.commercial_safe)

    def test_hardware_audit_returns_valid_telemetry(self):
        hw = audit_voice_hardware()
        self.assertGreaterEqual(hw["cpu_cores"], 1)
        self.assertIn("maya_2_local_compatible", hw)
        self.assertIn("voice_root", hw)


class TestUniversalVoiceHttpAndFrontend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = aura_web.make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _req(self, path: str, method: str = "GET", data: dict | None = None, token: str = ""):
        url = f"http://127.0.0.1:{self.port}{path}"
        headers = {}
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, resp.headers.get("Content-Type", ""), resp.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers.get("Content-Type", ""), err.read()

    def _register_user(self, username: str) -> str:
        st, _, raw = self._req(
            "/api/auth/register",
            method="POST",
            data={"username": username, "password": "VoicePassword123!"},
        )
        self.assertEqual(st, 200)
        return json.loads(raw.decode("utf-8"))["token"]

    def test_universal_voice_api_lifecycle_and_tenant_isolation(self):
        st_v, _, raw_v = self._req("/v1/voices")
        self.assertEqual(st_v, 200)
        voices_payload = json.loads(raw_v.decode("utf-8"))
        self.assertTrue(voices_payload["success"])
        voice_ids = {v["id"] for v in voices_payload["voices"]}
        self.assertTrue({"male_01", "male_02", "female_01", "female_02", "hi_female_01", "te_female_01"}.issubset(voice_ids))

        st_l, _, raw_l = self._req("/api/v1/languages")
        self.assertEqual(st_l, 200)
        langs = {x["code"] for x in json.loads(raw_l.decode("utf-8"))["languages"]}
        self.assertEqual(langs, {"en", "hi", "hi-en", "te"})

        # Unauthenticated protected route must return 401
        st_unauth, _, _ = self._req("/v1/voice/hardware")
        self.assertEqual(st_unauth, 401)

        tok1 = self._register_user(f"vt_a_{secrets.token_hex(4)}")
        tok2 = self._register_user(f"vt_b_{secrets.token_hex(4)}")

        st_hw, _, raw_hw = self._req("/v1/voice/hardware", token=tok1)
        self.assertEqual(st_hw, 200)
        self.assertIn("hardware", json.loads(raw_hw.decode("utf-8")))

        # Synthesize speech cleanly (using local SAPI/silent fallback if mocked so test is fast & offline-safe)
        st_sp, _, raw_sp = self._req(
            "/v1/speech",
            method="POST",
            token=tok1,
            data={"text": "Hello! Voice synthesis works.", "language": "en", "voice_id": "male_02", "engine": "sapi"},
        )
        self.assertEqual(st_sp, 200)
        speech = json.loads(raw_sp.decode("utf-8"))["speech"]
        self.assertEqual(speech["language"], "en")
        audio_url = speech["audio_url"]
        speech_id = speech["speech_id"]

        # Owner can read speech job and binary audio
        st_job, _, _ = self._req(f"/v1/speech/{speech_id}", token=tok1)
        self.assertEqual(st_job, 200)
        st_aud, ctype, wav_bytes = self._req(audio_url, token=tok1)
        self.assertEqual(st_aud, 200)
        self.assertIn("audio/", ctype)
        self.assertGreater(len(wav_bytes), 100)

        # Tenant 2 cannot read or delete Tenant 1's audio
        st_aud2, _, _ = self._req(audio_url, token=tok2)
        self.assertEqual(st_aud2, 404)
        st_del2, _, _ = self._req(audio_url, method="DELETE", token=tok2)
        self.assertEqual(st_del2, 404)

        # Owner deletes audio cleanly
        st_del, _, _ = self._req(audio_url, method="DELETE", token=tok1)
        self.assertEqual(st_del, 200)
        st_after, _, _ = self._req(audio_url, token=tok1)
        self.assertEqual(st_after, 404)

        # Call session create -> read -> end
        st_c, _, raw_c = self._req(
            "/v1/calls",
            method="POST",
            token=tok1,
            data={"voice_id": "female_02", "language": "en", "engine": "auto", "consent_confirmed": True},
        )
        self.assertEqual(st_c, 200)
        cid = json.loads(raw_c.decode("utf-8"))["call"]["call_id"]
        st_cget, _, raw_cg = self._req(f"/v1/calls/{cid}", token=tok1)
        self.assertEqual(st_cget, 200)
        self.assertEqual(json.loads(raw_cg.decode("utf-8"))["call"]["status"], "active")
        st_cend, _, raw_ce = self._req(
            f"/v1/calls/{cid}/state",
            method="POST",
            token=tok1,
            data={"status": "ended", "interrupted": True},
        )
        self.assertEqual(st_cend, 200)
        self.assertEqual(json.loads(raw_ce.decode("utf-8"))["call"]["status"], "ended")

    def test_voice_chat_turn_locks_english_and_strips_thought_blocks(self):
        tok = self._register_user(f"vlt_{secrets.token_hex(4)}")
        with patch.object(aura_web.AuraBrain, "think_and_act", return_value="Hello! I am listening clearly in English."):
            st, _, raw = self._req(
                "/api/chat",
                method="POST",
                token=tok,
                data={
                    "prompt": "Yo bro, are you listening what I'm saying you?",
                    "thread_id": "voice_t1",
                    "voice_turn": True,
                    "preferred_language": "en",
                    "aura_model": "aura-2.6",
                },
            )
            self.assertEqual(st, 200)
            payload = json.loads(raw.decode("utf-8"))
            self.assertEqual(payload["resolved_language"], "en")
            self.assertNotIn(":::thought", payload["reply"])
            self.assertEqual(payload["speech_text"], "Hello! I am listening clearly in English.")

    def test_frontend_voice_studio_dom_and_js_syntax(self):
        html = (ROOT_DIR / "index.html").read_text(encoding="utf-8")
        for token in (
            'id="voiceHudLangSelect"',
            'id="voiceHudVoiceSelect"',
            'id="voiceHudEngineSelect"',
            'id="voiceStudioAudioPlayer"',
            'id="voiceCommercialOnlyCheckbox"',
            'testVoiceStudioSynthesis',
            '_fetchSentenceCloudAudio',
        ):
            self.assertIn(token, html)

        # Validate main inline JavaScript block parses without SyntaxError via Node.js
        import re
        import tempfile
        blocks = re.findall(r"<script\b[^>]*>(.*?)</script>", html, flags=re.DOTALL)
        main_script = max(blocks, key=len)
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tf:
            tf.write(main_script)
            tmp_js = tf.name
        try:
            proc = subprocess.run(
                ["node", "--check", tmp_js],
                text=True,
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        finally:
            try:
                os.unlink(tmp_js)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
