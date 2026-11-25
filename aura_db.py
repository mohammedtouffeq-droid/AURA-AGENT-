"""
===================================================================================
                     AURA AGENT - MULTI-USER SECURE DATABASE
===================================================================================
Enterprise-grade SQLite / LibSQL database supporting:
- Multi-user authentication (scrypt password hashing + constant-time verification)
- Per-connection SQLite foreign-key enforcement (PRAGMA foreign_keys = ON)
- Database-backed distributed login rate limiting
- Isolated user workspaces, conversation threads, pinned sessions
- Per-user long-term memory vault & credential-free signed workspace backups
- Account password rotation, account deletion, and token-gated admin bootstrap
===================================================================================
"""

import base64
import datetime
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _resolve_db_path() -> Path:
    custom_path = os.environ.get("AURA_PERSISTENT_DB_PATH", "").strip()
    if custom_path:
        return Path(custom_path)
    default_dir = Path(__file__).resolve().parent
    if os.environ.get("VERCEL") or not os.access(default_dir, os.W_OK):
        return Path(tempfile.gettempdir()) / "aura_workspace.db"
    return default_dir / "aura_workspace.db"


DB_PATH = _resolve_db_path()


def _resolve_projects_root() -> Path:
    default_dir = Path(__file__).resolve().parent
    if os.environ.get("VERCEL") or not os.access(default_dir, os.W_OK):
        base = Path(tempfile.gettempdir()) / "aura_workspace" / "projects"
    else:
        base = default_dir / "workspace" / "projects"
    base.mkdir(parents=True, exist_ok=True)
    return base


# Ephemeral / per-installation secret management (never falls back to a public constant)
_RUNTIME_SECRETS_CACHE: Dict[str, str] = {}


def _resolve_shared_deployment_seed(include_legacy_url: bool = False) -> str:
    """
    Combines shared immutable deployment runtime env vars that are identical across
    all serverless containers of a deployment (returns '' if none exist).
    Excludes volatile `VERCEL_PROJECT_PRODUCTION_URL` by default so custom domain
    changes never invalidate lifetime login proofs or sessions.
    """
    env_keys = [
        "AURA_SESSION_SECRET",
        "AURA_VAULT_SECRET",
        "AURA_CSRF_SECRET",
        "TURSO_AUTH_TOKEN",
        "AURA_DATABASE_URL",
        "TURSO_DATABASE_URL",
        "GEMINI_API_KEY",
        "VERCEL_PROJECT_ID",
        "VERCEL_ORG_ID",
        "VERCEL_GIT_REPO_ID",
    ]
    if include_legacy_url:
        env_keys.append("VERCEL_PROJECT_PRODUCTION_URL")
    parts = [f"{k}={os.environ.get(k, '').strip()}" for k in env_keys if os.environ.get(k, "").strip()]
    if not parts:
        return ""
    return "|".join(parts)


def _get_legacy_vault_secret_candidates() -> List[str]:
    """Optional legacy deployment seeds so proofs minted prior to custom-domain migration still verify."""
    if not os.environ.get("VERCEL"):
        return []
    if os.environ.get("AURA_VAULT_SECRET", "").strip():
        return []
    cur_seed = _resolve_shared_deployment_seed(include_legacy_url=False)
    leg_seed = _resolve_shared_deployment_seed(include_legacy_url=True)
    if leg_seed and leg_seed != cur_seed:
        return [hashlib.sha256(f"aura-v2:vault_secret:{leg_seed}".encode("utf-8")).hexdigest()]
    return []


def _get_or_create_secret(env_name: str, key_name: str) -> str:
    env_val = os.environ.get(env_name, "").strip()
    if env_val:
        return env_val

    if os.environ.get("VERCEL"):
        shared_seed = _resolve_shared_deployment_seed()
        if shared_seed:
            return hashlib.sha256(f"aura-v2:{key_name}:{shared_seed}".encode("utf-8")).hexdigest()

    if key_name in _RUNTIME_SECRETS_CACHE:
        return _RUNTIME_SECRETS_CACHE[key_name]

    # On non-serverless local installations, persist random 256-bit secret next to DB_PATH
    if not os.environ.get("VERCEL"):
        secret_file = DB_PATH.parent / ".aura_local_secrets.json"
        try:
            data: Dict[str, str] = {}
            if secret_file.exists():
                data = json.loads(secret_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get(key_name) and len(data[key_name]) >= 32:
                _RUNTIME_SECRETS_CACHE[key_name] = data[key_name]
                return data[key_name]
            generated = secrets.token_hex(32)
            data[key_name] = generated
            secret_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            try:
                os.chmod(secret_file, 0o600)
            except OSError:
                pass
            _RUNTIME_SECRETS_CACHE[key_name] = generated
            return generated
        except OSError:
            pass

    generated = secrets.token_hex(32)
    _RUNTIME_SECRETS_CACHE[key_name] = generated
    return generated


def is_persistent_storage_configured() -> bool:
    """
    Returns True only when backed by durable storage:
    - External cloud database via AURA_DATABASE_URL / TURSO_DATABASE_URL, OR
    - Explicit persistent volume path via AURA_PERSISTENT_DB_PATH, OR
    - Local writable non-serverless filesystem (when not running in Vercel serverless).
    Never claims /tmp SQLite on Vercel is persistent.
    """
    if os.environ.get("AURA_DATABASE_URL", "").strip() or os.environ.get("TURSO_DATABASE_URL", "").strip():
        return True
    if os.environ.get("AURA_PERSISTENT_DB_PATH", "").strip():
        return True
    if os.environ.get("VERCEL"):
        return False
    default_dir = Path(__file__).resolve().parent
    return os.access(default_dir, os.W_OK)


def get_storage_status() -> Dict[str, Any]:
    """Returns honest metadata about the active database storage layer."""
    remote_url = os.environ.get("AURA_DATABASE_URL", "").strip() or os.environ.get("TURSO_DATABASE_URL", "").strip()
    custom_path = os.environ.get("AURA_PERSISTENT_DB_PATH", "").strip()
    if remote_url:
        return {
            "persistent": True,
            "mode": "persistent_cloud_db",
            "engine": "libsql_remote",
            "production_accounts_available": True,
            "message": "Connected to persistent cloud database."
        }
    if custom_path:
        return {
            "persistent": True,
            "mode": "persistent_volume_sqlite",
            "engine": "sqlite3",
            "production_accounts_available": True,
            "message": "Using configured persistent volume database."
        }
    if os.environ.get("VERCEL"):
        vault_configured = bool(os.environ.get("AURA_VAULT_SECRET", "").strip())
        shared_seed_active = bool(_resolve_shared_deployment_seed())
        return {
            "persistent": False,
            "mode": "serverless_ephemeral_sqlite",
            "engine": "sqlite3_ephemeral",
            "production_accounts_available": True,
            "vault_sync_enabled": vault_configured,
            "history_sync_enabled": True,
            "stateless_session_sync": shared_seed_active,
            "message": "Serverless SQLite (/tmp is ephemeral across cold starts; configure TURSO_DATABASE_URL for durable multi-instance persistence)."
        }
    return {
        "persistent": True,
        "mode": "persistent_local_sqlite",
        "engine": "sqlite3",
        "production_accounts_available": True,
        "message": "Saved in local persistent SQLite workspace database."
    }


class _RemoteLibSQLCursor:
    """DB-API 2.0 compatible cursor wrapper for Turso / LibSQL HTTP v2 pipeline API."""
    def __init__(self, conn: "_RemoteLibSQLConnection"):
        self.conn = conn
        self._rows: List[Dict[str, Any]] = []
        self._pos = 0
        self.lastrowid: Optional[int] = None
        self.rowcount: int = 0

    @staticmethod
    def _convert_arg(val: Any) -> Dict[str, Any]:
        if val is None:
            return {"type": "null"}
        if isinstance(val, bool):
            return {"type": "integer", "value": "1" if val else "0"}
        if isinstance(val, int):
            return {"type": "integer", "value": str(val)}
        if isinstance(val, float):
            return {"type": "float", "value": val}
        return {"type": "text", "value": str(val)}

    def execute(self, sql: str, params: Tuple[Any, ...] = ()):
        stmt: Dict[str, Any] = {"sql": sql}
        if params:
            stmt["args"] = [self._convert_arg(p) for p in params]

        is_write = not sql.lstrip().upper().startswith(("SELECT", "PRAGMA"))
        if is_write and self.conn.buffer_writes:
            self.conn._pending_stmts.append(stmt)
            # Flush immediately if lastrowid is needed on INSERT INTO users
            if "INSERT INTO USERS" not in sql.upper():
                self.rowcount = 1
                return self
            self.conn.commit()
            self.lastrowid = self.conn._last_insert_id
            self.rowcount = self.conn._last_rowcount
            return self

        res = self.conn._send_pipeline([stmt])
        cols = [c.get("name") for c in res.get("cols", [])]
        raw_rows = res.get("rows", [])
        self._rows = []
        for r in raw_rows:
            row_dict = {}
            for idx, col_name in enumerate(cols):
                cell = r[idx]
                ctype = cell.get("type")
                cval = cell.get("value")
                if ctype == "null":
                    row_dict[col_name] = None
                elif ctype == "integer":
                    row_dict[col_name] = int(cval) if cval is not None else 0
                elif ctype == "float":
                    row_dict[col_name] = float(cval) if cval is not None else 0.0
                else:
                    row_dict[col_name] = cval
            self._rows.append(row_dict)
        self._pos = 0
        last_id = res.get("last_insert_rowid")
        self.lastrowid = int(last_id) if last_id is not None else None
        self.rowcount = int(res.get("affected_row_count", 0))
        return self

    def fetchone(self):
        if self._pos < len(self._rows):
            r = self._rows[self._pos]
            self._pos += 1
            return r
        return None

    def fetchall(self):
        rem = self._rows[self._pos:]
        self._pos = len(self._rows)
        return rem


class _RemoteLibSQLConnection:
    """Supports atomic batched pipeline commits over LibSQL HTTP v2."""
    def __init__(self, url: str, auth_token: str):
        clean = url.rstrip("/")
        if clean.startswith("libsql://"):
            clean = "https://" + clean[len("libsql://"):]
        if not clean.endswith("/v2/pipeline"):
            clean = clean + "/v2/pipeline"
        self.url = clean
        self.auth_token = auth_token
        self.buffer_writes = False
        self._pending_stmts: List[Dict[str, Any]] = []
        self._last_insert_id: Optional[int] = None
        self._last_rowcount: int = 0

    def _send_pipeline(self, stmts: List[Dict[str, Any]], transactional: bool = False) -> Dict[str, Any]:
        reqs: List[Dict[str, Any]] = []
        if transactional and len(stmts) > 1:
            reqs.append({"type": "execute", "stmt": {"sql": "BEGIN IMMEDIATE"}})
        for s in stmts:
            reqs.append({"type": "execute", "stmt": s})
        if transactional and len(stmts) > 1:
            reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
        reqs.append({"type": "close"})

        payload = json.dumps({"requests": reqs}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        req = urllib.request.Request(self.url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        last_res: Dict[str, Any] = {}
        for item in data.get("results", []):
            if item.get("type") == "error":
                err_msg = item.get("error", {}).get("message", "LibSQL execution error")
                if "UNIQUE constraint failed" in err_msg:
                    raise sqlite3.IntegrityError(err_msg)
                raise sqlite3.OperationalError(err_msg)
            if item.get("type") == "ok" and "response" in item:
                r = item["response"].get("result")
                if isinstance(r, dict):
                    last_res = r
        return last_res

    def cursor(self):
        return _RemoteLibSQLCursor(self)

    def commit(self):
        if not self._pending_stmts:
            return
        stmts = list(self._pending_stmts)
        self._pending_stmts.clear()
        res = self._send_pipeline(stmts, transactional=True)
        lid = res.get("last_insert_rowid")
        self._last_insert_id = int(lid) if lid is not None else None
        self._last_rowcount = int(res.get("affected_row_count", 0))

    def close(self):
        self._pending_stmts.clear()


# Scrypt configuration (OWASP standard, zero third-party dependencies)
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEYLEN = 64


def get_connection():
    remote_url = os.environ.get("AURA_DATABASE_URL", "").strip() or os.environ.get("TURSO_DATABASE_URL", "").strip()
    if remote_url:
        auth_token = os.environ.get("AURA_DATABASE_AUTH_TOKEN", "").strip() or os.environ.get("TURSO_AUTH_TOKEN", "").strip()
        return _RemoteLibSQLConnection(remote_url, auth_token)
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 12000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    except sqlite3.OperationalError:
        pass
    return conn


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Generates a versioned scrypt hash using salt and constant-time parameters."""
    if not salt:
        salt = secrets.token_hex(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=33554432,
        dklen=SCRYPT_KEYLEN
    )
    hashed = f"scrypt$v1$n={SCRYPT_N},r={SCRYPT_R},p={SCRYPT_P}${derived.hex()}"
    return hashed, salt


def verify_password(password: str, stored_hash: str, salt: str) -> Tuple[bool, bool]:
    """
    Verifies a password against stored hash using constant-time comparison.
    Returns (is_valid, needs_upgrade).
    """
    if stored_hash.startswith("scrypt$v1$"):
        parts = stored_hash.split("$")
        if len(parts) == 4:
            expected_hex = parts[3]
            actual_derived = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt.encode("utf-8"),
                n=SCRYPT_N,
                r=SCRYPT_R,
                p=SCRYPT_P,
                maxmem=33554432,
                dklen=SCRYPT_KEYLEN
            )
            is_valid = hmac.compare_digest(actual_derived.hex(), expected_hex)
            return is_valid, False
        return False, False
    return False, False


# Database-backed rate limiter (with in-memory fallback if DB table not yet initialized)
_LOGIN_FAILURES: Dict[str, List[float]] = {}
MAX_LOGIN_FAILURES = 5
LOCKOUT_WINDOW_SECONDS = 300  # 5 minutes lockout


def check_login_rate_limit(username: str) -> Tuple[bool, int]:
    uname = username.strip().lower()
    now = time.time()
    cutoff = now - LOCKOUT_WINDOW_SECONDS
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM login_attempts WHERE failed_at < ?", (cutoff,))
        c.execute("SELECT failed_at FROM login_attempts WHERE username = ? ORDER BY failed_at ASC", (uname,))
        rows = c.fetchall()
        conn.commit()
        conn.close()
        attempts = [float(r["failed_at"] if isinstance(r, (dict, sqlite3.Row)) else r[0]) for r in rows]
    except Exception:
        attempts = [t for t in _LOGIN_FAILURES.get(uname, []) if now - t < LOCKOUT_WINDOW_SECONDS]
        _LOGIN_FAILURES[uname] = attempts

    if len(attempts) >= MAX_LOGIN_FAILURES:
        wait_seconds = int(LOCKOUT_WINDOW_SECONDS - (now - attempts[0]))
        return False, max(1, wait_seconds)
    return True, 0


def record_login_failure(username: str):
    uname = username.strip().lower()
    now = time.time()
    _LOGIN_FAILURES.setdefault(uname, []).append(now)
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT INTO login_attempts (username, failed_at) VALUES (?, ?)", (uname, now))
        conn.commit()
        conn.close()
    except Exception:
        pass


def clear_login_failures(username: str):
    uname = username.strip().lower()
    _LOGIN_FAILURES.pop(uname, None)
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM login_attempts WHERE username = ?", (uname,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def validate_password_strength(password: str) -> Tuple[bool, str]:
    if not isinstance(password, str) or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password) > 256:
        return False, "Password must not exceed 256 characters."
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        return False, "Password must contain both letters and numbers."
    return True, ""


def init_database():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            display_name TEXT,
            settings_json TEXT,
            role TEXT DEFAULT 'user',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            failed_at REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tools_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, key),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            company TEXT,
            stack TEXT,
            path TEXT,
            description TEXT,
            is_pinned INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS permission_requests (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            action_type TEXT NOT NULL,
            target TEXT NOT NULL,
            command TEXT,
            details TEXT,
            risk TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            decision TEXT,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS revoked_sessions (
            token_hash TEXT PRIMARY KEY,
            revoked_at REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_quota_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS membership_activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            tier_id TEXT NOT NULL,
            activated_at REAL NOT NULL,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_revocations (
            username TEXT PRIMARY KEY,
            revoked_before REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS subscription_keys (
            key_code TEXT PRIMARY KEY,
            key_hash TEXT NOT NULL UNIQUE,
            tier_id TEXT NOT NULL,
            duration_days INTEGER NOT NULL DEFAULT 20,
            duration_seconds INTEGER,
            timer_mode TEXT DEFAULT 'on_activation',
            is_gift INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            bound_user_id INTEGER,
            bound_username TEXT DEFAULT '',
            activated_at REAL,
            expires_at REAL,
            created_at REAL NOT NULL,
            created_by TEXT DEFAULT 'ig.ahmed.irl',
            note TEXT DEFAULT '',
            renew_count INTEGER NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_username TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT DEFAULT '',
            details TEXT DEFAULT '',
            created_at REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_reports (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'bug',
            severity TEXT NOT NULL DEFAULT 'medium',
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            diagnostics_json TEXT DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'planned',
            action_plan_json TEXT DEFAULT '[]',
            admin_reply TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS mistake_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_scope TEXT DEFAULT 'workspace',
            error_signature TEXT NOT NULL,
            root_cause TEXT NOT NULL,
            verified_fix TEXT NOT NULL,
            prevention_rule TEXT NOT NULL,
            occurrences INTEGER NOT NULL DEFAULT 1,
            resolved_count INTEGER NOT NULL DEFAULT 1,
            last_seen_at REAL NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE(user_id, error_signature),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Schema migrations for existing local SQLite / LibSQL files
    c.execute("PRAGMA table_info(users)")
    user_cols = [(col["name"] if isinstance(col, dict) else col[1]) for col in c.fetchall()]
    for col_name, col_def in (
        ("role", "TEXT DEFAULT 'user'"),
        ("is_banned", "INTEGER DEFAULT 0"),
        ("ban_reason", "TEXT DEFAULT ''"),
        ("banned_at", "REAL"),
        ("last_login_at", "REAL"),
        ("last_seen_at", "REAL"),
        ("login_count", "INTEGER DEFAULT 0"),
        ("last_device", "TEXT DEFAULT ''"),
    ):
        if col_name not in user_cols:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass

    c.execute("PRAGMA table_info(subscription_keys)")
    key_cols = [(col["name"] if isinstance(col, dict) else col[1]) for col in c.fetchall()]
    for col_name, col_def in (
        ("duration_seconds", "INTEGER"),
        ("timer_mode", "TEXT DEFAULT 'on_activation'"),
        ("is_gift", "INTEGER DEFAULT 0"),
    ):
        if col_name not in key_cols:
            try:
                c.execute(f"ALTER TABLE subscription_keys ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass

    c.execute("PRAGMA table_info(auth_sessions)")
    existing_cols = [(row["name"] if isinstance(row, dict) else row[1]) for row in c.fetchall()]
    if "expires_at" not in existing_cols:
        try:
            c.execute("ALTER TABLE auth_sessions ADD COLUMN expires_at DATETIME")
        except Exception:
            pass

    conn.commit()
    conn.close()


init_database()


# ===================================================================================
# AUTHENTICATION & ACCOUNT LIFECYCLE API
# ===================================================================================

def _issue_signed_session_token(user_id: int, username: str, display_name: str = "", role: str = "user", ttl_days: int = 30) -> Tuple[str, str]:
    """
    Issues a signed, container-portable session token (`aura_s2.<payload>.<sig>`)
    that stays valid across Vercel multi-container invocations while still supporting
    per-token and per-user revocation in SQLite.
    """
    now_ts = time.time()
    exp_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=ttl_days)
    payload = {
        "v": 2,
        "jti": secrets.token_hex(12),
        "uid": int(user_id),
        "u": str(username).strip().lower(),
        "dn": (str(display_name or username).strip()[:64] or str(username).capitalize()),
        "r": str(role or "user").lower(),
        "iat": round(now_ts, 3),
        "exp": round(exp_dt.timestamp(), 3),
    }
    raw_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    secret_seed = _get_or_create_secret("AURA_SESSION_SECRET", "session_secret")
    sig = hmac.new(secret_seed.encode("utf-8"), raw_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"aura_s2.{raw_b64}.{sig}", exp_dt.isoformat()


def _verify_signed_session_token(token: str) -> Optional[Dict[str, Any]]:
    if not token or not isinstance(token, str) or not token.startswith("aura_s2."):
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    _, raw_b64, sig = parts
    if not raw_b64 or not sig:
        return None
    secret_seed = _get_or_create_secret("AURA_SESSION_SECRET", "session_secret")
    expected_sig = hmac.new(secret_seed.encode("utf-8"), raw_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        return None
    try:
        padded = raw_b64 + "=" * (-len(raw_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("v") != 2:
            return None
        if float(payload.get("exp", 0)) < time.time():
            return None
        uname = str(payload.get("u", "")).strip().lower()
        if not uname:
            return None
        return payload
    except Exception:
        return None


def _derive_account_proof_keystream(secret_seed: str, nonce: str, username: str, length: int) -> bytes:
    """Derives a deterministic HMAC-SHA256 stream key for obscuring encrypted client credential proofs."""
    out = bytearray()
    counter = 0
    uname = str(username or "").strip().lower()
    key_bytes = secret_seed.encode("utf-8")
    while len(out) < length:
        block = hmac.new(
            key_bytes,
            f"aura_ap1_enc:{nonce}:{uname}:{counter}".encode("utf-8"),
            hashlib.sha256,
        ).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _is_shadow_credentials(password_hash: Any, salt: Any) -> bool:
    p_hash = str(password_hash or "").strip()
    p_salt = str(salt or "").strip()
    return (not p_hash) or (not p_salt) or p_hash == "SHADOW_SESSION_ONLY" or p_salt == "SHADOW"


def _issue_account_proof(username: str, password_hash: str, salt: str) -> str:
    """
    Issues a server-signed, stream-encrypted credential proof (`aura_ap1.<nonce>.<cipher>.<sig>`)
    so ephemeral serverless containers can still verify the user's exact scrypt password across
    cold starts WITHOUT ever exposing raw `password_hash` or `salt` in client storage or `user_vault`.
    Never issues a proof for ephemeral shadow rows (`SHADOW_SESSION_ONLY`).
    """
    uname = str(username or "").strip().lower()
    if not uname or _is_shadow_credentials(password_hash, salt):
        return ""
    nonce = secrets.token_hex(12)
    payload_bytes = json.dumps(
        {
            "v": 1,
            "u": uname,
            "h": str(password_hash),
            "s": str(salt),
            "ts": round(time.time(), 3),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    secret_seed = _get_or_create_secret("AURA_VAULT_SECRET", "vault_secret")
    keystream = _derive_account_proof_keystream(secret_seed, nonce, uname, len(payload_bytes))
    cipher_bytes = bytes(b ^ k for b, k in zip(payload_bytes, keystream))
    cipher_b64 = base64.urlsafe_b64encode(cipher_bytes).decode("ascii").rstrip("=")
    body = f"aura_ap1.{nonce}.{cipher_b64}"
    sig = hmac.new(secret_seed.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _decrypt_account_proof_raw(account_proof: Any, username: str) -> Optional[Tuple[str, str]]:
    """Verifies HMAC signature of an `aura_ap1` proof and returns raw `(password_hash, salt)`."""
    if not account_proof or not isinstance(account_proof, str):
        return None
    parts = account_proof.strip().split(".")
    if len(parts) != 4 or parts[0] != "aura_ap1":
        return None
    _, nonce, cipher_b64, sig = parts
    if not nonce or not cipher_b64 or not sig:
        return None
    uname = str(username or "").strip().lower().lstrip("@")
    candidate_seeds = [_get_or_create_secret("AURA_VAULT_SECRET", "vault_secret")] + _get_legacy_vault_secret_candidates()
    body = f"aura_ap1.{nonce}.{cipher_b64}"
    matched_seed = None
    for seed in candidate_seeds:
        expected_sig = hmac.new(seed.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_sig, sig):
            matched_seed = seed
            break
    if not matched_seed:
        return None
    try:
        padded = cipher_b64 + "=" * (-len(cipher_b64) % 4)
        cipher_bytes = base64.urlsafe_b64decode(padded.encode("ascii"))
        keystream = _derive_account_proof_keystream(matched_seed, nonce, uname, len(cipher_bytes))
        plain_bytes = bytes(b ^ k for b, k in zip(cipher_bytes, keystream))
        data = json.loads(plain_bytes.decode("utf-8"))
        if int(data.get("v", 0)) != 1 or str(data.get("u", "")).strip().lower() != uname:
            return None
        p_hash = str(data.get("h", "")).strip()
        p_salt = str(data.get("s", "")).strip()
        if not p_hash or not p_salt:
            return None
        return p_hash, p_salt
    except Exception:
        return None


def _verify_and_extract_account_proof(account_proof: Any, username: str) -> Optional[Tuple[str, str]]:
    """Verifies an `aura_ap1` proof and decrypts real non-shadow `(password_hash, salt)` in memory only."""
    raw = _decrypt_account_proof_raw(account_proof, username)
    if not raw:
        return None
    p_hash, p_salt = raw
    if _is_shadow_credentials(p_hash, p_salt):
        return None
    return p_hash, p_salt


def _is_legacy_shadow_proof(account_proof: Any, username: str) -> bool:
    """Returns True only if proof has a valid server HMAC signature but holds legacy SHADOW credentials."""
    raw = _decrypt_account_proof_raw(account_proof, username)
    return bool(raw and _is_shadow_credentials(raw[0], raw[1]))


def heal_shadow_user_credentials(user_id: int, username: str, account_proof: Any) -> bool:
    """Upgrades an ephemeral shadow user row in-place using a verified real `account_proof`."""
    creds = _verify_and_extract_account_proof(account_proof, username)
    if not creds:
        return False
    real_hash, real_salt = creds
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT password_hash, salt FROM users WHERE id = ?", (int(user_id),))
        row = c.fetchone()
        if not row or not _is_shadow_credentials(row["password_hash"], row["salt"]):
            return False
        c.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (real_hash, real_salt, int(user_id)),
        )
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


def get_account_proof_for_user(user_id: int) -> str:
    """Returns a fresh signed credential proof for an authenticated user ID (empty for shadow rows)."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT username, password_hash, salt FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        if not row or _is_shadow_credentials(row["password_hash"], row["salt"]):
            return ""
        return _issue_account_proof(row["username"], row["password_hash"], row["salt"])
    finally:
        conn.close()


def register_user(username: str, password: str, device_label: str = "") -> Dict[str, Any]:
    if not isinstance(username, str) or not isinstance(password, str):
        return {"success": False, "error": "Username and password must be strings."}
    username = username.strip().lower().lstrip("@")
    if len(username) < 3 or len(username) > 64:
        return {"success": False, "error": "Username must be between 3 and 64 characters."}
    if not all(ch.isalnum() or ch in ("_", ".", "-") for ch in username):
        return {"success": False, "error": "Username may only contain letters, numbers, underscores, dots, or hyphens."}
    valid_pass, pass_err = validate_password_strength(password)
    if not valid_pass:
        return {"success": False, "error": pass_err}

    hashed, salt = hash_password(password)
    display_name = username.capitalize()
    now_ts = time.time()
    clean_dev = str(device_label or "").strip()[:80]

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (username, password_hash, salt, display_name, settings_json, role, last_login_at, last_seen_at, login_count, last_device)
            VALUES (?, ?, ?, ?, ?, 'user', ?, ?, 1, ?)
        """, (username, hashed, salt, display_name, json.dumps({}), now_ts, now_ts, clean_dev))
        user_id = c.lastrowid

        token, expires_at = _issue_signed_session_token(int(user_id), username, display_name, "user")
        c.execute("INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))

        default_thread_id = f"th_{secrets.token_hex(8)}"
        c.execute("""
            INSERT INTO threads (id, user_id, title, is_pinned)
            VALUES (?, ?, ?, 1)
        """, (default_thread_id, user_id, "Welcome & Overview"))

        conn.commit()
        return {
            "success": True,
            "token": token,
            "account_proof": _issue_account_proof(username, hashed, salt),
            "user": {
                "id": user_id,
                "username": username,
                "display_name": display_name,
                "role": "user"
            },
            "default_thread_id": default_thread_id
        }
    except sqlite3.IntegrityError:
        return {"success": False, "error": "This username is already taken. Please choose another."}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def login_user(
    username: str,
    password: str,
    vault_backup: Optional[Dict[str, Any]] = None,
    account_proof: Optional[str] = None,
    backup_proofs: Optional[List[str]] = None,
    device_label: str = "",
) -> Dict[str, Any]:
    if not isinstance(username, str) or not isinstance(password, str):
        return {"success": False, "error": "Invalid username or password."}
    username = username.strip().lower().lstrip("@")
    clean_dev = str(device_label or "").strip()[:80]
    allowed, wait_sec = check_login_rate_limit(username)
    if not allowed:
        return {"success": False, "error": f"Too many failed login attempts. Please wait {wait_sec} seconds before trying again."}

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, username, password_hash, salt, display_name, settings_json, COALESCE(role, 'user') as role, COALESCE(is_banned, 0) as is_banned, COALESCE(ban_reason, '') as ban_reason FROM users WHERE username = ?",
        (username,)
    )
    row = c.fetchone()
    if row and int(row["is_banned"] or 0) == 1:
        reason = str(row["ban_reason"] or "").strip()
        conn.close()
        detail = f" Reason: {reason}." if reason else ""
        return {
            "success": False,
            "banned": True,
            "error": f"This AURA account has been suspended by the administrator.{detail} Contact +91 9640875528 for assistance.",
        }
    row_is_shadow = bool(row and _is_shadow_credentials(row["password_hash"], row["salt"]))

    if not row or row_is_shadow:
        # Resilient multi-instance / serverless cold-start & shadow-row account restoration:
        # 1) Strict path: verify exact scrypt password via server-signed encrypted `account_proof`
        #    (or persistent HttpOnly `backup_proofs` cookie).
        candidate_proofs: List[str] = []
        primary_is_legacy_shadow = False
        if account_proof and isinstance(account_proof, str) and account_proof.strip():
            if _is_legacy_shadow_proof(account_proof, username):
                primary_is_legacy_shadow = True
            else:
                candidate_proofs.append(account_proof.strip())
        if backup_proofs and isinstance(backup_proofs, (list, tuple)):
            for bp in backup_proofs:
                if isinstance(bp, str) and bp.strip() and bp.strip() not in candidate_proofs:
                    if not _is_legacy_shadow_proof(bp, username):
                        candidate_proofs.append(bp.strip())

        proof_creds: Optional[Tuple[str, str]] = None
        for cand in candidate_proofs:
            extracted = _verify_and_extract_account_proof(cand, username)
            if extracted:
                proof_creds = extracted
                break

        # If caller explicitly provided a non-shadow account_proof and it failed HMAC/username checks
        # (and no valid backup proof succeeded), fail closed immediately (prevents tampered proof fallback).
        if account_proof and not primary_is_legacy_shadow and not proof_creds:
            conn.close()
            record_login_failure(username)
            return {"success": False, "error": "Invalid username or password."}

        if proof_creds:
            stored_hash, stored_salt = proof_creds
            ok, needs_upgrade = verify_password(password, stored_hash, stored_salt)
            if not ok:
                conn.close()
                record_login_failure(username)
                return {"success": False, "error": "Invalid username or password."}
            eff_hash, eff_salt = hash_password(password) if needs_upgrade else (stored_hash, stored_salt)
            now_ts = time.time()
            try:
                if row_is_shadow and row:
                    target_uid = int(row["id"])
                    user_role = row["role"] if "role" in row.keys() else "user"
                    disp_name = row["display_name"] or username.capitalize()
                    c.execute(
                        "UPDATE users SET password_hash = ?, salt = ?, last_login_at = ?, last_seen_at = ?, login_count = COALESCE(login_count, 0) + 1, last_device = CASE WHEN ? != '' THEN ? ELSE last_device END WHERE id = ?",
                        (eff_hash, eff_salt, now_ts, now_ts, clean_dev, clean_dev, target_uid),
                    )
                else:
                    disp_name = username.capitalize()
                    user_role = "user"
                    c.execute(
                        """
                        INSERT INTO users (username, password_hash, salt, display_name, settings_json, role, last_login_at, last_seen_at, login_count, last_device)
                        VALUES (?, ?, ?, ?, ?, 'user', ?, ?, 1, ?)
                        """,
                        (username, eff_hash, eff_salt, disp_name, json.dumps({}), now_ts, now_ts, clean_dev),
                    )
                    target_uid = int(c.lastrowid)
                    has_vault_threads = (
                        isinstance(vault_backup, dict)
                        and isinstance((vault_backup.get("payload") or {}).get("threads"), list)
                        and len((vault_backup.get("payload") or {}).get("threads") or []) > 0
                    )
                    if not has_vault_threads:
                        c.execute(
                            "INSERT INTO threads (id, user_id, title, is_pinned) VALUES (?, ?, ?, 1)",
                            (f"th_{secrets.token_hex(8)}", target_uid, "Welcome & Overview"),
                        )
                token, expires_at = _issue_signed_session_token(target_uid, username, disp_name, user_role)
                c.execute("INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, target_uid, expires_at))
                conn.commit()
            finally:
                conn.close()
            restored_ok = False
            if vault_backup and isinstance(vault_backup, dict):
                restored_ok = restore_user_vault(vault_backup, authenticated_user_id=target_uid)
            clear_login_failures(username)
            return {
                "success": True,
                "token": token,
                "account_proof": _issue_account_proof(username, eff_hash, eff_salt),
                "user": {
                    "id": target_uid,
                    "username": username,
                    "display_name": disp_name,
                    "role": user_role,
                },
                "vault_restored": restored_ok or bool(vault_backup),
                "session_restored": True,
            }

        # 2) Legacy compatibility path (signed vault_backup without separate non-shadow proof token):
        #    NEVER accepts forged/unsigned vaults; verifies vault HMAC signature first.
        if vault_backup and isinstance(vault_backup, dict):
            vault_username = str(vault_backup.get("username", "")).strip().lower()
            v_payload = vault_backup.get("payload")
            v_sig = str(vault_backup.get("signature", ""))
            sig_ok = False
            if vault_username == username and isinstance(v_payload, dict) and v_sig:
                try:
                    canonical = json.dumps(v_payload, sort_keys=True, separators=(",", ":"))
                    sig_ok = hmac.compare_digest(compute_vault_signature(canonical), v_sig)
                except Exception:
                    sig_ok = False
            if sig_ok:
                valid_pw, pw_err = validate_password_strength(password)
                if not valid_pw:
                    conn.close()
                    record_login_failure(username)
                    return {"success": False, "error": pw_err or "Invalid username or password."}
                if row_is_shadow and row:
                    target_uid = int(row["id"])
                    user_role = row["role"] if "role" in row.keys() else "user"
                    disp_name = row["display_name"] or username.capitalize()
                    new_hash, new_salt = hash_password(password)
                    c.execute(
                        "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                        (new_hash, new_salt, target_uid),
                    )
                    token, expires_at = _issue_signed_session_token(target_uid, username, disp_name, user_role)
                    c.execute("INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, target_uid, expires_at))
                    conn.commit()
                    conn.close()
                    restore_user_vault(vault_backup, authenticated_user_id=target_uid)
                    clear_login_failures(username)
                    return {
                        "success": True,
                        "token": token,
                        "account_proof": _issue_account_proof(username, new_hash, new_salt),
                        "user": {
                            "id": target_uid,
                            "username": username,
                            "display_name": disp_name,
                            "role": user_role,
                        },
                        "vault_restored": True,
                    }
                conn.close()
                reg_res = register_user(username, password)
                if reg_res.get("success"):
                    new_uid = reg_res["user"]["id"]
                    restore_user_vault(vault_backup, authenticated_user_id=new_uid)
                    clear_login_failures(username)
                    return {
                        "success": True,
                        "token": reg_res["token"],
                        "account_proof": reg_res.get("account_proof", ""),
                        "user": reg_res["user"],
                        "vault_restored": True,
                    }
                return {"success": False, "error": reg_res.get("error", "Invalid username or password.")}

        # 3) Cold-Start Owner Lifetime Access (Zero Plaintext: strictly salted SHA-256 digest check).
        #    Ensures @ig.ahmed.irl never loses login access across Vercel serverless cold starts or new devices.
        owner_uname = os.environ.get("AURA_KEY_ADMIN_USERNAME", "ig.ahmed.irl").strip().lower() or "ig.ahmed.irl"
        if not row and username == owner_uname and not account_proof:
            try:
                import aura_membership as _am
                if _am._verify_admin_vault_password(password):
                    conn.close()
                    reg_owner = register_user(username, password, device_label=clean_dev)
                    if reg_owner.get("success"):
                        clear_login_failures(username)
                        reg_owner["owner_cold_start_restored"] = True
                        return reg_owner
            except Exception:
                pass
        conn.close()
        record_login_failure(username)
        return {"success": False, "error": "Invalid username or password."}

    user_id = row["id"]
    is_valid, needs_upgrade = verify_password(password, row["password_hash"], row["salt"])
    if not is_valid:
        conn.close()
        record_login_failure(username)
        return {"success": False, "error": "Invalid username or password."}

    eff_hash = row["password_hash"]
    eff_salt = row["salt"]
    if needs_upgrade:
        new_hash, new_salt = hash_password(password)
        c.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, user_id))
        conn.commit()
        eff_hash, eff_salt = new_hash, new_salt

    clear_login_failures(username)
    now_ts = time.time()
    if clean_dev:
        c.execute(
            "UPDATE users SET last_login_at = ?, last_seen_at = ?, login_count = COALESCE(login_count, 0) + 1, last_device = ? WHERE id = ?",
            (now_ts, now_ts, clean_dev, user_id),
        )
    else:
        c.execute(
            "UPDATE users SET last_login_at = ?, last_seen_at = ?, login_count = COALESCE(login_count, 0) + 1 WHERE id = ?",
            (now_ts, now_ts, user_id),
        )
    user_role = row["role"] if "role" in row.keys() else "user"
    disp_name = row["display_name"] or row["username"].capitalize()
    token, expires_at = _issue_signed_session_token(int(user_id), row["username"], disp_name, user_role)
    c.execute("INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "token": token,
        "account_proof": _issue_account_proof(row["username"], eff_hash, eff_salt),
        "user": {
            "id": user_id,
            "username": row["username"],
            "display_name": disp_name,
            "role": user_role
        }
    }


def change_user_password(
    user_id: int,
    current_password: str,
    new_password: str,
    account_proof: Optional[str] = None,
) -> Dict[str, Any]:
    """Rotates a user's password after verifying current_password and revokes all prior sessions."""
    valid_pass, pass_err = validate_password_strength(new_password)
    if not valid_pass:
        return {"success": False, "error": pass_err}
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT username, display_name, COALESCE(role, 'user') as role, password_hash, salt FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            return {"success": False, "error": "Account not found."}
        stored_hash, stored_salt = row["password_hash"], row["salt"]
        if _is_shadow_credentials(stored_hash, stored_salt) and account_proof:
            proof_creds = _verify_and_extract_account_proof(account_proof, row["username"])
            if proof_creds:
                stored_hash, stored_salt = proof_creds
        ok, _ = verify_password(current_password, stored_hash, stored_salt)
        if not ok:
            return {"success": False, "error": "Current password is incorrect."}
        new_hash, new_salt = hash_password(new_password)
        c.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, user_id))
        c.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        c.execute(
            "INSERT OR REPLACE INTO user_revocations (username, revoked_before) VALUES (?, ?)",
            (str(row["username"]).lower(), time.time() - 0.002),
        )
        fresh_token, expires_at = _issue_signed_session_token(
            int(user_id),
            row["username"],
            row["display_name"] or row["username"].capitalize(),
            row["role"] if "role" in row.keys() else "user",
        )
        c.execute("INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (fresh_token, user_id, expires_at))
        conn.commit()
        return {
            "success": True,
            "token": fresh_token,
            "account_proof": _issue_account_proof(row["username"], new_hash, new_salt),
            "message": "Password updated and old sessions revoked.",
        }
    finally:
        conn.close()


def delete_user_account(user_id: int, password: str, account_proof: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a user's account and cascades removal of all sessions, threads, messages, memories, and projects."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT username, password_hash, salt FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            return {"success": False, "error": "Account not found."}
        stored_hash, stored_salt = row["password_hash"], row["salt"]
        if _is_shadow_credentials(stored_hash, stored_salt) and account_proof:
            proof_creds = _verify_and_extract_account_proof(account_proof, row["username"])
            if proof_creds:
                stored_hash, stored_salt = proof_creds
        ok, _ = verify_password(password, stored_hash, stored_salt)
        if not ok:
            return {"success": False, "error": "Incorrect password."}
        c.execute(
            "INSERT OR REPLACE INTO user_revocations (username, revoked_before) VALUES (?, ?)",
            (str(row["username"]).lower(), time.time() + 1.0),
        )
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return {"success": True, "message": "Account and all associated data permanently deleted."}
    finally:
        conn.close()


def bootstrap_admin_user(user_id: int, provided_secret: str) -> Dict[str, Any]:
    """
    Promotes an authenticated user to 'admin' ONLY when AURA_ADMIN_BOOTSTRAP_TOKEN
    is configured on the server and matches provided_secret in constant time.
    """
    configured = os.environ.get("AURA_ADMIN_BOOTSTRAP_TOKEN", "").strip()
    if not configured or len(configured) < 16:
        return {"success": False, "error": "Admin bootstrap is disabled (configure AURA_ADMIN_BOOTSTRAP_TOKEN >= 16 chars on server)."}
    if not provided_secret or not hmac.compare_digest(configured, provided_secret.strip()):
        return {"success": False, "error": "Invalid admin bootstrap token."}
    set_user_role(user_id, "admin")
    return {"success": True, "role": "admin"}


def create_session_token(user_id: int) -> str:
    """Generates and registers a signed active session token for a given user ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT username, display_name, COALESCE(role, 'user') as role FROM users WHERE id = ?", (user_id,))
    u_row = c.fetchone()
    if u_row:
        token, expires_at = _issue_signed_session_token(
            int(user_id),
            u_row["username"],
            u_row["display_name"] or u_row["username"].capitalize(),
            u_row["role"] if "role" in u_row.keys() else "user",
        )
    else:
        token = secrets.token_hex(24)
        expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat()
    c.execute("INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    conn.commit()
    conn.close()
    return token


def authenticate_token(token: str, touch_device: str = "") -> Optional[Dict[str, Any]]:
    if not token or not isinstance(token, str):
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now_ts = time.time()
    clean_dev = str(touch_device or "").strip()[:80]
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT 1 FROM revoked_sessions WHERE token_hash = ?", (token_hash,))
        if c.fetchone():
            return None

        c.execute("""
            SELECT u.id, u.username, u.display_name, u.settings_json, s.expires_at,
                   COALESCE(u.role, 'user') as role,
                   COALESCE(u.is_banned, 0) as is_banned,
                   u.last_seen_at,
                   COALESCE(u.last_device, '') as last_device
            FROM auth_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ?
        """, (token,))
        row = c.fetchone()

        signed_payload = _verify_signed_session_token(token) if token.startswith("aura_s2.") else None
        if signed_payload:
            uname = str(signed_payload.get("u", "")).lower()
            c.execute("SELECT revoked_before FROM user_revocations WHERE username = ?", (uname,))
            rev_row = c.fetchone()
            if rev_row and float(signed_payload.get("iat", 0)) < float(rev_row["revoked_before"]):
                c.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
                conn.commit()
                return None

        if not row:
            # Stateless cold-start / multi-container rehydration for valid signed aura_s2 tokens
            if not signed_payload:
                return None
            uname = str(signed_payload["u"]).strip().lower()
            disp = str(signed_payload.get("dn") or uname.capitalize())
            role = str(signed_payload.get("r") or "user")
            c.execute(
                "SELECT id, username, display_name, settings_json, COALESCE(role, 'user') as role, COALESCE(is_banned, 0) as is_banned FROM users WHERE username = ?",
                (uname,),
            )
            u_row = c.fetchone()
            if u_row and int(u_row["is_banned"] or 0) == 1:
                return None
            if not u_row:
                c.execute("""
                    INSERT OR IGNORE INTO users (username, password_hash, salt, display_name, settings_json, role, last_login_at, last_seen_at, login_count, last_device)
                    VALUES (?, 'SHADOW_SESSION_ONLY', 'SHADOW', ?, ?, ?, ?, ?, 1, ?)
                """, (uname, disp, json.dumps({}), role, now_ts, now_ts, clean_dev))
                c.execute(
                    "SELECT id, username, display_name, settings_json, COALESCE(role, 'user') as role, COALESCE(is_banned, 0) as is_banned FROM users WHERE username = ?",
                    (uname,),
                )
                u_row = c.fetchone()
                if not u_row or int(u_row["is_banned"] or 0) == 1:
                    return None
            actual_uid = int(u_row["id"])
            exp_iso = datetime.datetime.fromtimestamp(float(signed_payload["exp"]), tz=datetime.timezone.utc).isoformat()
            c.execute(
                "INSERT OR IGNORE INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
                (token, actual_uid, exp_iso),
            )
            if clean_dev:
                c.execute("UPDATE users SET last_seen_at = ?, last_device = ? WHERE id = ?", (now_ts, clean_dev, actual_uid))
            else:
                c.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (now_ts, actual_uid))
            conn.commit()
            try:
                parsed_settings = json.loads(u_row["settings_json"] or "{}")
            except Exception:
                parsed_settings = {}
            return {
                "id": actual_uid,
                "username": u_row["username"],
                "display_name": u_row["display_name"] or u_row["username"].capitalize(),
                "role": u_row["role"] if "role" in u_row.keys() else "user",
                "settings": parsed_settings,
            }

        # Enforce immediate admin ban kill-switch on live sessions
        if int(row["is_banned"] or 0) == 1:
            c.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            conn.commit()
            return None

        # Fail-closed session expiration validation
        expires_at_str = row["expires_at"]
        if not expires_at_str:
            c.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            conn.commit()
            return None
        try:
            exp = datetime.datetime.fromisoformat(str(expires_at_str))
            now = datetime.datetime.now(datetime.timezone.utc)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=datetime.timezone.utc)
            if exp < now:
                c.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
                conn.commit()
                return None
        except (ValueError, TypeError):
            c.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            conn.commit()
            return None

        # Throttled real-time activity heartbeat for Admin Users Directory
        prev_seen = float(row["last_seen_at"] or 0)
        prev_dev = str(row["last_device"] or "")
        if (now_ts - prev_seen) >= 45.0 or (clean_dev and clean_dev != prev_dev):
            try:
                if clean_dev:
                    c.execute("UPDATE users SET last_seen_at = ?, last_device = ? WHERE id = ?", (now_ts, clean_dev, int(row["id"])))
                else:
                    c.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (now_ts, int(row["id"])))
                conn.commit()
            except Exception:
                pass

        try:
            parsed_settings = json.loads(row["settings_json"] or "{}")
        except Exception:
            parsed_settings = {}
        return {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"] or row["username"].capitalize(),
            "role": row["role"] if "role" in row.keys() else "user",
            "settings": parsed_settings,
        }
    finally:
        conn.close()


def revoke_session(token: str) -> bool:
    if not token or not isinstance(token, str):
        return False
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
    affected = c.rowcount > 0
    c.execute("INSERT OR REPLACE INTO revoked_sessions (token_hash, revoked_at) VALUES (?, ?)", (token_hash, time.time()))
    conn.commit()
    conn.close()
    return affected or token.startswith("aura_s2.")


# ===================================================================================
# THREADS & MESSAGES API
# ===================================================================================

def get_user_threads(user_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, title, is_pinned, updated_at
        FROM threads
        WHERE user_id = ?
        ORDER BY is_pinned DESC, updated_at DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_user_thread(user_id: int, title: str = "New Session", thread_id: Optional[str] = None) -> Dict[str, Any]:
    if not thread_id or not isinstance(thread_id, str):
        thread_id = f"th_{secrets.token_hex(8)}"
    else:
        # Sanitize client-supplied thread_id to safe alphanumeric/underscore/hyphen characters
        safe_chars = "".join(ch for ch in thread_id if ch.isalnum() or ch in ("_", "-"))[:64]
        thread_id = safe_chars if len(safe_chars) >= 4 else f"th_{secrets.token_hex(8)}"

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, title, is_pinned, user_id FROM threads WHERE id = ?", (thread_id,))
    existing = c.fetchone()
    if existing:
        if existing["user_id"] == user_id:
            conn.close()
            return {"id": existing["id"], "title": existing["title"], "is_pinned": existing["is_pinned"]}
        # Never collide with another user's thread ID
        thread_id = f"th_{secrets.token_hex(8)}"

    clean_title = (title or "New Session").strip()[:120] or "New Session"
    c.execute("""
        INSERT INTO threads (id, user_id, title)
        VALUES (?, ?, ?)
    """, (thread_id, user_id, clean_title))
    conn.commit()
    conn.close()
    return {"id": thread_id, "title": clean_title, "is_pinned": 0}


def rename_user_thread(user_id: int, thread_id: str, new_title: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE threads
        SET title = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
    """, (new_title.strip()[:120], thread_id, user_id))
    affected = c.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def pin_user_thread(user_id: int, thread_id: str, is_pinned: bool) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE threads
        SET is_pinned = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
    """, (1 if is_pinned else 0, thread_id, user_id))
    affected = c.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def delete_user_thread(user_id: int, thread_id: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM threads WHERE id = ? AND user_id = ?", (thread_id, user_id))
    affected = c.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def get_thread_messages(user_id: int, thread_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, role, content, tools_json, created_at
        FROM messages
        WHERE thread_id = ? AND user_id = ?
        ORDER BY id ASC
    """, (thread_id, user_id))
    rows = c.fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        d["tools"] = json.loads(d["tools_json"]) if d["tools_json"] else []
        res.append(d)
    return res


def save_message(user_id: int, thread_id: str, role: str, content: str, tools: Optional[List[Dict[str, Any]]] = None):
    safe_tid = "".join(ch for ch in str(thread_id or "") if ch.isalnum() or ch in ("_", "-"))[:64] or f"th_{secrets.token_hex(8)}"
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, user_id, title FROM threads WHERE id = ?", (safe_tid,))
    t_row = c.fetchone()
    clean_first = content.strip().split("\n")[0].strip()
    auto_title = (clean_first[:42] + "...") if len(clean_first) > 42 else (clean_first or "New Conversation")
    if not t_row:
        c.execute("""
            INSERT INTO threads (id, user_id, title)
            VALUES (?, ?, ?)
        """, (safe_tid, user_id, auto_title))
    elif t_row["user_id"] != user_id:
        # Prevent cross-tenant thread ID collision
        safe_tid = f"th_{user_id}_{secrets.token_hex(6)}"
        c.execute("""
            INSERT INTO threads (id, user_id, title)
            VALUES (?, ?, ?)
        """, (safe_tid, user_id, auto_title))
    elif role == "user" and str(t_row["title"]) in ("New Session", "Welcome & Overview", "New Conversation"):
        c.execute("SELECT COUNT(*) as cnt FROM messages WHERE thread_id = ? AND user_id = ?", (safe_tid, user_id))
        m_cnt_row = c.fetchone()
        m_cnt = (m_cnt_row["cnt"] if isinstance(m_cnt_row, (dict, sqlite3.Row)) else m_cnt_row[0]) if m_cnt_row else 0
        if m_cnt == 0 and auto_title:
            c.execute("UPDATE threads SET title = ? WHERE id = ? AND user_id = ?", (auto_title, safe_tid, user_id))

    tools_str = json.dumps(tools) if tools else None
    c.execute("""
        INSERT INTO messages (thread_id, user_id, role, content, tools_json)
        VALUES (?, ?, ?, ?, ?)
    """, (safe_tid, user_id, role, content, tools_str))
    c.execute("""
        UPDATE threads
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
    """, (safe_tid, user_id))
    conn.commit()
    conn.close()


# ===================================================================================
# PER-USER MEMORY API
# ===================================================================================

def get_user_memories(user_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT key, value, created_at
        FROM user_memories
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_user_memory(user_id: int, key: str, value: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO user_memories (user_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value, created_at = CURRENT_TIMESTAMP
    """, (user_id, key.strip(), value.strip()))
    conn.commit()
    conn.close()
    return True


def delete_user_memory(user_id: int, key: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM user_memories WHERE user_id = ? AND key = ?", (user_id, key))
    affected = c.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def get_user_settings_dict(user_id: int) -> Dict[str, Any]:
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT settings_json FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            return {}
        raw = row["settings_json"] if isinstance(row, (dict, sqlite3.Row)) else row[0]
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}
    finally:
        conn.close()


def save_user_settings(user_id: int, settings: Dict[str, Any]) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET settings_json = ? WHERE id = ?", (json.dumps(settings), user_id))
    conn.commit()
    conn.close()
    return True


def record_chat_quota_event(user_id: int, created_at: Optional[float] = None) -> None:
    ts = float(created_at if created_at is not None else time.time())
    conn = get_connection()
    c = conn.cursor()
    try:
        cutoff = ts - (48 * 3600)
        c.execute("DELETE FROM chat_quota_events WHERE user_id = ? AND created_at < ?", (int(user_id), cutoff))
        c.execute(
            "INSERT INTO chat_quota_events (user_id, created_at) VALUES (?, ?)",
            (int(user_id), ts),
        )
        conn.commit()
    finally:
        conn.close()


def get_rolling_24h_quota_usage(user_id: int, window_seconds: int = 86400) -> Dict[str, Any]:
    cutoff = time.time() - float(window_seconds)
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "SELECT COUNT(*) AS cnt, MIN(created_at) AS oldest_ts FROM chat_quota_events WHERE user_id = ? AND created_at >= ?",
            (int(user_id), cutoff),
        )
        row = c.fetchone()
        if not row:
            return {"used": 0, "oldest_ts": None}
        used = int(row["cnt"] if isinstance(row, (dict, sqlite3.Row)) else row[0])
        oldest_ts = row["oldest_ts"] if isinstance(row, (dict, sqlite3.Row)) else row[1]
        return {"used": used, "oldest_ts": float(oldest_ts) if oldest_ts is not None else None}
    except Exception:
        return {"used": 0, "oldest_ts": None}
    finally:
        conn.close()


def record_membership_activation(user_id: int, username: str, key_hash: str, tier_id: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO membership_activations (user_id, username, key_hash, tier_id, activated_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (int(user_id), str(username or "").strip().lower(), str(key_hash)[:64], str(tier_id)[:24], time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_subscription_key(
    key_code: str,
    key_hash: str,
    tier_id: str,
    duration_days: int = 20,
    status: str = "active",
    bound_user_id: Optional[int] = None,
    bound_username: str = "",
    activated_at: Optional[float] = None,
    expires_at: Optional[float] = None,
    created_by: str = "ig.ahmed.irl",
    note: str = "",
    renew_count: int = 0,
    duration_seconds: Optional[int] = None,
    timer_mode: str = "on_activation",
    is_gift: bool = False,
) -> Dict[str, Any]:
    now_ts = time.time()
    dur_days_clean = max(1, int(duration_days))
    dur_secs_clean = max(60, int(duration_seconds)) if duration_seconds is not None else (dur_days_clean * 86400)
    t_mode = "fixed_now" if str(timer_mode or "").strip().lower() == "fixed_now" else "on_activation"
    gift_flag = 1 if bool(is_gift) else 0
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT key_code, created_at FROM subscription_keys WHERE key_code = ? OR key_hash = ?", (key_code, key_hash))
        existing = c.fetchone()
        if existing:
            c.execute(
                """
                UPDATE subscription_keys
                SET tier_id = ?, duration_days = ?, duration_seconds = ?, timer_mode = ?, is_gift = ?,
                    status = ?, bound_user_id = ?, bound_username = ?,
                    activated_at = ?, expires_at = ?, note = ?, renew_count = ?, updated_at = ?
                WHERE key_code = ?
                """,
                (
                    str(tier_id)[:24],
                    dur_days_clean,
                    dur_secs_clean,
                    t_mode,
                    gift_flag,
                    str(status or "active")[:24],
                    int(bound_user_id) if bound_user_id is not None else None,
                    str(bound_username or "").strip().lower()[:64],
                    float(activated_at) if activated_at is not None else None,
                    float(expires_at) if expires_at is not None else None,
                    str(note or "").strip()[:240],
                    max(0, int(renew_count)),
                    now_ts,
                    existing["key_code"],
                ),
            )
            target_code = existing["key_code"]
        else:
            c.execute(
                """
                INSERT INTO subscription_keys (
                    key_code, key_hash, tier_id, duration_days, duration_seconds, timer_mode, is_gift,
                    status, bound_user_id, bound_username, activated_at, expires_at,
                    created_at, created_by, note, renew_count, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(key_code).strip().upper()[:64],
                    str(key_hash).strip()[:64],
                    str(tier_id)[:24],
                    dur_days_clean,
                    dur_secs_clean,
                    t_mode,
                    gift_flag,
                    str(status or "active")[:24],
                    int(bound_user_id) if bound_user_id is not None else None,
                    str(bound_username or "").strip().lower()[:64],
                    float(activated_at) if activated_at is not None else None,
                    float(expires_at) if expires_at is not None else None,
                    now_ts,
                    str(created_by or "ig.ahmed.irl").strip().lower()[:64],
                    str(note or "").strip()[:240],
                    max(0, int(renew_count)),
                    now_ts,
                ),
            )
            target_code = str(key_code).strip().upper()[:64]
        conn.commit()
        c.execute("SELECT * FROM subscription_keys WHERE key_code = ?", (target_code,))
        row = c.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def get_subscription_key_by_code(key_code: str) -> Optional[Dict[str, Any]]:
    norm = str(key_code or "").strip().upper()
    if not norm:
        return None
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM subscription_keys WHERE key_code = ?", (norm,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_subscription_key_by_hash(key_hash: str) -> Optional[Dict[str, Any]]:
    h = str(key_hash or "").strip().lower()
    if not h:
        return None
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM subscription_keys WHERE key_hash = ?", (h,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_subscription_keys(limit: int = 250) -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM subscription_keys ORDER BY updated_at DESC, created_at DESC LIMIT ?", (max(1, min(1000, int(limit))),))
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()


def update_subscription_key(key_code: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    norm = str(key_code or "").strip().upper()
    if not norm or not fields:
        return None
    allowed = {
        "tier_id", "duration_days", "duration_seconds", "timer_mode", "is_gift",
        "status", "bound_user_id", "bound_username",
        "activated_at", "expires_at", "note", "renew_count",
    }
    sets = []
    vals = []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return None
    sets.append("updated_at = ?")
    vals.append(time.time())
    vals.append(norm)
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(f"UPDATE subscription_keys SET {', '.join(sets)} WHERE key_code = ?", tuple(vals))
        conn.commit()
        c.execute("SELECT * FROM subscription_keys WHERE key_code = ?", (norm,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_subscription_key(key_code: str) -> bool:
    norm = str(key_code or "").strip().upper()
    if not norm:
        return False
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM subscription_keys WHERE key_code = ?", (norm,))
        affected = c.rowcount > 0
        conn.commit()
        return affected
    finally:
        conn.close()


def update_user_membership_by_username(username: str, membership_dict: Optional[Dict[str, Any]]) -> bool:
    uname = str(username or "").strip().lower()
    if not uname:
        return False
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id, settings_json FROM users WHERE LOWER(username) = ?", (uname,))
        row = c.fetchone()
        if not row:
            return False
        uid = int(row["id"])
        try:
            settings = json.loads(row["settings_json"] or "{}")
            if not isinstance(settings, dict):
                settings = {}
        except Exception:
            settings = {}
        if membership_dict is None:
            settings.pop("membership", None)
        else:
            settings["membership"] = membership_dict
        c.execute("UPDATE users SET settings_json = ? WHERE id = ?", (json.dumps(settings), uid))
        conn.commit()
        return True
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    uname = str(username or "").strip().lower()
    if not uname:
        return None
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            SELECT id, username, display_name, settings_json, COALESCE(role, 'user') as role,
                   created_at, COALESCE(is_banned, 0) as is_banned, COALESCE(ban_reason, '') as ban_reason,
                   banned_at, last_login_at, last_seen_at, COALESCE(login_count, 0) as login_count,
                   COALESCE(last_device, '') as last_device
            FROM users WHERE LOWER(username) = ?
            """,
            (uname,),
        )
        row = c.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["settings"] = json.loads(d.get("settings_json") or "{}")
            if not isinstance(d["settings"], dict):
                d["settings"] = {}
        except Exception:
            d["settings"] = {}
        return d
    finally:
        conn.close()


def list_all_users_for_admin(limit: int = 500) -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    cutoff_24h = time.time() - 86400
    try:
        c.execute(
            """
            SELECT u.id, u.username, u.display_name, u.settings_json,
                   COALESCE(u.role, 'user') as role, u.created_at,
                   COALESCE(u.is_banned, 0) as is_banned,
                   COALESCE(u.ban_reason, '') as ban_reason,
                   u.banned_at, u.last_login_at, u.last_seen_at,
                   COALESCE(u.login_count, 0) as login_count,
                   COALESCE(u.last_device, '') as last_device,
                   (SELECT COUNT(*) FROM chat_quota_events q WHERE q.user_id = u.id AND q.created_at >= ?) as chats_24h
            FROM users u
            ORDER BY COALESCE(u.last_seen_at, u.last_login_at, 0) DESC, u.id DESC
            LIMIT ?
            """,
            (cutoff_24h, max(1, min(1000, int(limit)))),
        )
        out: List[Dict[str, Any]] = []
        for r in c.fetchall():
            d = dict(r)
            try:
                d["settings"] = json.loads(d.get("settings_json") or "{}")
                if not isinstance(d["settings"], dict):
                    d["settings"] = {}
            except Exception:
                d["settings"] = {}
            out.append(d)
        return out
    finally:
        conn.close()


def set_user_ban_status(username: str, banned: bool, reason: str = "") -> Optional[Dict[str, Any]]:
    uname = str(username or "").strip().lower()
    if not uname:
        return None
    now_ts = time.time()
    clean_reason = str(reason or "").strip()[:200]
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id, username FROM users WHERE LOWER(username) = ?", (uname,))
        row = c.fetchone()
        if not row:
            return None
        uid = int(row["id"])
        if banned:
            c.execute(
                "UPDATE users SET is_banned = 1, ban_reason = ?, banned_at = ? WHERE id = ?",
                (clean_reason, now_ts, uid),
            )
            c.execute("DELETE FROM auth_sessions WHERE user_id = ?", (uid,))
            c.execute(
                "INSERT OR REPLACE INTO user_revocations (username, revoked_before) VALUES (?, ?)",
                (uname, now_ts + 1.0),
            )
        else:
            c.execute(
                "UPDATE users SET is_banned = 0, ban_reason = '', banned_at = NULL WHERE id = ?",
                (uid,),
            )
            c.execute(
                "INSERT OR REPLACE INTO user_revocations (username, revoked_before) VALUES (?, ?)",
                (uname, now_ts - 0.5),
            )
        conn.commit()
    finally:
        conn.close()
    return get_user_by_username(uname)


def record_admin_audit(admin_username: str, action: str, target: str = "", details: str = "") -> None:
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO admin_audit_logs (admin_username, action, target, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                str(admin_username or "ig.ahmed.irl").strip().lower()[:64],
                str(action or "action").strip()[:64],
                str(target or "").strip()[:120],
                str(details or "").strip()[:300],
                time.time(),
            ),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def list_admin_audit_logs(limit: int = 60) -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "SELECT id, admin_username, action, target, details, created_at FROM admin_audit_logs ORDER BY created_at DESC, id DESC LIMIT ?",
            (max(1, min(200, int(limit))),),
        )
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()


# ===================================================================================
# DEDICATED CODING WORKSPACES / PROJECTS API
# ===================================================================================

def create_user_project(user_id: int, name: str, company: str = "", stack: str = "Python", path: str = "", description: str = "") -> Dict[str, Any]:
    project_id = f"proj_{secrets.token_hex(8)}"
    safe_slug = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in (name or "project").lower()).strip("_") or "project"
    user_proj_root = (_resolve_projects_root() / f"user_{int(user_id)}").resolve()
    user_proj_root.mkdir(parents=True, exist_ok=True)

    if not path:
        resolved_proj_path = (user_proj_root / safe_slug).resolve()
    else:
        # Keep backward-compatibility for explicit test paths when local, otherwise scope inside user_proj_root
        cand = Path(path)
        if not cand.is_absolute():
            resolved_proj_path = (user_proj_root / safe_slug).resolve()
        else:
            resolved_proj_path = cand
    path_str = str(resolved_proj_path)

    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO projects (id, user_id, name, company, stack, path, description, is_pinned)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    """, (project_id, user_id, name.strip(), company.strip(), stack.strip(), path_str, description.strip()))

    thread_id = f"th_p_{project_id}"
    c.execute("""
        INSERT INTO threads (id, user_id, title, is_pinned)
        VALUES (?, ?, ?, 1)
    """, (thread_id, user_id, f"💻 {name} (Coding)"))

    conn.commit()
    conn.close()
    return {
        "id": project_id,
        "name": name,
        "company": company,
        "stack": stack,
        "path": path_str,
        "description": description,
        "thread_id": thread_id
    }


def get_user_projects(user_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, name, company, stack, path, description, is_pinned, created_at, updated_at
        FROM projects
        WHERE user_id = ?
        ORDER BY is_pinned DESC, updated_at DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def pin_user_project(user_id: int, project_id: str, is_pinned: bool) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE projects SET is_pinned = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
        (1 if is_pinned else 0, project_id, user_id)
    )
    affected = c.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def rename_user_project(user_id: int, project_id: str, new_name: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE projects SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
        (new_name.strip(), project_id, user_id)
    )
    affected = c.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def delete_user_project(user_id: int, project_id: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
    affected = c.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def set_user_role(user_id: int, role: str) -> bool:
    """Assigns a verified role ('admin', 'developer', 'user') to a user."""
    if role not in ("admin", "developer", "user"):
        return False
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()
    return True


# ===================================================================================
# DATABASE BACKUP & MIGRATION API (SERVER-SIDE ADMIN / CLI ONLY)
# ===================================================================================

def export_database_backup(backup_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Server-side administrative backup snapshot (never exposed to browser clients).
    """
    conn = get_connection()
    c = conn.cursor()
    table_queries = {
        "users": "SELECT id, username, display_name, settings_json, role, created_at FROM users",
        "threads": "SELECT * FROM threads",
        "messages": "SELECT * FROM messages",
        "user_memories": "SELECT * FROM user_memories",
        "projects": "SELECT * FROM projects",
    }
    snapshot: Dict[str, Any] = {
        "schema_version": 2,
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "storage_status": get_storage_status(),
        "tables": {}
    }
    for tbl, query_sql in table_queries.items():
        c.execute(query_sql)
        snapshot["tables"][tbl] = [dict(r) for r in c.fetchall()]
    conn.close()

    if backup_path:
        target = Path(backup_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return snapshot


def import_database_backup(snapshot: Dict[str, Any]) -> Dict[str, int]:
    """Idempotently imports non-credential workspace records from a backup snapshot."""
    tables = snapshot.get("tables", {})
    counts: Dict[str, int] = {"users": len(tables.get("users", []))}
    conn = get_connection()
    if isinstance(conn, _RemoteLibSQLConnection):
        conn.buffer_writes = True
    c = conn.cursor()
    try:
        for t in tables.get("threads", []):
            c.execute("""
                INSERT OR IGNORE INTO threads (id, user_id, title, is_pinned, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                t["id"], t["user_id"], t["title"], t.get("is_pinned", 0),
                t.get("created_at"), t.get("updated_at")
            ))
        counts["threads"] = len(tables.get("threads", []))

        for m in tables.get("messages", []):
            c.execute("""
                INSERT OR IGNORE INTO messages (id, thread_id, user_id, role, content, tools_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                m["id"], m["thread_id"], m["user_id"], m["role"],
                m["content"], m.get("tools_json"), m.get("created_at")
            ))
        counts["messages"] = len(tables.get("messages", []))

        for mem in tables.get("user_memories", []):
            c.execute("""
                INSERT OR IGNORE INTO user_memories (id, user_id, key, value, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                mem["id"], mem["user_id"], mem["key"], mem["value"], mem.get("created_at")
            ))
        counts["user_memories"] = len(tables.get("user_memories", []))

        for p in tables.get("projects", []):
            c.execute("""
                INSERT OR IGNORE INTO projects (id, user_id, name, company, stack, path, description, is_pinned, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p["id"], p["user_id"], p["name"], p.get("company", ""),
                p.get("stack", "Python"), p.get("path", ""), p.get("description", ""),
                p.get("is_pinned", 0), p.get("created_at"), p.get("updated_at")
            ))
        counts["projects"] = len(tables.get("projects", []))

        conn.commit()
    finally:
        conn.close()
    return counts


# ===================================================================================
# CSRF & CREDENTIAL-FREE SIGNED WORKSPACE VAULT
# ===================================================================================

def compute_csrf_token(session_token: str) -> str:
    """Computes a deterministic per-session CSRF token using a non-public installation secret."""
    secret_seed = _get_or_create_secret("AURA_CSRF_SECRET", "csrf_secret")
    return hmac.new(
        secret_seed.encode("utf-8"),
        session_token.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()[:32]


def verify_csrf_token(session_token: str, csrf_token: str) -> bool:
    """Constant-time verification of a per-session CSRF token."""
    if not session_token or not csrf_token:
        return False
    expected = compute_csrf_token(session_token)
    return hmac.compare_digest(expected, csrf_token.strip())


def compute_vault_signature(payload_json: str) -> str:
    """Computes an HMAC-SHA256 signature using a non-public installation/env secret."""
    secret_seed = _get_or_create_secret("AURA_VAULT_SECRET", "vault_secret")
    return hmac.new(
        secret_seed.encode("utf-8"),
        payload_json.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def export_user_vault(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Exports a signed, CREDENTIAL-FREE snapshot of a user's threads, messages,
    memories, and projects.
    SECURITY INVARIANT: NEVER includes password_hash, salt, or session tokens!
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "SELECT id, username, display_name, settings_json, created_at FROM users WHERE id = ?",
            (user_id,)
        )
        u_row = c.fetchone()
        if not u_row:
            return None
        user_public = {
            "id": u_row["id"],
            "username": u_row["username"],
            "display_name": u_row["display_name"],
            "settings_json": u_row["settings_json"] or "{}",
            "created_at": u_row["created_at"],
        }

        c.execute("SELECT id, title, is_pinned, created_at, updated_at FROM threads WHERE user_id = ?", (user_id,))
        threads = [dict(r) for r in c.fetchall()]

        c.execute("SELECT thread_id, role, content, tools_json, created_at FROM messages WHERE user_id = ? ORDER BY id ASC", (user_id,))
        messages = [dict(r) for r in c.fetchall()]

        c.execute("SELECT key, value, created_at FROM user_memories WHERE user_id = ?", (user_id,))
        memories = [dict(r) for r in c.fetchall()]

        c.execute("SELECT id, name, company, stack, path, description, is_pinned, created_at, updated_at FROM projects WHERE user_id = ?", (user_id,))
        projects = [dict(r) for r in c.fetchall()]

        payload = {
            "user": user_public,
            "threads": threads,
            "messages": messages,
            "user_memories": memories,
            "projects": projects,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        sig = compute_vault_signature(canonical)
        return {
            "version": 2,
            "username": user_public["username"],
            "credentials_excluded": True,
            "payload": payload,
            "signature": sig
        }
    finally:
        conn.close()


def restore_user_vault(vault_envelope: Any, authenticated_user_id: Optional[int] = None) -> bool:
    """
    Verifies the HMAC-SHA256 signature of a credential-free user vault envelope and
    restores workspace threads, messages, memories, and projects ONLY for an ALREADY
    EXISTING / AUTHENTICATED user account.
    SECURITY INVARIANTS:
    - NEVER creates user accounts or modifies password hashes / roles.
    - NEVER imports or resurrects session tokens.
    - In Vercel serverless, requires AURA_VAULT_SECRET to be explicitly configured.
    """
    if os.environ.get("VERCEL") and not os.environ.get("AURA_VAULT_SECRET", "").strip():
        return False
    if not vault_envelope:
        return False
    if isinstance(vault_envelope, str):
        try:
            vault_envelope = json.loads(vault_envelope)
        except Exception:
            return False
    if not isinstance(vault_envelope, dict):
        return False

    payload = vault_envelope.get("payload")
    sig = vault_envelope.get("signature", "")
    if not isinstance(payload, dict) or not sig or not isinstance(sig, str):
        return False

    # Reject legacy/forged vaults that attempt to smuggle credentials or sessions
    u = payload.get("user")
    if not isinstance(u, dict) or not u.get("username"):
        return False
    if "password_hash" in u or "salt" in u or "sessions" in payload:
        return False

    try:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except Exception:
        return False

    expected_sig = compute_vault_signature(canonical)
    if not hmac.compare_digest(expected_sig, sig):
        return False

    username = str(u["username"]).strip().lower()
    conn = get_connection()
    if isinstance(conn, _RemoteLibSQLConnection):
        conn.buffer_writes = True
    c = conn.cursor()
    try:
        if authenticated_user_id is not None:
            c.execute("SELECT id, username FROM users WHERE id = ?", (authenticated_user_id,))
            existing = c.fetchone()
            if not existing or str(existing["username"]).lower() != username:
                return False
            target_user_id = int(existing["id"])
        else:
            c.execute("SELECT id FROM users WHERE username = ?", (username,))
            existing = c.fetchone()
            if not existing:
                # Never create unauthenticated accounts from vault payloads
                return False
            target_user_id = int(existing["id"])

        # Restore verified server-signed membership & engineering rules on serverless cold starts
        try:
            vault_settings = json.loads(u.get("settings_json") or "{}")
            if isinstance(vault_settings, dict) and (vault_settings.get("membership") or vault_settings.get("aura_rules")):
                c.execute("SELECT settings_json FROM users WHERE id = ?", (target_user_id,))
                cur_s_row = c.fetchone()
                cur_s = json.loads((cur_s_row["settings_json"] if cur_s_row else "{}") or "{}")
                if not isinstance(cur_s, dict):
                    cur_s = {}
                changed = False
                if not cur_s.get("membership") and isinstance(vault_settings.get("membership"), dict):
                    cur_s["membership"] = vault_settings["membership"]
                    changed = True
                if not cur_s.get("aura_rules") and isinstance(vault_settings.get("aura_rules"), str):
                    cur_s["aura_rules"] = vault_settings["aura_rules"][:6000]
                    changed = True
                if changed:
                    c.execute("UPDATE users SET settings_json = ? WHERE id = ?", (json.dumps(cur_s), target_user_id))
        except Exception:
            pass

        for t in payload.get("threads", []):
            if isinstance(t, dict) and t.get("id") and t.get("title"):
                safe_tid = "".join(ch for ch in str(t["id"]) if ch.isalnum() or ch in ("_", "-"))[:64]
                if not safe_tid:
                    continue
                c.execute("SELECT user_id FROM threads WHERE id = ?", (safe_tid,))
                owner_row = c.fetchone()
                if owner_row and owner_row["user_id"] != target_user_id:
                    continue
                c.execute("""
                    INSERT OR IGNORE INTO threads (id, user_id, title, is_pinned)
                    VALUES (?, ?, ?, ?)
                """, (safe_tid, target_user_id, str(t["title"])[:120], int(t.get("is_pinned", 0))))

                c.execute("SELECT COUNT(*) as cnt FROM messages WHERE thread_id = ? AND user_id = ?", (safe_tid, target_user_id))
                cnt_row = c.fetchone()
                existing_cnt = (cnt_row["cnt"] if isinstance(cnt_row, (dict, sqlite3.Row)) else cnt_row[0]) if cnt_row else 0
                t_msgs = [m for m in payload.get("messages", []) if isinstance(m, dict) and m.get("thread_id") == t.get("id")]
                if existing_cnt == 0 and t_msgs:
                    for m in t_msgs:
                        c.execute("""
                            INSERT INTO messages (thread_id, user_id, role, content, tools_json)
                            VALUES (?, ?, ?, ?, ?)
                        """, (safe_tid, target_user_id, str(m.get("role", "user")), str(m.get("content", "")), m.get("tools_json")))

        for mem in payload.get("user_memories", []):
            if isinstance(mem, dict) and mem.get("key"):
                c.execute("""
                    INSERT OR IGNORE INTO user_memories (user_id, key, value)
                    VALUES (?, ?, ?)
                """, (target_user_id, str(mem["key"]), str(mem.get("value", ""))))

        for p in payload.get("projects", []):
            if isinstance(p, dict) and p.get("id") and p.get("name"):
                safe_pid = "".join(ch for ch in str(p["id"]) if ch.isalnum() or ch in ("_", "-"))[:64]
                if not safe_pid:
                    continue
                c.execute("SELECT user_id FROM projects WHERE id = ?", (safe_pid,))
                p_owner = c.fetchone()
                if p_owner and p_owner["user_id"] != target_user_id:
                    continue
                c.execute("""
                    INSERT OR IGNORE INTO projects (id, user_id, name, company, stack, path, description, is_pinned)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    safe_pid, target_user_id, str(p["name"]), str(p.get("company", "")),
                    str(p.get("stack", "Python")), str(p.get("path", "")), str(p.get("description", "")),
                    int(p.get("is_pinned", 0))
                ))

        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def sync_user_history(
    authenticated_user_id: int,
    owner_username: str,
    threads: Optional[List[Dict[str, Any]]] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
    user_memories: Optional[List[Dict[str, Any]]] = None,
    projects: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Strictly tenant-scoped history synchronization for an ALREADY authenticated user.
    Used when ephemeral cloud containers reset /tmp SQLite or when importing a user's
    portable backup archive. Rejects cross-user payloads and namespaces colliding IDs.
    """
    conn = get_connection()
    if isinstance(conn, _RemoteLibSQLConnection):
        conn.buffer_writes = True
    c = conn.cursor()
    try:
        c.execute("SELECT id, username FROM users WHERE id = ?", (int(authenticated_user_id),))
        existing = c.fetchone()
        if not existing:
            return {"success": False, "error": "Authenticated account not found", "status": 401}
        actual_uname = str(existing["username"]).strip().lower()
        req_uname = str(owner_username or "").strip().lower()
        if req_uname and req_uname != actual_uname:
            return {"success": False, "error": "Forbidden: Cross-account history payload rejected", "status": 403}

        target_uid = int(existing["id"])
        restored_threads = 0
        restored_messages = 0
        id_remap: Dict[str, str] = {}

        for t in (threads or [])[:5000]:
            if not isinstance(t, dict) or not t.get("id"):
                continue
            raw_tid = str(t["id"])
            safe_tid = "".join(ch for ch in raw_tid if ch.isalnum() or ch in ("_", "-"))[:64]
            if not safe_tid:
                continue
            c.execute("SELECT user_id FROM threads WHERE id = ?", (safe_tid,))
            owner_row = c.fetchone()
            if owner_row and int(owner_row["user_id"]) != target_uid:
                safe_tid = f"th_{target_uid}_{safe_tid}"[:64]
            id_remap[raw_tid] = safe_tid

            title = str(t.get("title") or "Saved Conversation").strip()[:120] or "Saved Conversation"
            is_pinned = int(bool(t.get("is_pinned", 0)))
            updated_at = str(t.get("updated_at") or datetime.datetime.now(datetime.timezone.utc).isoformat())[:32]
            c.execute("""
                INSERT OR IGNORE INTO threads (id, user_id, title, is_pinned, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (safe_tid, target_uid, title, is_pinned, updated_at))
            if c.rowcount > 0:
                restored_threads += 1

        msgs_by_tid: Dict[str, List[Dict[str, Any]]] = {}
        for m in (messages or [])[:50000]:
            if not isinstance(m, dict) or not m.get("thread_id"):
                continue
            raw_tid = str(m["thread_id"])
            mapped_tid = id_remap.get(raw_tid)
            if not mapped_tid:
                safe_tid = "".join(ch for ch in raw_tid if ch.isalnum() or ch in ("_", "-"))[:64]
                if not safe_tid:
                    continue
                c.execute("SELECT user_id FROM threads WHERE id = ?", (safe_tid,))
                owner_row = c.fetchone()
                if owner_row and int(owner_row["user_id"]) != target_uid:
                    safe_tid = f"th_{target_uid}_{safe_tid}"[:64]
                c.execute("INSERT OR IGNORE INTO threads (id, user_id, title) VALUES (?, ?, ?)", (safe_tid, target_uid, "Restored Conversation"))
                mapped_tid = safe_tid
                id_remap[raw_tid] = safe_tid
            msgs_by_tid.setdefault(mapped_tid, []).append(m)

        for mapped_tid, t_msgs in msgs_by_tid.items():
            c.execute("SELECT COUNT(*) as cnt FROM messages WHERE thread_id = ? AND user_id = ?", (mapped_tid, target_uid))
            cnt_row = c.fetchone()
            existing_cnt = int((cnt_row["cnt"] if isinstance(cnt_row, (dict, sqlite3.Row)) else cnt_row[0]) if cnt_row else 0)
            # Only append slice beyond what already exists on this container
            if len(t_msgs) > existing_cnt:
                for m in t_msgs[existing_cnt:]:
                    tools_json = m.get("tools_json")
                    if tools_json is None and isinstance(m.get("tools"), list) and m.get("tools"):
                        tools_json = json.dumps(m["tools"])
                    c.execute("""
                        INSERT INTO messages (thread_id, user_id, role, content, tools_json)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        mapped_tid,
                        target_uid,
                        str(m.get("role", "user"))[:24],
                        str(m.get("content", "")),
                        tools_json,
                    ))
                    restored_messages += 1

        for mem in (user_memories or [])[:500]:
            if isinstance(mem, dict) and mem.get("key"):
                c.execute("""
                    INSERT OR IGNORE INTO user_memories (user_id, key, value)
                    VALUES (?, ?, ?)
                """, (target_uid, str(mem["key"])[:120], str(mem.get("value", ""))[:4000]))

        for p in (projects or [])[:200]:
            if isinstance(p, dict) and p.get("id") and p.get("name"):
                safe_pid = "".join(ch for ch in str(p["id"]) if ch.isalnum() or ch in ("_", "-"))[:64]
                if not safe_pid:
                    continue
                c.execute("SELECT user_id FROM projects WHERE id = ?", (safe_pid,))
                p_owner = c.fetchone()
                if p_owner and int(p_owner["user_id"]) != target_uid:
                    safe_pid = f"p_{target_uid}_{safe_pid}"[:64]
                c.execute("""
                    INSERT OR IGNORE INTO projects (id, user_id, name, company, stack, path, description, is_pinned)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    safe_pid, target_uid, str(p["name"])[:100], str(p.get("company", ""))[:100],
                    str(p.get("stack", "Python"))[:80], str(p.get("path", ""))[:260], str(p.get("description", ""))[:500],
                    int(bool(p.get("is_pinned", 0))),
                ))

        conn.commit()
        return {
            "success": True,
            "restored_threads": restored_threads,
            "restored_messages": restored_messages,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "status": 500}
    finally:
        conn.close()


# ===================================================================================
# COMPLAINTS, BUG REPORTS & STRUCTURED ACTION PLANNING ENGINE
# ===================================================================================

_REPORT_TRACKS = {
    "bug": ("Core Engineering", "24h SLA", "Reproduce failure trace & add automated regression test"),
    "ui": ("Design & Experience Studio", "24h SLA", "Audit responsive layout, glass contrast & interaction polish"),
    "feature": ("Product Roadmap Council", "48h SLA", "Scope architecture spec, zero-cost feasibility & sprint milestone"),
    "billing": ("Owner Membership Desk (@ig.ahmed.irl)", "4h Priority SLA", "Verify activation key timer, quota ledger & instant renewal"),
    "ai": ("AURA Brain & Model Engineering", "24h SLA", "Evaluate prompt routing, reasoning depth & self-healing guardrails"),
    "security": ("Security & Data Vault Ops", "2h Critical SLA", "Audit scrypt auth, CSP/CORS boundaries & tenant isolation"),
}


def build_report_action_plan(category: str, severity: str, title: str, description: str) -> Dict[str, Any]:
    """Generates a deterministic engineering resolution plan for every complaint/report."""
    cat = str(category or "bug").strip().lower()
    if cat not in _REPORT_TRACKS:
        cat = "bug"
    sev = str(severity or "medium").strip().lower()
    if sev not in ("critical", "high", "medium", "low"):
        sev = "medium"
    track, default_sla, core_step = _REPORT_TRACKS[cat]
    sla = "2h Emergency SLA" if sev == "critical" else ("8h High-Priority SLA" if sev == "high" else default_sla)
    summary_hint = (str(title or "").strip() or str(description or "").strip())[:90]
    steps = [
        {
            "id": "step_1",
            "title": "Automated Diagnostics & Ticket Triage",
            "detail": f"Captured ticket context ({cat.upper()} / {sev.upper()}) and routed directly to {track}.",
            "status": "done",
        },
        {
            "id": "step_2",
            "title": "Root-Cause Engineering Audit",
            "detail": f"{core_step} for: \"{summary_hint}\".",
            "status": "in_progress",
        },
        {
            "id": "step_3",
            "title": "Patch Implementation & Automated Test Verification",
            "detail": "Apply surgical fix, run full pytest + JS runtime regression suite, and verify zero side-effects.",
            "status": "pending",
        },
        {
            "id": "step_4",
            "title": "Production Release & Member Confirmation",
            "detail": "Deploy live to aura-agent.xyz and notify member with Owner resolution note.",
            "status": "pending",
        },
    ]
    return {
        "track": track,
        "sla": sla,
        "priority": sev.upper(),
        "steps": steps,
    }


def create_user_report(
    user_id: int,
    username: str,
    category: str,
    severity: str,
    title: str,
    description: str,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    clean_title = str(title or "").strip()[:140]
    clean_desc = str(description or "").strip()[:4000]
    if len(clean_title) < 3:
        return {"success": False, "error": "Please enter a clear title (at least 3 characters)."}
    if len(clean_desc) < 8:
        return {"success": False, "error": "Please describe the complaint or report (at least 8 characters)."}

    cat = str(category or "bug").strip().lower()[:32]
    if cat not in _REPORT_TRACKS:
        cat = "bug"
    sev = str(severity or "medium").strip().lower()[:16]
    if sev not in ("critical", "high", "medium", "low"):
        sev = "medium"

    report_id = f"AURA-RPT-{secrets.token_hex(3).upper()}"
    now_ts = time.time()
    plan = build_report_action_plan(cat, sev, clean_title, clean_desc)
    diag_safe = diagnostics if isinstance(diagnostics, dict) else {}

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT INTO user_reports
            (id, user_id, username, category, severity, title, description, diagnostics_json, status, action_plan_json, admin_reply, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planned', ?, '', ?, ?)
            """,
            (
                report_id,
                int(user_id),
                str(username or "").strip().lower()[:64],
                cat,
                sev,
                clean_title,
                clean_desc,
                json.dumps(diag_safe)[:4000],
                json.dumps(plan),
                now_ts,
                now_ts,
            ),
        )
        conn.commit()
        return {
            "success": True,
            "report": {
                "id": report_id,
                "user_id": int(user_id),
                "username": str(username or "").strip().lower(),
                "category": cat,
                "severity": sev,
                "title": clean_title,
                "description": clean_desc,
                "diagnostics": diag_safe,
                "status": "planned",
                "action_plan": plan,
                "admin_reply": "",
                "created_at": now_ts,
                "updated_at": now_ts,
            },
        }
    finally:
        conn.close()


def _row_to_report_dict(row: Any) -> Dict[str, Any]:
    try:
        plan = json.loads(row["action_plan_json"] or "{}")
    except Exception:
        plan = {}
    try:
        diag = json.loads(row["diagnostics_json"] or "{}")
    except Exception:
        diag = {}
    return {
        "id": row["id"],
        "user_id": int(row["user_id"]),
        "username": row["username"],
        "category": row["category"],
        "severity": row["severity"],
        "title": row["title"],
        "description": row["description"],
        "diagnostics": diag,
        "status": row["status"],
        "action_plan": plan,
        "admin_reply": row["admin_reply"] or "",
        "created_at": float(row["created_at"] or 0),
        "updated_at": float(row["updated_at"] or 0),
    }


def list_user_reports(user_id: Optional[int] = None, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    try:
        clauses = []
        params: List[Any] = []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(int(user_id))
        if status and str(status).strip().lower() not in ("", "all"):
            clauses.append("status = ?")
            params.append(str(status).strip().lower())
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(max(1, min(int(limit or 100), 300)))
        c.execute(f"SELECT * FROM user_reports {where_sql} ORDER BY created_at DESC LIMIT ?", tuple(params))
        return [_row_to_report_dict(r) for r in c.fetchall()]
    finally:
        conn.close()


def update_user_report(
    report_id: str,
    status: Optional[str] = None,
    admin_reply: Optional[str] = None,
    action_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rid = str(report_id or "").strip().upper()
    if not rid:
        return {"success": False, "error": "Report ID is required."}
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM user_reports WHERE id = ?", (rid,))
        row = c.fetchone()
        if not row:
            return {"success": False, "error": f"Report {rid} not found."}
        cur_status = str(row["status"] or "planned")
        new_status = cur_status
        if status and str(status).strip().lower() in ("submitted", "triage", "planned", "in_progress", "resolved", "closed"):
            new_status = str(status).strip().lower()
        new_reply = str(admin_reply).strip()[:2000] if admin_reply is not None else str(row["admin_reply"] or "")
        try:
            plan_obj = json.loads(row["action_plan_json"] or "{}")
        except Exception:
            plan_obj = {}
        if isinstance(action_plan, dict):
            plan_obj = action_plan
        elif new_status in ("resolved", "closed") and isinstance(plan_obj.get("steps"), list):
            for st in plan_obj["steps"]:
                if isinstance(st, dict):
                    st["status"] = "done"
        elif new_status == "in_progress" and isinstance(plan_obj.get("steps"), list):
            for idx, st in enumerate(plan_obj["steps"]):
                if isinstance(st, dict):
                    st["status"] = "done" if idx < 2 else ("in_progress" if idx == 2 else "pending")
        now_ts = time.time()
        c.execute(
            "UPDATE user_reports SET status = ?, admin_reply = ?, action_plan_json = ?, updated_at = ? WHERE id = ?",
            (new_status, new_reply, json.dumps(plan_obj), now_ts, rid),
        )
        conn.commit()
        c.execute("SELECT * FROM user_reports WHERE id = ?", (rid,))
        updated = c.fetchone()
        return {"success": True, "report": _row_to_report_dict(updated)}
    finally:
        conn.close()


# ===================================================================================
# SELF-HEALING MISTAKE-PREVENTION MEMORY (NEVER REPEAT A FIXED BUG TWICE)
# ===================================================================================

def record_mistake_lesson(
    user_id: int,
    error_signature: str,
    root_cause: str,
    verified_fix: str,
    prevention_rule: str,
    project_scope: str = "workspace",
) -> Dict[str, Any]:
    sig = str(error_signature or "").strip()[:180]
    if not sig:
        return {"success": False, "error": "error_signature required"}
    now_ts = time.time()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id, occurrences, resolved_count FROM mistake_memory WHERE user_id = ? AND error_signature = ?", (int(user_id), sig))
        existing = c.fetchone()
        if existing:
            c.execute(
                """
                UPDATE mistake_memory
                SET root_cause = ?, verified_fix = ?, prevention_rule = ?, project_scope = ?,
                    occurrences = occurrences + 1, resolved_count = resolved_count + 1, last_seen_at = ?
                WHERE id = ?
                """,
                (
                    str(root_cause or "")[:600],
                    str(verified_fix or "")[:800],
                    str(prevention_rule or "")[:600],
                    str(project_scope or "workspace")[:80],
                    now_ts,
                    int(existing["id"]),
                ),
            )
            lesson_id = int(existing["id"])
        else:
            c.execute(
                """
                INSERT INTO mistake_memory
                (user_id, project_scope, error_signature, root_cause, verified_fix, prevention_rule, occurrences, resolved_count, last_seen_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
                """,
                (
                    int(user_id),
                    str(project_scope or "workspace")[:80],
                    sig,
                    str(root_cause or "")[:600],
                    str(verified_fix or "")[:800],
                    str(prevention_rule or "")[:600],
                    now_ts,
                    now_ts,
                ),
            )
            lesson_id = int(c.lastrowid)
        conn.commit()
        return {"success": True, "id": lesson_id, "error_signature": sig}
    finally:
        conn.close()


def list_mistake_lessons(user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "SELECT * FROM mistake_memory WHERE user_id = ? ORDER BY last_seen_at DESC LIMIT ?",
            (int(user_id), max(1, min(int(limit or 30), 100))),
        )
        return [
            {
                "id": int(r["id"]),
                "project_scope": r["project_scope"],
                "error_signature": r["error_signature"],
                "root_cause": r["root_cause"],
                "verified_fix": r["verified_fix"],
                "prevention_rule": r["prevention_rule"],
                "occurrences": int(r["occurrences"] or 1),
                "resolved_count": int(r["resolved_count"] or 1),
                "last_seen_at": float(r["last_seen_at"] or 0),
                "created_at": float(r["created_at"] or 0),
            }
            for r in c.fetchall()
        ]
    finally:
        conn.close()


def build_mistake_prevention_prompt(user_id: int, limit: int = 10) -> str:
    lessons = list_mistake_lessons(user_id, limit=limit)
    if not lessons:
        return ""
    lines = ["[SELF-HEALING MISTAKE-PREVENTION MEMORY — NEVER REPEAT THESE PAST ERRORS]:"]
    for item in lessons[:limit]:
        lines.append(f"- Avoid `{item['error_signature']}`: {item['prevention_rule']} (Verified fix: {item['verified_fix']})")
    return "\n".join(lines)
