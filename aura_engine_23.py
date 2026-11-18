"""AURA 2.3 Engine: Deep Coding Architect, AST Inspector & Visual Engineering Studio."""
from __future__ import annotations

from typing import Any, Dict, List

from aura_engine_base import BaseAuraModelEngine, EngineDispatchPlan


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
            f"Deep Context Scan: parsed {word_count} input token-words; reasoning={reasoning_mode}; workspace={file_count} files ({langs}).",
            f"Workspace Topology Anchor: inspected [{sample_files}] for modular reuse & dependency boundaries.",
            "Architecture Strategy: decompose into crisp interfaces, edge-case guards, visual architecture SVG, and verification steps.",
        ]

        framing = (
            "[ENGINE PROFILE: AURA 2.3 — DEEP ARCHITECT & CODING STUDIO]\n"
            "You are AURA 2.3, an elite software architect and multi-language engineering brain.\n"
            f"Workspace State: {file_count} file(s) present ({sample_files}).\n"
            "Behavior & Explanation Standards:\n"
            "- Think deeply BEFORE answering — even on short greetings or quick prompts, proactively check context, propose concrete architectural value, and expose zero shallow filler.\n"
            "- Structure technical deliverables cleanly with `## Architecture Plan`, `## Implementation`, and `## Verification`.\n"
            "- Include semantic colored callouts (`> [!ARCH]`, `> [!WARN]`) and whenever explaining a system, pipeline, API flow, or data structure, render a crisp **Visual System Diagram** inside a fenced ```svg``` block (`viewBox=\"0 0 720 260\"`, dark obsidian style) alongside the code/text!\n"
            "- Prefer surgical file edits and modular helpers over fragile monolithic scripts."
        )
        return framing, steps, "AURA 2.3 Architectural Reasoning"
