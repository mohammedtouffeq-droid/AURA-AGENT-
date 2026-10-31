"""
AURA Production Permission & OS Security Gatekeeper
Enables 100% full laptop access for autonomous execution
while providing interactive real-time approval notifications.
"""

import time
import uuid
import threading
from typing import Dict, Any, Optional, List
from enum import Enum

class RiskLevel(str, Enum):
    SAFE = "SAFE"           # Auto-allowed (read-only, metrics, status)
    CAUTION = "CAUTION"     # Workspace file write, local package install, test runs
    CRITICAL = "CRITICAL"   # Elevated admin cmd, file deletion, registry, system modify, kill external process

class SecurityMode(str, Enum):
    PROMPT_HIGH_RISK = "PROMPT_HIGH_RISK"  # Prompt for CRITICAL, auto-allow SAFE & CAUTION
    PARANOID = "PARANOID"                  # Prompt for CAUTION and CRITICAL
    FULL_AUTONOMOUS = "FULL_AUTONOMOUS"    # Auto-allow all actions within safety boundaries

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
        self.session_allowlist = set()
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        self.request_events: Dict[str, threading.Event] = {}
        self.request_decisions: Dict[str, str] = {}
        self.history: List[Dict[str, Any]] = []
        self._history_lock = threading.Lock()

    def set_security_mode(self, mode: str):
        if mode in SecurityMode.__members__:
            self.security_mode = SecurityMode(mode)
            return True
        return False

    def classify_action(self, action_type: str, target: str, command: str = "") -> RiskLevel:
        """
        Classifies risk level based on action type, target path, and command string.
        """
        act = action_type.lower()
        cmd = command.lower()
        tgt = target.lower()

        # Critical triggers
        critical_patterns = [
            "rmdir", "remove-item", "del /f", "rm -rf", "format",
            "shutdown", "restart-computer", "stop-computer",
            "reg add", "reg delete", "set-itemproperty hklm",
            "net user", "net localgroup", "icacls", "takeown",
            "stop-process -force", "taskkill /f /im"
        ]
        for pat in critical_patterns:
            if pat in cmd:
                return RiskLevel.CRITICAL

        if act in ["delete_file", "delete_directory", "kill_process", "admin_powershell", "modify_registry"]:
            return RiskLevel.CRITICAL

        # Target system path triggers
        if any(tgt.startswith(p) for p in ["c:\\windows", "c:\\program files", "c:\\users\\hp\\appdata\\local\\microsoft"]):
            return RiskLevel.CRITICAL

        # Caution triggers
        caution_patterns = [
            "pip install", "npm install", "git push", "git commit",
            "set-content", "new-item", "out-file", "echo >"
        ]
        for pat in caution_patterns:
            if pat in cmd:
                return RiskLevel.CAUTION

        if act in ["write_file", "create_file", "powershell_exec", "run_script"]:
            return RiskLevel.CAUTION

        # Safe read-only defaults
        if act in ["read_file", "list_files", "system_metrics", "get_process", "screen_capture"]:
            return RiskLevel.SAFE

        return RiskLevel.CAUTION

    def request_permission(
        self,
        action_type: str,
        target: str,
        command: str = "",
        details: str = "",
        timeout: float = 45.0,
        require_approval: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluates permission. Forced-approval actions always wait for a decision;
        other actions follow the selected risk policy.
        """
        risk = self.classify_action(action_type, target, command)

        # A forced-approval action must always be approved for this invocation.
        signature = f"{action_type}:{command.strip() if command else target.strip()}"
        if not require_approval and signature in self.session_allowlist:
            self._log_history(action_type, target, command, risk, "ALLOW_SESSION_CACHED")
            return {"granted": True, "reason": "session_allowlisted", "risk": risk.value}

        # Some workflows require per-action consent even when their risk would
        # normally be auto-allowed by the selected security mode.
        if not require_approval and self.security_mode == SecurityMode.FULL_AUTONOMOUS:
            self._log_history(action_type, target, command, risk, "ALLOW_AUTONOMOUS")
            return {"granted": True, "reason": "full_autonomous_mode", "risk": risk.value}

        if not require_approval and risk == RiskLevel.SAFE:
            self._log_history(action_type, target, command, risk, "ALLOW_SAFE")
            return {"granted": True, "reason": "safe_action", "risk": risk.value}

        if (
            not require_approval
            and risk == RiskLevel.CAUTION
            and self.security_mode == SecurityMode.PROMPT_HIGH_RISK
        ):
            self._log_history(action_type, target, command, risk, "ALLOW_CAUTION_POLICY")
            return {"granted": True, "reason": "caution_auto_allowed", "risk": risk.value}

        # Requires explicit user approval: register pending request
        req_id = uuid.uuid4().hex[:8]
        event = threading.Event()

        req_data = {
            "id": req_id,
            "action_type": action_type,
            "target": target,
            "command": command,
            "details": details,
            "risk": risk.value,
            "timestamp": time.time(),
            "expires_in": timeout
        }

        with self._lock:
            self.pending_requests[req_id] = req_data
            self.request_events[req_id] = event

        # Wait for user response
        answered = event.wait(timeout=timeout)

        with self._lock:
            decision = self.request_decisions.get(req_id, "TIMEOUT" if not answered else "DENIED")
            self.pending_requests.pop(req_id, None)
            self.request_events.pop(req_id, None)
            self.request_decisions.pop(req_id, None)

        if decision == "ALLOW_ALWAYS" and not require_approval:
            self.session_allowlist.add(signature)
            granted = True
        elif decision in ["ALLOW_ONCE", "ALLOW_ALWAYS"]:
            granted = True
        else:
            granted = False

        self._log_history(action_type, target, command, risk, decision)
        return {
            "granted": granted,
            "decision": decision,
            "reason": f"user_decision_{decision.lower()}",
            "risk": risk.value
        }

    def respond_request(self, req_id: str, decision: str) -> bool:
        """
        Called when user clicks [Allow Once], [Always Allow], or [Deny] in UI.
        """
        norm_decision = decision.upper().strip()
        if norm_decision not in ["ALLOW_ONCE", "ALLOW_ALWAYS", "DENY"]:
            norm_decision = "DENY"

        with self._lock:
            if req_id in self.request_events:
                self.request_decisions[req_id] = norm_decision
                self.request_events[req_id].set()
                return True
        return False

    def get_pending(self) -> List[Dict[str, Any]]:
        with self._lock:
            now = time.time()
            valid = []
            for rid, req in list(self.pending_requests.items()):
                if rid in self.request_decisions:
                    continue
                elapsed = now - req["timestamp"]
                if elapsed < req["expires_in"]:
                    req_copy = dict(req)
                    req_copy["remaining_seconds"] = max(0, int(req["expires_in"] - elapsed))
                    valid.append(req_copy)
                else:
                    # Expire timed-out request
                    ev = self.request_events.pop(rid, None)
                    if ev:
                        self.request_decisions[rid] = "TIMEOUT"
                        ev.set()
                    self.pending_requests.pop(rid, None)
            return valid

    def _log_history(self, action_type, target, command, risk, decision):
        with self._history_lock:
            self.history.append({
                "timestamp": time.time(),
                "action_type": action_type,
                "target": target,
                "command": command[:150] if command else "",
                "risk": risk.value,
                "decision": decision
            })
            if len(self.history) > 200:
                self.history = self.history[-200:]

# Global Singleton Instance
permission_manager = PermissionManager()
