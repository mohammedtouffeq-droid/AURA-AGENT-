"""Unified AURA Model Router coordinating AURA 2.0, AURA 2.3, and AURA 2.6 engines."""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from aura_engine_base import BaseAuraModelEngine, EngineDispatchPlan
from aura_engine_20 import Aura20StudyEngine
from aura_engine_23 import Aura23ArchitectEngine
from aura_engine_26 import Aura26ApexEngine


DEFAULT_AURA_TIER = "aura-2.3"


class AuraModelRouter:
    """Thread-safe registry & dispatcher mapping user selections to AURA 2.0 / 2.3 / 2.6."""

    def __init__(self) -> None:
        self._engines: Dict[str, BaseAuraModelEngine] = {
            "aura-2.0": Aura20StudyEngine(),
            "aura-2.3": Aura23ArchitectEngine(),
            "aura-2.6": Aura26ApexEngine(),
        }
        self._lock = threading.Lock()
        self._user_tiers: Dict[str, str] = {}

    def normalize_tier(self, raw_tier: Any) -> Optional[str]:
        if not isinstance(raw_tier, str):
            return None
        key = raw_tier.strip().lower().replace("_", "-").replace(" ", "-")
        aliases = {
            "2.0": "aura-2.0",
            "aura2.0": "aura-2.0",
            "aura-2.0": "aura-2.0",
            "2.3": "aura-2.3",
            "aura2.3": "aura-2.3",
            "aura-2.3": "aura-2.3",
            "2.6": "aura-2.6",
            "aura2.6": "aura-2.6",
            "aura-2.6": "aura-2.6",
        }
        return aliases.get(key)

    def get_engine(self, tier: Optional[str]) -> BaseAuraModelEngine:
        norm = self.normalize_tier(tier) or DEFAULT_AURA_TIER
        return self._engines[norm]

    def set_user_tier(self, user_id: Any, tier: str) -> str:
        norm = self.normalize_tier(tier) or DEFAULT_AURA_TIER
        with self._lock:
            self._user_tiers[str(user_id)] = norm
        return norm

    def get_user_tier(self, user_id: Any) -> str:
        with self._lock:
            return self._user_tiers.get(str(user_id), DEFAULT_AURA_TIER)

    def list_catalog(self) -> List[Dict[str, Any]]:
        """Returns ordered descriptors and real disk sizes for all AURA flagship engines."""
        ordered = [self._engines[k].describe() for k in ("aura-2.0", "aura-2.3", "aura-2.6")]
        total_kb = round(sum(item.get("engine_disk_kb", 0.0) for item in ordered), 2)
        for item in ordered:
            item["total_engines_kb"] = total_kb
        return ordered

    def prepare_turn(
        self,
        user_id: Any,
        tier: Optional[str],
        prompt: str,
        reasoning_mode: str = "fast",
    ) -> EngineDispatchPlan:
        engine = self.get_engine(tier)
        if tier:
            self.set_user_tier(user_id, engine.tier_id)
        return engine.build_dispatch_plan(user_id, prompt, reasoning_mode=reasoning_mode)

    def postprocess_reply(self, tier: Optional[str], prompt: str, reply: str, plan: EngineDispatchPlan) -> str:
        engine = self.get_engine(tier)
        return engine.enrich_reply(prompt, reply, plan)


AURA_MODEL_ROUTER = AuraModelRouter()
