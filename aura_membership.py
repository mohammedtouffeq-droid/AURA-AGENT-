"""
AURA 3-Plan Subscription System, Dynamic Time-Limited Cryptographic Key Engine,
24h Rolling Daily Quota Engine & Exclusive Admin Key Vault (ig.ahmed.irl).

Architecture:
- 3 Flagship Paid Subscriptions (2 entry tiers removed — keeping the BIG 3):
    * Standard (tier_0 · Free):      30 chats / 24h
    * Plan 1 — AURA Sovereign (tier_3): Rs. 40  | 20 Days | 100 chats / 24h | Half of Flagship Suite
    * Plan 2 — AURA Titan     (tier_4): Rs. 99  | 30 Days | 300 chats / 24h | Expanded Autonomous Suite
    * Plan 3 — AURA Apex Omnis(tier_5): Rs. 199 | 30 Days | Unlimited / 24h | 100% All 64 Flagship Features
- Hybrid Key Engine:
    * Admin-generated keys (`AURA-<SOV|TTN|APX>-<DAYS>D-<NONCE6>-<SIG8>`) are stored in
      `subscription_keys` SQLite/LibSQL table AND cryptographically self-verifiable across
      serverless cold starts via HMAC-SHA256.
    * Automatic expiration when `expires_at` passes — user returns to Standard until Admin renews.
    * Admin can renew expired/disabled keys on the exact same key code when payment arrives,
      change plan or duration, disable/turn off keys instantly, or unbind users.
- Strict Admin Isolation:
    * Admin Key Vault endpoints require BOTH authenticated username == `ig.ahmed.irl`
      AND a verified Admin Vault session token unlocked with the server-hashed Admin Vault password.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

import aura_db

KEY_HASH_SALT = "AURA_MEMBER_KEY_V1:"
ADMIN_VAULT_SALT = "AURA_ADMIN_VAULT_V1:"
ADMIN_OWNER_USERNAME = "ig.ahmed.irl"
# Salted SHA-256 digest of the exclusive Admin Key Vault password (never stored in plaintext)
DEFAULT_ADMIN_VAULT_HASH = "7555131f70c3e4fae18f50dfb15527f55c45cd53c682ae54058ff745e7c90748"
ADMIN_VAULT_TOKEN_TTL_SECONDS = 12 * 60 * 60
ROLLING_WINDOW_SECONDS = 24 * 60 * 60
SECONDS_PER_DAY = 24 * 60 * 60

SUBSCRIPTION_CONTACT: Dict[str, str] = {
    "whatsapp_display": "+91 9640875528",
    "whatsapp_digits": "919640875528",
    "whatsapp_url": "https://wa.me/919640875528",
    "support_note": "Message directly on WhatsApp (+91 9640875528) to purchase a new key or renew an expired key.",
}

MEMBERSHIP_TIERS: Dict[str, Dict[str, Any]] = {
    "tier_0": {
        "id": "tier_0",
        "plan_number": 0,
        "rank": 0,
        "name": "AURA Standard",
        "short_name": "Standard",
        "badge": "STANDARD",
        "multiplier": "FREE",
        "price_inr": 0,
        "price_label": "Free",
        "duration_days": None,
        "duration_label": "Always Free",
        "daily_limit": 30,
        "unlimited": False,
        "theme": "standard",
        "accent": "#7aa2ff",
        "feature_coverage": "Core Starter",
        "tagline": "Core AURA 2.0 / 2.3 / 2.6 workspace with 30 chats per 24 hours.",
        "features": [
            "30 Chats / 24h Rolling Refresh",
            "AURA 2.0 / 2.3 / 2.6 Core Chat Access",
            "Live Split Preview & Multi-Wallpaper Studio",
            "TRINETRA Cyber Defense & Voice HUD",
        ],
    },
    "tier_3": {
        "id": "tier_3",
        "plan_number": 1,
        "rank": 3,
        "name": "AURA Sovereign",
        "short_name": "Sovereign",
        "badge": "SOVEREIGN · PLAN 1",
        "multiplier": "100/DAY · 20D",
        "price_inr": 40,
        "price_label": "₹40",
        "duration_days": 20,
        "duration_label": "20 Days",
        "daily_limit": 100,
        "unlimited": False,
        "theme": "amethyst",
        "accent": "#818cf8",
        "feature_coverage": "50% Flagship Suite",
        "tagline": "100 chats/day for 20 days with half of AURA's flagship engineering & agent capabilities unlocked.",
        "features": [
            "100 Chats / Day (24h Rolling Refresh)",
            "20-Day Validity (Auto-Deactivates · Admin Renewable)",
            "Dev Studio AI Code (Autocomplete, Explain, Bug Scan & Refactor)",
            "AST Symbol Indexer, @file Context & Polyglot Code Sandbox",
            "Multi-File Diffs, Snapshots, Repo Scaffolder & Self-Healing Repair",
            "AURA Live Browser & Persistent .aura-rules Memory",
            "Upgraded Sapphire-Amethyst Obsidian Executive Design",
        ],
    },
    "tier_4": {
        "id": "tier_4",
        "plan_number": 2,
        "rank": 4,
        "name": "AURA Titan",
        "short_name": "Titan",
        "badge": "TITAN · PLAN 2",
        "multiplier": "300/DAY · 30D",
        "price_inr": 99,
        "price_label": "₹99",
        "duration_days": 30,
        "duration_label": "30 Days",
        "daily_limit": 300,
        "unlimited": False,
        "theme": "champagne",
        "accent": "#60a5fa",
        "feature_coverage": "80% Flagship Suite",
        "tagline": "300 chats/day for 30 days with parallel multi-agent war room, desktop automation, Git diffs, and workflows.",
        "features": [
            "300 Chats / Day (3x Sovereign Capacity)",
            "30-Day Validity (Auto-Deactivates · Admin Renewable)",
            "Everything Included in AURA Sovereign (Plan 1)",
            "Parallel 4-Agent War Room & Multi-Agent Orchestrator",
            "Computer Use Desktop Automation with Guarded Allow/Deny Control",
            "Git Visual Diffs, Worktrees, PR Assistant & Security AST Audits",
            "Automation Hub: Reusable Workflows, Cron Schedules & Custom Skills",
            "Upgraded Indigo-Titanium Obsidian Executive Design",
        ],
    },
    "tier_5": {
        "id": "tier_5",
        "plan_number": 3,
        "rank": 5,
        "name": "AURA Apex Omnis",
        "short_name": "Apex Omnis",
        "badge": "APEX OMNIS · PLAN 3",
        "multiplier": "UNLIMITED · 30D",
        "price_inr": 199,
        "price_label": "₹199",
        "duration_days": 30,
        "duration_label": "30 Days",
        "daily_limit": None,
        "unlimited": True,
        "theme": "platinum",
        "accent": "#e2e8f0",
        "feature_coverage": "100% Complete Flagship",
        "tagline": "Unlimited daily chats for 30 days with 100% of all 64 AURA autonomous engineering, remote control, and Platinum Monolith studio capabilities.",
        "features": [
            "Unlimited Daily Chats (Zero 24h Cap)",
            "30-Day Validity (Custom Admin Duration & Instant Renewal)",
            "Everything Included in Sovereign (Plan 1) & Titan (Plan 2)",
            "6-Stage Apex Omnis Autonomous Build, Verify & Self-Heal Pipeline",
            "Full-Screen Apex Engineering Studio IDE & 20+ Language Mastery",
            "Remote Agent Control, MCP Servers, Plugins & Deep Reasoning Routing",
            "Exclusive Platinum Monolith Executive Workspace Design & Priority Engine",
        ],
    },
}

TIER_CODE_TO_ID: Dict[str, str] = {"SOV": "tier_3", "TTN": "tier_4", "APX": "tier_5"}
TIER_ID_TO_CODE: Dict[str, str] = {"tier_3": "SOV", "tier_4": "TTN", "tier_5": "APX"}
PAID_TIER_ORDER: Tuple[str, ...] = ("tier_3", "tier_4", "tier_5")

# Salted SHA-256 fallback registry for the 15 big-tier owner keys (5 per active flagship plan).
# The 2 smaller legacy tiers (tier_1, tier_2) were retired per 3-plan consolidation.
ACTIVATION_KEY_HASHES: Dict[str, Dict[str, Any]] = {
    # Plan 1 — AURA Sovereign (tier_3 · 20 days)
    "978db932c2244221ca1b23d2672dc88fb57983fa802723b90272ea4178f1f6ce": {"tier_id": "tier_3", "slot": "plan_1_key_1", "duration_days": 20},
    "7808533c3534739be696aba38b01828614e83160e8f4f1aeb7eec52dc548f1eb": {"tier_id": "tier_3", "slot": "plan_1_key_2", "duration_days": 20},
    "ac929a91611bb9b436e6d1a0dbe67a8a4d3dfe2ec1734f1d5f6314c0f42a301e": {"tier_id": "tier_3", "slot": "plan_1_key_3", "duration_days": 20},
    "d6fe44dabd6703eb15942ec82f885f71e65f6ca8446660a557f8f978d571b6de": {"tier_id": "tier_3", "slot": "plan_1_key_4", "duration_days": 20},
    "bd6bad3e09a9ebad31df4c488be1aee8141ac264593726308c222ab4c46be431": {"tier_id": "tier_3", "slot": "plan_1_key_5", "duration_days": 20},
    # Plan 2 — AURA Titan (tier_4 · 30 days)
    "6f801ffa534a3dbb81e09b7f01cd25feae6e4411625b734b3877ca1201702e3c": {"tier_id": "tier_4", "slot": "plan_2_key_1", "duration_days": 30},
    "b5ec78fe7ac9ddc69d816773d63ef5b9bf50cc9c907daa81c194f0c6d166e838": {"tier_id": "tier_4", "slot": "plan_2_key_2", "duration_days": 30},
    "32ac0f31b1e9f9b8b9d1ae8eb5d5c1ff941f5ba2ebff69166b2ff5bccc1e469d": {"tier_id": "tier_4", "slot": "plan_2_key_3", "duration_days": 30},
    "5b6ea9a2c32ff195721e4e5ef8a3164dbcc704ed7248117503e463ad26b0ade4": {"tier_id": "tier_4", "slot": "plan_2_key_4", "duration_days": 30},
    "ac5de735a48cc10b1ca2d0582d9f9c543fbf67c4d80f1388923b9c85b69f5101": {"tier_id": "tier_4", "slot": "plan_2_key_5", "duration_days": 30},
    # Plan 3 — AURA Apex Omnis (tier_5 · 30 days)
    "cc33417088b2e6bd45aec1162f459e224749198e3c758f4ee77eceec095b39fd": {"tier_id": "tier_5", "slot": "plan_3_key_1", "duration_days": 30},
    "a53d9e1b69df7424faf88e2239475e71fdda00d296837d95b5827214469ab6be": {"tier_id": "tier_5", "slot": "plan_3_key_2", "duration_days": 30},
    "77a219fc856974467f60629c9b0638ef3ac921e785bb4077934feb7d911bfa55": {"tier_id": "tier_5", "slot": "plan_3_key_3", "duration_days": 30},
    "33ee56dfdfd4dbc0e79f4979ef3fc897e5ef6a7298bccb939535d37c90b3e474": {"tier_id": "tier_5", "slot": "plan_3_key_4", "duration_days": 30},
    "4c32426b9cfa3c44afc2ee887ea4455dba2026f224f0337f2b8673f4430529cb": {"tier_id": "tier_5", "slot": "plan_3_key_5", "duration_days": 30},
}

_DYNAMIC_KEY_RE = re.compile(r"^AURA-(SOV|TTN|APX)-(\d{1,4})([DHM])-([A-Z0-9]{6})(?:-R(\d{1,3}))?-([A-F0-9]{8})$")

UNIT_TO_SECONDS: Dict[str, int] = {"M": 60, "H": 3600, "D": 86400}


def normalize_duration_unit(raw_unit: Optional[str]) -> str:
    val = str(raw_unit or "days").strip().lower()
    if val in ("m", "min", "mins", "minute", "minutes"):
        return "M"
    if val in ("h", "hr", "hrs", "hour", "hours"):
        return "H"
    return "D"


def format_duration_seconds(seconds: int) -> str:
    secs = max(60, int(seconds))
    if secs % 86400 == 0:
        d = secs // 86400
        return f"{d} Day" if d == 1 else f"{d} Days"
    if secs % 3600 == 0:
        h = secs // 3600
        return f"{h} Hour" if h == 1 else f"{h} Hours"
    if secs % 60 == 0:
        m = secs // 60
        return f"{m} Min" if m == 1 else f"{m} Mins"
    return f"{secs}s"


def format_countdown(seconds_left: int) -> str:
    s = max(0, int(seconds_left))
    if s <= 0:
        return "Expired"
    days, rem = divmod(s, 86400)
    hrs, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hrs:02d}h {mins:02d}m"
    if hrs > 0:
        return f"{hrs:02d}h {mins:02d}m {secs:02d}s"
    if mins > 0:
        return f"{mins:02d}m {secs:02d}s"
    return f"{secs}s"


def _fmt_datetime(ts: Optional[float]) -> str:
    if not ts:
        return ""
    try:
        return datetime.datetime.fromtimestamp(float(ts)).strftime("%d %b %Y, %H:%M")
    except Exception:
        return ""


def _fmt_relative_ago(ts: Optional[float], now_ts: Optional[float] = None) -> str:
    if not ts:
        return "Never"
    now = now_ts if now_ts is not None else time.time()
    diff = max(0, int(now - float(ts)))
    if diff < 60:
        return "Just now"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    if diff < 86400 * 14:
        return f"{diff // 86400}d ago"
    return _fmt_date(ts)


def resolve_duration_spec(
    duration_days: Optional[int] = None,
    duration_value: Optional[int] = None,
    duration_unit: Optional[str] = None,
    default_days: int = 20,
) -> Tuple[int, int, str, int, str]:
    """
    Resolves flexible duration input (minutes / hours / days or legacy duration_days) into:
    (duration_seconds, approx_days_int, unit_code 'M'|'H'|'D', unit_value, human_label).
    """
    if duration_value is not None and str(duration_value).strip():
        unit = normalize_duration_unit(duration_unit or "days")
        val = int(duration_value)
        if unit == "M":
            val = max(1, min(9999, val))
        elif unit == "H":
            val = max(1, min(8760, val))
        else:
            val = max(1, min(365, val))
        secs = val * UNIT_TO_SECONDS[unit]
        approx_days = max(1, (secs + SECONDS_PER_DAY - 1) // SECONDS_PER_DAY)
        return secs, approx_days, unit, val, format_duration_seconds(secs)

    days = int(duration_days) if duration_days is not None and str(duration_days).strip() else int(default_days or 20)
    days = max(1, min(365, days))
    secs = days * SECONDS_PER_DAY
    return secs, days, "D", days, format_duration_seconds(secs)


def normalize_tier_id(raw_tier: str) -> str:
    val = str(raw_tier or "").strip().lower()
    if val in ("tier_3", "plan_1", "1", "sovereign", "sov", "tier_1", "tier_2"):
        return "tier_3"
    if val in ("tier_4", "plan_2", "2", "titan", "ttn"):
        return "tier_4"
    if val in ("tier_5", "plan_3", "3", "apex", "apex_omnis", "apx"):
        return "tier_5"
    return "tier_0"


def normalize_activation_key(raw_key: str) -> str:
    return "".join(ch for ch in str(raw_key or "").strip().upper() if ch.isalnum() or ch == "-")


def hash_activation_key(raw_key: str) -> str:
    norm = normalize_activation_key(raw_key)
    return hashlib.sha256((KEY_HASH_SALT + norm).encode("utf-8")).hexdigest()


def _sign_dynamic_key(tier_code: str, duration_val: int, nonce: str, renew_gen: int = 0, unit_code: str = "D") -> str:
    u = unit_code if unit_code in ("D", "H", "M") else "D"
    tag = f"AURA_KEY_V2:{tier_code}:{int(duration_val)}{u}:{nonce}"
    if renew_gen > 0:
        tag += f":R{int(renew_gen)}"
    return aura_db.compute_vault_signature(tag)[:8].upper()


def format_dynamic_key(
    tier_id: str,
    duration_days: int,
    nonce: str,
    renew_gen: int = 0,
    duration_value: Optional[int] = None,
    duration_unit: str = "D",
) -> str:
    norm_tier = normalize_tier_id(tier_id)
    if norm_tier not in TIER_ID_TO_CODE:
        norm_tier = "tier_3"
    tcode = TIER_ID_TO_CODE[norm_tier]
    unit = normalize_duration_unit(duration_unit) if duration_value is not None else "D"
    val = int(duration_value) if duration_value is not None else int(duration_days)
    if unit == "M":
        val = max(1, min(9999, val))
    elif unit == "H":
        val = max(1, min(8760, val))
    else:
        val = max(1, min(365, val))
    clean_nonce = "".join(ch for ch in str(nonce or "").upper() if ch.isalnum())[:6].ljust(6, "X")
    sig = _sign_dynamic_key(tcode, val, clean_nonce, renew_gen=renew_gen, unit_code=unit)
    if renew_gen > 0:
        return f"AURA-{tcode}-{val}{unit}-{clean_nonce}-R{int(renew_gen)}-{sig}"
    return f"AURA-{tcode}-{val}{unit}-{clean_nonce}-{sig}"


def verify_dynamic_key_format(raw_key: str) -> Optional[Dict[str, Any]]:
    norm = normalize_activation_key(raw_key)
    m = _DYNAMIC_KEY_RE.match(norm)
    if not m:
        return None
    tcode, val_str, unit_code, nonce, rgen_str, provided_sig = m.groups()
    val = int(val_str)
    renew_gen = int(rgen_str) if rgen_str else 0
    if unit_code == "D" and (val < 1 or val > 365):
        return None
    if unit_code == "H" and (val < 1 or val > 8760):
        return None
    if unit_code == "M" and (val < 1 or val > 9999):
        return None
    expected_sig = _sign_dynamic_key(tcode, val, nonce, renew_gen=renew_gen, unit_code=unit_code)
    if not hmac.compare_digest(expected_sig, provided_sig):
        return None
    tier_id = TIER_CODE_TO_ID[tcode]
    dur_secs = val * UNIT_TO_SECONDS[unit_code]
    approx_days = max(1, (dur_secs + SECONDS_PER_DAY - 1) // SECONDS_PER_DAY)
    return {
        "key_code": norm,
        "key_hash": hash_activation_key(norm),
        "tier_id": tier_id,
        "duration_days": approx_days,
        "duration_seconds": dur_secs,
        "duration_label": format_duration_seconds(dur_secs),
        "nonce": nonce,
        "renew_gen": renew_gen,
        "slot": f"dyn_{tcode.lower()}_{nonce.lower()}",
    }


def lookup_activation_key(raw_key: str) -> Optional[Dict[str, Any]]:
    norm = normalize_activation_key(raw_key)
    if not norm:
        return None
    digest = hash_activation_key(norm)

    # 1. Check live SQLite/LibSQL subscription_keys registry first (admin-generated, renewed, or disabled keys)
    db_row = aura_db.get_subscription_key_by_code(norm) or aura_db.get_subscription_key_by_hash(digest)
    if db_row:
        d_days = max(1, int(db_row.get("duration_days") or 20))
        d_secs = int(db_row["duration_seconds"]) if db_row.get("duration_seconds") else (d_days * SECONDS_PER_DAY)
        return {
            "source": "db",
            "key_code": db_row["key_code"],
            "key_hash": db_row["key_hash"],
            "tier_id": normalize_tier_id(db_row["tier_id"]),
            "duration_days": d_days,
            "duration_seconds": max(60, d_secs),
            "duration_label": format_duration_seconds(max(60, d_secs)),
            "is_gift": bool(db_row.get("is_gift")),
            "slot": db_row["key_code"],
            "db_row": db_row,
        }

    # 2. Cross-container cryptographic verification for Admin-generated dynamic keys
    dyn = verify_dynamic_key_format(norm)
    if dyn:
        return {
            "source": "dynamic_sig",
            "key_code": dyn["key_code"],
            "key_hash": dyn["key_hash"],
            "tier_id": dyn["tier_id"],
            "duration_days": dyn["duration_days"],
            "duration_seconds": dyn["duration_seconds"],
            "duration_label": dyn["duration_label"],
            "is_gift": False,
            "slot": dyn["key_code"],
            "db_row": None,
        }

    # 3. Fallback: 15 hashed owner keys (time-limited per tier defaults)
    entry = ACTIVATION_KEY_HASHES.get(digest)
    if entry:
        tid = normalize_tier_id(entry["tier_id"])
        default_days = int(entry.get("duration_days") or MEMBERSHIP_TIERS[tid].get("duration_days") or 20)
        return {
            "source": "static_hash",
            "key_code": norm,
            "key_hash": digest,
            "tier_id": tid,
            "duration_days": default_days,
            "duration_seconds": default_days * SECONDS_PER_DAY,
            "duration_label": format_duration_seconds(default_days * SECONDS_PER_DAY),
            "is_gift": False,
            "slot": str(entry.get("slot") or norm[:24]),
            "db_row": None,
        }
    return None


def _sign_membership_payload(canonical_json: str) -> str:
    return aura_db.compute_vault_signature("AURA_MP2:" + canonical_json)


def build_membership_proof(
    username: str,
    tier_id: str,
    key_slot: str,
    activated_at: float,
    expires_at: Optional[float] = None,
    key_code: str = "",
) -> str:
    norm_tier = normalize_tier_id(tier_id)
    payload: Dict[str, Any] = {
        "u": str(username or "").strip().lower(),
        "t": norm_tier,
        "s": str(key_slot or "")[:40],
        "ts": int(activated_at),
    }
    if expires_at:
        payload["exp"] = int(expires_at)
    if key_code:
        payload["k"] = str(key_code).strip().upper()[:48]
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
        tier_id = normalize_tier_id(str(data.get("t", "tier_0")))
        if tier_id not in MEMBERSHIP_TIERS:
            return None
        exp = data.get("exp")
        if exp is not None and float(exp) <= time.time():
            return None
        return {
            "tier_id": tier_id,
            "key_slot": str(data.get("s", "")),
            "key_code": str(data.get("k", "")),
            "activated_at": float(data.get("ts", time.time())),
            "expires_at": float(exp) if exp is not None else None,
        }
    except Exception:
        return None


def get_tier_spec(tier_id: str) -> Dict[str, Any]:
    norm = normalize_tier_id(tier_id)
    return dict(MEMBERSHIP_TIERS.get(norm, MEMBERSHIP_TIERS["tier_0"]))


def list_public_tiers() -> List[Dict[str, Any]]:
    """Returns Standard + the 3 Flagship Paid Subscriptions."""
    return [dict(MEMBERSHIP_TIERS[k]) for k in ("tier_0", "tier_3", "tier_4", "tier_5")]


def _safe_int_uid(user: Dict[str, Any]) -> Optional[int]:
    try:
        return int(user.get("id"))
    except (TypeError, ValueError):
        return None


def _fmt_date(ts: Optional[float]) -> str:
    if not ts:
        return ""
    try:
        return datetime.datetime.fromtimestamp(float(ts)).strftime("%d %b %Y")
    except Exception:
        return ""


def _mask_key_code(code: str) -> str:
    c = str(code or "").strip().upper()
    if len(c) <= 10:
        return c
    return f"{c[:12]}••••{c[-4:]}"


def resolve_user_membership(
    user: Dict[str, Any],
    membership_proof: str = "",
) -> Dict[str, Any]:
    """
    Resolves active subscription tier for an authenticated user:
    - Enforces Admin disable/kill-switch in real time.
    - Enforces automatic time expiration (`expires_at <= now`) and returns user to Standard.
    - Auto-syncs Admin renewals directly onto the user's account.
    - Hydrates verified non-expired `membership_proof` across serverless cold starts.
    """
    uid = _safe_int_uid(user)
    uname = str(user.get("username") or "").strip().lower()
    settings = aura_db.get_user_settings_dict(uid) if uid is not None else (user.get("settings") if isinstance(user.get("settings"), dict) else {})
    mem = settings.get("membership") if isinstance(settings.get("membership"), dict) else {}
    raw_tier = str(mem.get("tier_id") or "tier_0")
    tier_id = normalize_tier_id(raw_tier) if raw_tier != "tier_0" else "tier_0"
    now_ts = time.time()
    expired_notice = ""
    disabled_notice = ""

    # Cross-container serverless recovery via server-signed non-expired membership_proof
    if tier_id == "tier_0" and membership_proof and uid is not None:
        verified = verify_membership_proof(membership_proof, uname)
        if verified and verified["tier_id"] != "tier_0":
            tier_id = verified["tier_id"]
            mem = {
                "tier_id": tier_id,
                "key_slot": verified.get("key_slot", ""),
                "key_code": verified.get("key_code", ""),
                "activated_at": verified.get("activated_at", now_ts),
                "expires_at": verified.get("expires_at"),
            }
            settings["membership"] = mem
            aura_db.save_user_settings(uid, settings)

    # Authoritative live check against `subscription_keys` table (handles disable, expiry & Admin renewal)
    key_code = str(mem.get("key_code") or "").strip().upper()
    db_key = aura_db.get_subscription_key_by_code(key_code) if key_code else None
    if db_key is None and uname:
        # Check if Admin renewed a key bound to this user even after earlier expiry
        for krow in aura_db.list_subscription_keys(limit=200):
            if str(krow.get("bound_username") or "").lower() == uname:
                if krow.get("status") == "active" and krow.get("expires_at") and float(krow["expires_at"]) > now_ts:
                    db_key = krow
                    key_code = krow["key_code"]
                    break

    if db_key:
        k_status = str(db_key.get("status") or "active").lower()
        k_exp = float(db_key["expires_at"]) if db_key.get("expires_at") is not None else None
        k_bound = str(db_key.get("bound_username") or "").lower()
        if k_status == "disabled":
            if tier_id != "tier_0":
                disabled_notice = f"Your subscription key was disabled by the administrator. Message {SUBSCRIPTION_CONTACT['whatsapp_display']} for support."
            tier_id = "tier_0"
            if uid is not None and "membership" in settings:
                settings.pop("membership", None)
                aura_db.save_user_settings(uid, settings)
        elif k_bound and k_bound != uname:
            tier_id = "tier_0"
            if uid is not None and "membership" in settings:
                settings.pop("membership", None)
                aura_db.save_user_settings(uid, settings)
        elif k_exp is not None and k_exp <= now_ts:
            if k_status != "expired":
                aura_db.update_subscription_key(db_key["key_code"], {"status": "expired"})
            old_name = get_tier_spec(db_key.get("tier_id", "tier_3"))["name"]
            expired_notice = f"Your {old_name} subscription expired on {_fmt_date(k_exp)}. Message {SUBSCRIPTION_CONTACT['whatsapp_display']} to renew your key."
            tier_id = "tier_0"
            if uid is not None and "membership" in settings:
                settings.pop("membership", None)
                aura_db.save_user_settings(uid, settings)
        elif k_status == "active" and (k_exp is None or k_exp > now_ts):
            # Sync live tier/expiry (picks up instant Admin renewals, free gifts or plan upgrades!)
            synced_tier = normalize_tier_id(db_key.get("tier_id", "tier_3"))
            tier_id = synced_tier
            k_dur_days = int(db_key.get("duration_days") or 20)
            k_dur_secs = int(db_key["duration_seconds"]) if db_key.get("duration_seconds") else (k_dur_days * SECONDS_PER_DAY)
            mem = {
                "tier_id": synced_tier,
                "key_slot": db_key["key_code"],
                "key_code": db_key["key_code"],
                "activated_at": float(db_key.get("activated_at") or now_ts),
                "expires_at": k_exp,
                "duration_days": k_dur_days,
                "duration_seconds": k_dur_secs,
                "is_gift": bool(db_key.get("is_gift")),
            }
            if uid is not None and settings.get("membership") != mem:
                settings["membership"] = mem
                aura_db.save_user_settings(uid, settings)

    # Also enforce expiry stored directly on mem (e.g. cold serverless without DB row)
    expires_at = float(mem["expires_at"]) if mem.get("expires_at") is not None else None
    if tier_id != "tier_0" and expires_at is not None and expires_at <= now_ts:
        old_name = get_tier_spec(tier_id)["name"]
        expired_notice = f"Your {old_name} subscription expired on {_fmt_date(expires_at)}. Message {SUBSCRIPTION_CONTACT['whatsapp_display']} to renew your key."
        tier_id = "tier_0"
        expires_at = None
        if uid is not None and "membership" in settings:
            settings.pop("membership", None)
            aura_db.save_user_settings(uid, settings)

    spec = get_tier_spec(tier_id)
    activated_at = float(mem.get("activated_at") or 0) if tier_id != "tier_0" else None
    key_slot = str(mem.get("key_slot") or "") if tier_id != "tier_0" else ""
    active_key_code = str(mem.get("key_code") or "") if tier_id != "tier_0" else ""
    is_gift = bool(mem.get("is_gift", False)) if tier_id != "tier_0" else False
    seconds_left = max(0, int(expires_at - now_ts)) if (tier_id != "tier_0" and expires_at) else 0
    days_remaining = round(seconds_left / SECONDS_PER_DAY, 1) if seconds_left > 0 else 0
    days_remaining_floor = int(seconds_left // SECONDS_PER_DAY) if seconds_left > 0 else 0
    days_remaining_ceil = int((seconds_left + SECONDS_PER_DAY - 1) // SECONDS_PER_DAY) if seconds_left > 0 else 0
    hours_remaining = (seconds_left % SECONDS_PER_DAY) // 3600 if seconds_left > 0 else 0
    countdown_label = format_countdown(seconds_left) if (tier_id != "tier_0" and expires_at) else ""

    proof = (
        build_membership_proof(
            uname,
            tier_id,
            key_slot,
            activated_at or now_ts,
            expires_at=expires_at,
            key_code=active_key_code,
        )
        if tier_id != "tier_0"
        else ""
    )

    return {
        **spec,
        "activated_at": activated_at,
        "expires_at": expires_at if tier_id != "tier_0" else None,
        "expires_label": _fmt_datetime(expires_at) if (tier_id != "tier_0" and expires_at and seconds_left < SECONDS_PER_DAY) else (_fmt_date(expires_at) if (tier_id != "tier_0" and expires_at) else ""),
        "seconds_remaining": seconds_left if tier_id != "tier_0" else 0,
        "countdown_label": countdown_label,
        "days_remaining": days_remaining if tier_id != "tier_0" else 0,
        "days_remaining_floor": days_remaining_floor if tier_id != "tier_0" else 0,
        "days_remaining_int": days_remaining_ceil if tier_id != "tier_0" else 0,
        "hours_remaining": hours_remaining if tier_id != "tier_0" else 0,
        "subscription_active": tier_id != "tier_0",
        "is_gift": is_gift,
        "key_slot": key_slot,
        "key_code": active_key_code,
        "key_code_masked": _mask_key_code(active_key_code) if active_key_code else "",
        "membership_proof": proof,
        "expired_notice": expired_notice or disabled_notice,
        "aura_rules": str(settings.get("aura_rules") or ""),
    }


def activate_membership_key(user: Dict[str, Any], raw_key: str) -> Dict[str, Any]:
    """
    Validates a dynamic or hashed subscription key, enforces admin kill-switch,
    exact second-precision expiry window (minutes/hours/days), and single-account binding,
    activates the plan, and returns the special subscriber welcome payload.
    """
    match = lookup_activation_key(raw_key)
    if not match:
        return {
            "success": False,
            "error": f"Invalid subscription key. Message {SUBSCRIPTION_CONTACT['whatsapp_display']} on WhatsApp to get a valid AURA key.",
        }

    uid = int(user["id"])
    uname = str(user.get("username") or "").strip().lower()
    tier_id = normalize_tier_id(match["tier_id"])
    key_code = str(match["key_code"]).strip().upper()
    key_hash = str(match["key_hash"])
    duration_days = max(1, int(match.get("duration_days") or MEMBERSHIP_TIERS[tier_id].get("duration_days") or 20))
    duration_seconds = max(60, int(match.get("duration_seconds") or (duration_days * SECONDS_PER_DAY)))
    duration_label = format_duration_seconds(duration_seconds)
    is_gift = bool(match.get("is_gift", False))
    db_row = match.get("db_row")
    now_ts = time.time()

    if db_row:
        status = str(db_row.get("status") or "active").lower()
        if status == "disabled":
            return {
                "success": False,
                "error": f"This key has been deactivated by the administrator. Message {SUBSCRIPTION_CONTACT['whatsapp_display']} to reactivate or renew.",
            }
        bound_u = str(db_row.get("bound_username") or "").strip().lower()
        if bound_u and bound_u != uname:
            return {
                "success": False,
                "error": "This subscription key is already bound to another AURA account.",
            }
        existing_exp = float(db_row["expires_at"]) if db_row.get("expires_at") is not None else None
        if status == "expired" or (existing_exp is not None and existing_exp <= now_ts):
            if status != "expired":
                aura_db.update_subscription_key(key_code, {"status": "expired"})
            return {
                "success": False,
                "error": f"This key expired on {_fmt_datetime(existing_exp) or _fmt_date(existing_exp)}. Message {SUBSCRIPTION_CONTACT['whatsapp_display']} to renew your same key.",
            }
        # If key already has a future expires_at (e.g. fixed_now timer or renewed key), preserve it; otherwise start clock now!
        expires_at = existing_exp if (existing_exp and existing_exp > now_ts) else (now_ts + duration_seconds)
        activated_at = float(db_row.get("activated_at") or now_ts)
        is_gift = bool(db_row.get("is_gift", is_gift))
        aura_db.update_subscription_key(
            key_code,
            {
                "status": "active",
                "bound_user_id": uid,
                "bound_username": uname,
                "activated_at": activated_at,
                "expires_at": expires_at,
            },
        )
    else:
        activated_at = now_ts
        expires_at = now_ts + duration_seconds
        aura_db.upsert_subscription_key(
            key_code=key_code,
            key_hash=key_hash,
            tier_id=tier_id,
            duration_days=duration_days,
            duration_seconds=duration_seconds,
            is_gift=is_gift,
            status="active",
            bound_user_id=uid,
            bound_username=uname,
            activated_at=activated_at,
            expires_at=expires_at,
            created_by=ADMIN_OWNER_USERNAME,
            note="Activated on account",
        )

    settings = aura_db.get_user_settings_dict(uid)
    settings["membership"] = {
        "tier_id": tier_id,
        "key_slot": match["slot"],
        "key_code": key_code,
        "key_hash_prefix": key_hash[:12],
        "activated_at": activated_at,
        "expires_at": expires_at,
        "duration_days": duration_days,
        "duration_seconds": duration_seconds,
        "is_gift": is_gift,
    }
    aura_db.save_user_settings(uid, settings)
    aura_db.record_membership_activation(uid, uname, key_hash, tier_id)

    resolved = resolve_user_membership(user)
    quota = get_user_quota_status(user, resolved)
    spec = get_tier_spec(tier_id)
    welcome_payload = {
        "plan_id": tier_id,
        "plan_number": spec["plan_number"],
        "plan_name": spec["name"],
        "badge": spec["badge"],
        "accent": spec["accent"],
        "theme": spec["theme"],
        "price_label": "FREE GIFT" if is_gift else spec["price_label"],
        "duration_days": duration_days,
        "duration_label": duration_label,
        "expires_label": resolved["expires_label"],
        "countdown_label": resolved["countdown_label"],
        "daily_limit_label": "Unlimited Chats / Day" if spec["unlimited"] else f"{spec['daily_limit']} Chats / Day",
        "feature_coverage": spec["feature_coverage"],
        "unlocked_features": spec["features"],
        "username": user.get("display_name") or user.get("username") or "Member",
        "is_gift": is_gift,
    }
    return {
        "success": True,
        "message": f"{resolved['name']} activated for {duration_label} (expires {resolved['expires_label']}).",
        "membership": resolved,
        "quota": quota,
        "welcome": welcome_payload,
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
            "error": "Persistent .aura-rules engineering memory requires AURA Sovereign (Plan 1) or higher.",
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
    rank = int(membership.get("rank", 0))
    parts: List[str] = []

    if rank >= 5:
        parts.append(
            "[AURA APEX OMNIS · PLAN 3 PLATINUM ENGINEERING ENGINE]\n"
            "You are operating at Apex Omnis capacity — an institutional autonomous polyglot software engineer across 20+ languages "
            "(Python, TypeScript, JavaScript, React, Rust, Go, Java, C/C++, C#, SQL, Kotlin, Swift, Bash, Docker/K8s).\n"
            "Standards: Zero placeholder comments ('TODO', 'pass', '...'), full edge-case validation, crisp Big-O complexity proofs, "
            "security-by-default patterns, multi-file unified diffs when editing existing code, and runnable verification tests."
        )
    elif rank >= 4:
        parts.append(
            "[AURA TITAN · PLAN 2 AUTONOMOUS SUITE]\n"
            "Operate with multi-agent rigor (Architecture + Implementation + Security + QA). Flag OWASP/security pitfalls proactively "
            "and always provide explicit verification commands or runnable code blocks."
        )
    elif rank >= 3:
        parts.append(
            "[AURA SOVEREIGN · PLAN 1 PRO ENGINEERING]\n"
            "Deliver production-complete, self-verified implementations with clear error handling, unit tests, and architectural rationale."
        )

    rules = str(membership.get("aura_rules") or "").strip()
    if rank >= 3 and rules:
        parts.append(f"[USER .AURA-RULES ENGINEERING CONSTRAINTS]\n{rules[:3000]}")

    if rank >= 3 and context_files_block:
        parts.append(f"[ATTACHED WORKSPACE @FILE CONTEXT]\n{context_files_block[:14000]}")

    return "\n\n".join(parts)


# ===================================================================================
# EXCLUSIVE ADMIN KEY VAULT & GENERATOR (ONLY AUTHORIZED FOR `ig.ahmed.irl`)
# ===================================================================================

def is_key_admin_user(user: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(user, dict):
        return False
    uname = str(user.get("username") or "").strip().lower()
    allowed_admin = os.environ.get("AURA_KEY_ADMIN_USERNAME", ADMIN_OWNER_USERNAME).strip().lower() or ADMIN_OWNER_USERNAME
    return bool(uname) and hmac.compare_digest(uname, allowed_admin)


def _verify_admin_vault_password(password: str) -> bool:
    candidate = str(password or "")
    if not candidate:
        return False
    env_pw = os.environ.get("AURA_ADMIN_VAULT_PASSWORD", "").strip()
    if env_pw:
        return hmac.compare_digest(candidate, env_pw)
    digest = hashlib.sha256((ADMIN_VAULT_SALT + candidate).encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, DEFAULT_ADMIN_VAULT_HASH)


def _sign_admin_vault_token(canonical: str) -> str:
    return aura_db.compute_vault_signature("AURA_ADMIN_VAULT_TOK:" + canonical)


def unlock_admin_key_vault(user: Optional[Dict[str, Any]], password: str) -> Dict[str, Any]:
    if not is_key_admin_user(user):
        return {
            "success": False,
            "status": 403,
            "error": f"Forbidden: Admin Key Vault access is restricted exclusively to @{ADMIN_OWNER_USERNAME}.",
        }
    if not _verify_admin_vault_password(password):
        return {
            "success": False,
            "status": 403,
            "error": "Invalid Admin Key Vault password.",
        }
    now_ts = time.time()
    payload = {
        "u": str(user["username"]).strip().lower(),
        "iat": int(now_ts),
        "exp": int(now_ts + ADMIN_VAULT_TOKEN_TTL_SECONDS),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(canonical.encode("utf-8")).decode("ascii").rstrip("=")
    sig = _sign_admin_vault_token(canonical)
    token = f"aura_av1.{b64}.{sig}"
    return {
        "success": True,
        "status": 200,
        "admin_vault_token": token,
        "expires_at": payload["exp"],
        "admin_username": payload["u"],
    }


def verify_admin_vault_token(user: Optional[Dict[str, Any]], token: str) -> bool:
    if not is_key_admin_user(user):
        return False
    raw = str(token or "").strip()
    if not raw.startswith("aura_av1."):
        return False
    parts = raw.split(".")
    if len(parts) != 3:
        return False
    _, b64, sig = parts
    try:
        pad = "=" * ((4 - len(b64) % 4) % 4)
        canonical = base64.urlsafe_b64decode((b64 + pad).encode("ascii")).decode("utf-8")
        if not hmac.compare_digest(_sign_admin_vault_token(canonical), sig):
            return False
        data = json.loads(canonical)
        if not isinstance(data, dict):
            return False
        uname = str(user.get("username") or "").strip().lower()
        if str(data.get("u", "")).lower() != uname:
            return False
        if float(data.get("exp", 0)) <= time.time():
            return False
        return True
    except Exception:
        return False


def _enrich_admin_key_row(row: Dict[str, Any], now_ts: Optional[float] = None) -> Dict[str, Any]:
    now = now_ts if now_ts is not None else time.time()
    tier_id = normalize_tier_id(row.get("tier_id", "tier_3"))
    spec = get_tier_spec(tier_id)
    raw_status = str(row.get("status") or "active").lower()
    exp = float(row["expires_at"]) if row.get("expires_at") is not None else None
    bound_u = str(row.get("bound_username") or "").strip()
    dur_days = int(row.get("duration_days") or spec.get("duration_days") or 20)
    dur_secs = int(row["duration_seconds"]) if row.get("duration_seconds") else (dur_days * SECONDS_PER_DAY)
    timer_mode = "fixed_now" if str(row.get("timer_mode") or "").lower() == "fixed_now" else "on_activation"
    is_gift = bool(row.get("is_gift", False))

    if raw_status == "disabled":
        effective = "disabled"
    elif exp is not None and exp <= now:
        effective = "expired"
        if raw_status != "expired":
            aura_db.update_subscription_key(row["key_code"], {"status": "expired"})
    elif bound_u:
        effective = "active"
    else:
        effective = "unused"

    has_live_timer = exp is not None and effective in ("active", "unused") and exp > now
    secs_left = max(0, int(exp - now)) if has_live_timer else 0
    days_left = round(secs_left / SECONDS_PER_DAY, 1) if secs_left > 0 else 0
    return {
        "key_code": row["key_code"],
        "tier_id": tier_id,
        "plan_number": spec["plan_number"],
        "plan_name": spec["name"],
        "badge": spec["badge"],
        "price_label": "FREE GIFT" if is_gift else spec["price_label"],
        "daily_limit": spec["daily_limit"],
        "unlimited": spec["unlimited"],
        "duration_days": dur_days,
        "duration_seconds": dur_secs,
        "duration_label": format_duration_seconds(dur_secs),
        "timer_mode": timer_mode,
        "is_gift": is_gift,
        "status": effective,
        "raw_status": raw_status,
        "bound_username": bound_u,
        "activated_at": row.get("activated_at"),
        "expires_at": exp,
        "expires_label": _fmt_datetime(exp) if exp else "Starts on activation",
        "seconds_remaining": secs_left,
        "countdown_label": format_countdown(secs_left) if has_live_timer else ("Expired" if effective == "expired" else "Not started"),
        "days_left": days_left,
        "note": str(row.get("note") or ""),
        "renew_count": int(row.get("renew_count") or 0),
        "created_at": row.get("created_at"),
        "created_label": _fmt_datetime(row.get("created_at")),
    }


def admin_generate_keys(
    tier_id: str,
    duration_days: Optional[int] = None,
    count: int = 1,
    note: str = "",
    created_by: str = ADMIN_OWNER_USERNAME,
    duration_value: Optional[int] = None,
    duration_unit: Optional[str] = None,
    timer_mode: str = "on_activation",
    is_gift: bool = False,
    target_username: str = "",
) -> Dict[str, Any]:
    norm_tier = normalize_tier_id(tier_id)
    if norm_tier not in PAID_TIER_ORDER:
        return {"success": False, "error": "Select Plan 1 (Sovereign), Plan 2 (Titan), or Plan 3 (Apex Omnis)."}
    spec = get_tier_spec(norm_tier)
    default_days = int(spec.get("duration_days") or 20)
    dur_secs, approx_days, unit_code, unit_val, dur_label = resolve_duration_spec(
        duration_days=duration_days,
        duration_value=duration_value,
        duration_unit=duration_unit,
        default_days=default_days,
    )
    t_mode = "fixed_now" if str(timer_mode or "").strip().lower() == "fixed_now" else "on_activation"
    target_u = str(target_username or "").strip().lstrip("@").lower()
    target_row = None
    if target_u:
        target_row = aura_db.get_user_by_username(target_u)
        if not target_row:
            return {"success": False, "error": f"User '@{target_u}' not found. Ask them to register/login first."}
        qty = 1
    else:
        qty = max(1, min(25, int(count or 1)))

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    created: List[Dict[str, Any]] = []
    now_ts = time.time()
    clean_note = str(note or "").strip()[:200]
    if is_gift and not clean_note:
        clean_note = "Free Gift from Admin"

    for _ in range(qty):
        nonce = "".join(secrets.choice(alphabet) for _ in range(6))
        code = format_dynamic_key(
            norm_tier,
            approx_days,
            nonce,
            duration_value=unit_val if unit_code != "D" else None,
            duration_unit=unit_code,
        )
        key_hash = hash_activation_key(code)
        exp_ts = (now_ts + dur_secs) if (t_mode == "fixed_now" or target_row is not None) else None
        act_ts = now_ts if target_row is not None else None
        row = aura_db.upsert_subscription_key(
            key_code=code,
            key_hash=key_hash,
            tier_id=norm_tier,
            duration_days=approx_days,
            duration_seconds=dur_secs,
            timer_mode=t_mode,
            is_gift=bool(is_gift),
            status="active",
            bound_user_id=int(target_row["id"]) if target_row else None,
            bound_username=target_u if target_row else "",
            activated_at=act_ts,
            expires_at=exp_ts,
            created_by=created_by,
            note=clean_note,
        )
        if target_row is not None and exp_ts is not None:
            aura_db.update_user_membership_by_username(
                target_u,
                {
                    "tier_id": norm_tier,
                    "key_slot": code,
                    "key_code": code,
                    "key_hash_prefix": key_hash[:12],
                    "activated_at": now_ts,
                    "expires_at": exp_ts,
                    "duration_days": approx_days,
                    "duration_seconds": dur_secs,
                    "is_gift": bool(is_gift),
                },
            )
            aura_db.record_membership_activation(int(target_row["id"]), target_u, key_hash, norm_tier)
        created.append(_enrich_admin_key_row(row))

    action_tag = "gift_key_created" if is_gift else "key_generated"
    aura_db.record_admin_audit(
        created_by,
        action_tag,
        target=f"@{target_u}" if target_u else (created[0]["key_code"] if len(created) == 1 else f"{len(created)} keys"),
        details=f"{spec['name']} · {dur_label} · mode={t_mode}" + (f" · {clean_note}" if clean_note else ""),
    )
    return {
        "success": True,
        "generated_count": len(created),
        "keys": created,
        "message": (
            f"Activated {'Free Gift ' if is_gift else ''}{spec['name']} on @{target_u} for {dur_label}."
            if target_u
            else f"Generated {len(created)} {'Free Gift ' if is_gift else ''}{spec['name']} key(s) valid for {dur_label}."
        ),
    }


def admin_list_keys(status_filter: str = "all", search: str = "") -> Dict[str, Any]:
    now_ts = time.time()
    raw_rows = aura_db.list_subscription_keys(limit=500)
    enriched = [_enrich_admin_key_row(r, now_ts=now_ts) for r in raw_rows]
    summary = {
        "total": len(enriched),
        "active": sum(1 for k in enriched if k["status"] == "active"),
        "unused": sum(1 for k in enriched if k["status"] == "unused"),
        "expired": sum(1 for k in enriched if k["status"] == "expired"),
        "disabled": sum(1 for k in enriched if k["status"] == "disabled"),
    }
    sf = str(status_filter or "all").strip().lower()
    q = str(search or "").strip().lower()
    filtered = []
    for k in enriched:
        if sf != "all" and k["status"] != sf:
            continue
        if q:
            hay = f"{k['key_code']} {k['bound_username']} {k['plan_name']} {k['note']}".lower()
            if q not in hay:
                continue
        filtered.append(k)
    return {
        "success": True,
        "summary": summary,
        "keys": filtered,
        "tiers": [get_tier_spec(tid) for tid in PAID_TIER_ORDER],
    }


def admin_renew_key(
    key_code: str,
    duration_days: Optional[int] = None,
    tier_id: Optional[str] = None,
    note: Optional[str] = None,
    duration_value: Optional[int] = None,
    duration_unit: Optional[str] = None,
    admin_username: str = ADMIN_OWNER_USERNAME,
) -> Dict[str, Any]:
    norm_code = normalize_activation_key(key_code)
    row = aura_db.get_subscription_key_by_code(norm_code)
    if not row:
        return {"success": False, "error": f"Subscription key '{norm_code}' not found."}

    target_tier = normalize_tier_id(tier_id) if tier_id else normalize_tier_id(row["tier_id"])
    if target_tier not in PAID_TIER_ORDER:
        target_tier = normalize_tier_id(row["tier_id"])
    spec = get_tier_spec(target_tier)
    add_secs, add_days, _, _, dur_label = resolve_duration_spec(
        duration_days=duration_days,
        duration_value=duration_value,
        duration_unit=duration_unit,
        default_days=int(spec.get("duration_days") or 20),
    )

    now_ts = time.time()
    prev_exp = float(row["expires_at"]) if row.get("expires_at") is not None else 0.0
    was_active = str(row.get("status") or "").lower() == "active" and prev_exp > now_ts
    base_ts = prev_exp if was_active else now_ts
    new_exp = base_ts + add_secs
    new_renew_count = int(row.get("renew_count") or 0) + 1

    fields: Dict[str, Any] = {
        "tier_id": target_tier,
        "duration_days": add_days,
        "duration_seconds": add_secs,
        "status": "active",
        "expires_at": new_exp,
        "renew_count": new_renew_count,
    }
    if not row.get("activated_at") and row.get("bound_username"):
        fields["activated_at"] = now_ts
    if note is not None and str(note).strip():
        fields["note"] = str(note).strip()[:200]

    updated = aura_db.update_subscription_key(norm_code, fields)
    bound_u = str((updated or {}).get("bound_username") or "").strip().lower()
    if bound_u:
        aura_db.update_user_membership_by_username(
            bound_u,
            {
                "tier_id": target_tier,
                "key_slot": norm_code,
                "key_code": norm_code,
                "key_hash_prefix": str((updated or {}).get("key_hash") or "")[:12],
                "activated_at": float((updated or {}).get("activated_at") or now_ts),
                "expires_at": new_exp,
                "duration_days": add_days,
                "duration_seconds": add_secs,
                "is_gift": bool((updated or {}).get("is_gift", False)),
            },
        )
    enriched = _enrich_admin_key_row(updated or row)
    aura_db.record_admin_audit(
        admin_username,
        "key_renewed",
        target=f"{norm_code}" + (f" (@{bound_u})" if bound_u else ""),
        details=f"{spec['name']} · +{dur_label} · exp {enriched['expires_label']}",
    )
    return {
        "success": True,
        "message": f"Key {norm_code} renewed on {spec['name']} for +{dur_label} (expires {enriched['expires_label']}).",
        "key": enriched,
    }


def admin_toggle_key_status(key_code: str, disable: bool, admin_username: str = ADMIN_OWNER_USERNAME) -> Dict[str, Any]:
    norm_code = normalize_activation_key(key_code)
    row = aura_db.get_subscription_key_by_code(norm_code)
    if not row:
        return {"success": False, "error": f"Subscription key '{norm_code}' not found."}
    now_ts = time.time()
    bound_u = str(row.get("bound_username") or "").strip().lower()
    if disable:
        updated = aura_db.update_subscription_key(norm_code, {"status": "disabled"})
        if bound_u:
            aura_db.update_user_membership_by_username(bound_u, None)
        aura_db.record_admin_audit(admin_username, "key_disabled", target=norm_code, details=f"bound=@{bound_u}" if bound_u else "unclaimed")
        return {
            "success": True,
            "message": f"Key {norm_code} disabled immediately." + (f" Account @{bound_u} returned to Standard." if bound_u else ""),
            "key": _enrich_admin_key_row(updated or row),
        }

    # Re-enabling a disabled key
    exp = float(row["expires_at"]) if row.get("expires_at") is not None else None
    days = max(1, int(row.get("duration_days") or 20))
    dur_secs = int(row["duration_seconds"]) if row.get("duration_seconds") else (days * SECONDS_PER_DAY)
    if bound_u and (exp is None or exp <= now_ts):
        exp = now_ts + dur_secs
    fields: Dict[str, Any] = {"status": "active"}
    if exp is not None:
        fields["expires_at"] = exp
    updated = aura_db.update_subscription_key(norm_code, fields)
    if bound_u and exp:
        tier_id = normalize_tier_id(row["tier_id"])
        aura_db.update_user_membership_by_username(
            bound_u,
            {
                "tier_id": tier_id,
                "key_slot": norm_code,
                "key_code": norm_code,
                "key_hash_prefix": str(row.get("key_hash") or "")[:12],
                "activated_at": float(row.get("activated_at") or now_ts),
                "expires_at": exp,
                "duration_days": days,
                "duration_seconds": dur_secs,
                "is_gift": bool(row.get("is_gift", False)),
            },
        )
    aura_db.record_admin_audit(admin_username, "key_enabled", target=norm_code, details=f"bound=@{bound_u}" if bound_u else "unclaimed")
    return {
        "success": True,
        "message": f"Key {norm_code} re-enabled.",
        "key": _enrich_admin_key_row(updated or row),
    }


def admin_unbind_key(key_code: str, admin_username: str = ADMIN_OWNER_USERNAME) -> Dict[str, Any]:
    norm_code = normalize_activation_key(key_code)
    row = aura_db.get_subscription_key_by_code(norm_code)
    if not row:
        return {"success": False, "error": f"Subscription key '{norm_code}' not found."}
    old_user = str(row.get("bound_username") or "").strip().lower()
    if old_user:
        aura_db.update_user_membership_by_username(old_user, None)
    updated = aura_db.update_subscription_key(
        norm_code,
        {"bound_user_id": None, "bound_username": "", "activated_at": None, "expires_at": None, "status": "active"},
    )
    aura_db.record_admin_audit(admin_username, "key_unbound", target=norm_code, details=f"previous=@{old_user}" if old_user else "")
    return {
        "success": True,
        "message": f"Key {norm_code} unbound and ready for activation.",
        "key": _enrich_admin_key_row(updated or row),
    }


def admin_delete_key(key_code: str, admin_username: str = ADMIN_OWNER_USERNAME) -> Dict[str, Any]:
    norm_code = normalize_activation_key(key_code)
    row = aura_db.get_subscription_key_by_code(norm_code)
    if not row:
        return {"success": False, "error": f"Subscription key '{norm_code}' not found."}
    old_user = str(row.get("bound_username") or "").strip().lower()
    if old_user:
        aura_db.update_user_membership_by_username(old_user, None)
    deleted = aura_db.delete_subscription_key(norm_code)
    if not deleted:
        return {"success": False, "error": f"Could not delete key '{norm_code}'."}
    aura_db.record_admin_audit(admin_username, "key_deleted", target=norm_code, details=f"previous=@{old_user}" if old_user else "")
    return {
        "success": True,
        "message": f"Key {norm_code} permanently deleted." + (f" @{old_user} returned to Standard." if old_user else ""),
    }


# ===================================================================================
# EXCLUSIVE ADMIN USERS COMMAND CENTER (REAL LOGINS, BAN, FREE GIFT, RENEW, AUDIT)
# ===================================================================================

def admin_get_users_overview(search: str = "", filter_mode: str = "all") -> Dict[str, Any]:
    now_ts = time.time()
    raw_users = aura_db.list_all_users_for_admin(limit=500)
    keys_info = admin_list_keys(status_filter="all", search="")
    allowed_admin = os.environ.get("AURA_KEY_ADMIN_USERNAME", ADMIN_OWNER_USERNAME).strip().lower() or ADMIN_OWNER_USERNAME

    enriched_users: List[Dict[str, Any]] = []
    online_cutoff = now_ts - (10 * 60)
    active_24h_cutoff = now_ts - SECONDS_PER_DAY

    for u in raw_users:
        uname = str(u.get("username") or "").strip().lower()
        mem = resolve_user_membership(u)
        last_seen = float(u["last_seen_at"]) if u.get("last_seen_at") else (float(u["last_login_at"]) if u.get("last_login_at") else None)
        last_login = float(u["last_login_at"]) if u.get("last_login_at") else None
        is_online = bool(last_seen and last_seen >= online_cutoff and not bool(u.get("is_banned")))
        is_active_24h = bool(last_seen and last_seen >= active_24h_cutoff)
        is_banned = bool(u.get("is_banned"))
        is_owner = hmac.compare_digest(uname, allowed_admin)
        sub_active = bool(mem.get("subscription_active"))
        enriched_users.append({
            "id": int(u["id"]),
            "username": uname,
            "display_name": str(u.get("display_name") or uname.capitalize()),
            "role": str(u.get("role") or "user"),
            "is_owner": is_owner,
            "is_banned": is_banned,
            "ban_reason": str(u.get("ban_reason") or ""),
            "banned_at": u.get("banned_at"),
            "created_at": str(u.get("created_at") or ""),
            "last_login_at": last_login,
            "last_login_label": _fmt_relative_ago(last_login, now_ts=now_ts),
            "last_seen_at": last_seen,
            "last_seen_label": _fmt_relative_ago(last_seen, now_ts=now_ts),
            "login_count": max(1 if last_login else 0, int(u.get("login_count") or 0)),
            "last_device": str(u.get("last_device") or "Web Client"),
            "is_online": is_online,
            "is_active_24h": is_active_24h,
            "chats_24h": int(u.get("chats_24h") or 0),
            "subscription_active": sub_active,
            "tier_id": mem["id"],
            "plan_name": mem["name"],
            "plan_short": mem["short_name"],
            "plan_badge": mem["badge"],
            "daily_limit": mem["daily_limit"],
            "unlimited": bool(mem["unlimited"]),
            "is_gift": bool(mem.get("is_gift", False)),
            "key_code": str(mem.get("key_code") or ""),
            "expires_at": mem.get("expires_at"),
            "expires_label": str(mem.get("expires_label") or ""),
            "seconds_remaining": int(mem.get("seconds_remaining") or 0),
            "countdown_label": str(mem.get("countdown_label") or ""),
        })

    summary = {
        "total_users": len(enriched_users),
        "online_now": sum(1 for x in enriched_users if x["is_online"]),
        "active_24h": sum(1 for x in enriched_users if x["is_active_24h"]),
        "subscribed_users": sum(1 for x in enriched_users if x["subscription_active"] and not x["is_banned"]),
        "free_users": sum(1 for x in enriched_users if not x["subscription_active"] and not x["is_banned"]),
        "banned_users": sum(1 for x in enriched_users if x["is_banned"]),
        "keys": keys_info["summary"],
    }

    fm = str(filter_mode or "all").strip().lower()
    q = str(search or "").strip().lstrip("@").lower()
    filtered = []
    for x in enriched_users:
        if fm == "online" and not x["is_online"]:
            continue
        elif fm == "subscribed" and not x["subscription_active"]:
            continue
        elif fm == "free" and (x["subscription_active"] or x["is_banned"]):
            continue
        elif fm == "banned" and not x["is_banned"]:
            continue
        if q:
            hay = f"{x['username']} {x['display_name']} {x['plan_name']} {x['last_device']} {x['key_code']}".lower()
            if q not in hay:
                continue
        filtered.append(x)

    return {
        "success": True,
        "summary": summary,
        "users": filtered,
        "storage_status": aura_db.get_storage_status(),
        "audit_logs": admin_get_audit_logs(limit=40)["logs"],
        "tiers": [get_tier_spec(tid) for tid in PAID_TIER_ORDER],
    }


def admin_gift_user_subscription(
    username: str,
    tier_id: str = "tier_5",
    duration_days: Optional[int] = None,
    duration_value: Optional[int] = None,
    duration_unit: Optional[str] = None,
    note: str = "",
    admin_username: str = ADMIN_OWNER_USERNAME,
) -> Dict[str, Any]:
    target_u = str(username or "").strip().lstrip("@").lower()
    if not target_u:
        return {"success": False, "error": "Target username is required."}
    user_row = aura_db.get_user_by_username(target_u)
    if not user_row:
        return {"success": False, "error": f"User '@{target_u}' not found."}
    clean_note = str(note or "").strip() or f"Free Gift from @{admin_username}"
    return admin_generate_keys(
        tier_id=tier_id,
        duration_days=duration_days,
        duration_value=duration_value,
        duration_unit=duration_unit,
        count=1,
        note=clean_note,
        created_by=admin_username,
        timer_mode="fixed_now",
        is_gift=True,
        target_username=target_u,
    )


def admin_renew_user_subscription(
    username: str,
    tier_id: Optional[str] = None,
    duration_days: Optional[int] = None,
    duration_value: Optional[int] = None,
    duration_unit: Optional[str] = None,
    note: Optional[str] = None,
    admin_username: str = ADMIN_OWNER_USERNAME,
) -> Dict[str, Any]:
    target_u = str(username or "").strip().lstrip("@").lower()
    if not target_u:
        return {"success": False, "error": "Target username is required."}
    user_row = aura_db.get_user_by_username(target_u)
    if not user_row:
        return {"success": False, "error": f"User '@{target_u}' not found."}

    # Look for existing key bound to this user first
    existing_key = None
    mem_settings = (user_row.get("settings") or {}).get("membership") if isinstance(user_row.get("settings"), dict) else None
    if isinstance(mem_settings, dict) and mem_settings.get("key_code"):
        existing_key = aura_db.get_subscription_key_by_code(str(mem_settings["key_code"]))
    if not existing_key:
        for krow in aura_db.list_subscription_keys(limit=500):
            if str(krow.get("bound_username") or "").strip().lower() == target_u:
                existing_key = krow
                break

    if existing_key:
        return admin_renew_key(
            key_code=existing_key["key_code"],
            duration_days=duration_days,
            duration_value=duration_value,
            duration_unit=duration_unit,
            tier_id=tier_id or existing_key.get("tier_id"),
            note=note,
            admin_username=admin_username,
        )

    # No prior key exists — grant & bind a renewed subscription immediately!
    chosen_tier = normalize_tier_id(tier_id or "tier_3")
    if chosen_tier not in PAID_TIER_ORDER:
        chosen_tier = "tier_3"
    return admin_generate_keys(
        tier_id=chosen_tier,
        duration_days=duration_days,
        duration_value=duration_value,
        duration_unit=duration_unit,
        count=1,
        note=str(note or "Admin Direct Renewal").strip(),
        created_by=admin_username,
        timer_mode="fixed_now",
        is_gift=False,
        target_username=target_u,
    )


def admin_revoke_user_subscription(username: str, admin_username: str = ADMIN_OWNER_USERNAME) -> Dict[str, Any]:
    target_u = str(username or "").strip().lstrip("@").lower()
    if not target_u:
        return {"success": False, "error": "Target username is required."}
    user_row = aura_db.get_user_by_username(target_u)
    if not user_row:
        return {"success": False, "error": f"User '@{target_u}' not found."}
    disabled_count = 0
    for krow in aura_db.list_subscription_keys(limit=500):
        if str(krow.get("bound_username") or "").strip().lower() == target_u and str(krow.get("status") or "").lower() == "active":
            aura_db.update_subscription_key(krow["key_code"], {"status": "disabled"})
            disabled_count += 1
    aura_db.update_user_membership_by_username(target_u, None)
    aura_db.record_admin_audit(
        admin_username,
        "subscription_revoked",
        target=f"@{target_u}",
        details=f"Disabled {disabled_count} active key(s) & returned to Standard.",
    )
    return {
        "success": True,
        "message": f"Subscription stopped for @{target_u}. Account returned to Free Standard.",
        "disabled_keys": disabled_count,
    }


def admin_set_user_ban(
    username: str,
    banned: bool,
    reason: str = "",
    admin_username: str = ADMIN_OWNER_USERNAME,
) -> Dict[str, Any]:
    target_u = str(username or "").strip().lstrip("@").lower()
    if not target_u:
        return {"success": False, "error": "Target username is required."}
    allowed_admin = os.environ.get("AURA_KEY_ADMIN_USERNAME", ADMIN_OWNER_USERNAME).strip().lower() or ADMIN_OWNER_USERNAME
    if banned and hmac.compare_digest(target_u, allowed_admin):
        return {"success": False, "error": f"Safety guard: Owner account @{allowed_admin} cannot be banned."}
    updated = aura_db.set_user_ban_status(target_u, banned=bool(banned), reason=reason)
    if not updated:
        return {"success": False, "error": f"User '@{target_u}' not found."}
    aura_db.record_admin_audit(
        admin_username,
        "user_banned" if banned else "user_unbanned",
        target=f"@{target_u}",
        details=str(reason or "").strip() if banned else "Account restored by admin",
    )
    return {
        "success": True,
        "message": (
            f"Account @{target_u} has been BANNED and all active sessions revoked immediately."
            if banned
            else f"Account @{target_u} has been UNBANNED and can log in again."
        ),
        "username": target_u,
        "is_banned": bool(banned),
        "ban_reason": str(updated.get("ban_reason") or ""),
    }


def admin_get_audit_logs(limit: int = 60) -> Dict[str, Any]:
    now_ts = time.time()
    rows = aura_db.list_admin_audit_logs(limit=limit)
    out = []
    for r in rows:
        ts = float(r.get("created_at") or now_ts)
        out.append({
            "id": int(r["id"]),
            "admin_username": str(r.get("admin_username") or ADMIN_OWNER_USERNAME),
            "action": str(r.get("action") or ""),
            "target": str(r.get("target") or ""),
            "details": str(r.get("details") or ""),
            "created_at": ts,
            "time_label": _fmt_datetime(ts),
            "ago_label": _fmt_relative_ago(ts, now_ts=now_ts),
        })
    return {"success": True, "logs": out}
