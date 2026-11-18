# AURA Sovereign — Multi-User Agentic AI Operating System

**AURA** is a multi-tenant, safety-gated AI Engineering, Multimodal Voice, and Automation Operating System built in Python + Vanilla Web Platform (zero heavyweight bundler lock-in) with Vercel Serverless & Localhost Parity.

## Core Sovereign Flagship Pillars

1. **ChatGPT-Style Full-Duplex Live Voice HUD (`#voiceCallOverlay` + `<canvas id="voiceCallOrb">`)**
   - Real-time procedural acoustic orb reacting dynamically across `listening`, `thinking`, `speaking`, and `halted` states.
   - Continuous Web Speech Recognition (`SpeechRecognition` / `webkitSpeechRecognition`) -> `/api/chat` -> stripped plain-text Speech Synthesis (`speechSynthesis`) with instant barge-in interruption, mute toggle, and keyboard turn fallback.

2. **Claude-Style Live Artifact Split Pane & Isolated IDE Workbench (`aura_workspace_ide.py`, `coderx_engine.py`)**
   - Interactive side-by-side Live Artifact Workspace (`#artifactSplitPane`) rendering `HTML` and `SVG` outputs safely inside sandboxed `blob:` `<iframe>` (`sandbox="allow-scripts"`, CSP compliant) with source inspection, copy, and 1-click **Save to IDE Workspace** (`/api/workspace/save`).
   - Full IDE drawer with isolated per-user file explorer (`workspace/user_<id>`), line-sliced AST/search grep, atomic file writes (`_atomic_write_text`), live static preview servers, and 390px mobile viewport simulation.

3. **Reasoning Mode Selector & Multi-Provider Brain (`aura_brain.py`, `aura_settings.py`)**
   - Switch dynamically between **`Fast Core`**, **`Architect Mode`** (`## Plan`, `## Implementation`, `## Verification`), and **`Verifier Mode`** (low-temperature security/edge-case auditing) in `/api/chat` and `/api/chat/stream`.
   - Per-user configurable **Google Gemini** (via server `GEMINI_API_KEY` env var) or **local Ollama** (`127.0.0.1:11434`).

4. **JARVIS Safe Automations & Per-Tenant Hardware Kill Switch (`aura_jarvis_hub.py`)**
   - Thread-safe coordinator (`JARVIS_HUB`) exposing audited real routines via `GET /api/jarvis/status`, `POST /api/jarvis/run`, and `POST /api/jarvis/kill_switch`:
     - `repo_health_audit` — Walks repository Python files via native `ast.parse`, checks secret hygiene, and inventories test suites.
     - `security_threat_scan` — Dispatches **TRINETRA** Cyber Forensics + **PayGuard UPI** phishing shield.
     - `code_ast_review` — Native AST audit calculating docstring coverage and flagging `eval`/`exec`/`os.system` calls with strict path traversal protection.
     - `executive_briefing` — Aggregates live city weather, AI news headlines, and workspace health.
   - **Emergency Kill Switch:** Per-user hardware/autonomy halt (`halted=True`) immediately blocks `POST /api/jarvis/run` (`HTTP 423 Locked`), maintains an immutable tenant audit log, and forces chat dispatch into strict `ask_first` verification until re-armed.

5. **Sovereign 10-Nexus & Antigravity Omni-Core (`aura_bharatcode_top10.py`, `aura_antigravity_core.py`, `aura_10_systems.py`)**
   - 10 deterministic specialist engines (**TRINETRA** Cyber/BNS Legal Defense, **AURA Neural IDE**, **GitKitty**, **Ashby Job Radar**, **LearnOS**, **Form2Fact**, **OrvynAI**, **Spare-GPU**, **PayGuard UPI**, **Anonymous-Campus**).
   - 9 Agentic Slash Commands (`/goal`, `/plan`, `/boost`, `/teamwork`, `/browser`, `/schedule`, `/compact`, `/learn`, `/grill-me`), multi-agent swarm coordination, and browser-safe hardware bridge controls.

6. **Dedicated Modular Flagship Engines & Generative UI (`aura_models_hub.py`, `aura_engine_20.py`, `aura_engine_23.py`, `aura_engine_26.py`)**
   - **`AURA 2.0` (`aura-2.0`)**: Fast everyday assistant & warm study mentor generating expressive, cartoon-style SVG concept explainers.
   - **`AURA 2.3` (`aura-2.3`)**: Deep Architect & coding studio with AST/workspace context tracing, architecture SVG blueprints, and low-temperature multi-step verification.
   - **`AURA 2.6` (`aura-2.6`)**: Apex multi-agent synthesis engine streaming live `:::thought :::` traces, semantic callout banners, interactive `aura-chart` SVG graphs, animated visuals, and 1-prompt sandboxed apps.
   - **Theme & Wallpaper Studio**: Built-in curated dark presets (`Obsidian Gold`, `Pure Matte Black`, `Titanium Cyan`, `Emerald Matrix`) and client-side gallery wallpaper compression stored privately per browser.

7. **Universal Voice Cloud & Permanent Hybrid TTS (`aura_voice_cloud.py`, `/v1/*`)**
   - **Multi-Engine Adapter Orchestrator**: Pluggable `Kokoro-82M` INT8 CPU offline engine (`Apache-2.0`, stored on `D:\PERMANENT-VOICE-SYSTEM` locally), zero-key `Edge Neural` bridge (`English`, `Hindi`, `Hinglish`, `Telugu`), remote `Maya 2 Native` CUDA worker (`MAYA_ENGINE_URL` with `Apache-2.0` + `Mimi CC-BY-4.0` notice), license-guarded `Piper` (`Lessac` commercial block), and Windows `System.Speech` offline fallback.
   - **Strict English Language Lock & Progressive Audio**: Defaults strictly to natural English unless Hindi/Hinglish/Telugu is detected or chosen in Live Voice HUD / Voice Studio, with sentence-by-sentence neural audio prefetching and instant Barge-In interrupt.
   - **Versioned Developer & SaaS API**: `/v1/voices`, `/v1/languages`, `/v1/speech`, `/v1/speech/{id}`, `/v1/audio/{id}` (`GET`/`DELETE`), `/v1/calls`, and `/v1/voice/hardware`.

## Security & Privacy Architecture

- **Authentication & Sessions:** Scrypt password hashing (`aura_db.py`), `HttpOnly; SameSite=Strict` cookies + dynamic CSRF token (`X-CSRF-Token`), unique username enforcement, and 1-click isolated guest sessions.
- **Workspace Containment:** Strict `Path.relative_to()` path-escape guards keep all user reads/writes confined to `workspace/user_<id>`.
- **Zero-Secret Hygiene:** API keys and secrets are never hardcoded or committed (`.env` protected in `.gitignore`, checked automatically by `repo_health_audit`).
- **Atomic File Writes:** `coderx_engine._atomic_write_text` writes via same-directory `tempfile` + `os.fsync` + `os.replace`.

## Quickstart (Local & Cloud)

```powershell
# Optional: configure your Gemini API key in environment (never commit secrets)
$env:GEMINI_API_KEY="your_gemini_api_key_here"

# Start AURA Web OS (default http://127.0.0.1:5050)
python aura_web.py
```

Deploy serverless directly on Vercel via [`vercel.json`](vercel.json) and [`api/index.py`](api/index.py).

## Running Verified Test Suites

```powershell
python -m unittest test_aura_voice_cloud test_aura_models_v2_engines test_aura_sovereign_v5 test_aura_workspace_ide -v
python -m pytest test_aura_voice_cloud.py test_aura_models_v2_engines.py test_aura_reliability_fixes.py test_aura_workspace_ide.py test_aura_sovereign_v5.py test_aura_pipeline.py -v
```
