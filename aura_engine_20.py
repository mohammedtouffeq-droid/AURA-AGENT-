"""AURA 2.0 Engine: Cartoon-Vibe Study Mentor & Fast Everyday Visual Storyteller."""
from __future__ import annotations

from typing import Any, Dict, List

from aura_engine_base import BaseAuraModelEngine, EngineDispatchPlan


class Aura20StudyEngine(BaseAuraModelEngine):
    """Lightweight fast tutor blending conversational clarity with cartoon-style SVG concept visuals."""

    tier_id = "aura-2.0"
    display_name = "AURA 2.0"
    tagline = "Fast Study & Cartoon Visuals"
    tier_rank = 1
    default_temperature = 0.55

    def _compose_blueprint(
        self, prompt: str, ws_info: Dict[str, Any], reasoning_mode: str
    ) -> tuple[str, List[str], str]:
        framing = (
            "[ENGINE PROFILE: AURA 2.0 — STORYTELLER & STUDY MENTOR]\n"
            "You are AURA 2.0, engineered for fast everyday intelligence, student mastery, and crystal-clear visual intuition.\n"
            "Formatting & Visual Rules:\n"
            "- Explain concepts simply using relatable real-world analogies, crisp bullet highlights, and friendly mentor energy.\n"
            "- Use semantic callout lines where helpful (e.g. `> [!TIP] Quick Memory Trick` or `> [!KEY] Core Rule`).\n"
            "- When explaining a study concept, process, algorithm, or visual topic, include a clean, playful cartoon-style inline ```svg``` illustration "
            "(rounded shapes, expressive friendly character/mascot bubble, colorful clear diagram boxes, viewBox=\"0 0 640 240\") so learners visualize it immediately!\n"
            "- Keep answers focused, accurate, and punchy."
        )
        # Keep AURA 2.0 trace zero-clutter on fast study chats
        steps: List[str] = []
        return framing, steps, "AURA 2.0 Study Pass"

    @staticmethod
    def build_cartoon_study_svg(topic: str) -> str:
        """Builds a clean cartoon-vibe SVG concept card when illustrating study prompts offline."""
        safe_topic = (topic or "Concept Breakdown").replace("<", "").replace(">", "").replace("&", "and")[:46]
        return (
            "```svg\n"
            "<svg viewBox=\"0 0 640 230\" xmlns=\"http://www.w3.org/2000/svg\">\n"
            "  <rect width=\"640\" height=\"230\" rx=\"18\" fill=\"#0f1320\" stroke=\"#e2b96f\" stroke-width=\"2\"/>\n"
            "  <circle cx=\"95\" cy=\"125\" r=\"46\" fill=\"#1d2b4f\" stroke=\"#38bdf8\" stroke-width=\"3\"/>\n"
            "  <circle cx=\"80\" cy=\"115\" r=\"6\" fill=\"#ffffff\"/><circle cx=\"110\" cy=\"115\" r=\"6\" fill=\"#ffffff\"/>\n"
            "  <path d=\"M78 138 Q95 152 112 138\" stroke=\"#e2b96f\" stroke-width=\"3.5\" fill=\"none\" stroke-linecap=\"round\"/>\n"
            "  <rect x=\"165\" y=\"32\" width=\"445\" height=\"166\" rx=\"16\" fill=\"#161b2e\" stroke=\"#334155\" stroke-width=\"1.5\"/>\n"
            "  <text x=\"188\" y=\"64\" fill=\"#e2b96f\" font-size=\"13\" font-weight=\"700\" font-family=\"sans-serif\">AURA 2.0 STUDY CARD</text>\n"
            f"  <text x=\"188\" y=\"96\" fill=\"#f8fafc\" font-size=\"18\" font-weight=\"700\" font-family=\"sans-serif\">{safe_topic}</text>\n"
            "  <rect x=\"188\" y=\"116\" width=\"122\" height=\"58\" rx=\"10\" fill=\"#1e293b\" stroke=\"#38bdf8\"/><text x=\"249\" y=\"149\" text-anchor=\"middle\" fill=\"#bae6fd\" font-size=\"12\" font-family=\"sans-serif\">1. Intuition</text>\n"
            "  <rect x=\"326\" y=\"116\" width=\"122\" height=\"58\" rx=\"10\" fill=\"#1e293b\" stroke=\"#10b981\"/><text x=\"387\" y=\"149\" text-anchor=\"middle\" fill=\"#a7f3d0\" font-size=\"12\" font-family=\"sans-serif\">2. Example</text>\n"
            "  <rect x=\"464\" y=\"116\" width=\"124\" height=\"58\" rx=\"10\" fill=\"#1e293b\" stroke=\"#a855f7\"/><text x=\"526\" y=\"149\" text-anchor=\"middle\" fill=\"#e9d5ff\" font-size=\"12\" font-family=\"sans-serif\">3. Mastery</text>\n"
            "</svg>\n"
            "```"
        )
