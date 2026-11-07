"""
===================================================================================
                     AURA AGENT - MULTI-USER SECURE DATABASE
===================================================================================
Enterprise-grade SQLite database supporting:
- Multi-user authentication (password hashing with SHA-256 + salt)
- Isolated user workspaces, conversation threads, pinned sessions
- Per-user long-term memory vault
- Cloud and LAN deployment ready
Author: AURA Technologies Inc.
===================================================================================
"""

import os
import datetime
import time
import sqlite3
import hashlib
import hmac
import secrets
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import tempfile
import urllib.request
import urllib.error

def _resolve_db_path() -> Path:
    custom_path = os.environ.get("AURA_PERSISTENT_DB_PATH", "").strip()
    if custom_path:
        return Path(custom_path)
    default_dir = Path(__file__).resolve().parent
    if os.environ.get("VERCEL") or not os.access(default_dir, os.W_OK):
        return Path(tempfile.gettempdir()) / "aura_workspace.db"
    return default_dir / "aura_workspace.db"

DB_PATH = _resolve_db_path()


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
        return {
            "persistent": False,
            "mode": "ephemeral_serverless_tmp",
            "engine": "sqlite3_ephemeral",
            "production_accounts_available": False,
            "message": "Production accounts unavailable: persistent database storage (AURA_DATABASE_URL / TURSO_DATABASE_URL) is not configured on this serverless deployment. /tmp SQLite is ephemeral and is not used for permanent account storage."
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
    def __init__(self, url: str, auth_token: str):
        self.url = url.rstrip("/")
        if self.url.startswith("libsql://"):
            self.url = "https://" + self.url[len("libsql://"):]
        if not self.url.endswith("/v2/pipeline"):
            self.url = self.url + "/v2/pipeline"
        self.auth_token = auth_token
        self._rows: List[Dict[str, Any]] = []
        self._pos = 0
        self.lastrowid: Optional[int] = None
        self.rowcount: int = 0

    def _convert_arg(self, val: Any) -> Dict[str, Any]:
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
        payload = json.dumps({
            "requests": [
                {"type": "execute", "stmt": stmt},
                {"type": "close"}
            ]
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        req = urllib.request.Request(self.url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        first = data.get("results", [{}])[0]
        if first.get("type") == "error":
            err_msg = first.get("error", {}).get("message", "LibSQL execution error")
            if "UNIQUE constraint failed" in err_msg:
                raise sqlite3.IntegrityError(err_msg)
            raise sqlite3.OperationalError(err_msg)
        res = first.get("response", {}).get("result", {})
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
    def __init__(self, url: str, auth_token: str):
        self.url = url
        self.auth_token = auth_token

    def cursor(self):
        return _RemoteLibSQLCursor(self.url, self.auth_token)

    def commit(self):
        pass

    def close(self):
        pass

# Scrypt configuration (OWASP standard, ~20ms, zero third-party dependencies)
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEYLEN = 64


def get_connection():
    remote_url = os.environ.get("AURA_DATABASE_URL", "").strip() or os.environ.get("TURSO_DATABASE_URL", "").strip()
    if remote_url:
        auth_token = os.environ.get("AURA_DATABASE_AUTH_TOKEN", "").strip() or os.environ.get("TURSO_AUTH_TOKEN", "").strip()
        return _RemoteLibSQLConnection(remote_url, auth_token)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
    Seamlessly verifies legacy SHA-256 and flags it for automatic upgrade!
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
    else:
        # Legacy SHA-256 constant-time check
        legacy_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
        is_valid = hmac.compare_digest(legacy_hash, stored_hash)
        return is_valid, is_valid



_LOGIN_FAILURES: Dict[str, List[float]] = {}
MAX_LOGIN_FAILURES = 5
LOCKOUT_WINDOW_SECONDS = 300  # 5 minutes lockout

def check_login_rate_limit(username: str) -> Tuple[bool, int]:
    now = time.time()
    attempts = [t for t in _LOGIN_FAILURES.get(username, []) if now - t < LOCKOUT_WINDOW_SECONDS]
    _LOGIN_FAILURES[username] = attempts
    if len(attempts) >= MAX_LOGIN_FAILURES:
        wait_seconds = int(LOCKOUT_WINDOW_SECONDS - (now - attempts[0]))
        return False, max(1, wait_seconds)
    return True, 0

def record_login_failure(username: str):
    now = time.time()
    if username not in _LOGIN_FAILURES:
        _LOGIN_FAILURES[username] = []
    _LOGIN_FAILURES[username].append(now)

def clear_login_failures(username: str):
    _LOGIN_FAILURES.pop(username, None)

def validate_password_strength(password: str) -> Tuple[bool, str]:
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        return False, "Password must contain both letters and numbers."
    return True, ""

def init_database():
    conn = get_connection()
    c = conn.cursor()

    # Users Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            display_name TEXT,
            settings_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Active Auth Sessions Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Conversation Threads Table (with Pinning & Rename)
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

    # Messages Table
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

    # Per-user Persistent Memory
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

    # Dedicated Coding Workspaces / Projects Table
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


    # Schema migration: ensure role exists in users table defaulting to 'user'
    c.execute("PRAGMA table_info(users)")
    user_cols = [(col["name"] if isinstance(col, dict) else col[1]) for col in c.fetchall()]
    if "role" not in user_cols:
        try:
            c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        except Exception:
            pass
    conn.commit()

    # Schema migration: ensure expires_at exists in auth_sessions
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
# AUTHENTICATION API
# ===================================================================================

def register_user(username: str, password: str) -> Dict[str, Any]:
    if not is_persistent_storage_configured():
        return {
            "success": False,
            "storage_unavailable": True,
            "error": "Production accounts are unavailable: persistent database storage is not configured on this serverless deployment."
        }
    username = username.strip().lower()
    if len(username) < 3:
        return {"success": False, "error": "Username must be at least 3 characters."}
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

        # Generate session token with 30-day expiration
        token = secrets.token_hex(24)
        expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat()
        c.execute("INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))

        # Create default initial thread
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
                "display_name": display_name
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
    if not is_persistent_storage_configured():
        return {
            "success": False,
            "storage_unavailable": True,
            "error": "Production accounts are unavailable: persistent database storage is not configured on this serverless deployment."
        }
    username = username.strip().lower()
    allowed, wait_sec = check_login_rate_limit(username)
    if not allowed:
        return {"success": False, "error": f"Too many failed login attempts. Please wait {wait_sec} seconds before trying again."}

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, username, password_hash, salt, display_name, settings_json FROM users WHERE username = ?", (username,))
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

    # Seamless automatic upgrade of legacy hashes to scrypt upon successful login
    if needs_upgrade:
        new_hash, new_salt = hash_password(password)
        c.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, user_id))
        conn.commit()

    # Successful authentication
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
            "display_name": row["display_name"] or row["username"].capitalize()
        }
    }


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
    if not token:
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

    # Enforce session expiration check
    expires_at_str = row["expires_at"]
    if expires_at_str:
        try:
            exp = datetime.datetime.fromisoformat(expires_at_str)
            now = datetime.datetime.now(datetime.timezone.utc)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=datetime.timezone.utc)
            if exp < now:
                c.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
                conn.commit()
                conn.close()
                return None
        except Exception:
            pass

    conn.close()
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"] or row["username"].capitalize(),
        "role": row["role"] if "role" in row.keys() else "user",
        "settings": json.loads(row["settings_json"] or "{}")
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
    if not thread_id:
        thread_id = f"th_{secrets.token_hex(8)}"
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, title, is_pinned FROM threads WHERE id = ? AND user_id = ?", (thread_id, user_id))
    existing = c.fetchone()
    if existing:
        conn.close()
        return dict(existing)

    c.execute("""
        INSERT INTO threads (id, user_id, title)
        VALUES (?, ?, ?)
    """, (thread_id, user_id, title))
    conn.commit()
    conn.close()
    return {"id": thread_id, "title": title, "is_pinned": 0}


def rename_user_thread(user_id: int, thread_id: str, new_title: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE threads
        SET title = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
    """, (new_title.strip(), thread_id, user_id))
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
    conn = get_connection()
    c = conn.cursor()
    # Ensure thread exists for this user
    c.execute("SELECT id FROM threads WHERE id = ? AND user_id = ?", (thread_id, user_id))
    if not c.fetchone():
        clean_first = content.strip().split("\n")[0].strip()
        title = (clean_first[:28] + "...") if len(clean_first) > 28 else (clean_first or "New Conversation")
        c.execute("""
            INSERT INTO threads (id, user_id, title)
            VALUES (?, ?, ?)
        """, (thread_id, user_id, title))

    tools_str = json.dumps(tools) if tools else None
    c.execute("""
        INSERT INTO messages (thread_id, user_id, role, content, tools_json)
        VALUES (?, ?, ?, ?, ?)
    """, (thread_id, user_id, role, content, tools_str))
    c.execute("""
        UPDATE threads
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
    """, (thread_id, user_id))
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
    if not path:
        # Default project directory
        path = str(Path(r"c:\Users\hp\cyberheist") / name.replace(" ", "_").lower())
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO projects (id, user_id, name, company, stack, path, description, is_pinned)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    """, (project_id, user_id, name.strip(), company.strip(), stack.strip(), path.strip(), description.strip()))
    
    # Also create initial project thread
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
        "path": path,
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
    c.execute("UPDATE projects SET is_pinned = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
              (1 if is_pinned else 0, project_id, user_id))
    affected = c.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def rename_user_project(user_id: int, project_id: str, new_name: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE projects SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
              (new_name.strip(), project_id, user_id))
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
    """Assigns a verified role ('admin', 'developer', 'user') to a user. Cannot be self-invoked via API."""
    if role not in ("admin", "developer", "user"):
        return False
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()
    return True


# ===================================================================================
# DATABASE BACKUP & MIGRATION API
# ===================================================================================

def export_database_backup(backup_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Exports all users, threads, messages, user_memories, and projects into a
    portable JSON backup snapshot so existing local SQLite data can be safely
    migrated to a persistent cloud database (e.g., Turso/LibSQL) or restored.
    """
    conn = get_connection()
    c = conn.cursor()
    table_queries = {
        "users": "SELECT * FROM users",
        "threads": "SELECT * FROM threads",
        "messages": "SELECT * FROM messages",
        "user_memories": "SELECT * FROM user_memories",
        "projects": "SELECT * FROM projects",
    }
    snapshot: Dict[str, Any] = {
        "schema_version": 1,
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
    """
    Idempotently imports a database backup snapshot into the active database
    (local SQLite or remote cloud LibSQL/Turso) without overwriting existing conflicts.
    """
    tables = snapshot.get("tables", {})
    counts: Dict[str, int] = {}
    conn = get_connection()
    c = conn.cursor()
    try:
        for u in tables.get("users", []):
            c.execute("""
                INSERT OR IGNORE INTO users (id, username, password_hash, salt, display_name, settings_json, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                u["id"], u["username"], u["password_hash"], u["salt"],
                u.get("display_name"), u.get("settings_json", "{}"),
                u.get("role", "user"), u.get("created_at")
            ))
        counts["users"] = len(tables.get("users", []))

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


def compute_csrf_token(session_token: str) -> str:
    """Computes a deterministic per-session CSRF token bound to the session token."""
    secret_seed = os.environ.get("AURA_CSRF_SECRET", "aura-csrf-hmac-key-v1")
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

