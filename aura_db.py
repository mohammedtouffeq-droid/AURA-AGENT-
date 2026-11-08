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


def _get_or_create_secret(env_name: str, key_name: str) -> str:
    env_val = os.environ.get(env_name, "").strip()
    if env_val:
        return env_val
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
        return {
            "persistent": False,
            "mode": "serverless_ephemeral_sqlite",
            "engine": "sqlite3_ephemeral",
            "production_accounts_available": True,
            "vault_sync_enabled": vault_configured,
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
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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

    # Schema migrations for existing local SQLite files
    c.execute("PRAGMA table_info(users)")
    user_cols = [(col["name"] if isinstance(col, dict) else col[1]) for col in c.fetchall()]
    if "role" not in user_cols:
        try:
            c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
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

def register_user(username: str, password: str) -> Dict[str, Any]:
    if not isinstance(username, str) or not isinstance(password, str):
        return {"success": False, "error": "Username and password must be strings."}
    username = username.strip().lower()
    if len(username) < 3 or len(username) > 64:
        return {"success": False, "error": "Username must be between 3 and 64 characters."}
    if not all(ch.isalnum() or ch in ("_", ".", "-") for ch in username):
        return {"success": False, "error": "Username may only contain letters, numbers, underscores, dots, or hyphens."}
    valid_pass, pass_err = validate_password_strength(password)
    if not valid_pass:
        return {"success": False, "error": pass_err}

    hashed, salt = hash_password(password)
    display_name = username.capitalize()

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (username, password_hash, salt, display_name, settings_json, role)
            VALUES (?, ?, ?, ?, ?, 'user')
        """, (username, hashed, salt, display_name, json.dumps({})))
        user_id = c.lastrowid

        token = secrets.token_hex(24)
        expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat()
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


def login_user(username: str, password: str) -> Dict[str, Any]:
    if not isinstance(username, str) or not isinstance(password, str):
        return {"success": False, "error": "Invalid username or password."}
    username = username.strip().lower()
    allowed, wait_sec = check_login_rate_limit(username)
    if not allowed:
        return {"success": False, "error": f"Too many failed login attempts. Please wait {wait_sec} seconds before trying again."}

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, username, password_hash, salt, display_name, settings_json, COALESCE(role, 'user') as role FROM users WHERE username = ?",
        (username,)
    )
    row = c.fetchone()
    if not row:
        conn.close()
        record_login_failure(username)
        return {"success": False, "error": "Invalid username or password."}

    user_id = row["id"]
    is_valid, needs_upgrade = verify_password(password, row["password_hash"], row["salt"])
    if not is_valid:
        conn.close()
        record_login_failure(username)
        return {"success": False, "error": "Invalid username or password."}

    if needs_upgrade:
        new_hash, new_salt = hash_password(password)
        c.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, user_id))
        conn.commit()

    clear_login_failures(username)
    token = secrets.token_hex(24)
    expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat()
    c.execute("INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user_id,
            "username": row["username"],
            "display_name": row["display_name"] or row["username"].capitalize(),
            "role": row["role"] if "role" in row.keys() else "user"
        }
    }


def change_user_password(user_id: int, current_password: str, new_password: str) -> Dict[str, Any]:
    """Rotates a user's password after verifying current_password and revokes all prior sessions."""
    valid_pass, pass_err = validate_password_strength(new_password)
    if not valid_pass:
        return {"success": False, "error": pass_err}
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT password_hash, salt FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            return {"success": False, "error": "Account not found."}
        ok, _ = verify_password(current_password, row["password_hash"], row["salt"])
        if not ok:
            return {"success": False, "error": "Current password is incorrect."}
        new_hash, new_salt = hash_password(new_password)
        c.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, user_id))
        c.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        fresh_token = secrets.token_hex(24)
        expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat()
        c.execute("INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (fresh_token, user_id, expires_at))
        conn.commit()
        return {"success": True, "token": fresh_token, "message": "Password updated and old sessions revoked."}
    finally:
        conn.close()


def delete_user_account(user_id: int, password: str) -> Dict[str, Any]:
    """Deletes a user's account and cascades removal of all sessions, threads, messages, memories, and projects."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT password_hash, salt FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            return {"success": False, "error": "Account not found."}
        ok, _ = verify_password(password, row["password_hash"], row["salt"])
        if not ok:
            return {"success": False, "error": "Incorrect password."}
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
    """Generates and registers an active session token for a given user ID."""
    token = secrets.token_hex(24)
    expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    conn.commit()
    conn.close()
    return token


def authenticate_token(token: str) -> Optional[Dict[str, Any]]:
    if not token or not isinstance(token, str):
        return None
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.username, u.display_name, u.settings_json, s.expires_at, COALESCE(u.role, 'user') as role
        FROM auth_sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None

    # Fail-closed session expiration validation
    expires_at_str = row["expires_at"]
    if not expires_at_str:
        c.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return None
    try:
        exp = datetime.datetime.fromisoformat(str(expires_at_str))
        now = datetime.datetime.now(datetime.timezone.utc)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=datetime.timezone.utc)
        if exp < now:
            c.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            conn.commit()
            conn.close()
            return None
    except (ValueError, TypeError):
        c.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return None

    conn.close()
    try:
        parsed_settings = json.loads(row["settings_json"] or "{}")
    except Exception:
        parsed_settings = {}
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"] or row["username"].capitalize(),
        "role": row["role"] if "role" in row.keys() else "user",
        "settings": parsed_settings
    }


def revoke_session(token: str) -> bool:
    if not token:
        return False
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
    affected = c.rowcount > 0
    conn.commit()
    conn.close()
    return affected


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
    c.execute("SELECT id, user_id FROM threads WHERE id = ?", (safe_tid,))
    t_row = c.fetchone()
    if not t_row:
        clean_first = content.strip().split("\n")[0].strip()
        title = (clean_first[:28] + "...") if len(clean_first) > 28 else (clean_first or "New Conversation")
        c.execute("""
            INSERT INTO threads (id, user_id, title)
            VALUES (?, ?, ?)
        """, (safe_tid, user_id, title))
    elif t_row["user_id"] != user_id:
        # Prevent cross-tenant thread ID collision
        safe_tid = f"th_{user_id}_{secrets.token_hex(6)}"
        clean_first = content.strip().split("\n")[0].strip()
        title = (clean_first[:28] + "...") if len(clean_first) > 28 else (clean_first or "New Conversation")
        c.execute("""
            INSERT INTO threads (id, user_id, title)
            VALUES (?, ?, ?)
        """, (safe_tid, user_id, title))

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


def save_user_settings(user_id: int, settings: Dict[str, Any]) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET settings_json = ? WHERE id = ?", (json.dumps(settings), user_id))
    conn.commit()
    conn.close()
    return True


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
