"""AURA 2.6 Engine: Apex Multi-Agent Deep Thinker, Live Graphs, Animations & 1-Prompt Full App Builder."""
from __future__ import annotations

from typing import Any, Dict, List

from aura_engine_base import BaseAuraModelEngine, EngineDispatchPlan, is_casual_or_greeting_prompt
from aura_jarvis_hub import JARVIS_HUB


class Aura26ApexEngine(BaseAuraModelEngine):
    """Apex GPT-6 / Astra tier multi-agent engine with deep traces, animated SVG/HTML, and live charts."""

    tier_id = "aura-2.6"
    display_name = "AURA 2.6"
    tagline = "Autonomous Multi-Agent Company"
    tier_rank = 3
    default_temperature = 0.25
    preferred_llm = "gemini-3-flash-preview"

    def _compose_blueprint(
        self, prompt: str, ws_info: Dict[str, Any], reasoning_mode: str
    ) -> tuple[str, List[str], str]:
        p_clean = (prompt or "").strip()
        word_count = len(p_clean.split())
        file_count = ws_info.get("file_count", 0)
        sample_files = ", ".join((ws_info.get("files") or [])[:6]) or "fresh canvas"

        steps = [
            f"Phase 1 [Strategist / CEO]: Decomposed objective ({word_count} words) into deliverables & constraints.",
            f"Phase 2 [Engineering & Ops]: Evaluated {file_count} workspace file(s) [{sample_files}] and multi-step execution plan.",
            "Phase 3 [Analyst / Growth]: Prepared real data comparisons, tables, or `aura-chart` analytics if quantitative metrics apply.",
            "Phase 4 [QA & Security Auditor]: Verified edge cases, grounded facts, and zero fabricated telemetry.",
        ]

        casual_rule = (
            "0. CASUAL TURN MODE: The user sent a short greeting or casual message. Respond directly and cleanly in 1-2 sentences — "
            "strictly NO charts, NO SVGs, NO callout boxes, NO fake diagnostics on greetings.\n"
            if is_casual_or_greeting_prompt(prompt)
            else ""
        )

        framing = (
            "[ENGINE PROFILE: AURA 2.6 — APEX MULTI-AGENT SUPER-BRAIN (AUTONOMOUS COMPANY)]\n"
            "You are AURA 2.6, operating like an autonomous end-to-end engineering, research, and product company (Strategist + Principal Engineer + Security/QA Auditor).\n"
            f"Active Workspace Context: {file_count} file(s) [{sample_files}].\n"
            "Execution & Quality Directives:\n"
            f"{casual_rule}"
            "1. AUTONOMOUS END-TO-END OWNERSHIP: Break ambitious goals down cleanly and deliver complete, production-ready execution (full HTML5 apps, backend APIs, launch roadmaps, cybersecurity audits, or structured research briefs) — execute workspace tools directly when the task modifies files.\n"
            "2. DATA & CHARTS ONLY WHEN REAL: Emit structured ```aura-chart``` JSON (`{\"title\":\"...\",\"subtitle\":\"...\",\"type\":\"bar\",\"labels\":[...],\"values\":[...],\"unit\":\"...\"}`) at column 0 ONLY when real numbers, benchmarks, or quantitative comparisons belong in the answer — NEVER invent self-praising filler charts.\n"
            "3. ZERO CARTOON SPAM: Never decorate normal answers with unsolicited SVGs or loud callouts. Use clean `html` artifacts when building real interactive tools/games/dashboards.\n"
            "4. STRICT FORMATTING: Never prefix ```html``` or ```aura-chart``` blocks with `>` blockquote markers."
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
