"""
===================================================================================
      AURA AUTOMATIC DEVICE INTELLIGENCE & CAPABILITY MATRIX
===================================================================================
Identifies the exact device, operating system, form factor, and runtime environment
behind every user message (Phone / Tablet / iPad / MacBook / Laptop / Desktop)
without cluttering the UI.

Allows AURA Core & JARVIS to adapt automatically:
- Mobile Phone (iOS / Android): Smooth conversational chat, voice, full Cloud Coder
  (files, AST refactor, bug scan, git commit/push, isolated terminal), Cloud Browser
  automation, and 1-click Remote Companion (/remote) to control their Desktop/Laptop.
- Tablet (iPadOS / Android Tablet): Split Coder Studio + Cloud Browser + Remote Bridge.
- Laptop / Desktop (Windows / macOS / Linux): Full autonomous stack — Coder Studio,
  Git/GitHub workflows, Live Embedded Browser control, Multi-Agent Swarm, JARVIS,
  and full OS/Desktop Computer-Use automation when running on local host.
===================================================================================
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Mapping, Optional


def _clean_str(val: Any, limit: int = 120) -> str:
    return str(val or "").strip()[:limit]


def detect_client_device(
    headers: Optional[Mapping[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Builds a normalized device & capability profile from client telemetry + User-Agent."""
    hdrs = headers or {}
    payload = body if isinstance(body, dict) else {}

    # 1. Extract optional rich client telemetry from body (`client_device`) or `X-AURA-Device` header
    client_info: Dict[str, Any] = {}
    if isinstance(payload.get("client_device"), dict):
        client_info = dict(payload["client_device"])
    else:
        raw_hdr = hdrs.get("X-AURA-Device") or hdrs.get("x-aura-device") or ""
        if isinstance(raw_hdr, str) and raw_hdr.strip().startswith("{"):
            try:
                parsed = json.loads(raw_hdr[:1024])
                if isinstance(parsed, dict):
                    client_info = parsed
            except Exception:
                client_info = {}

    ua = _clean_str(
        client_info.get("user_agent")
        or hdrs.get("User-Agent")
        or hdrs.get("user-agent")
        or "",
        300,
    )
    ua_low = ua.lower()
    platform_raw = _clean_str(client_info.get("platform"), 80).lower()
    hint_class = _clean_str(client_info.get("device_class"), 32).lower()

    try:
        vw = int(client_info.get("viewport_w") or client_info.get("screen_w") or 0)
        vh = int(client_info.get("viewport_h") or client_info.get("screen_h") or 0)
    except (ValueError, TypeError):
        vw, vh = 0, 0
    try:
        max_touch = int(client_info.get("max_touch_points") or 0)
    except (ValueError, TypeError):
        max_touch = 0
    has_battery_laptop_hint = bool(client_info.get("likely_laptop"))
    is_pwa = bool(client_info.get("standalone"))

    # 2. Detect OS accurately (including iPadOS masquerading as MacIntel + touch points)
    os_name = "Unknown"
    if "iphone" in ua_low or "ipod" in ua_low:
        os_name = "iOS"
    elif "ipad" in ua_low or ("mac" in ua_low and max_touch >= 2) or ("macintel" in platform_raw and max_touch >= 2):
        os_name = "iPadOS"
    elif "android" in ua_low:
        os_name = "Android"
    elif "windows" in ua_low or "win32" in platform_raw or "win64" in platform_raw:
        os_name = "Windows"
    elif "macintosh" in ua_low or "mac os" in ua_low or "mac" in platform_raw:
        os_name = "macOS"
    elif "cros" in ua_low:
        os_name = "ChromeOS"
    elif "linux" in ua_low or "x11" in ua_low or "linux" in platform_raw:
        os_name = "Linux"

    # 3. Classify device form factor: mobile | tablet | laptop | desktop
    if hint_class in ("mobile", "tablet", "laptop", "desktop"):
        device_class = hint_class
    elif os_name == "iOS":
        device_class = "mobile"
    elif os_name == "iPadOS":
        device_class = "tablet"
    elif os_name == "Android":
        if "mobile" in ua_low or (vw > 0 and vw < 680):
            device_class = "mobile"
        else:
            device_class = "tablet"
    elif re.search(r"\b(mobile|phone|blackberry|opera mini|iemobile)\b", ua_low):
        device_class = "mobile"
    elif re.search(r"\b(tablet|kindle|silk|playbook)\b", ua_low):
        device_class = "tablet"
    elif os_name == "ChromeOS":
        device_class = "laptop"
    elif os_name == "macOS":
        # MacBooks typically report <= 1728px logical viewport or laptop hint; larger external monitors -> desktop
        if has_battery_laptop_hint or (0 < vw <= 1728):
            device_class = "laptop"
        else:
            device_class = "desktop"
    elif os_name in ("Windows", "Linux"):
        if has_battery_laptop_hint or (0 < vw <= 1600):
            device_class = "laptop"
        else:
            device_class = "desktop"
    else:
        if 0 < vw < 680:
            device_class = "mobile"
        elif 680 <= vw <= 1024 and max_touch >= 1:
            device_class = "tablet"
        else:
            device_class = "desktop"

    # 4. Human-friendly form factor label
    if device_class == "mobile":
        if os_name == "iOS":
            device_label = "iPhone (iOS Mobile)"
        elif os_name == "Android":
            device_label = "Android Phone"
        else:
            device_label = f"Mobile Phone ({os_name})"
    elif device_class == "tablet":
        if os_name == "iPadOS":
            device_label = "iPad (iPadOS Tablet)"
        elif os_name == "Android":
            device_label = "Android Tablet"
        else:
            device_label = f"Tablet ({os_name})"
    elif device_class == "laptop":
        if os_name == "macOS":
            device_label = "MacBook / macOS Laptop"
        elif os_name == "Windows":
            device_label = "Windows Laptop"
        elif os_name == "ChromeOS":
            device_label = "Chromebook Laptop"
        else:
            device_label = f"{os_name} Laptop"
    else:
        if os_name == "macOS":
            device_label = "Mac Desktop (macOS)"
        elif os_name == "Windows":
            device_label = "Windows Desktop"
        elif os_name == "Linux":
            device_label = "Linux Desktop Workstation"
        else:
            device_label = "Desktop Workstation"

    is_vercel_cloud = bool(os.environ.get("VERCEL"))
    runtime_env = "vercel_cloud" if is_vercel_cloud else "local_host"
    is_mobile = device_class == "mobile"
    is_tablet = device_class == "tablet"
    is_desktop_capable = device_class in ("laptop", "desktop")
    full_desktop_os_automation = is_desktop_capable and (runtime_env == "local_host")

    capabilities = {
        "chat_and_voice": True,
        "cloud_coder_ide_git_terminal": True,
        "live_browser_automation": True,
        "multi_agent_orchestration": True,
        "jarvis_routines": True,
        "full_desktop_os_automation": full_desktop_os_automation,
        "remote_companion_recommended": is_mobile or is_tablet,
    }

    if is_mobile:
        automation_tier = "MOBILE_CHAT_AND_CLOUD_CODER"
        guidance = (
            "User is messaging from a Mobile Phone. Keep replies crisp & mobile-friendly. "
            "Full Chat, Voice, Cloud Coder IDE (files, AST bug scan, refactor, Git commit/push, isolated terminal), "
            "Cloud Live Browser, Multi-Agent Swarm, and JARVIS are 100% available. "
            "Physical host mouse/keyboard desktop control cannot run directly on a phone — offer Cloud Browser or /remote pairing to control their Laptop/Desktop."
        )
    elif is_tablet:
        automation_tier = "TABLET_STUDIO_AND_CLOUD_AUTOMATION"
        guidance = (
            "User is messaging from a Tablet / iPad. Full Chat, Cloud Coder IDE, Git commit/push, "
            "Live Browser automation, Multi-Agent Swarm, and JARVIS are active. "
            "For host OS desktop mouse/keyboard automation, offer /remote pairing to their Laptop/Desktop."
        )
    elif full_desktop_os_automation:
        automation_tier = "DESKTOP_FULL_AUTONOMOUS_CONTROL"
        guidance = (
            f"User is on {device_label} (Local Host Runtime). FULL UNRESTRICTED AUTONOMY ACTIVE: "
            "Coder IDE, Git commit/branch/merge/push/PR, Isolated Terminal/Pytest, Live Embedded Browser control, "
            "Physical Desktop/OS Automation (screen, mouse, keyboard, apps), Multi-Agent Swarm, and JARVIS."
        )
    else:
        automation_tier = "DESKTOP_CLOUD_AUTONOMOUS_WORKSPACE"
        guidance = (
            f"User is on {device_label} via AURA Cloud (Vercel). Full Cloud Coder IDE, Git commit/branch/merge/push/PR, "
            "Isolated Terminal, Live Cloud Browser automation, Multi-Agent Swarm, and JARVIS are fully active. "
            "If the user requests physical local desktop mouse/keyboard control on their own PC, explain they can run AURA locally or connect via Remote Pairing."
        )

    return {
        "device_class": device_class,
        "os_name": os_name,
        "device_label": device_label,
        "runtime_env": runtime_env,
        "automation_tier": automation_tier,
        "is_mobile": is_mobile,
        "is_tablet": is_tablet,
        "is_desktop_capable": is_desktop_capable,
        "standalone_pwa": is_pwa,
        "viewport": f"{vw}x{vh}" if (vw > 0 and vh > 0) else "unknown",
        "capabilities": capabilities,
        "guidance": guidance,
    }


def format_device_context_block(device_ctx: Optional[Dict[str, Any]]) -> str:
    """Compact prompt header giving AURA instant awareness of the user's exact device."""
    if not isinstance(device_ctx, dict) or not device_ctx.get("device_label"):
        return ""
    caps = device_ctx.get("capabilities") or {}
    desktop_os = "ENABLED" if caps.get("full_desktop_os_automation") else "CLOUD_OR_REMOTE_ONLY"
    return (
        f"[DEVICE CONTEXT]\n"
        f"Client Device: {device_ctx.get('device_label')} | Class: {device_ctx.get('device_class')} | "
        f"OS: {device_ctx.get('os_name')} | Runtime: {device_ctx.get('runtime_env')} | "
        f"Tier: {device_ctx.get('automation_tier')}\n"
        f"Capabilities: Chat/Voice=ON, Coder/Git/Terminal=ON, LiveBrowser=ON, MultiAgent/JARVIS=ON, PhysicalDesktopOS={desktop_os}\n"
        f"Policy: {device_ctx.get('guidance', '')}\n"
        f"[/DEVICE CONTEXT]"
    )
