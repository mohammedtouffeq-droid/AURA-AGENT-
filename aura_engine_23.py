"""AURA 2.3 Engine: Deep Coding Architect, AST Inspector & Visual Engineering Studio."""
from __future__ import annotations

from typing import Any, Dict, List

from aura_engine_base import BaseAuraModelEngine, EngineDispatchPlan, is_casual_or_greeting_prompt


class Aura23ArchitectEngine(BaseAuraModelEngine):
    """Deep engineering studio outperforming standard assistants on architecture, AST diffs, and visual blueprints."""

    tier_id = "aura-2.3"
    display_name = "AURA 2.3"
    tagline = "Engineering, Code & Systems Architect"
    tier_rank = 2
    default_temperature = 0.2
    preferred_llm = "gemini-3-flash-preview"

    def _compose_blueprint(
        self, prompt: str, ws_info: Dict[str, Any], reasoning_mode: str
    ) -> tuple[str, List[str], str]:
        p_clean = (prompt or "").strip()
        word_count = len(p_clean.split())
        file_count = ws_info.get("file_count", 0)
        langs = ", ".join(ws_info.get("languages") or []) or "multi-stack"
        sample_files = ", ".join((ws_info.get("files") or [])[:5]) or "clean workspace"

        steps = [
            f"Context Scan: parsed {word_count} token-words; reasoning={reasoning_mode}; workspace={file_count} files ({langs}).",
            f"Codebase Anchor: checked [{sample_files}] interfaces & dependency boundaries.",
            "Engineering Delivery: prioritized production code correctness and edge-case safety.",
        ]

        casual_rule = (
            "- CASUAL TURN MODE: This is a brief conversational message. Reply naturally and concisely in 1-2 plain sentences asking what they want to build or debug. "
            "Strictly NO charts, NO SVGs, NO callouts, NO boilerplate plans on greetings.\n"
            if is_casual_or_greeting_prompt(prompt)
            else ""
        )

        framing = (
            "[ENGINE PROFILE: AURA 2.3 — DEEP ARCHITECT & CODING STUDIO]\n"
            "You are AURA 2.3, a Principal Staff Engineer delivering battle-tested code and systems architecture.\n"
            f"Workspace: {file_count} file(s) ({sample_files}).\n"
            f"{casual_rule}"
            "- Code Excellence: Deliver complete, runnable, typed, edge-case-safe code (no placeholders or `TODO` stubs), stating exact Time/Space Big-O complexity and a runnable `assert`/test verification block.\n"
            "- LIVE WEB APP STUDIO: When building any web app, calculator, game, timer, dashboard, or UI component (unless editing multi-file repo code), ALWAYS emit one complete self-contained runnable ```html``` block (inline `<style>` + `<script>`) so Live Render Studio opens immediately.\n"
            "- Structure technical solutions crisply (`## Architecture`, `## Implementation`, `## Complexity & Edge Cases`, `## Verification`). Zero filler fluff or unsolicited charts.\n"
            "[/ENGINE PROFILE]"
        )
        return framing, steps, "AURA 2.3 Engineering Trace"
