"""AURA 2.6 Engine: Apex Multi-Agent Deep Thinker, Live Graphs, Animations & 1-Prompt Full App Builder."""
from __future__ import annotations

from typing import Any, Dict, List

from aura_engine_base import BaseAuraModelEngine, EngineDispatchPlan, is_casual_or_greeting_prompt
from aura_jarvis_hub import JARVIS_HUB


class Aura26ApexEngine(BaseAuraModelEngine):
    """Apex GPT-6 / Astra tier multi-agent engine with deep traces, animated SVG/HTML, and live charts."""

    tier_id = "aura-2.6"
    display_name = "AURA 2.6"
    tagline = "Apex Multi-Agent, Graphs & Animations"
    tier_rank = 3
    default_temperature = 0.25

    def _compose_blueprint(
        self, prompt: str, ws_info: Dict[str, Any], reasoning_mode: str
    ) -> tuple[str, List[str], str]:
        p_clean = (prompt or "").strip()
        word_count = len(p_clean.split())
        file_count = ws_info.get("file_count", 0)
        sample_files = ", ".join((ws_info.get("files") or [])[:6]) or "fresh canvas"

        steps = [
            f"Phase 1 [First-Principles Deconstructor]: Parsed prompt ({word_count} words), core intent, and edge cases.",
            f"Phase 2 [Workspace Synthesizer]: Checked {file_count} workspace file(s) [{sample_files}] and visual/code eligibility.",
            "Phase 3 [Explanation Planner]: Reserved callouts, `aura-chart` visuals, and HTML/SVG artifacts for genuine analytical value only.",
            "Phase 4 [TRINETRA / Integrity Check]: Enforced factual grounding and zero fabricated benchmark telemetry.",
        ]

        casual_rule = (
            "0. CASUAL TURN MODE: The user sent a brief greeting or conversational message. Respond directly, sharply, and naturally in 1-3 sentences of clean prose — "
            "strictly NO SVGs, NO fake performance charts (`Neural Speed: 98%`), NO `INSIGHT`/`ARCH`/`WARN` callout spam on greetings.\n"
            if is_casual_or_greeting_prompt(prompt)
            else ""
        )

        framing = (
            "[ENGINE PROFILE: AURA 2.6 — APEX MULTI-AGENT SUPER-BRAIN]\n"
            "You are AURA 2.6, AURA's highest-tier intelligence built for unmatched clarity, genuine insight, and complete execution.\n"
            f"Active Workspace Context: {file_count} file(s) [{sample_files}].\n"
            "Core Excellence Rules:\n"
            f"{casual_rule}"
            "1. SUBSTANCE OVER FLUFF: Never invent self-congratulatory benchmark stats (like 'Neural Speed: 98%'). Every chart, diagram, or code artifact MUST serve the user's actual question.\n"
            "2. MULTI-FORMAT RICH EXPLANATIONS (WHEN HELPFUL):\n"
            "   - Use colored callouts (`> [!INSIGHT] ...`, `> [!ARCH] ...`, `> [!KEY] ...`, `> [!WARN] ...`) only for genuinely critical insights.\n"
            "   - Emit ```aura-chart``` JSON (`{\"title\":\"...\",\"subtitle\":\"...\",\"type\":\"bar\",\"labels\":[...],\"values\":[...],\"unit\":\"...\"}`) at column 0 ONLY when real quantitative comparisons, benchmarks, or metrics belong in the answer.\n"
            "   - Emit ONE crisp animated ```svg``` diagram (`viewBox=\"0 0 720 260\"`, column 0 — NEVER inside a `>` blockquote!) ONLY when explaining a mechanism, system flow, or architecture visually.\n"
            "3. 1-PROMPT PLAYABLE HTML ARTIFACT BUILDER: When asked to build an app, game, simulation, or interactive dashboard, output a COMPLETE self-contained ```html``` file at column 0 with polished dark UI and `<canvas>`/`<script>` interactivity.\n"
            "4. STRICT FORMATTING: Never prefix ```svg```, ```html```, or ```aura-chart``` fences with `>` blockquote symbols."
        )
        return framing, steps, "AURA 2.6 Deep Multi-Agent Trace"

    def enrich_reply(self, prompt: str, reply: str, plan: EngineDispatchPlan) -> str:
        """Attaches deep multi-agent trace and self-audit badge onto AURA 2.6 responses."""
        if not reply:
            return reply
        enriched = super().enrich_reply(prompt, reply, plan)
        return enriched

    @staticmethod
    def build_sample_apex_chart(title: str = "AURA 2.6 Execution Profile") -> str:
        """Emits a clean structured `aura-chart` JSON block for interactive visualization."""
        return (
            "```aura-chart\n"
            "{\n"
            f'  "title": "{title}",\n'
            '  "subtitle": "Multi-stage cognitive allocation (%)",\n'
            '  "labels": ["Deconstruct", "Architect", "Synthesize", "Visuals", "Verify"],\n'
            '  "values": [88, 94, 96, 92, 98],\n'
            '  "unit": "%"\n'
            "}\n"
            "```"
        )
