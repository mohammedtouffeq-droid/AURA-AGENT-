"""
AURA Production Permission & OS Security Gatekeeper
Provides per-user tenant-isolated approval queues, DB-backed cross-instance
state synchronization for serverless workers, and risk-tier classification.
"""

import secrets
import threading
import time
from enum import Enum
from typing import Any, Dict, List, Optional


class RiskLevel(str, Enum):
    SAFE = "SAFE"           # Auto-allowed (read-only, metrics, status)
    CAUTION = "CAUTION"     # Workspace file write, local package install, test runs
    CRITICAL = "CRITICAL"   # Elevated admin cmd, file deletion, registry, system modify, kill external process


class SecurityMode(str, Enum):
    PROMPT_HIGH_RISK = "PROMPT_HIGH_RISK"  # Prompt for CRITICAL, auto-allow SAFE & CAUTION
    PARANOID = "PARANOID"                  # Prompt for CAUTION and CRITICAL
    FULL_AUTONOMOUS = "FULL_AUTONOMOUS"    # Auto-allow actions within safety boundaries (admin/CLI only)


class PermissionManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.security_mode = SecurityMode.PROMPT_HIGH_RISK
        self.user_security_modes: Dict[int, SecurityMode] = {}
        self.session_allowlist = set()
        self.user_allowlists: Dict[int, set] = {}
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        self.request_events: Dict[str, threading.Event] = {}
        self.request_decisions: Dict[str, str] = {}
        self.history: List[Dict[str, Any]] = []
        self._history_lock = threading.Lock()

    def get_security_mode(self, user_id: Optional[int] = None) -> SecurityMode:
        if user_id is not None:
            return self.user_security_modes.get(int(user_id), SecurityMode.PROMPT_HIGH_RISK)
        return self.security_mode

    def set_security_mode(
        self,
        mode: str,
        user_id: Optional[int] = None,
        is_admin: bool = False,
    ) -> bool:
        if mode not in SecurityMode.__members__:
            return False
        resolved_mode = SecurityMode(mode)
        if user_id is not None:
            # Non-admin tenants cannot disable high-risk prompts via FULL_AUTONOMOUS
            if resolved_mode == SecurityMode.FULL_AUTONOMOUS and not is_admin:
                return False
            with self._lock:
                self.user_security_modes[int(user_id)] = resolved_mode
            return True
        self.security_mode = resolved_mode
        return True

    def classify_action(self, action_type: str, target: str, command: str = "") -> RiskLevel:
        """
        Classifies risk level based on action type, target path, and command string.
        """
        act = (action_type or "").lower()
        cmd = (command or "").lower()
        tgt = (target or "").lower()

        critical_patterns = [
            "rmdir", "remove-item", "del /f", "rm -rf", "format",
            "shutdown", "restart-computer", "stop-computer",
            "reg add", "reg delete", "set-itemproperty hklm",
            "net user", "net localgroup", "icacls", "takeown",
            "stop-process -force", "taskkill /f /im",
            "invoke-webrequest", "iex ", "invoke-expression", "encodedcommand",
        ]
        for pat in critical_patterns:
            if pat in cmd:
                return RiskLevel.CRITICAL

        if act in ["delete_file", "delete_directory", "kill_process", "admin_powershell", "modify_registry"]:
            return RiskLevel.CRITICAL

        if any(tgt.startswith(p) for p in ["c:\\windows", "c:\\program files", "c:\\users\\hp\\appdata\\local\\microsoft", "/etc", "/bin", "/usr"]):
            return RiskLevel.CRITICAL

        caution_patterns = [
            "pip install", "npm install", "git push", "git commit",
            "set-content", "new-item", "out-file", "echo >",
        ]
        for pat in caution_patterns:
            if pat in cmd:
                return RiskLevel.CAUTION

        if act in ["write_file", "create_file", "powershell_exec", "run_script"]:
            return RiskLevel.CAUTION

        if act in ["read_file", "list_files", "system_metrics", "get_process", "screen_capture"]:
            return RiskLevel.SAFE

        return RiskLevel.CAUTION

    # ------------------------------------------------------------------
    # SQLite-backed persistence helpers (serverless cross-worker sync)
    # ------------------------------------------------------------------
    @staticmethod
    def _db_upsert_request(req_data: Dict[str, Any]) -> None:
        try:
            import aura_db
            conn = aura_db.get_connection()
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO permission_requests
                    (id, user_id, action_type, target, command, details, risk, status, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                    """,
                    (
                        req_data["id"],
                        req_data.get("user_id"),
                        req_data["action_type"],
                        req_data["target"],
                        req_data.get("command", ""),
                        req_data.get("details", ""),
                        req_data["risk"],
                        float(req_data["timestamp"]),
                        float(req_data["timestamp"]) + float(req_data["expires_in"]),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

    @staticmethod
    def _db_get_request(req_id: str) -> Optional[Dict[str, Any]]:
        try:
            import aura_db
            conn = aura_db.get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, user_id, action_type, target, command, details, risk, status, created_at, expires_at FROM permission_requests WHERE id = ?",
                    (req_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
        except Exception:
            return None

    @staticmethod
    def _db_set_status(req_id: str, status: str) -> bool:
        try:
            import aura_db
            conn = aura_db.get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE permission_requests SET status = ?, decided_at = ? WHERE id = ?",
                    (status, time.time(), req_id),
                )
                conn.commit()
                return (cur.rowcount or 0) > 0
            finally:
                conn.close()
        except Exception:
            return False

    @staticmethod
    def _db_list_pending(user_id: Optional[int], now: float) -> List[Dict[str, Any]]:
        try:
            import aura_db
            conn = aura_db.get_connection()
            try:
                cur = conn.cursor()
                if user_id is not None:
                    cur.execute(
                        """
                        SELECT id, user_id, action_type, target, command, details, risk, created_at, expires_at
                        FROM permission_requests
                        WHERE status = 'PENDING' AND user_id = ? AND expires_at > ?
                        ORDER BY created_at ASC
                        """,
                        (int(user_id), now),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, user_id, action_type, target, command, details, risk, created_at, expires_at
                        FROM permission_requests
                        WHERE status = 'PENDING' AND user_id IS NULL AND expires_at > ?
                        ORDER BY created_at ASC
                        """,
                        (now,),
                    )
                out = []
                for row in cur.fetchall():
                    d = dict(row)
                    created_at = float(d.get("created_at") or now)
                    expires_at = float(d.get("expires_at") or now)
                    out.append({
                        "id": d["id"],
                        "user_id": d.get("user_id"),
                        "action_type": d["action_type"],
                        "target": d["target"],
                        "command": d.get("command") or "",
                        "details": d.get("details") or "",
                        "risk": d["risk"],
                        "timestamp": created_at,
                        "expires_in": max(0.0, expires_at - created_at),
                        "remaining_seconds": max(0, int(expires_at - now)),
                    })
                return out
            finally:
                conn.close()
        except Exception:
            return []

    def request_permission(
        self,
        action_type: str,
        target: str,
        command: str = "",
        details: str = "",
        timeout: float = 45.0,
        require_approval: bool = False,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates permission scoped to `user_id` (when provided).
        Forced-approval actions always wait for an explicit decision.
        """
        risk = self.classify_action(action_type, target, command)
        scoped_uid = int(user_id) if user_id is not None else None
        signature = f"{action_type}:{command.strip() if command else target.strip()}"

        with self._lock:
            allowlist = (
                self.user_allowlists.setdefault(scoped_uid, set())
                if scoped_uid is not None
                else self.session_allowlist
            )
            in_allowlist = signature in allowlist

        active_mode = self.get_security_mode(scoped_uid)

        if not require_approval and in_allowlist:
            self._log_history(action_type, target, command, risk, "ALLOW_SESSION_CACHED", user_id=scoped_uid)
            return {"granted": True, "reason": "session_allowlisted", "risk": risk.value}

        if not require_approval and active_mode == SecurityMode.FULL_AUTONOMOUS:
            self._log_history(action_type, target, command, risk, "ALLOW_AUTONOMOUS", user_id=scoped_uid)
            return {"granted": True, "reason": "full_autonomous_mode", "risk": risk.value}

        if not require_approval and risk == RiskLevel.SAFE:
            self._log_history(action_type, target, command, risk, "ALLOW_SAFE", user_id=scoped_uid)
            return {"granted": True, "reason": "safe_action", "risk": risk.value}

        if (
            not require_approval
            and risk == RiskLevel.CAUTION
            and active_mode == SecurityMode.PROMPT_HIGH_RISK
        ):
            self._log_history(action_type, target, command, risk, "ALLOW_CAUTION_POLICY", user_id=scoped_uid)
            return {"granted": True, "reason": "caution_auto_allowed", "risk": risk.value}

        req_id = secrets.token_hex(8)
        event = threading.Event()
        now = time.time()
        safe_timeout = max(0.2, min(float(timeout), 120.0))

        req_data = {
            "id": req_id,
            "user_id": scoped_uid,
            "action_type": action_type,
            "target": target,
            "command": command,
            "details": details,
            "risk": risk.value,
            "timestamp": now,
            "expires_in": safe_timeout,
        }

        with self._lock:
            self.pending_requests[req_id] = req_data
            self.request_events[req_id] = event

        self._db_upsert_request(req_data)

        # Wait in short slices so both local threading.Event and cross-instance DB decisions wake up promptly
        deadline = now + safe_timeout
        answered = False
        db_decision: Optional[str] = None
        while time.time() < deadline:
            remaining = max(0.01, min(0.25, deadline - time.time()))
            if event.wait(timeout=remaining):
                answered = True
                break
            row = self._db_get_request(req_id)
            if row and row.get("status") not in (None, "PENDING"):
                db_decision = str(row["status"])
                answered = True
                break

        with self._lock:
            decision = self.request_decisions.get(
                req_id,
                db_decision if db_decision else ("TIMEOUT" if not answered else "DENIED"),
            )
            self.pending_requests.pop(req_id, None)
            self.request_events.pop(req_id, None)
            self.request_decisions.pop(req_id, None)

        if decision == "TIMEOUT":
            self._db_set_status(req_id, "TIMEOUT")

        if decision == "ALLOW_ALWAYS" and not require_approval:
            with self._lock:
                target_allowlist = (
                    self.user_allowlists.setdefault(scoped_uid, set())
                    if scoped_uid is not None
                    else self.session_allowlist
                )
                target_allowlist.add(signature)
            granted = True
        elif decision in ["ALLOW_ONCE", "ALLOW_ALWAYS"]:
            granted = True
        else:
            granted = False

        self._log_history(action_type, target, command, risk, decision, user_id=scoped_uid)
        return {
            "granted": granted,
            "decision": decision,
            "reason": f"user_decision_{decision.lower()}",
            "risk": risk.value,
        }

    def respond_request(
        self,
        req_id: str,
        decision: str,
        user_id: Optional[int] = None,
    ) -> bool:
        """
        Records a user's decision after verifying strict tenant ownership.
        """
        if not req_id or not isinstance(req_id, str):
            return False
        norm_decision = (decision or "").upper().strip()
        if norm_decision not in ["ALLOW_ONCE", "ALLOW_ALWAYS", "DENY"]:
            norm_decision = "DENY"

        scoped_uid = int(user_id) if user_id is not None else None

        with self._lock:
            mem_req = self.pending_requests.get(req_id)
            if mem_req is not None:
                req_owner = mem_req.get("user_id")
                # Enforce strict tenant ownership whenever either side specifies a user_id
                if scoped_uid is not None and req_owner != scoped_uid:
                    return False
                if scoped_uid is None and req_owner is not None:
                    return False
                if req_id in self.request_events:
                    self.request_decisions[req_id] = norm_decision
                    self.request_events[req_id].set()
                    self._db_set_status(req_id, norm_decision)
                    return True

        # Cross-instance serverless fallback via SQLite
        db_req = self._db_get_request(req_id)
        if not db_req or db_req.get("status") != "PENDING":
            return False
        db_owner = db_req.get("user_id")
        if scoped_uid is not None and db_owner != scoped_uid:
            return False
        if scoped_uid is None and db_owner is not None:
            return False
        if float(db_req.get("expires_at") or 0) <= time.time():
            self._db_set_status(req_id, "TIMEOUT")
            return False
        return self._db_set_status(req_id, norm_decision)

    def get_pending(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        scoped_uid = int(user_id) if user_id is not None else None
        now = time.time()
        valid_by_id: Dict[str, Dict[str, Any]] = {}

        with self._lock:
            for rid, req in list(self.pending_requests.items()):
                if rid in self.request_decisions:
                    continue
                elapsed = now - req["timestamp"]
                if elapsed >= req["expires_in"]:
                    ev = self.request_events.pop(rid, None)
                    if ev:
                        self.request_decisions[rid] = "TIMEOUT"
                        ev.set()
                    self.pending_requests.pop(rid, None)
                    self._db_set_status(rid, "TIMEOUT")
                    continue

                req_owner = req.get("user_id")
                if scoped_uid is not None and req_owner != scoped_uid:
                    continue
                if scoped_uid is None and req_owner is not None:
                    continue

                req_copy = dict(req)
                req_copy["remaining_seconds"] = max(0, int(req["expires_in"] - elapsed))
                valid_by_id[rid] = req_copy

        for db_item in self._db_list_pending(scoped_uid, now):
            if db_item["id"] not in valid_by_id:
                valid_by_id[db_item["id"]] = db_item

        return list(valid_by_id.values())

    def get_history(self, user_id: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
        scoped_uid = int(user_id) if user_id is not None else None
        with self._history_lock:
            if scoped_uid is not None:
                filtered = [h for h in self.history if h.get("user_id") == scoped_uid]
            else:
                filtered = [h for h in self.history if h.get("user_id") is None]
            return filtered[-max(1, int(limit)):]

    def _log_history(self, action_type, target, command, risk, decision, user_id: Optional[int] = None):
        with self._history_lock:
            self.history.append({
                "timestamp": time.time(),
                "user_id": user_id,
                "action_type": action_type,
                "target": target,
                "command": command[:150] if command else "",
                "risk": risk.value,
                "decision": decision,
            })
            if len(self.history) > 200:
                self.history = self.history[-200:]


# Global Singleton Instance
permission_manager = PermissionManager()
