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
import sqlite3
import hashlib
import secrets
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

DB_PATH = Path(__file__).resolve().parent / "aura_workspace.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    return hashed, salt


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

    conn.commit()
    conn.close()


init_database()


# ===================================================================================
# AUTHENTICATION API
# ===================================================================================

def register_user(username: str, password: str) -> Dict[str, Any]:
    username = username.strip().lower()
    if len(username) < 3:
        return {"success": False, "error": "Username must be at least 3 characters."}
    if len(password) < 4:
        return {"success": False, "error": "Password must be at least 4 characters."}

    hashed, salt = hash_password(password)
    display_name = username.capitalize()

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (username, password_hash, salt, display_name, settings_json)
            VALUES (?, ?, ?, ?, ?)
        """, (username, hashed, salt, display_name, json.dumps({})))
        user_id = c.lastrowid

        # Generate session token
        token = secrets.token_hex(24)
        c.execute("INSERT INTO auth_sessions (token, user_id) VALUES (?, ?)", (token, user_id))

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
    username = username.strip().lower()
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, username, password_hash, salt, display_name, settings_json FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Invalid username or password."}

    user_id = row["id"]
    hashed, _ = hash_password(password, row["salt"])
    if hashed != row["password_hash"]:
        conn.close()
        return {"success": False, "error": "Invalid username or password."}

    token = secrets.token_hex(24)
    c.execute("INSERT INTO auth_sessions (token, user_id) VALUES (?, ?)", (token, user_id))
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


def authenticate_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.username, u.display_name, u.settings_json
        FROM auth_sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"] or row["username"].capitalize(),
        "settings": json.loads(row["settings_json"] or "{}")
    }


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


def create_user_thread(user_id: int, title: str = "New Session") -> Dict[str, Any]:
    thread_id = f"th_{secrets.token_hex(8)}"
    conn = get_connection()
    c = conn.cursor()
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
