"""AURA 2.0 Engine: Fast Everyday Storyteller, Study Mentor & Clean Concept Explainer."""
from __future__ import annotations

from typing import Any, Dict, List

from aura_engine_base import BaseAuraModelEngine, EngineDispatchPlan, is_casual_or_greeting_prompt


class Aura20StudyEngine(BaseAuraModelEngine):
    """Lightweight fast tutor blending conversational clarity with sleek editorial concept visuals."""

    tier_id = "aura-2.0"
    display_name = "AURA 2.0"
    tagline = "Fast Explanations & Everyday Clarity"
    tier_rank = 1
    default_temperature = 0.55
    preferred_llm = "gemini-3-flash-preview"

    def _compose_blueprint(
        self, prompt: str, ws_info: Dict[str, Any], reasoning_mode: str
    ) -> tuple[str, List[str], str]:
        casual = is_casual_or_greeting_prompt(prompt)
        casual_rule = (
            "- CASUAL TURN MODE: Reply warmly, naturally, and concisely in 1-3 plain sentences. Never inject diagrams or filler boxes.\n"
            if casual
            else ""
        )
        framing = (
            "[ENGINE PROFILE: AURA 2.0 — STORYTELLER & STUDY MENTOR]\n"
            "You are AURA 2.0: crystal-clear, fast, and unforgettable.\n"
            f"{casual_rule}"
            "- Lead with a sharp 1-sentence core intuition, then a vivid real-world analogy and clean bullet breakdown.\n"
            "- For coding/CS/STEM questions, include a crisp minimal code/example and one quick 'Mastery Check' question.\n"
            "- If the user asks to visualize, diagram, or draw a concept/flow, output a clean inline ```svg``` diagram; otherwise keep replies tight and zero-fluff.\n"
            "[/ENGINE PROFILE]"
        )
        steps: List[str] = []
        return framing, steps, "AURA 2.0 Fast Pass"

    @staticmethod
    def build_cartoon_study_svg(topic: str) -> str:
        """Builds a sleek editorial obsidian SVG concept blueprint card when illustrating study prompts offline."""
        safe_topic = (topic or "Concept Breakdown").replace("<", "").replace(">", "").replace("&", "and")[:46]
        return (
            "```svg\n"
            "<svg viewBox=\"0 0 640 230\" xmlns=\"http://www.w3.org/2000/svg\">\n"
            "  <defs>\n"
            "    <linearGradient id=\"auraCardBg\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"1\">\n"
            "      <stop offset=\"0%\" stop-color=\"#0b0d14\"/>\n"
            "      <stop offset=\"100%\" stop-color=\"#131722\"/>\n"
            "    </linearGradient>\n"
            "    <linearGradient id=\"auraAccent\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"0\">\n"
            "      <stop offset=\"0%\" stop-color=\"#e4e4e7\"/>\n"
            "      <stop offset=\"100%\" stop-color=\"#93c5fd\"/>\n"
            "    </linearGradient>\n"
            "  </defs>\n"
            "  <rect width=\"640\" height=\"230\" rx=\"16\" fill=\"url(#auraCardBg)\" stroke=\"rgba(255,255,255,0.12)\" stroke-width=\"1.2\"/>\n"
            "  <g transform=\"translate(34,36)\">\n"
            "    <polygon points=\"32,2 58,17 58,47 32,62 6,47 6,17\" fill=\"rgba(255,255,255,0.04)\" stroke=\"url(#auraAccent)\" stroke-width=\"1.6\"/>\n"
            "    <circle cx=\"32\" cy=\"32\" r=\"9\" fill=\"none\" stroke=\"#e4e4e7\" stroke-width=\"1.6\"/>\n"
            "  </g>\n"
            "  <text x=\"112\" y=\"56\" fill=\"#94a3b8\" font-size=\"11\" font-weight=\"600\" letter-spacing=\"1.6\" font-family=\"Inter,sans-serif\">AURA 2.0 STUDY CARD</text>\n"
            f"  <text x=\"112\" y=\"84\" fill=\"#f8fafc\" font-size=\"20\" font-weight=\"700\" font-family=\"Inter,sans-serif\">{safe_topic}</text>\n"
            "  <line x1=\"34\" y1=\"108\" x2=\"606\" y2=\"108\" stroke=\"rgba(255,255,255,0.08)\" stroke-width=\"1\"/>\n"
            "  <rect x=\"34\" y=\"126\" width=\"176\" height=\"72\" rx=\"10\" fill=\"rgba(255,255,255,0.03)\" stroke=\"rgba(255,255,255,0.12)\"/>\n"
            "  <text x=\"50\" y=\"150\" fill=\"#93c5fd\" font-size=\"10.5\" font-weight=\"600\" font-family=\"monospace\">01 / INTUITION</text>\n"
            "  <text x=\"50\" y=\"174\" fill=\"#e4e4e7\" font-size=\"13\" font-weight=\"600\" font-family=\"Inter,sans-serif\">Core Mental Model</text>\n"
            "  <rect x=\"232\" y=\"126\" width=\"176\" height=\"72\" rx=\"10\" fill=\"rgba(255,255,255,0.03)\" stroke=\"rgba(255,255,255,0.12)\"/>\n"
            "  <text x=\"248\" y=\"150\" fill=\"#6ee7b7\" font-size=\"10.5\" font-weight=\"600\" font-family=\"monospace\">02 / MECHANICS</text>\n"
            "  <text x=\"248\" y=\"174\" fill=\"#e4e4e7\" font-size=\"13\" font-weight=\"600\" font-family=\"Inter,sans-serif\">Worked Example</text>\n"
            "  <rect x=\"430\" y=\"126\" width=\"176\" height=\"72\" rx=\"10\" fill=\"rgba(255,255,255,0.03)\" stroke=\"rgba(255,255,255,0.12)\"/>\n"
            "  <text x=\"446\" y=\"150\" fill=\"#c4b5fd\" font-size=\"10.5\" font-weight=\"600\" font-family=\"monospace\">03 / MASTERY</text>\n"
            "  <text x=\"446\" y=\"174\" fill=\"#e4e4e7\" font-size=\"13\" font-weight=\"600\" font-family=\"Inter,sans-serif\">Practice &amp; Trade-offs</text>\n"
            "</svg>\n"
            "```"
        )
