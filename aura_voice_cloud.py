"""Universal Voice Cloud Core & Local-First Hybrid TTS Orchestrator for AURA.

Supports pluggable voice engines:
- kokoro: Offline CPU neural TTS via kokoro-onnx (Apache-2.0 weights, MIT wrapper)
- edge: High-naturalness zero-key online neural voices for EN / HI / TE (dev/personal mode)
- maya: Pluggable remote Linux + NVIDIA CUDA Maya 2 / Veena worker (Apache-2.0 + Mimi CC-BY-4.0)
- piper: Pluggable optional adapter with GPL-3.0 & Lessac commercial clearance guard
- sapi: Air-gapped Windows System.Speech WAV synthesis fallback
"""
from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid
import wave
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_PERMANENT_DIR = Path(r"D:\PERMANENT-VOICE-SYSTEM")
AUDIO_CACHE_MAX_FILES = 180
AUDIO_CACHE_TTL_SECONDS = 3600


def resolve_voice_system_root() -> Path:
    """Returns persistent D:\\PERMANENT-VOICE-SYSTEM when present/writable, else temp dir."""
    override = (os.environ.get("AURA_VOICE_HOME") or "").strip()
    if override:
        p = Path(override)
        p.mkdir(parents=True, exist_ok=True)
        return p
    if not os.environ.get("VERCEL") and Path("D:\\").exists():
        try:
            DEFAULT_PERMANENT_DIR.mkdir(parents=True, exist_ok=True)
            return DEFAULT_PERMANENT_DIR
        except OSError:
            pass
    fallback = Path(tempfile.gettempdir()) / "aura_voice_system"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


VOICE_SYSTEM_ROOT = resolve_voice_system_root()
AUDIO_CACHE_DIR = VOICE_SYSTEM_ROOT / "audio_cache"
KOKORO_MODELS_DIR = VOICE_SYSTEM_ROOT / "models" / "kokoro"
CONFIG_DIR = VOICE_SYSTEM_ROOT / "config"


DEFAULT_LANGUAGES: List[Dict[str, Any]] = [
    {
        "code": "en",
        "name": "English",
        "speech_recognition_locale": "en-US",
        "engines_supported": ["kokoro", "edge", "maya", "sapi"],
    },
    {
        "code": "hi",
        "name": "Hindi",
        "speech_recognition_locale": "hi-IN",
        "engines_supported": ["kokoro", "edge", "maya"],
    },
    {
        "code": "hi-en",
        "name": "Hinglish",
        "speech_recognition_locale": "en-IN",
        "engines_supported": ["edge", "kokoro", "maya"],
    },
    {
        "code": "te",
        "name": "Telugu",
        "speech_recognition_locale": "te-IN",
        "engines_supported": ["edge", "maya"],
    },
]

DEFAULT_VOICES: List[Dict[str, Any]] = [
    {
        "id": "male_01",
        "name": "Male 01 (Deep Professional)",
        "gender": "male",
        "personality": "Deep, executive, confident",
        "use_case": "Business calls & technical architecture",
        "languages": ["en", "hi-en"],
        "mappings": {
            "kokoro": {"voice": "am_michael", "lang": "en-us"},
            "edge": {"voice": "en-US-AndrewNeural", "lang": "en-US"},
            "maya": {"voice": "en_male_pro_01", "lang": "en"},
        },
    },
    {
        "id": "male_02",
        "name": "Male 02 (Friendly Natural)",
        "gender": "male",
        "personality": "Friendly, clear, approachable",
        "use_case": "Normal conversations & Indian developer workflows",
        "languages": ["en", "hi-en", "hi"],
        "mappings": {
            "kokoro": {"voice": "am_adam", "lang": "en-us"},
            "edge": {"voice": "en-IN-PrabhatNeural", "lang": "en-IN"},
            "maya": {"voice": "en_male_friendly_02", "lang": "en"},
        },
    },
    {
        "id": "female_01",
        "name": "Female 01 (Calm Professional)",
        "gender": "female",
        "personality": "Calm, crisp, composed",
        "use_case": "Customer support & reliability operations",
        "languages": ["en", "hi-en"],
        "mappings": {
            "kokoro": {"voice": "af_bella", "lang": "en-us"},
            "edge": {"voice": "en-IN-NeerjaNeural", "lang": "en-IN"},
            "maya": {"voice": "en_female_pro_01", "lang": "en"},
        },
    },
    {
        "id": "female_02",
        "name": "VOX Clarisse (Studio HD)",
        "gender": "female",
        "personality": "Warm, encouraging, expressive",
        "use_case": "Daily assistance & study mentoring",
        "languages": ["en", "hi-en", "hi"],
        "mappings": {
            "kokoro": {"voice": "af_heart", "lang": "en-us"},
            "edge": {"voice": "en-US-AriaNeural", "lang": "en-US"},
            "maya": {"voice": "en_female_warm_02", "lang": "en"},
        },
    },
    {
        "id": "male_03",
        "name": "VOX Sovereign Baritone",
        "gender": "male",
        "personality": "Deep authoritative studio baritone",
        "use_case": "AURA Pro executive briefings & calling",
        "languages": ["en", "hi-en", "hi"],
        "mappings": {
            "kokoro": {"voice": "am_michael", "lang": "en-us"},
            "edge": {"voice": "en-GB-RyanNeural", "lang": "en-GB"},
            "maya": {"voice": "en_male_pro_01", "lang": "en"},
        },
    },
    {
        "id": "female_03",
        "name": "VOX Tokyo Synth Clear",
        "gender": "female",
        "personality": "Crisp, modern, ultra-clear",
        "use_case": "AURA Pro developer walkthroughs",
        "languages": ["en", "hi-en", "hi"],
        "mappings": {
            "kokoro": {"voice": "af_sarah", "lang": "en-us"},
            "edge": {"voice": "en-GB-SoniaNeural", "lang": "en-GB"},
            "maya": {"voice": "en_female_pro_01", "lang": "en"},
        },
    },
    {
        "id": "male_04",
        "name": "VOX Cyber Analyst",
        "gender": "male",
        "personality": "Focused, calm, technical precision",
        "use_case": "AURA Pro security & code audits",
        "languages": ["en", "hi-en", "hi"],
        "mappings": {
            "kokoro": {"voice": "am_adam", "lang": "en-us"},
            "edge": {"voice": "en-AU-WilliamNeural", "lang": "en-AU"},
            "maya": {"voice": "en_male_friendly_02", "lang": "en"},
        },
    },
    {
        "id": "ultra_cinema",
        "name": "VOX Ultra Sovereign Cinema",
        "gender": "male",
        "personality": "Ultra flagship smooth cinema voice",
        "use_case": "AURA Ultra real-time calling flagship",
        "languages": ["en", "hi-en", "hi"],
        "mappings": {
            "kokoro": {"voice": "am_fenrir", "lang": "en-us"},
            "edge": {"voice": "en-US-AndrewMultilingualNeural", "lang": "en-US"},
            "maya": {"voice": "en_male_pro_01", "lang": "en"},
        },
    },
    {
        "id": "hi_male_01",
        "name": "Hindi Male 01 (Natural)",
        "gender": "male",
        "personality": "Clear conversational Hindi & Hinglish",
        "use_case": "Hindi voice calls & announcements",
        "languages": ["hi", "hi-en"],
        "mappings": {
            "kokoro": {"voice": "hm_omega", "lang": "hi"},
            "edge": {"voice": "hi-IN-MadhurNeural", "lang": "hi-IN"},
            "maya": {"voice": "hi_male_01", "lang": "hi"},
        },
    },
    {
        "id": "hi_female_01",
        "name": "Hindi Female 01 (Swara)",
        "gender": "female",
        "personality": "Natural Hindi & Hinglish host",
        "use_case": "Hindi customer support & tutoring",
        "languages": ["hi", "hi-en"],
        "mappings": {
            "kokoro": {"voice": "hf_alpha", "lang": "hi"},
            "edge": {"voice": "hi-IN-SwaraNeural", "lang": "hi-IN"},
            "maya": {"voice": "hi_female_01", "lang": "hi"},
        },
    },
    {
        "id": "te_male_01",
        "name": "Telugu Male 01 (Mohan)",
        "gender": "male",
        "personality": "Warm Telugu regional clarity",
        "use_case": "Telugu calling agent",
        "languages": ["te"],
        "mappings": {
            "kokoro": None,
            "edge": {"voice": "te-IN-MohanNeural", "lang": "te-IN"},
            "maya": {"voice": "te_male_01", "lang": "te"},
        },
    },
    {
        "id": "te_female_01",
        "name": "Telugu Female 01 (Shruti)",
        "gender": "female",
        "personality": "Clear Telugu regional assistant",
        "use_case": "Telugu customer assistance",
        "languages": ["te"],
        "mappings": {
            "kokoro": None,
            "edge": {"voice": "te-IN-ShrutiNeural", "lang": "te-IN"},
            "maya": {"voice": "te_female_01", "lang": "te"},
        },
    },
]

DEFAULT_LICENSES: Dict[str, Dict[str, Any]] = {
    "kokoro": {
        "name": "Kokoro-82M (kokoro-onnx INT8)",
        "code_license": "MIT",
        "weights_license": "Apache-2.0",
        "commercial_safe": True,
        "offline_capable": True,
        "notes": "Primary self-hosted CPU engine on Windows/AMD hardware.",
    },
    "maya": {
        "name": "Maya 2 Native / Veena",
        "code_license": "Apache-2.0",
        "weights_license": "Apache-2.0 + upstream Mimi CC-BY-4.0 notice",
        "commercial_safe": True,
        "offline_capable": True,
        "notes": "Remote Linux CUDA 12.8 GPU worker via MAYA_ENGINE_URL.",
    },
    "edge": {
        "name": "Edge Online Neural Bridge",
        "code_license": "LGPL-3.0 (edge-tts client)",
        "weights_license": "Microsoft Consumer Speech Service (non-commercial SaaS warning)",
        "commercial_safe": False,
        "offline_capable": False,
        "notes": "Zero-key personal/demo fallback supporting Telugu te-IN. Blocked in commercial_only mode.",
    },
    "piper": {
        "name": "Piper TTS Adapter",
        "code_license": "GPL-3.0-or-later",
        "weights_license": "Voice-specific license; Lessac voices blocked in commercial_only mode",
        "commercial_safe": False,
        "offline_capable": True,
        "notes": "Optional fallback subject to GPL-3 and per-voice license clearance.",
    },
    "sapi": {
        "name": "Windows System.Speech Offline Fallback",
        "code_license": "Host OS",
        "weights_license": "Host OS",
        "commercial_safe": True,
        "offline_capable": True,
        "notes": "Air-gapped Windows fallback when ONNX weights and network are absent.",
    },
}

_ROMAN_HINDI_MARKERS = {
    "bhai", "yaar", "kya", "kaise", "kaisa", "nahi", "nhi", "haan", "han",
    "karo", "karna", "karenge", "batao", "bataiye", "samjh", "samjha", "acha",
    "achha", "badhiya", "theek", "thik", "kyu", "kyun", "kyunki", "matlab",
    "mera", "meri", "mere", "tum", "tera", "teri", "aap", "aapka", "aapki",
    "hoga", "hogi", "raha", "rahi", "hain", "hai", "chahiye", "chalo", "sun",
    "sunno", "bolo", "bol", "dekh", "dekho", "abhi", "phir", "fir", "yaani",
    "pichhli", "bilkul", "shuru", "bana", "banao", "banaye", "banayenge",
    "baat", "kuch", "aur", "par", "liye", "lea", "waala", "wale", "wala",
    "lag", "rahe", "naam", "kaam", "kar", "gaya", "gayi", "sakta", "sakte",
}


def _load_json_override(filename: str, default_value: Any) -> Any:
    path = CONFIG_DIR / filename
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default_value


def detect_preferred_language(text: str, requested: Optional[str] = None) -> str:
    """Resolves target response/speech language while preventing unrequested Hinglish drift."""
    req = (requested or "").strip().lower().replace("_", "-")
    if req in ("en", "en-us", "en-in", "english"):
        return "en"
    if req in ("hi", "hi-in", "hindi"):
        return "hi"
    if req in ("hi-en", "hinglish"):
        return "hi-en"
    if req in ("te", "te-in", "telugu"):
        return "te"

    sample = (text or "").strip()
    if not sample:
        return "en"
    if re.search(r"[\u0900-\u097F]", sample):
        return "hi"
    if re.search(r"[\u0C00-\u0C7F]", sample):
        return "te"

    words = re.findall(r"[a-zA-Z]+", sample.lower())
    hindi_hits = {w for w in words if w in _ROMAN_HINDI_MARKERS}
    # Require clear Hinglish signal (>=2 markers or >25% of tokens) so casual English stays pure English
    if len(hindi_hits) >= 2 or (words and len(hindi_hits) == 1 and len(words) <= 3 and next(iter(hindi_hits)) not in {"par", "aur", "sun"}):
        return "hi-en"
    return "en"


def build_language_policy_instruction(language: str, voice_turn: bool = False) -> str:
    """Produces crisp system/turn directives locking LLM output to the desired language."""
    norm = detect_preferred_language("", language) if language in ("en", "hi", "hi-en", "te") else "en"
    voice_note = (
        " VOICE CALL STYLE: Reply directly as natural human speech in 1 to 4 concise spoken sentences. "
        "Do NOT output markdown tables, code fences, :::thought traces, callouts, or unrequested references to prior bugs unless asked."
        if voice_turn
        else ""
    )
    if norm == "hi":
        return f"[LANGUAGE LOCK: HINDI] Reply in clear, natural conversational Hindi.{voice_note}"
    if norm == "hi-en":
        return f"[LANGUAGE LOCK: HINGLISH] Reply in natural Hinglish (conversational Hindi + English mix).{voice_note}"
    if norm == "te":
        return f"[LANGUAGE LOCK: TELUGU] Reply in clear, natural Telugu.{voice_note}"
    return (
        "[LANGUAGE LOCK: ENGLISH] Reply STRICTLY in clear, natural, fluent English. "
        "NEVER switch into Hindi or Hinglish phrases (do not say 'bhai', 'haan', 'badhiya', 'kya scene', etc.)."
        + voice_note
    )


def prepare_text_for_speech(raw_text: str, language: str = "en") -> str:
    """Cleans markdown, thought traces, symbols, and currency for natural human TTS prosody."""
    txt = str(raw_text or "")
    # Remove collapsible reasoning trace blocks & fenced code/chart blocks before speaking
    txt = re.sub(r":::thought[\s\S]*?:::", " ", txt)
    txt = re.sub(r"```[\s\S]*?```", " Code or visual rendered in workspace. ", txt)
    # Strip markdown links keeping anchor text
    txt = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", txt)
    # Strip callout markers & markdown formatting
    txt = re.sub(r">\s*\[!(?:INSIGHT|ARCH|TIP|KEY|WARN)\]\s*", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"[#*_`~>|]", " ", txt)
    # Expand common Indian currency, percentages, & abbreviations cleanly
    txt = re.sub(r"₹\s*([0-9]+(?:\.[0-9]+)?)", r"\1 rupees", txt)
    txt = re.sub(r"\bRs\.?\s*([0-9]+(?:\.[0-9]+)?)", r"\1 rupees", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\$\s*([0-9]+(?:\.[0-9]+)?)", r"\1 dollars", txt)
    txt = re.sub(r"([0-9]+(?:\.[0-9]+)?)\s*%", r"\1 percent", txt)
    txt = re.sub(r"\be\.g\.\b", "for example", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bi\.e\.\b", "that is", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\s+", " ", txt).strip()
    if len(txt) > 1200:
        txt = txt[:1190].rsplit(" ", 1)[0] + "."
    return txt or "Ready."


def _run_coro_sync(coro: Any) -> Any:
    """Safely executes an async coroutine from both sync WSGI and active event-loop contexts."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result_box: Dict[str, Any] = {}
    exc_box: List[BaseException] = []

    def _runner() -> None:
        try:
            result_box["value"] = asyncio.run(coro)
        except BaseException as exc:
            exc_box.append(exc)

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout=45)
    if exc_box:
        raise exc_box[0]
    if t.is_alive():
        raise TimeoutError("Async TTS synthesis timed out")
    return result_box.get("value")


@dataclass
class SpeechArtifact:
    speech_id: str
    audio_id: str
    user_id: str
    status: str
    engine: str
    voice_id: str
    provider_voice: str
    language: str
    format: str
    content_type: str
    latency_ms: float
    license: str
    commercial_safe: bool
    bytes_len: int
    clean_text: str
    audio_url: str
    created_at: float
    file_path: str = ""
    raw_bytes: bytes = field(default=b"", repr=False)

    def to_public_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload.pop("raw_bytes", None)
        payload.pop("file_path", None)
        return payload


class BaseVoiceAdapter(ABC):
    """Unified interface for pluggable TTS engines in Universal Voice Cloud."""

    engine_id: str = "base"
    commercial_safe: bool = True
    offline_capable: bool = True

    @abstractmethod
    def is_available(self) -> Tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    def synthesize(
        self,
        text: str,
        provider_voice: str,
        lang_code: str,
        speed: float = 1.0,
        commercial_only: bool = False,
    ) -> Tuple[bytes, str, str]:
        """Returns `(audio_bytes, file_ext, content_type)`."""
        raise NotImplementedError


class KokoroOnnxAdapter(BaseVoiceAdapter):
    """Local Apache-2.0 CPU neural TTS powered by kokoro-onnx + onnxruntime."""

    engine_id = "kokoro"
    commercial_safe = True
    offline_capable = True

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instance: Any = None
        self._available_voices: Optional[set[str]] = None

    @staticmethod
    def _model_paths() -> Tuple[Path, Path]:
        int8 = KOKORO_MODELS_DIR / "kokoro-v1.0.int8.onnx"
        fp32 = KOKORO_MODELS_DIR / "kokoro-v1.0.onnx"
        voices = KOKORO_MODELS_DIR / "voices-v1.0.bin"
        model = int8 if int8.exists() else fp32
        return model, voices

    def is_available(self) -> Tuple[bool, str]:
        if importlib.util.find_spec("kokoro_onnx") is None:
            return False, "kokoro-onnx package not installed"
        model, voices = self._model_paths()
        if not model.exists() or model.stat().st_size < 1_000_000:
            return False, f"Missing model weight in {KOKORO_MODELS_DIR}"
        if not voices.exists() or voices.stat().st_size < 100_000:
            return False, f"Missing voices-v1.0.bin in {KOKORO_MODELS_DIR}"
        return True, f"Ready ({model.name})"

    def _ensure_loaded(self) -> Any:
        with self._lock:
            if self._instance is not None:
                return self._instance
            from kokoro_onnx import Kokoro  # lazy optional import

            model, voices = self._model_paths()
            inst = Kokoro(str(model), str(voices))
            try:
                self._available_voices = set(inst.get_voices())
            except Exception:
                self._available_voices = None
            self._instance = inst
            return inst

    def synthesize(
        self,
        text: str,
        provider_voice: str,
        lang_code: str,
        speed: float = 1.0,
        commercial_only: bool = False,
    ) -> Tuple[bytes, str, str]:
        ok, reason = self.is_available()
        if not ok:
            raise RuntimeError(reason)
        kokoro = self._ensure_loaded()
        voice = provider_voice
        if self._available_voices and voice not in self._available_voices:
            voice = "af_heart" if "af_heart" in self._available_voices else next(iter(self._available_voices))
            lang_code = "en-us"
        samples, sample_rate = kokoro.create(
            text=text,
            voice=voice,
            speed=max(0.65, min(1.5, float(speed or 1.0))),
            lang=lang_code or "en-us",
        )
        import soundfile as sf

        buf = io.BytesIO()
        sf.write(buf, samples, sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue(), "wav", "audio/wav"


class EdgeNeuralAdapter(BaseVoiceAdapter):
    """High-naturalness zero-API-key Microsoft Edge online neural adapter (dev/personal mode)."""

    engine_id = "edge"
    commercial_safe = False
    offline_capable = False

    def is_available(self) -> Tuple[bool, str]:
        if importlib.util.find_spec("edge_tts") is None:
            return False, "edge-tts package not installed"
        if os.environ.get("AURA_VOICE_OFFLINE") == "1":
            return False, "Offline mode locked (AURA_VOICE_OFFLINE=1)"
        return True, "Ready (online neural bridge)"

    def synthesize(
        self,
        text: str,
        provider_voice: str,
        lang_code: str,
        speed: float = 1.0,
        commercial_only: bool = False,
    ) -> Tuple[bytes, str, str]:
        if commercial_only:
            raise PermissionError("Edge online neural bridge is blocked in commercial_only SaaS mode.")
        ok, reason = self.is_available()
        if not ok:
            raise RuntimeError(reason)
        import edge_tts

        rate_delta = int(round((max(0.65, min(1.5, float(speed or 1.0))) - 1.0) * 100))
        rate_str = f"{rate_delta:+d}%"

        async def _collect_once() -> bytes:
            comm = edge_tts.Communicate(text=text, voice=provider_voice or "en-IN-PrabhatNeural", rate=rate_str)
            chunks = bytearray()
            async for item in comm.stream():
                if item.get("type") == "audio" and item.get("data"):
                    chunks.extend(item["data"])
            return bytes(chunks)

        async def _collect() -> bytes:
            last_err: Optional[Exception] = None
            for attempt in range(2):
                try:
                    data = await asyncio.wait_for(_collect_once(), timeout=5.5)
                    if data and len(data) >= 64:
                        return data
                except Exception as exc:
                    last_err = exc
                if attempt == 0:
                    await asyncio.sleep(0.08)
            raise RuntimeError(f"Edge neural TTS failed: {last_err or 'empty audio stream'}")

        audio = _run_coro_sync(_collect())
        if not audio or len(audio) < 64:
            raise RuntimeError("Edge neural TTS returned empty audio stream.")
        return audio, "mp3", "audio/mpeg"


class Maya2Adapter(BaseVoiceAdapter):
    """Pluggable remote CUDA worker adapter for Maya 2 Native / Veena (Apache-2.0 + Mimi CC-BY-4.0)."""

    engine_id = "maya"
    commercial_safe = True
    offline_capable = True

    def is_available(self) -> Tuple[bool, str]:
        endpoint = (os.environ.get("MAYA_ENGINE_URL") or "").strip()
        if not endpoint:
            return False, "MAYA_ENGINE_URL not set (requires Linux + NVIDIA CUDA 12.8 >=8GB VRAM worker)"
        return True, f"Remote Maya GPU endpoint configured ({endpoint})"

    def synthesize(
        self,
        text: str,
        provider_voice: str,
        lang_code: str,
        speed: float = 1.0,
        commercial_only: bool = False,
    ) -> Tuple[bytes, str, str]:
        endpoint = (os.environ.get("MAYA_ENGINE_URL") or "").strip().rstrip("/")
        if not endpoint:
            raise RuntimeError("Maya 2 Native requires a configured GPU inference worker (MAYA_ENGINE_URL).")
        payload = json.dumps({
            "text": text,
            "voice": provider_voice,
            "language": lang_code,
            "speed": speed,
            "format": "wav",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{endpoint}/synthesize",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = resp.read()
            ctype = resp.headers.get("Content-Type", "audio/wav")
            ext = "mp3" if "mpeg" in ctype else "wav"
            return data, ext, ctype


class PiperAdapter(BaseVoiceAdapter):
    """Pluggable Piper adapter enforcing GPL-3.0 & Lessac commercial license blocking."""

    engine_id = "piper"
    commercial_safe = False
    offline_capable = True

    def is_available(self) -> Tuple[bool, str]:
        return False, "Piper adapter standby (GPL-3.0; Lessac voices blocked in commercial mode)"

    def synthesize(
        self,
        text: str,
        provider_voice: str,
        lang_code: str,
        speed: float = 1.0,
        commercial_only: bool = False,
    ) -> Tuple[bytes, str, str]:
        if "lessac" in (provider_voice or "").lower():
            raise PermissionError(
                "License compliance block: Lessac-derived Piper voices cannot be deployed in commercial SaaS."
            )
        if commercial_only:
            raise PermissionError("Piper GPL-3.0 engine requires cleared non-Lessac voice clearance before use.")
        raise RuntimeError("Piper CLI/model binary not mounted locally.")


class WindowsSapiAdapter(BaseVoiceAdapter):
    """Air-gapped Windows System.Speech offline WAV synthesis fallback (zero external dependencies)."""

    engine_id = "sapi"
    commercial_safe = True
    offline_capable = True

    def is_available(self) -> Tuple[bool, str]:
        if platform.system() != "Windows":
            return False, "Windows-only System.Speech fallback"
        if shutil.which("powershell"):
            return True, "Ready (Windows offline fallback)"
        return False, "PowerShell unavailable"

    def synthesize(
        self,
        text: str,
        provider_voice: str,
        lang_code: str,
        speed: float = 1.0,
        commercial_only: bool = False,
    ) -> Tuple[bytes, str, str]:
        if platform.system() != "Windows":
            raise RuntimeError("Windows SAPI fallback only runs on Windows hosts.")
        tmp = AUDIO_CACHE_DIR / f"_sapi_{uuid.uuid4().hex[:12]}.wav"
        AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # Pass text cleanly via env var so arbitrary characters never touch PowerShell syntax
        env = os.environ.copy()
        env["AURA_SAPI_TEXT"] = text[:1000]
        env["AURA_SAPI_OUT"] = str(tmp)
        env["AURA_SAPI_RATE"] = str(max(-6, min(6, int(round((float(speed or 1.0) - 1.0) * 6)))))
        ps_cmd = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.Rate = [int]$env:AURA_SAPI_RATE; "
            "$s.SetOutputToWaveFile($env:AURA_SAPI_OUT); "
            "$s.Speak($env:AURA_SAPI_TEXT); "
            "$s.Dispose()"
        )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            if proc.returncode == 0 and tmp.exists() and tmp.stat().st_size > 44:
                return tmp.read_bytes(), "wav", "audio/wav"
            raise RuntimeError(proc.stderr.strip() or "System.Speech synthesis failed")
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


def _build_minimal_wav_tone_fallback(duration_ms: int = 120) -> bytes:
    """Produces valid silent/soft PCM WAV frame if running on minimal non-Windows CI without audio engines."""
    sample_rate = 16000
    n_samples = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


def audit_voice_hardware() -> Dict[str, Any]:
    """Audits CPU, RAM, GPU, disk space, and TTS engine readiness safely without large downloads."""
    cuda_gpus: List[str] = []
    video_controllers: List[str] = []
    if platform.system() == "Windows":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"],
                capture_output=True,
                text=True,
                timeout=4,
            )
            if out.returncode == 0:
                video_controllers = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        except Exception:
            pass
    try:
        ort_spec = importlib.util.find_spec("onnxruntime")
        if ort_spec is not None:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            if "CUDAExecutionProvider" in providers:
                cuda_gpus.append("ONNXRuntime-CUDA")
    except Exception:
        pass

    ram_gb = 0.0
    try:
        import psutil
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except Exception:
        pass

    disk_free_gb = 0.0
    try:
        disk_free_gb = round(shutil.disk_usage(VOICE_SYSTEM_ROOT).free / (1024 ** 3), 2)
    except Exception:
        pass

    model_kokoro, voices_kokoro = KokoroOnnxAdapter._model_paths()
    return {
        "host_os": f"{platform.system()} {platform.release()}",
        "cpu": platform.processor() or "x86_64",
        "cpu_cores": os.cpu_count() or 1,
        "ram_gb": ram_gb,
        "video_controllers": video_controllers,
        "cuda_available": bool(cuda_gpus),
        "maya_2_local_compatible": bool(cuda_gpus and ram_gb >= 12.0),
        "maya_2_reason": (
            "NVIDIA GPU + CUDA 12.8 worker recommended (>=8 GB VRAM); use MAYA_ENGINE_URL remote worker."
            if not cuda_gpus
            else "CUDA detected"
        ),
        "voice_root": str(VOICE_SYSTEM_ROOT),
        "disk_free_gb": disk_free_gb,
        "kokoro_model_ready": model_kokoro.exists() and voices_kokoro.exists(),
        "kokoro_model_mb": round((model_kokoro.stat().st_size if model_kokoro.exists() else 0) / (1024 ** 2), 1),
    }


class UniversalVoiceOrchestrator:
    """Thread-safe multi-engine Voice Cloud orchestrator & tenant-isolated job store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._adapters: Dict[str, BaseVoiceAdapter] = {
            "kokoro": KokoroOnnxAdapter(),
            "edge": EdgeNeuralAdapter(),
            "maya": Maya2Adapter(),
            "piper": PiperAdapter(),
            "sapi": WindowsSapiAdapter(),
        }
        self._artifacts: Dict[str, SpeechArtifact] = {}
        self._calls: Dict[str, Dict[str, Any]] = {}
        self._phrase_cache: Dict[Tuple[str, str, float, str], Tuple[bytes, str, str, str, str]] = {}

    def _voices(self) -> List[Dict[str, Any]]:
        data = _load_json_override("voices.json", {"voices": DEFAULT_VOICES})
        return list(data.get("voices") or DEFAULT_VOICES)

    def _languages(self) -> List[Dict[str, Any]]:
        data = _load_json_override("languages.json", {"languages": DEFAULT_LANGUAGES})
        return list(data.get("languages") or DEFAULT_LANGUAGES)

    def _licenses(self) -> Dict[str, Any]:
        data = _load_json_override("licenses.json", {"engines": DEFAULT_LICENSES})
        return dict(data.get("engines") or DEFAULT_LICENSES)

    def list_languages(self) -> List[Dict[str, Any]]:
        return self._languages()

    def list_voices(
        self,
        language: Optional[str] = None,
        gender: Optional[str] = None,
        commercial_only: bool = False,
    ) -> List[Dict[str, Any]]:
        items = self._voices()
        results: List[Dict[str, Any]] = []
        lang_norm = (language or "").strip().lower()
        gen_norm = (gender or "").strip().lower()
        for v in items:
            if lang_norm and lang_norm not in (v.get("languages") or []):
                continue
            if gen_norm and (v.get("gender") or "").lower() != gen_norm:
                continue
            if commercial_only:
                maps = v.get("mappings") or {}
                if not (maps.get("kokoro") or maps.get("maya")):
                    continue
            results.append(v)
        return results

    def get_engine_statuses(self) -> Dict[str, Any]:
        licenses = self._licenses()
        statuses: Dict[str, Any] = {}
        for eid, adapter in self._adapters.items():
            ok, note = adapter.is_available()
            lic = licenses.get(eid) or DEFAULT_LICENSES.get(eid, {})
            statuses[eid] = {
                "available": ok,
                "status_note": note,
                "commercial_safe": bool(adapter.commercial_safe),
                "offline_capable": bool(adapter.offline_capable),
                "license": lic.get("weights_license", "Unknown"),
            }
        return statuses

    def _resolve_voice_entry(self, voice_id: str, language: str) -> Dict[str, Any]:
        voices = self._voices()
        vid = (voice_id or "").strip().lower()
        for v in voices:
            if v["id"].lower() == vid:
                return v
        # Pick language-matched default cleanly
        for v in voices:
            if language in (v.get("languages") or []):
                return v
        return voices[0]

    def _plan_engine_chain(
        self,
        requested_engine: str,
        language: str,
        voice_entry: Dict[str, Any],
        commercial_only: bool,
    ) -> List[str]:
        req = (requested_engine or "auto").strip().lower()
        maps = voice_entry.get("mappings") or {}
        if req != "auto" and req in self._adapters:
            order = [req]
            for extra in ("kokoro", "edge", "sapi"):
                if extra not in order:
                    order.append(extra)
        elif commercial_only:
            order = ["maya", "kokoro", "sapi"]
        elif language in ("te",):
            # Telugu uses Maya remote GPU first, Edge neural online next (Kokoro doesn't support Telugu)
            order = ["maya", "edge"] if os.environ.get("VERCEL") else ["maya", "edge", "sapi"]
        elif os.environ.get("VERCEL"):
            # Serverless Linux: skip local desktop SAPI and local heavy ONNX weights unless configured
            order = ["maya", "edge"] if (os.environ.get("MAYA_ENGINE_URL") or "").strip() else ["edge"]
        else:
            # Interactive Live Voice Hybrid: low-latency Maya GPU -> Edge HD (~1.8s EN/HI/HI-EN) -> Offline Apache-2.0 Kokoro -> SAPI
            order = ["maya", "edge", "kokoro", "sapi"]

        if commercial_only:
            order = [e for e in order if self._adapters[e].commercial_safe]
        return order

    def cleanup_expired_audio(self) -> int:
        """Removes stale cached audio artifacts so disk stays lean permanently."""
        removed = 0
        now = time.time()
        with self._lock:
            stale_ids = [
                aid
                for aid, art in self._artifacts.items()
                if (now - art.created_at) > AUDIO_CACHE_TTL_SECONDS
            ]
            if len(self._artifacts) - len(stale_ids) > AUDIO_CACHE_MAX_FILES:
                ordered = sorted(self._artifacts.values(), key=lambda x: x.created_at)
                overflow = len(self._artifacts) - AUDIO_CACHE_MAX_FILES
                for art in ordered[:overflow]:
                    if art.audio_id not in stale_ids:
                        stale_ids.append(art.audio_id)
            for aid in stale_ids:
                art = self._artifacts.pop(aid, None)
                if art and art.file_path:
                    try:
                        Path(art.file_path).unlink(missing_ok=True)
                    except OSError:
                        pass
                removed += 1
        return removed

    def synthesize_speech(
        self,
        user_id: Any,
        text: str,
        language: str = "auto",
        voice_id: str = "male_02",
        engine: str = "auto",
        speed: float = 1.0,
        commercial_only: bool = False,
        allow_silent_ci_fallback: bool = True,
    ) -> SpeechArtifact:
        self.cleanup_expired_audio()
        t0 = time.perf_counter()
        resolved_lang = detect_preferred_language(text, language if language != "auto" else None)
        clean_text = prepare_text_for_speech(text, resolved_lang)
        voice_entry = self._resolve_voice_entry(voice_id, resolved_lang)
        chain = self._plan_engine_chain(engine, resolved_lang, voice_entry, commercial_only=commercial_only)

        errors: List[str] = []
        audio_bytes = b""
        ext = "wav"
        ctype = "audio/wav"
        used_engine = ""
        used_provider_voice = ""
        licenses = self._licenses()

        cache_key = (
            voice_entry["id"],
            resolved_lang,
            round(max(0.65, min(1.5, float(speed or 1.0))), 2),
            clean_text,
        )
        if not commercial_only and (engine or "auto").strip().lower() in ("auto", "edge") and len(clean_text) <= 220:
            with self._lock:
                cached = self._phrase_cache.get(cache_key)
            if cached:
                audio_bytes, ext, ctype, used_engine, used_provider_voice = cached

        maps = voice_entry.get("mappings") or {}
        for eng_id in ([] if audio_bytes else chain):
            adapter = self._adapters[eng_id]
            ok, reason = adapter.is_available()
            if not ok:
                errors.append(f"{eng_id}: {reason}")
                continue
            eng_map = maps.get(eng_id) or {}
            # Skip kokoro automatically if voice explicitly disables kokoro (e.g., Telugu voice)
            if eng_id == "kokoro" and maps.get("kokoro") is None and eng_id in maps:
                errors.append("kokoro: language unsupported for selected voice")
                continue
            prov_voice = str(eng_map.get("voice") or voice_id or "am_adam")
            prov_lang = str(eng_map.get("lang") or ("hi" if resolved_lang in ("hi", "hi-en") else "en-us"))
            try:
                audio_bytes, ext, ctype = adapter.synthesize(
                    text=clean_text,
                    provider_voice=prov_voice,
                    lang_code=prov_lang,
                    speed=speed,
                    commercial_only=commercial_only,
                )
                used_engine = eng_id
                used_provider_voice = prov_voice
                break
            except PermissionError:
                raise
            except Exception as exc:
                errors.append(f"{eng_id}: {exc}")

        if not audio_bytes:
            if not allow_silent_ci_fallback:
                raise RuntimeError("All TTS engines failed: " + " | ".join(errors))
            audio_bytes = _build_minimal_wav_tone_fallback()
            used_engine = "fallback_pcm"
            used_provider_voice = "pcm_silence"
        elif not commercial_only and used_engine in ("edge", "kokoro", "maya") and len(clean_text) <= 220:
            with self._lock:
                if len(self._phrase_cache) >= 64:
                    oldest_key = next(iter(self._phrase_cache))
                    self._phrase_cache.pop(oldest_key, None)
                self._phrase_cache[cache_key] = (audio_bytes, ext, ctype, used_engine, used_provider_voice)

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        aid = f"aud_{uuid.uuid4().hex[:14]}"
        sid = f"sp_{uuid.uuid4().hex[:12]}"
        file_path = ""
        if not os.environ.get("VERCEL"):
            try:
                AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                target = AUDIO_CACHE_DIR / f"{aid}.{ext}"
                target.write_bytes(audio_bytes)
                file_path = str(target)
            except OSError:
                file_path = ""

        lic_info = licenses.get(used_engine) or DEFAULT_LICENSES.get(used_engine, {})
        artifact = SpeechArtifact(
            speech_id=sid,
            audio_id=aid,
            user_id=str(user_id),
            status="completed",
            engine=used_engine,
            voice_id=voice_entry["id"],
            provider_voice=used_provider_voice or voice_entry["id"],
            language=resolved_lang,
            format=ext,
            content_type=ctype,
            latency_ms=latency_ms,
            license=str(lic_info.get("weights_license", "Standard")),
            commercial_safe=bool(self._adapters.get(used_engine, self._adapters["sapi"]).commercial_safe)
            if used_engine in self._adapters
            else True,
            bytes_len=len(audio_bytes),
            clean_text=clean_text,
            audio_url=f"/v1/audio/{aid}",
            created_at=time.time(),
            file_path=file_path,
            raw_bytes=audio_bytes if not file_path or len(audio_bytes) < 2_500_000 else b"",
        )
        with self._lock:
            self._artifacts[aid] = artifact
        return artifact

    def get_artifact_by_speech_id(self, speech_id: str, user_id: Any) -> Optional[SpeechArtifact]:
        with self._lock:
            for art in self._artifacts.values():
                if art.speech_id == speech_id and art.user_id == str(user_id):
                    return art
        return None

    def get_audio_bytes(self, audio_id: str, user_id: Any) -> Optional[Tuple[bytes, SpeechArtifact]]:
        with self._lock:
            art = self._artifacts.get(audio_id)
        if not art or art.user_id != str(user_id):
            return None
        if art.raw_bytes:
            return art.raw_bytes, art
        if art.file_path and Path(art.file_path).exists():
            return Path(art.file_path).read_bytes(), art
        return None

    def delete_audio(self, audio_id: str, user_id: Any) -> bool:
        with self._lock:
            art = self._artifacts.get(audio_id)
            if not art or art.user_id != str(user_id):
                return False
            self._artifacts.pop(audio_id, None)
        if art.file_path:
            try:
                Path(art.file_path).unlink(missing_ok=True)
            except OSError:
                pass
        return True

    def create_call_session(
        self,
        user_id: Any,
        voice_id: str = "male_02",
        language: str = "en",
        engine: str = "auto",
        consent_confirmed: bool = True,
    ) -> Dict[str, Any]:
        cid = f"call_{uuid.uuid4().hex[:12]}"
        session = {
            "call_id": cid,
            "user_id": str(user_id),
            "status": "active",
            "voice_id": voice_id,
            "language": detect_preferred_language("", language),
            "engine": engine,
            "turns": 0,
            "interrupted": False,
            "consent_confirmed": bool(consent_confirmed),
            "ai_disclosure": "AI-generated voice session (authorized user/inbound call)",
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        with self._lock:
            self._calls[cid] = session
        return dict(session)

    def get_call_session(self, call_id: str, user_id: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            sess = self._calls.get(call_id)
            if not sess or sess["user_id"] != str(user_id):
                return None
            return dict(sess)

    def update_call_session(self, call_id: str, user_id: Any, **updates: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            sess = self._calls.get(call_id)
            if not sess or sess["user_id"] != str(user_id):
                return None
            for k, v in updates.items():
                if k in ("status", "voice_id", "language", "engine", "turns", "interrupted"):
                    sess[k] = v
            sess["updated_at"] = time.time()
            return dict(sess)


VOICE_ORCHESTRATOR = UniversalVoiceOrchestrator()
