"""
AURA Membership, 25-Key Cryptographic Activation Registry & 24h Rolling Daily Quota Engine.

Security & Serverless Architecture:
- Stores ONLY salted SHA-256 digests of the 25 owner-issued activation keys (zero plaintext keys in repo).
- Issues server-signed HMAC-SHA256 `membership_proof` envelopes (`aura_mp1.<b64>.<sig>`) bound to the user
  so activated memberships seamlessly persist across Vercel serverless cold starts and local restarts.
- Enforces rolling 24-hour daily chat quotas:
    * Standard (tier_0): 30 chats / 24h
    * Tier 1 (AURA Velocity · 10x): 60 chats / 24h
    * Tier 2 (AURA Architect · 30x): 60 chats / 24h
    * Tier 3 (AURA Sovereign · 60x): Unlimited
    * Tier 4 (AURA Titan · 100x): Unlimited
    * Tier 5 (AURA Apex Omnis · 100x Ultimate Autonomous Engineering Suite): Unlimited
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import aura_db

KEY_HASH_SALT = "AURA_MEMBER_KEY_V1:"
ROLLING_WINDOW_SECONDS = 24 * 60 * 60

MEMBERSHIP_TIERS: Dict[str, Dict[str, Any]] = {
    "tier_0": {
        "id": "tier_0",
        "rank": 0,
        "name": "AURA Standard",
        "short_name": "Standard",
        "badge": "STANDARD",
        "multiplier": "1x",
        "daily_limit": 30,
        "unlimited": False,
        "theme": "standard",
        "accent": "#3b82f6",
        "tagline": "Core AURA 2.0 / 2.3 / 2.6 workspace with 30 chats per 24 hours.",
        "features": [
            "AURA 2.0 / 2.3 / 2.6 Core Access",
            "30 Chats / 24h Rolling Refresh",
            "Live Split Preview & Multi-Wallpaper Studio",
            "TRINETRA Cyber Defense & Voice HUD",
        ],
    },
    "tier_1": {
        "id": "tier_1",
        "rank": 1,
        "name": "AURA Velocity",
        "short_name": "Velocity",
        "badge": "VELOCITY · 10X",
        "multiplier": "10x",
        "daily_limit": 60,
        "unlimited": False,
        "theme": "cobalt",
        "accent": "#3b82f6",
        "tagline": "10x engineering velocity with Cobalt Titanium UI, @file context injection, and live AST symbol indexing.",
        "features": [
            "60 Chats / 24h Rolling Refresh",
            "Cobalt Titanium Executive UI Theme",
            "Smart @file Multi-File Context Injection",
            "Instant Codebase AST & Symbol Indexer",
            "Priority Fast Stream Routing & Split Export",
        ],
    },
    "tier_2": {
        "id": "tier_2",
        "rank": 2,
        "name": "AURA Architect",
        "short_name": "Architect",
        "badge": "ARCHITECT · 30X",
        "multiplier": "30x",
        "daily_limit": 60,
        "unlimited": False,
        "theme": "emerald",
        "accent": "#10b981",
        "tagline": "30x studio precision with Emerald Noir UI, multi-file unified diffs with rollback, and polyglot code execution.",
        "features": [
            "60 Chats / 24h Rolling Refresh",
            "Emerald Noir Executive UI Theme",
            "Everything in AURA Velocity (Tier 1)",
            "Multi-File Unified Diff Composer + Snapshot Rollback",
            "Polyglot Sandbox Runner (Python / JS / SQL / JSON / HTML)",
            "Deep Architecture Thinking Mode",
        ],
    },
    "tier_3": {
        "id": "tier_3",
        "rank": 3,
        "name": "AURA Sovereign",
        "short_name": "Sovereign",
        "badge": "SOVEREIGN · 60X",
        "multiplier": "60x",
        "daily_limit": None,
        "unlimited": True,
        "theme": "amethyst",
        "accent": "#a78bfa",
        "tagline": "60x unlimited workspace with Royal Amethyst glass, self-healing bug repair, repo scaffolder, and .aura-rules.",
        "features": [
            "Unlimited Daily Chats (No 24h Cap)",
            "Royal Amethyst Executive UI Theme",
            "Everything in Tiers 1 & 2",
            "Autonomous Self-Healing Bug & Test Repair Loop",
            "Full Multi-File Production Repo Scaffolder",
            "Persistent .aura-rules Custom Engineering Memory",
        ],
    },
    "tier_4": {
        "id": "tier_4",
        "rank": 4,
        "name": "AURA Titan",
        "short_name": "Titan",
        "badge": "TITAN · 100X",
        "multiplier": "100x",
        "daily_limit": None,
        "unlimited": True,
        "theme": "champagne",
        "accent": "#d4a759",
        "tagline": "100x autonomous suite with Champagne Obsidian finish, 4-Agent War Room, security AST audits, and guarded desktop OS automation.",
        "features": [
            "Unlimited Daily Chats (No 24h Cap)",
            "Champagne Obsidian Executive UI Theme",
            "Everything in Tiers 1, 2 & 3",
            "Desktop / Laptop OS Automation with Allow/Deny Reason Popup",
            "Parallel 4-Agent War Room (Architect · Coder · Security · QA)",
            "Deep Workspace Security & Static Vulnerability Audit Suite",
        ],
    },
    "tier_5": {
        "id": "tier_5",
        "rank": 5,
        "name": "AURA Apex Omnis",
        "short_name": "Apex Omnis",
        "badge": "APEX OMNIS · 100X",
        "multiplier": "100x",
        "daily_limit": None,
        "unlimited": True,
        "theme": "platinum",
        "accent": "#f4f4f5",
        "tagline": "100x flagship Platinum Monolith autonomous engineering studio — 6-stage polyglot build, verify, self-heal, and rollback engine.",
        "features": [
            "Unlimited Daily Chats (No 24h Cap)",
            "Platinum Monolith Exclusive UI & Command Deck",
            "Everything in Tiers 1, 2, 3 & 4",
            "6-Stage Autonomous End-to-End Engineering Pipeline",
            "Dedicated Full-Screen Apex Engineering Studio IDE",
            "20+ Language Polyglot Mastery with Zero-Placeholder Gate",
        ],
    },
}

# Salted SHA-256 registry for the 25 owner-issued activation keys (5 unique keys per tier).
# Plaintext keys are NEVER committed into source control.
ACTIVATION_KEY_HASHES: Dict[str, Dict[str, str]] = {
    # Tier 1 — AURA Velocity (5 keys)
    "dc3762783ec4969892b011f5c505e33033c777a92594250bf2c90be7548beb92": {"tier_id": "tier_1", "slot": "tier_1_key_1"},
    "01b75d441d20a3b5058077b39dd66956263fbef42a667dd0ecb08a2582ac9773": {"tier_id": "tier_1", "slot": "tier_1_key_2"},
    "0a1531fd49e28d32ba7575f7db2f6896cea5b80b2ef46e0dbab894684f9cb8dc": {"tier_id": "tier_1", "slot": "tier_1_key_3"},
    "9fa156e9b136592db39cc45dbf8889c1154c523ee50128c5129402909e0756fa": {"tier_id": "tier_1", "slot": "tier_1_key_4"},
    "2a2838a835ffdd25f648402711a0ec4b9e4c67fc6fd4dede87f78ee5cfa5504a": {"tier_id": "tier_1", "slot": "tier_1_key_5"},
    # Tier 2 — AURA Architect (5 keys)
    "5d5d3a1ff60b8881186b4d262c582dc0a3632676657197b34a4c0cd83087711b": {"tier_id": "tier_2", "slot": "tier_2_key_1"},
    "6937b37689a82d0a1ab20caf41ce220cf981d6f4497873826131ce241025032b": {"tier_id": "tier_2", "slot": "tier_2_key_2"},
    "a9a741815164bc751812984e354eb5c1b24dd013564f794be975cd5034e525e6": {"tier_id": "tier_2", "slot": "tier_2_key_3"},
    "58194b91a33973c1e9acc1f3e8d409a773a589163c80e3209862f77ee927d6f7": {"tier_id": "tier_2", "slot": "tier_2_key_4"},
    "574983e84fc2a29aa7e6c13ed333c4ea5fe49b371334faff099e50ff1582338d": {"tier_id": "tier_2", "slot": "tier_2_key_5"},
    # Tier 3 — AURA Sovereign (5 keys)
    "978db932c2244221ca1b23d2672dc88fb57983fa802723b90272ea4178f1f6ce": {"tier_id": "tier_3", "slot": "tier_3_key_1"},
    "7808533c3534739be696aba38b01828614e83160e8f4f1aeb7eec52dc548f1eb": {"tier_id": "tier_3", "slot": "tier_3_key_2"},
    "ac929a91611bb9b436e6d1a0dbe67a8a4d3dfe2ec1734f1d5f6314c0f42a301e": {"tier_id": "tier_3", "slot": "tier_3_key_3"},
    "d6fe44dabd6703eb15942ec82f885f71e65f6ca8446660a557f8f978d571b6de": {"tier_id": "tier_3", "slot": "tier_3_key_4"},
    "bd6bad3e09a9ebad31df4c488be1aee8141ac264593726308c222ab4c46be431": {"tier_id": "tier_3", "slot": "tier_3_key_5"},
    # Tier 4 — AURA Titan (5 keys)
    "6f801ffa534a3dbb81e09b7f01cd25feae6e4411625b734b3877ca1201702e3c": {"tier_id": "tier_4", "slot": "tier_4_key_1"},
    "b5ec78fe7ac9ddc69d816773d63ef5b9bf50cc9c907daa81c194f0c6d166e838": {"tier_id": "tier_4", "slot": "tier_4_key_2"},
    "32ac0f31b1e9f9b8b9d1ae8eb5d5c1ff941f5ba2ebff69166b2ff5bccc1e469d": {"tier_id": "tier_4", "slot": "tier_4_key_3"},
    "5b6ea9a2c32ff195721e4e5ef8a3164dbcc704ed7248117503e463ad26b0ade4": {"tier_id": "tier_4", "slot": "tier_4_key_4"},
    "ac5de735a48cc10b1ca2d0582d9f9c543fbf67c4d80f1388923b9c85b69f5101": {"tier_id": "tier_4", "slot": "tier_4_key_5"},
    # Tier 5 — AURA Apex Omnis (5 keys)
    "cc33417088b2e6bd45aec1162f459e224749198e3c758f4ee77eceec095b39fd": {"tier_id": "tier_5", "slot": "tier_5_key_1"},
    "a53d9e1b69df7424faf88e2239475e71fdda00d296837d95b5827214469ab6be": {"tier_id": "tier_5", "slot": "tier_5_key_2"},
    "77a219fc856974467f60629c9b0638ef3ac921e785bb4077934feb7d911bfa55": {"tier_id": "tier_5", "slot": "tier_5_key_3"},
    "33ee56dfdfd4dbc0e79f4979ef3fc897e5ef6a7298bccb939535d37c90b3e474": {"tier_id": "tier_5", "slot": "tier_5_key_4"},
    "4c32426b9cfa3c44afc2ee887ea4455dba2026f224f0337f2b8673f4430529cb": {"tier_id": "tier_5", "slot": "tier_5_key_5"},
}


def normalize_activation_key(raw_key: str) -> str:
    return "".join(ch for ch in str(raw_key or "").strip().upper() if ch.isalnum() or ch == "-")


def hash_activation_key(raw_key: str) -> str:
    norm = normalize_activation_key(raw_key)
    return hashlib.sha256((KEY_HASH_SALT + norm).encode("utf-8")).hexdigest()


def lookup_activation_key(raw_key: str) -> Optional[Dict[str, str]]:
    digest = hash_activation_key(raw_key)
    entry = ACTIVATION_KEY_HASHES.get(digest)
    if not entry:
        return None
    return {"tier_id": entry["tier_id"], "slot": entry["slot"], "key_hash": digest}


def _sign_membership_payload(canonical_json: str) -> str:
    return aura_db.compute_vault_signature("AURA_MP1:" + canonical_json)


def build_membership_proof(username: str, tier_id: str, key_slot: str, activated_at: float) -> str:
    payload = {
        "u": str(username or "").strip().lower(),
        "t": tier_id if tier_id in MEMBERSHIP_TIERS else "tier_0",
        "s": str(key_slot or "")[:32],
        "ts": int(activated_at),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(canonical.encode("utf-8")).decode("ascii").rstrip("=")
    sig = _sign_membership_payload(canonical)
    return f"aura_mp1.{b64}.{sig}"


def verify_membership_proof(proof: str, expected_username: str) -> Optional[Dict[str, Any]]:
    raw = str(proof or "").strip()
    if not raw.startswith("aura_mp1."):
        return None
    parts = raw.split(".")
    if len(parts) != 3:
        return None
    _, b64, sig = parts
    try:
        pad = "=" * ((4 - len(b64) % 4) % 4)
        canonical = base64.urlsafe_b64decode((b64 + pad).encode("ascii")).decode("utf-8")
        expected_sig = _sign_membership_payload(canonical)
        if not hmac.compare_digest(expected_sig, sig):
            return None
        data = json.loads(canonical)
        if not isinstance(data, dict):
            return None
        if str(data.get("u", "")).lower() != str(expected_username or "").strip().lower():
            return None
        tier_id = str(data.get("t", "tier_0"))
        if tier_id not in MEMBERSHIP_TIERS:
            return None
        return {
            "tier_id": tier_id,
            "key_slot": str(data.get("s", "")),
            "activated_at": float(data.get("ts", time.time())),
        }
    except Exception:
        return None


def get_tier_spec(tier_id: str) -> Dict[str, Any]:
    return dict(MEMBERSHIP_TIERS.get(str(tier_id or "tier_0"), MEMBERSHIP_TIERS["tier_0"]))


def list_public_tiers() -> List[Dict[str, Any]]:
    """Returns all 5 upgrade tiers + Standard spec (capability matrix only — zero prices)."""
    return [dict(MEMBERSHIP_TIERS[k]) for k in ("tier_0", "tier_1", "tier_2", "tier_3", "tier_4", "tier_5")]


def _safe_int_uid(user: Dict[str, Any]) -> Optional[int]:
    try:
        return int(user.get("id"))
    except (TypeError, ValueError):
        return None


def resolve_user_membership(
    user: Dict[str, Any],
    membership_proof: str = "",
) -> Dict[str, Any]:
    """
    Resolves active tier for an authenticated user from DB settings_json,
    automatically hydrating from a verified server-signed membership_proof on cold starts.
    """
    uid = _safe_int_uid(user)
    uname = str(user.get("username") or "").strip().lower()
    settings = aura_db.get_user_settings_dict(uid) if uid is not None else (user.get("settings") if isinstance(user.get("settings"), dict) else {})
    mem = settings.get("membership") if isinstance(settings.get("membership"), dict) else {}
    tier_id = str(mem.get("tier_id") or "tier_0")
    if tier_id not in MEMBERSHIP_TIERS:
        tier_id = "tier_0"

    # Cross-container serverless recovery via server-signed membership_proof
    if tier_id == "tier_0" and membership_proof and uid is not None:
        verified = verify_membership_proof(membership_proof, uname)
        if verified and verified["tier_id"] != "tier_0":
            tier_id = verified["tier_id"]
            mem = {
                "tier_id": tier_id,
                "key_slot": verified.get("key_slot", ""),
                "activated_at": verified.get("activated_at", time.time()),
            }
            settings["membership"] = mem
            aura_db.save_user_settings(uid, settings)

    spec = get_tier_spec(tier_id)
    activated_at = float(mem.get("activated_at") or 0)
    key_slot = str(mem.get("key_slot") or "")
    proof = build_membership_proof(uname, tier_id, key_slot, activated_at or time.time()) if tier_id != "tier_0" else ""

    return {
        **spec,
        "activated_at": activated_at if tier_id != "tier_0" else None,
        "key_slot": key_slot,
        "membership_proof": proof,
        "aura_rules": str(settings.get("aura_rules") or ""),
    }


def activate_membership_key(user: Dict[str, Any], raw_key: str) -> Dict[str, Any]:
    """Validates an activation key against the SHA-256 registry and activates the user's tier."""
    match = lookup_activation_key(raw_key)
    if not match:
        return {
            "success": False,
            "error": "Invalid activation key. Double-check the key format (AURA-XXXX-XXXX-XXXX-XXXX) and try again.",
        }

    uid = int(user["id"])
    uname = str(user.get("username") or "").strip().lower()
    tier_id = match["tier_id"]
    key_slot = match["slot"]
    key_hash = match["key_hash"]
    now_ts = time.time()

    settings = aura_db.get_user_settings_dict(uid)
    settings["membership"] = {
        "tier_id": tier_id,
        "key_slot": key_slot,
        "key_hash_prefix": key_hash[:12],
        "activated_at": now_ts,
    }
    aura_db.save_user_settings(uid, settings)
    aura_db.record_membership_activation(uid, uname, key_hash, tier_id)

    resolved = resolve_user_membership(user)
    quota = get_user_quota_status(user, resolved)
    return {
        "success": True,
        "message": f"{resolved['name']} ({resolved['multiplier']}) activated successfully.",
        "membership": resolved,
        "quota": quota,
    }


def deactivate_membership(user: Dict[str, Any]) -> Dict[str, Any]:
    uid = int(user["id"])
    settings = aura_db.get_user_settings_dict(uid)
    settings.pop("membership", None)
    aura_db.save_user_settings(uid, settings)
    resolved = resolve_user_membership(user)
    quota = get_user_quota_status(user, resolved)
    return {
        "success": True,
        "message": "Account returned to AURA Standard tier.",
        "membership": resolved,
        "quota": quota,
    }


def save_user_aura_rules(user: Dict[str, Any], rules_text: str, membership: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    mem = membership or resolve_user_membership(user)
    if int(mem.get("rank", 0)) < 3:
        return {
            "success": False,
            "error": "Persistent .aura-rules engineering memory requires AURA Sovereign (Tier 3) or higher.",
            "required_rank": 3,
        }
    uid = int(user["id"])
    clean_rules = str(rules_text or "").strip()[:6000]
    settings = aura_db.get_user_settings_dict(uid)
    settings["aura_rules"] = clean_rules
    aura_db.save_user_settings(uid, settings)
    return {"success": True, "aura_rules": clean_rules}


def get_user_quota_status(user: Dict[str, Any], membership: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    mem = membership or resolve_user_membership(user)
    limit = mem.get("daily_limit")
    unlimited = bool(mem.get("unlimited", False)) or limit is None
    uid = _safe_int_uid(user)
    usage = aura_db.get_rolling_24h_quota_usage(uid, window_seconds=ROLLING_WINDOW_SECONDS) if uid is not None else {"used": 0, "oldest_ts": None}
    used = int(usage.get("used", 0))
    oldest_ts = usage.get("oldest_ts")
    now_ts = time.time()

    if unlimited:
        return {
            "used": used,
            "limit": None,
            "remaining": None,
            "unlimited": True,
            "blocked": False,
            "reset_in_seconds": 0,
            "reset_label": "Unlimited",
            "tier_id": mem["id"],
        }

    limit_int = int(limit)
    remaining = max(0, limit_int - used)
    blocked = used >= limit_int
    reset_in = 0
    if oldest_ts:
        reset_in = max(0, int((float(oldest_ts) + ROLLING_WINDOW_SECONDS) - now_ts))
    hrs = reset_in // 3600
    mins = (reset_in % 3600) // 60
    reset_label = f"{hrs}h {mins}m" if reset_in > 0 else "24h rolling"

    return {
        "used": used,
        "limit": limit_int,
        "remaining": remaining,
        "unlimited": False,
        "blocked": blocked,
        "reset_in_seconds": reset_in,
        "reset_label": reset_label,
        "tier_id": mem["id"],
    }


def check_and_consume_chat_quota(
    user: Dict[str, Any],
    prompt: str,
    membership: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Checks rolling 24-hour chat limit before running a model turn.
    Utility commands (/help) bypass quota consumption so users are never stranded.
    Returns (allowed, quota_status).
    """
    mem = membership or resolve_user_membership(user)
    stripped = str(prompt or "").strip().lower()
    if stripped in ("/help", "help"):
        return True, get_user_quota_status(user, mem)

    status = get_user_quota_status(user, mem)
    if status["blocked"]:
        return False, status

    uid = _safe_int_uid(user)
    if uid is not None:
        aura_db.record_chat_quota_event(uid)
    updated = get_user_quota_status(user, mem)
    return True, updated


def build_tier_system_profile(membership: Dict[str, Any], context_files_block: str = "") -> str:
    """
    Builds concise, high-signal engineering profile instructions tailored to the user's
    activated membership tier, persistent .aura-rules, and attached @file context snippets.
    """
    rank = int(membership.get("rank", 0))
    parts: List[str] = []

    if rank >= 5:
        parts.append(
            "[AURA APEX OMNIS · TIER 5 PLATINUM ENGINEERING ENGINE]\n"
            "You are operating at Tier 5 Apex Omnis capacity — an institutional autonomous polyglot software engineer across 20+ languages "
            "(Python, TypeScript, JavaScript, React, Rust, Go, Java, C/C++, C#, SQL, Kotlin, Swift, Bash, Docker/K8s).\n"
            "Standards: Zero placeholder comments ('TODO', 'pass', '...'), full edge-case validation, crisp Big-O complexity proofs, "
            "security-by-default patterns, multi-file unified diffs when editing existing code, and runnable verification tests."
        )
    elif rank == 4:
        parts.append(
            "[AURA TITAN · TIER 4 AUTONOMOUS SUITE]\n"
            "Operate with multi-agent rigor (Architecture + Implementation + Security + QA). Flag OWASP/security pitfalls proactively "
            "and always provide explicit verification commands or runnable code blocks."
        )
    elif rank == 3:
        parts.append(
            "[AURA SOVEREIGN · TIER 3 UNLIMITED ENGINEERING]\n"
            "Deliver production-complete, self-verified implementations with clear error handling, unit tests, and architectural rationale."
        )
    elif rank == 2:
        parts.append(
            "[AURA ARCHITECT · TIER 2 STUDIO]\n"
            "Provide structured multi-file diffs, clean modular code, and concise architectural trade-offs."
        )
    elif rank == 1:
        parts.append(
            "[AURA VELOCITY · TIER 1 FAST ENGINEERING]\n"
            "Prioritize crisp, high-velocity, copy-ready engineering answers with zero fluff."
        )

    rules = str(membership.get("aura_rules") or "").strip()
    if rank >= 3 and rules:
        parts.append(f"[USER .AURA-RULES ENGINEERING CONSTRAINTS]\n{rules[:3000]}")

    if rank >= 1 and context_files_block:
        parts.append(f"[ATTACHED WORKSPACE @FILE CONTEXT]\n{context_files_block[:14000]}")

    return "\n\n".join(parts)
