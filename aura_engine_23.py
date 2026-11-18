"""AURA 2.3 Engine: Deep Coding Architect, AST Inspector & Visual Engineering Studio."""
from __future__ import annotations

from typing import Any, Dict, List

from aura_engine_base import BaseAuraModelEngine, EngineDispatchPlan, is_casual_or_greeting_prompt


class Aura23ArchitectEngine(BaseAuraModelEngine):
    """Deep engineering studio outperforming standard assistants on architecture, AST diffs, and visual blueprints."""

    tier_id = "aura-2.3"
    display_name = "AURA 2.3"
    tagline = "Architect & Deep Coding Studio"
    tier_rank = 2
    default_temperature = 0.2

    def _compose_blueprint(
        self, prompt: str, ws_info: Dict[str, Any], reasoning_mode: str
    ) -> tuple[str, List[str], str]:
        p_clean = (prompt or "").strip()
        word_count = len(p_clean.split())
        file_count = ws_info.get("file_count", 0)
        langs = ", ".join(ws_info.get("languages") or []) or "multi-stack"
        sample_files = ", ".join((ws_info.get("files") or [])[:5]) or "clean workspace"

        steps = [
            f"Deep Context Scan: parsed {word_count} token-words; reasoning={reasoning_mode}; workspace={file_count} files ({langs}).",
            f"Workspace Topology Anchor: inspected [{sample_files}] for modular interfaces & dependency boundaries.",
            "Engineering Strategy: deliver verified technical architecture and omit decorative fluff.",
        ]

        casual_rule = (
            "- CASUAL TURN MODE: This is a short conversational greeting. Reply sharply and naturally in plain prose (1-2 sentences) asking what engineering or debugging task is next. "
            "Do NOT output SVGs, fake Studio Telemetry charts, callout banners, or empty Architecture Plans.\n"
            if is_casual_or_greeting_prompt(prompt)
            else ""
        )

        framing = (
            "[ENGINE PROFILE: AURA 2.3 — DEEP ARCHITECT & CODING STUDIO]\n"
            "You are AURA 2.3, an elite software architect and multi-language engineering brain.\n"
            f"Workspace State: {file_count} file(s) present ({sample_files}).\n"
            "Behavior & Formatting Standards:\n"
            f"{casual_rule}"
            "- Deliver senior-engineer precision: zero self-promotional telemetry, zero fabricated benchmark numbers.\n"
            "- Structure substantial technical deliverables cleanly with `## Architecture Plan`, `## Implementation`, and `## Verification`.\n"
            "- ONLY when designing a multi-component system, API flow, or data pipeline, emit ONE crisp top-level ```svg``` system diagram (column 0, NEVER prefixed with `> ` blockquote markers!, `viewBox=\"0 0 720 260\"`).\n"
            "- Prefer surgical, modular code over boilerplate."
        )
        return framing, steps, "AURA 2.3 Architectural Reasoning"
