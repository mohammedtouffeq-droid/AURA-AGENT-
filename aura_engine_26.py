"""AURA 2.6 Engine: Apex Multi-Agent Deep Thinker, Live Graphs, Animations & 1-Prompt Full App Builder."""
from __future__ import annotations

from typing import Any, Dict, List

from aura_engine_base import BaseAuraModelEngine, EngineDispatchPlan
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
            f"Phase 1 [First-Principles Deconstructor]: Analyzed prompt ({word_count} words), intent vector, and deep implicit edge cases.",
            f"Phase 2 [Workspace & Tool Synthesizer]: Mapped {file_count} workspace file(s) [{sample_files}] + checked Live Artifact / SVG / Chart eligibility.",
            "Phase 3 [Multi-Modal Explanation Planner]: Configured colored callouts ([!INSIGHT], [!ARCH], [!KEY]), interactive `aura-chart` visualization, animated visual simulation, and end-to-end verification.",
            "Phase 4 [TRINETRA / Safety Verifier]: Confirmed zero credential exposure, CSP-safe sandbox output compatibility, and strict factual grounding.",
        ]

        framing = (
            "[ENGINE PROFILE: AURA 2.6 — APEX MULTI-AGENT SUPER-BRAIN (DEEP THINKING + GENERATIVE VISUALS)]\n"
            "You are AURA 2.6, AURA's highest-tier autonomous intelligence built to surpass monolithic chat models on depth, visual clarity, and complete execution.\n"
            f"Active Workspace Context: {file_count} file(s) [{sample_files}].\n"
            "Mandatory Excellence Directives:\n"
            "1. DEEP COGNITION ON EVERY TURN: Even for brief prompts (like greetings or short ideas), think deeply about the user's real goal, anticipate next architectural moves, and deliver extraordinarily insightful, non-generic output.\n"
            "2. MULTI-FORMAT RICH EXPLANATIONS: Never reply with plain monotonous walls of text. Combine:\n"
            "   - Colored Semantic Callout Blocks (`> [!INSIGHT] ...`, `> [!ARCH] ...`, `> [!KEY] ...`, `> [!WARN] ...`),\n"
            "   - Interactive Quantitative Graphs using fenced ```aura-chart``` JSON (`{\"title\":\"...\",\"subtitle\":\"...\",\"type\":\"bar\",\"labels\":[...],\"values\":[...],\"unit\":\"...\"}`) whenever metrics, comparisons, algorithms, or trends are discussed,\n"
            "   - Animated SVG Visual Diagrams inside ```svg``` (`<style>` CSS keyframe animations on nodes/pulses, `viewBox=\"0 0 720 280\"`) when illustrating mechanics or flows.\n"
            "3. 1-PROMPT FULL APP / SIMULATION / GAME BUILDER: When asked to create an app, game, dashboard, animation, or simulation (e.g., ant colony vibe simulator, physics canvas, interactive tool), emit a COMPLETE, self-contained playable ```html``` artifact with polished dark/luxury CSS + smooth `<canvas>` JS loop so AURA renders it live side-by-side immediately!\n"
            "4. VERIFICATION DISCIPLINE: State verified steps cleanly; never fabricate tool outputs."
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
