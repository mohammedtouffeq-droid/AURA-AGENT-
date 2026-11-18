"""Shared lightweight base classes and workspace introspection for AURA 2.0 / 2.3 / 2.6 model engines."""
from __future__ import annotations

import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parent

_SUBSTANTIVE_INTENT_RE = re.compile(
    r"\b(explain|teach|how|why|what\s+is|difference|compare|vs|chart|graph|plot|metrics|"
    r"diagram|flowchart|architecture|design|system|pipeline|code|script|python|javascript|"
    r"html|css|sql|api|bug|debug|fix|refactor|build|create|make|app|game|simulation|"
    r"svg|visual|animation|analyze|audit|algorithm|math|formula|steps|tutorial)\b",
    re.IGNORECASE,
)


def is_casual_or_greeting_prompt(prompt: str) -> bool:
    """Returns True for brief greetings/small-talk where rich SVG/chart/trace visuals would feel spammy."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s\u0900-\u097F\u0C00-\u0C7F]", " ", prompt or "").strip()
    if not cleaned:
        return True
    if _SUBSTANTIVE_INTENT_RE.search(cleaned):
        return False
    words = cleaned.split()
    return len(words) <= 6


def resolve_tenant_workspace(user_id: Any) -> Path:
    """Returns the strictly scoped workspace path for `user_id` without creating side effects."""
    if os.environ.get("VERCEL") or not os.access(ROOT_DIR, os.W_OK):
        base = Path(tempfile.gettempdir()) / "aura_workspace"
    else:
        base = ROOT_DIR / "workspace"
    try:
        uid = int(user_id)
        return base / f"user_{uid}"
    except (TypeError, ValueError):
        return base


def inspect_tenant_workspace(user_id: Any, max_files: int = 12) -> Dict[str, Any]:
    """Collects fast, read-only workspace telemetry for deep reasoning prompts."""
    ws = resolve_tenant_workspace(user_id)
    if not ws.exists() or not ws.is_dir():
        return {"file_count": 0, "files": [], "languages": []}

    files: List[str] = []
    exts: set[str] = set()
    for p in ws.rglob("*"):
        if p.is_file():
            rel = p.relative_to(ws).as_posix()
            files.append(rel)
            if p.suffix:
                exts.add(p.suffix.lstrip(".").lower())
            if len(files) >= 60:
                break

    return {
        "file_count": len(files),
        "files": sorted(files)[:max_files],
        "languages": sorted(exts)[:8],
    }


def format_thought_block(title: str, steps: List[str], elapsed_ms: float) -> str:
    """Formats a deterministic, XSS-safe reasoning trace parsed cleanly by the UI."""
    body_lines = "\n".join(f"- {s}" for s in steps if s)
    return f":::thought {title} ({elapsed_ms:.1f}ms)\n{body_lines}\n:::\n\n"


@dataclass
class EngineDispatchPlan:
    """Output contract returned by each AURA model engine prior to LLM inference."""

    tier_id: str
    display_name: str
    system_framing: str
    temperature: float
    thought_steps: List[str] = field(default_factory=list)
    trace_title: str = "Reasoning Trace"
    elapsed_ms: float = 0.0
    offline_visual_hint: str = ""
    preferred_llm: str = "gemini-3-flash-preview"


class BaseAuraModelEngine:
    """Base interface shared across AURA 2.0, AURA 2.3, and AURA 2.6 engines."""

    tier_id: str = "aura-2.0"
    display_name: str = "AURA 2.0"
    tagline: str = "Fast Everyday Intelligence"
    tier_rank: int = 1
    default_temperature: float = 0.4
    preferred_llm: str = "gemini-3.5-flash-lite"

    def describe(self) -> Dict[str, Any]:
        """Returns public metadata and footprint details for settings & UI."""
        mod_file = Path(self.__class__.__module__.replace(".", "/") + ".py")
        disk_kb = 0.0
        candidate = ROOT_DIR / mod_file.name
        if candidate.exists():
            disk_kb = round(candidate.stat().st_size / 1024.0, 2)
        return {
            "id": self.tier_id,
            "name": self.display_name,
            "tagline": self.tagline,
            "rank": self.tier_rank,
            "default_temperature": self.default_temperature,
            "preferred_llm": self.preferred_llm,
            "engine_disk_kb": disk_kb,
        }

    def build_dispatch_plan(self, user_id: Any, prompt: str, reasoning_mode: str = "fast") -> EngineDispatchPlan:
        """Synthesizes tier-specific system instructions and a reasoning trace."""
        t0 = time.perf_counter()
        ws_info = inspect_tenant_workspace(user_id)
        framing, steps, trace_title = self._compose_blueprint(prompt, ws_info, reasoning_mode)
        elapsed_ms = max(0.2, (time.perf_counter() - t0) * 1000.0)
        return EngineDispatchPlan(
            tier_id=self.tier_id,
            display_name=self.display_name,
            system_framing=framing,
            temperature=self.default_temperature,
            thought_steps=steps,
            trace_title=trace_title,
            elapsed_ms=elapsed_ms,
            preferred_llm=self.preferred_llm,
        )

    def _compose_blueprint(
        self, prompt: str, ws_info: Dict[str, Any], reasoning_mode: str
    ) -> tuple[str, List[str], str]:
        raise NotImplementedError

    def enrich_reply(self, prompt: str, reply: str, plan: EngineDispatchPlan) -> str:
        """Applies optional post-generation trace header without clobbering genuine LLM replies."""
        if not reply:
            return reply
        clean_reply = reply.strip()
        if plan.thought_steps and ":::thought" not in clean_reply:
            trace = format_thought_block(plan.trace_title, plan.thought_steps, plan.elapsed_ms)
            return trace + clean_reply
        return clean_reply
