"""
===================================================================================
AURA ADAPTER: SECURITY SANDBOX & ACCESS POLICIES
===================================================================================
Curated capabilities extracted from:
- semgrep/semgrep (Static Analysis Security Ruleset)
- gitleaks/gitleaks (Secret & Token Exposure Scanner)
- cedar-policy/cedar (Formal Authorization Policies)
- open-policy-agent/opa (Declarative Policy Decision Engine)
- e2b-dev/E2B (Ephemeral Workspace Sandbox Boundary)
===================================================================================
"""
import re
from typing import Dict, Any, List, Optional, Tuple


class SemgrepSecurityScanner:
    """semgrep-inspired AST & pattern security scanner."""
    RULES = [
        {"id": "eval-injection", "pattern": re.compile(r"\beval\s*\(", re.I), "severity": "HIGH", "message": "Prohibited eval() call detected."},
        {"id": "subshell-injection", "pattern": re.compile(r"os\.system\s*\(|subprocess\.call\s*\(", re.I), "severity": "HIGH", "message": "Unvalidated shell execution detected."},
        {"id": "sql-injection-risk", "pattern": re.compile(r"execute\s*\(\s*f[\"'].*?\{.*?\}", re.I), "severity": "MEDIUM", "message": "Interpolated f-string in SQL statement detected."}
    ]

    @classmethod
    def scan_code(cls, code_text: str) -> List[Dict[str, Any]]:
        findings = []
        lines = code_text.splitlines()
        for i, line in enumerate(lines):
            for rule in cls.RULES:
                if rule["pattern"].search(line):
                    findings.append({
                        "rule_id": rule["id"],
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "line": i + 1,
                        "code_snippet": line.strip()
                    })
        return findings


class GitleaksSecretScanner:
    """gitleaks-inspired regex secret and API key detector."""
    SECRET_PATTERNS = [
        {"name": "Generic High-Entropy Key", "regex": re.compile(r"(?:api[_-]?key|secret|token)\s*[:=]\s*['\"]([a-zA-Z0-9_\-]{20,})['\"]", re.I)},
        {"name": "AWS Access Key", "regex": re.compile(r"AKIA[0-9A-Z]{16}")},
        {"name": "GitHub Personal Access Token", "regex": re.compile(r"ghp_[a-zA-Z0-9]{36}")},
        {"name": "Google Gemini API Key", "regex": re.compile(r"AQ\.[a-zA-Z0-9_\-]{20,}")}
    ]

    @classmethod
    def scan_text(cls, content: str) -> List[Dict[str, Any]]:
        exposed = []
        for pat in cls.SECRET_PATTERNS:
            matches = pat["regex"].findall(content)
            if matches:
                exposed.append({
                    "secret_type": pat["name"],
                    "count": len(matches)
                })
        return exposed


class CedarPolicyEngine:
    """cedar-policy-inspired formal authorization policy evaluator."""
    def __init__(self):
        self.policies = [
            {"effect": "permit", "role": "admin", "action": "*", "resource": "*"},
            {"effect": "permit", "role": "developer", "action": ["read_code", "write_code", "run_test"], "resource": "workspace"},
            {"effect": "forbid", "role": "guest", "action": ["powershell_exec", "terminal_exec", "write_file"], "resource": "*"}
        ]

    def is_authorized(self, role: str, action: str, resource: str) -> Tuple[bool, str]:
        # Check explicit forbids first (deny overrides permit)
        for p in self.policies:
            if p["effect"] == "forbid" and (p["role"] == role or p["role"] == "*"):
                if action in p["action"] or p["action"] == "*":
                    return False, f"Cedar Policy: Action '{action}' is strictly FORBIDDEN for role '{role}'"

        # Check permits
        for p in self.policies:
            if p["effect"] == "permit" and (p["role"] == role or p["role"] == "*"):
                if action in p["action"] or p["action"] == "*":
                    return True, "Authorized by Cedar permit rule."

        return False, "Cedar Policy: Default deny."
