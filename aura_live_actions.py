"""
===================================================================================
                   AURA LIVE ACTION VIEW — REAL-TIME TELEMETRY HUB
===================================================================================
Capability #3: Real-time visual action stream & cursor telemetry shared across:
- AURA Live Browser (navigate, click, type, scroll, tab ops, screenshot, vision)
- AURA Computer Use (mouse move/click, keyboard type/hotkey, app launch, UI tree,
  screen capture, CV analysis, Human-in-the-Loop Start/Pause/Stop/Take Control)

All action logs and cursor streams are strictly tenant-isolated per `user_id`.
===================================================================================
"""

from __future__ import annotations

import base64
import io
import threading
import time
from typing import Any, Dict, List, Optional


def _make_compact_thumbnail_b64(raw_b64: str, max_w: int = 340, quality: int = 62) -> str:
    """Compresses a full viewport JPEG frame into a fast ~6KB thumbnail for Live Action View."""
    s = str(raw_b64 or "").strip()
    if not s:
        return ""
    if len(s) <= 18_000:
        return s
    try:
        from PIL import Image

        raw = base64.b64decode(s)
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = img.size
        if w > max_w:
            nh = max(90, int(round(h * (max_w / float(w)))))
            img = img.resize((max_w, nh))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality)
        return base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        return s if len(s) <= 85_000 else ""


class LiveActionHub:
    """Thread-safe per-user action stream for AURA Live Action View."""

    MAX_EVENTS_PER_USER = 120
    MAX_THUMBNAILS_PER_USER = 18

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._seq: Dict[str, int] = {}
        self._events: Dict[str, List[Dict[str, Any]]] = {}
        self._cursors: Dict[str, Dict[str, Dict[str, Any]]] = {}

    @staticmethod
    def _uid(user_id: Any) -> str:
        return str(user_id if user_id is not None else "guest")

    def record(
        self,
        user_id: Any,
        source: str,
        action: str,
        summary: str,
        *,
        target: str = "",
        coords: Optional[Dict[str, Any]] = None,
        status: str = "completed",
        duration_ms: int = 0,
        detail: str = "",
        thumbnail_b64: str = "",
        tab_id: str = "",
        window_title: str = "",
        engine: str = "",
    ) -> Dict[str, Any]:
        uid = self._uid(user_id)
        now = time.time()
        clean_source = str(source or "browser").strip().lower()
        allowed_sources = ("orchestrator", "verify", "browser", "computer", "terminal", "files", "vision", "system")
        if clean_source not in allowed_sources:
            clean_source = "system"

        clean_coords: Optional[Dict[str, int]] = None
        if isinstance(coords, dict) and coords.get("x") is not None and coords.get("y") is not None:
            try:
                clean_coords = {"x": int(round(float(coords["x"]))), "y": int(round(float(coords["y"])))}
            except (TypeError, ValueError):
                clean_coords = None

        with self._lock:
            next_id = self._seq.get(uid, 0) + 1
            self._seq[uid] = next_id
            event: Dict[str, Any] = {
                "id": next_id,
                "source": clean_source,
                "action": str(action or "step")[:48],
                "summary": str(summary or "")[:240],
                "target": str(target or "")[:240],
                "coords": clean_coords,
                "status": str(status or "completed")[:24],
                "duration_ms": max(0, int(duration_ms or 0)),
                "detail": str(detail or "")[:420],
                "tab_id": str(tab_id or "")[:32],
                "window_title": str(window_title or "")[:120],
                "engine": str(engine or "")[:40],
                "timestamp": now,
                "time_label": time.strftime("%H:%M:%S", time.localtime(now)),
                "thumbnail_b64": _make_compact_thumbnail_b64(thumbnail_b64),
            }
            bucket = self._events.setdefault(uid, [])
            bucket.append(event)
            if len(bucket) > self.MAX_EVENTS_PER_USER:
                del bucket[:-self.MAX_EVENTS_PER_USER]

            # Trim older thumbnails to keep payloads snappy
            thumb_count = 0
            for ev in reversed(bucket):
                if ev.get("thumbnail_b64"):
                    thumb_count += 1
                    if thumb_count > self.MAX_THUMBNAILS_PER_USER:
                        ev["thumbnail_b64"] = ""

            if clean_coords is not None:
                user_cursors = self._cursors.setdefault(uid, {})
                cursor_bucket = "computer" if clean_source == "computer" else "browser"
                user_cursors[cursor_bucket] = {
                    "x": clean_coords["x"],
                    "y": clean_coords["y"],
                    "action": event["action"],
                    "label": event["summary"][:64],
                    "timestamp": now,
                    "event_id": next_id,
                }
            return dict(event)

    def get_feed(
        self,
        user_id: Any,
        source: str = "all",
        limit: int = 50,
        since_id: int = 0,
        include_thumbnails: bool = True,
    ) -> Dict[str, Any]:
        uid = self._uid(user_id)
        clean_source = str(source or "all").strip().lower()
        safe_limit = max(1, min(120, int(limit or 50)))
        safe_since = max(0, int(since_id or 0))

        with self._lock:
            all_events = list(self._events.get(uid, []))
            cursors = {k: dict(v) for k, v in self._cursors.get(uid, {}).items()}
            latest_id = self._seq.get(uid, 0)

        stats = {
            "total": len(all_events),
            "orchestrator": sum(1 for e in all_events if e["source"] == "orchestrator"),
            "verify": sum(1 for e in all_events if e["source"] == "verify"),
            "browser": sum(1 for e in all_events if e["source"] == "browser"),
            "computer": sum(1 for e in all_events if e["source"] == "computer"),
            "terminal": sum(1 for e in all_events if e["source"] == "terminal"),
            "files": sum(1 for e in all_events if e["source"] == "files"),
            "vision": sum(1 for e in all_events if e["source"] == "vision"),
            "failed": sum(1 for e in all_events if e["status"] in ("error", "blocked", "stopped")),
        }

        filtered = [
            e
            for e in all_events
            if e["id"] > safe_since and (clean_source == "all" or e["source"] == clean_source)
        ]
        sliced = filtered[-safe_limit:]
        if not include_thumbnails:
            sliced = [{**e, "thumbnail_b64": ""} for e in sliced]
        else:
            sliced = [dict(e) for e in sliced]

        return {
            "success": True,
            "actions": list(reversed(sliced)),  # newest first for live stream UI
            "stats": stats,
            "cursors": cursors,
            "latest_id": latest_id,
        }

    def clear(self, user_id: Any) -> Dict[str, Any]:
        uid = self._uid(user_id)
        with self._lock:
            self._events[uid] = []
            self._cursors[uid] = {}
        return {"success": True, "cleared": True}


LIVE_ACTION_HUB = LiveActionHub()
