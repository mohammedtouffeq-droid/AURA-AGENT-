"""
===================================================================================
                AURA LIVE BROWSER — AGENTIC BROWSER WORKSPACE ENGINE
===================================================================================
Capability #1: Integrated multi-tab AI Browser with live visual rendering,
real DOM & coordinate interaction (click, type, scroll, navigate, press),
screenshot capture, Gemini Vision + DOM page understanding, and synchronized
AI chat automation.

Execution Modes:
- Local Host: Persistent Node.js Playwright Chromium daemon (`aura_browser_worker.mjs`)
  driving real multi-tab Chromium with live JPEG frame rendering.
- Cloud / Vercel / Test Fallback: Strict SSRF-guarded HTTPS DOM fetcher +
  interactive element extractor + rendered visual preview card so every endpoint
  remains 100% functional without Chromium binaries.

All sessions and tabs are strictly isolated per authenticated `user_id`.
===================================================================================
"""

from __future__ import annotations

import base64
import html
import io
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aura_brain import AuraBrain, _SafePublicRedirectHandler, is_safe_public_url
from aura_live_actions import LIVE_ACTION_HUB
from aura_os_controller import is_test_runner_active

ROOT = Path(__file__).resolve().parent
WORKER_SCRIPT = ROOT / "aura_browser_worker.mjs"
MAX_TABS_PER_USER = 10
VIEWPORT_DEFAULT = {"width": 1280, "height": 760}


def _is_cloud_or_test() -> bool:
    return bool(os.environ.get("VERCEL") or is_test_runner_active())


def normalize_browser_url(raw: str) -> str:
    """Normalizes user-entered URL or search query into a clean http(s) URL."""
    s = str(raw or "").strip()
    if not s:
        return ""
    lower = s.lower()
    if lower.startswith(("javascript:", "file:", "data:", "vbscript:", "chrome:", "about:")):
        return s  # Let is_safe_public_url explicitly reject dangerous schemes
    if re.match(r"^https?://", lower):
        return s
    # Domain-like input (e.g., "example.com", "wikipedia.org/wiki/AI", "github.com")
    if " " not in s and "." in s and not s.startswith("."):
        return "https://" + s
    # Otherwise convert natural search phrase into a clean DuckDuckGo HTML search URL
    return "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(s)


def validate_browser_url(raw_url: str) -> Tuple[bool, str, str]:
    """Normalizes and validates URL against AURA's strict SSRF guard."""
    normalized = normalize_browser_url(raw_url)
    if not normalized:
        return False, "", "URL cannot be empty."
    ok, reason = is_safe_public_url(normalized)
    if not ok:
        return False, normalized, reason
    return True, normalized, ""


class _DomExtractor(HTMLParser):
    """Safe zero-dependency HTML DOM & interactive element extractor for cloud fallback."""

    SKIP_TAGS = {"script", "style", "noscript", "svg", "template"}

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._skip_depth = 0
        self._in_title = False
        self._active_el: Optional[Dict[str, Any]] = None
        self.title_parts: List[str] = []
        self.text_parts: List[str] = []
        self.headings: List[str] = []
        self._in_heading = False
        self._heading_buf: List[str] = []
        self.elements: List[Dict[str, Any]] = []
        self.meta_desc: str = ""

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if t in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        if t == "title":
            self._in_title = True
        elif t == "meta" and attr_map.get("name", "").lower() == "description" and attr_map.get("content"):
            self.meta_desc = attr_map["content"].strip()[:300]
        elif t in ("h1", "h2", "h3"):
            self._in_heading = True
            self._heading_buf = []
        elif t in ("a", "button", "input", "textarea", "select") and len(self.elements) < 36:
            idx = len(self.elements) + 1
            href = ""
            if t == "a" and attr_map.get("href"):
                href = urllib.parse.urljoin(self.base_url, attr_map["href"].strip())
            el = {
                "index": idx,
                "tag": t,
                "type": attr_map.get("type", ""),
                "text": (
                    attr_map.get("aria-label")
                    or attr_map.get("placeholder")
                    or attr_map.get("value")
                    or attr_map.get("title")
                    or attr_map.get("name")
                    or ""
                ).strip()[:90],
                "href": href[:260],
                "x": 140 + ((idx - 1) % 3) * 340,
                "y": 180 + ((idx - 1) // 3) * 44,
                "w": 260,
                "h": 34,
            }
            if t in ("input", "textarea", "select"):
                if attr_map.get("type", "").lower() != "hidden":
                    if not el["text"]:
                        el["text"] = f"{t} ({el['type'] or 'text'})"
                    self.elements.append(el)
            else:
                self._active_el = el

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if t == "title":
            self._in_title = False
        elif t in ("h1", "h2", "h3") and self._in_heading:
            self._in_heading = False
            h_txt = " ".join("".join(self._heading_buf).split()).strip()
            if h_txt and len(self.headings) < 12:
                self.headings.append(h_txt[:140])
        elif self._active_el and t == self._active_el["tag"]:
            el = self._active_el
            self._active_el = None
            if el["text"] or el["href"]:
                if not el["text"]:
                    el["text"] = el["href"][:64]
                self.elements.append(el)

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        txt = " ".join(data.split()).strip()
        if not txt:
            return
        if self._in_title:
            self.title_parts.append(txt)
        if self._in_heading:
            self._heading_buf.append(txt + " ")
        if self._active_el is not None:
            combined = (self._active_el["text"] + " " + txt).strip()
            self._active_el["text"] = combined[:90]
        if len(self.text_parts) < 280:
            self.text_parts.append(txt)


def _render_cloud_preview_jpeg(
    url: str,
    title: str,
    page_text: str,
    elements: List[Dict[str, Any]],
    scroll_y: int = 0,
    cursor: Optional[Dict[str, int]] = None,
) -> str:
    """Renders a crisp dark-obsidian JPEG preview of fetched web content when Chromium is unavailable."""
    try:
        from PIL import Image, ImageDraw, ImageFont

        w, h = VIEWPORT_DEFAULT["width"], VIEWPORT_DEFAULT["height"]
        img = Image.new("RGB", (w, h), (10, 12, 18))
        draw = ImageDraw.Draw(img)

        try:
            font_lg = ImageFont.truetype("arial.ttf", 26)
            font_md = ImageFont.truetype("arial.ttf", 17)
            font_sm = ImageFont.truetype("arial.ttf", 14)
        except Exception:
            font_lg = ImageFont.load_default()
            font_md = ImageFont.load_default()
            font_sm = ImageFont.load_default()

        # Subtle top header bar
        draw.rectangle([0, 0, w, 72], fill=(15, 18, 28))
        draw.line([0, 72, w, 72], fill=(42, 50, 68), width=1)
        draw.text((28, 16), (title or url)[:78], fill=(244, 244, 245), font=font_lg)
        draw.text((28, 46), f"{url[:98]}   |   Cloud Live DOM Engine   |   Scroll Y: {scroll_y}px", fill=(148, 163, 184), font=font_sm)

        # Main readable content pane (left 760px)
        draw.rounded_rectangle([24, 92, 820, h - 24], radius=12, fill=(14, 17, 26), outline=(36, 44, 62), width=1)
        draw.text((42, 108), "EXTRACTED LIVE PAGE CONTENT", fill=(226, 185, 111), font=font_sm)

        clean_text = page_text or "No readable text extracted from this URL."
        char_offset = min(max(0, int(scroll_y * 2)), max(0, len(clean_text) - 180))
        visible = clean_text[char_offset : char_offset + 2200]
        words = visible.split()
        lines: List[str] = []
        cur = ""
        for word in words:
            if len(cur) + len(word) + 1 > 82:
                lines.append(cur)
                cur = word
                if len(lines) >= 24:
                    break
            else:
                cur = (cur + " " + word).strip()
        if cur and len(lines) < 24:
            lines.append(cur)

        y_pos = 138
        for ln in lines:
            draw.text((42, y_pos), ln, fill=(224, 228, 236), font=font_md)
            y_pos += 24

        # Interactive elements pane (right column)
        draw.rounded_rectangle([840, 92, w - 24, h - 24], radius=12, fill=(14, 17, 26), outline=(36, 44, 62), width=1)
        draw.text((858, 108), f"INTERACTIVE ELEMENTS ({len(elements)})", fill=(110, 231, 183), font=font_sm)

        ey = 140
        for el in elements[:16]:
            tag = str(el.get("tag") or "el").upper()
            label = str(el.get("text") or el.get("href") or "")[:36]
            draw.rounded_rectangle([856, ey, w - 40, ey + 30], radius=6, fill=(22, 27, 40), outline=(48, 58, 82), width=1)
            draw.text((866, ey + 7), f"[{el.get('index', 0)}] {tag}: {label}", fill=(228, 228, 231), font=font_sm)
            ey += 36
            if ey > h - 58:
                break

        if cursor and isinstance(cursor.get("x"), (int, float)) and isinstance(cursor.get("y"), (int, float)):
            cx, cy = int(cursor["x"]), int(cursor["y"])
            draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], outline=(226, 185, 111), width=3)
            draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(226, 185, 111))

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


class _NodePlaywrightBridge:
    """Thread-safe persistent JSON-RPC client for local `aura_browser_worker.mjs`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen[str]] = None
        self._req_id = 0
        self._unavailable_reason: Optional[str] = None
        self._checked = False

    def is_available(self) -> Tuple[bool, str]:
        if _is_cloud_or_test():
            return False, "Cloud serverless or test sandbox active"
        if not WORKER_SCRIPT.exists():
            return False, "aura_browser_worker.mjs missing"
        if not shutil.which("node"):
            return False, "Node.js runtime not found on PATH"
        if self._unavailable_reason and self._checked:
            return False, self._unavailable_reason
        return True, "Playwright Chromium local daemon ready"

    def _ensure_started_locked(self) -> subprocess.Popen[str]:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        node_bin = shutil.which("node")
        if not node_bin:
            self._checked = True
            self._unavailable_reason = "Node.js not installed"
            raise RuntimeError(self._unavailable_reason)

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        self._proc = subprocess.Popen(
            [node_bin, str(WORKER_SCRIPT)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=str(ROOT),
            creationflags=creationflags,
        )
        return self._proc

    def call(self, cmd: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 28.0) -> Dict[str, Any]:
        avail, reason = self.is_available()
        if not avail:
            raise RuntimeError(reason)

        with self._lock:
            proc = self._ensure_started_locked()
            self._req_id += 1
            req_id = self._req_id
            req_obj = {"id": req_id, "cmd": cmd, **(payload or {})}
            assert proc.stdin is not None and proc.stdout is not None
            try:
                proc.stdin.write(json.dumps(req_obj) + "\n")
                proc.stdin.flush()
            except Exception as exc:
                self._terminate_locked()
                raise RuntimeError(f"Playwright worker write failed: {exc}") from exc

            result_holder: Dict[str, Any] = {}

            def _read_line() -> None:
                try:
                    line = proc.stdout.readline()  # type: ignore[union-attr]
                    result_holder["line"] = line
                except Exception as exc:
                    result_holder["error"] = str(exc)

            reader = threading.Thread(target=_read_line, daemon=True)
            reader.start()
            reader.join(timeout=timeout)
            if reader.is_alive():
                self._terminate_locked()
                raise TimeoutError(f"Playwright browser command '{cmd}' timed out after {timeout}s")
            if "error" in result_holder:
                self._terminate_locked()
                raise RuntimeError(result_holder["error"])

            raw_line = (result_holder.get("line") or "").strip()
            if not raw_line:
                err_tail = ""
                try:
                    if proc.stderr:
                        err_tail = proc.stderr.read(400)
                except Exception:
                    pass
                self._terminate_locked()
                self._checked = True
                self._unavailable_reason = f"Playwright Chromium unavailable: {err_tail.strip() or 'worker exited'}"
                raise RuntimeError(self._unavailable_reason)

            parsed = json.loads(raw_line)
            if not parsed.get("ok"):
                err_msg = str(parsed.get("error") or "Browser command failed")
                if "playwright-core module not found" in err_msg or "executable doesn't exist" in err_msg.lower():
                    self._checked = True
                    self._unavailable_reason = err_msg
                raise RuntimeError(err_msg)
            self._checked = True
            self._unavailable_reason = None
            return parsed

    def _terminate_locked(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None


@dataclass
class BrowserTabState:
    id: str
    title: str = "New Tab"
    url: str = "about:blank"
    history: List[str] = field(default_factory=list)
    history_index: int = -1
    screenshot_b64: str = ""
    viewport: Dict[str, int] = field(default_factory=lambda: dict(VIEWPORT_DEFAULT))
    scroll: Dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0, "max_y": 0})
    page_text: str = ""
    meta_desc: str = ""
    headings: List[str] = field(default_factory=list)
    elements: List[Dict[str, Any]] = field(default_factory=list)
    engine: str = "standby"
    status: str = "ready"
    updated_at: float = field(default_factory=time.time)

    def to_summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title or self.url or "New Tab",
            "url": self.url,
            "engine": self.engine,
            "status": self.status,
            "can_back": self.history_index > 0,
            "can_forward": 0 <= self.history_index < len(self.history) - 1,
            "updated_at": self.updated_at,
        }

    def to_detail(self, include_screenshot: bool = True) -> Dict[str, Any]:
        return {
            **self.to_summary(),
            "viewport": dict(self.viewport),
            "scroll": dict(self.scroll),
            "page_text": self.page_text[:4000],
            "meta_desc": self.meta_desc,
            "headings": list(self.headings[:10]),
            "elements": list(self.elements[:36]),
            "screenshot_b64": self.screenshot_b64 if include_screenshot else "",
        }


class LiveBrowserManager:
    """Per-user multi-tab AURA Live Browser orchestrator."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._pw = _NodePlaywrightBridge()

    @staticmethod
    def _uid(user_id: Any) -> str:
        return str(user_id if user_id is not None else "guest")

    def _worker_tab_key(self, uid: str, tab_id: str) -> str:
        return f"u{uid}_{tab_id}"

    def _get_session(self, user_id: Any) -> Dict[str, Any]:
        uid = self._uid(user_id)
        with self._lock:
            sess = self._sessions.get(uid)
            if not sess:
                t1 = BrowserTabState(id="tab_1", title="New Tab", url="about:blank")
                sess = {
                    "tabs": {"tab_1": t1},
                    "order": ["tab_1"],
                    "active": "tab_1",
                    "seq": 1,
                    "agent_running": False,
                    "last_goal": "",
                }
                self._sessions[uid] = sess
            return sess

    def _resolve_tab(self, sess: Dict[str, Any], tab_id: Optional[str] = None) -> BrowserTabState:
        tid = str(tab_id or sess["active"])
        if tid not in sess["tabs"]:
            tid = sess["active"]
        if tid not in sess["tabs"]:
            t1 = BrowserTabState(id="tab_1", title="New Tab", url="about:blank")
            sess["tabs"]["tab_1"] = t1
            sess["order"] = ["tab_1"]
            sess["active"] = "tab_1"
            return t1
        return sess["tabs"][tid]

    def get_state(self, user_id: Any, include_screenshot: bool = True) -> Dict[str, Any]:
        sess = self._get_session(user_id)
        pw_avail, pw_reason = self._pw.is_available()
        with self._lock:
            active_tab = self._resolve_tab(sess)
            tabs_list = [sess["tabs"][tid].to_summary() for tid in sess["order"] if tid in sess["tabs"]]
            return {
                "success": True,
                "active_tab_id": active_tab.id,
                "tabs": tabs_list,
                "active_tab": active_tab.to_detail(include_screenshot=include_screenshot),
                "engine_capabilities": {
                    "playwright_local": pw_avail,
                    "engine_note": pw_reason,
                    "cloud_mode": bool(os.environ.get("VERCEL")),
                    "max_tabs": MAX_TABS_PER_USER,
                },
                "agent_running": bool(sess.get("agent_running", False)),
                "last_goal": str(sess.get("last_goal") or ""),
            }

    def new_tab(self, user_id: Any, url: str = "") -> Dict[str, Any]:
        uid = self._uid(user_id)
        sess = self._get_session(uid)
        with self._lock:
            if len(sess["order"]) >= MAX_TABS_PER_USER:
                return {"success": False, "error": f"Maximum of {MAX_TABS_PER_USER} simultaneous browser tabs reached."}
            sess["seq"] += 1
            tid = f"tab_{sess['seq']}"
            tab = BrowserTabState(id=tid, title="New Tab", url="about:blank")
            sess["tabs"][tid] = tab
            sess["order"].append(tid)
            sess["active"] = tid

        LIVE_ACTION_HUB.record(
            uid,
            "browser",
            "new_tab",
            f"Opened new browser tab ({tid})",
            target=url or "about:blank",
            tab_id=tid,
        )
        if url.strip():
            return self.navigate(uid, url, tab_id=tid)
        return self.get_state(uid)

    def switch_tab(self, user_id: Any, tab_id: str) -> Dict[str, Any]:
        uid = self._uid(user_id)
        sess = self._get_session(uid)
        with self._lock:
            if tab_id not in sess["tabs"]:
                return {"success": False, "error": f"Tab '{tab_id}' not found."}
            sess["active"] = tab_id
            tab = sess["tabs"][tab_id]

        pw_avail, _ = self._pw.is_available()
        if pw_avail and tab.url.startswith(("http://", "https://")):
            try:
                snap = self._pw.call("switch_tab", {"tab_id": self._worker_tab_key(uid, tab_id)})
                self._apply_snapshot_to_tab(tab, snap)
            except Exception:
                pass

        LIVE_ACTION_HUB.record(
            uid,
            "browser",
            "switch_tab",
            f"Switched to tab: {tab.title[:48]}",
            target=tab.url,
            tab_id=tab_id,
            engine=tab.engine,
        )
        return self.get_state(uid)

    def close_tab(self, user_id: Any, tab_id: str) -> Dict[str, Any]:
        uid = self._uid(user_id)
        sess = self._get_session(uid)
        with self._lock:
            if tab_id not in sess["tabs"]:
                return {"success": False, "error": f"Tab '{tab_id}' not found."}
            if len(sess["order"]) <= 1:
                # Reset single remaining tab to blank instead of leaving zero tabs
                tab = sess["tabs"][tab_id]
                tab.title = "New Tab"
                tab.url = "about:blank"
                tab.screenshot_b64 = ""
                tab.page_text = ""
                tab.elements = []
                tab.history = []
                tab.history_index = -1
                tab.engine = "standby"
            else:
                del sess["tabs"][tab_id]
                sess["order"] = [t for t in sess["order"] if t != tab_id]
                if sess["active"] == tab_id:
                    sess["active"] = sess["order"][-1]

        pw_avail, _ = self._pw.is_available()
        if pw_avail:
            try:
                self._pw.call("close_tab", {"tab_id": self._worker_tab_key(uid, tab_id)}, timeout=6.0)
            except Exception:
                pass

        LIVE_ACTION_HUB.record(uid, "browser", "close_tab", f"Closed browser tab ({tab_id})", tab_id=tab_id)
        return self.get_state(uid)

    def _apply_snapshot_to_tab(self, tab: BrowserTabState, snap: Dict[str, Any], push_history: bool = False) -> None:
        new_url = str(snap.get("url") or tab.url or "about:blank")
        if push_history and new_url.startswith(("http://", "https://")):
            if tab.history_index < len(tab.history) - 1:
                tab.history = tab.history[: tab.history_index + 1]
            if not tab.history or tab.history[-1] != new_url:
                tab.history.append(new_url)
                tab.history_index = len(tab.history) - 1
        tab.url = new_url
        tab.title = str(snap.get("title") or new_url)[:160]
        if snap.get("screenshot_b64"):
            tab.screenshot_b64 = str(snap["screenshot_b64"])
        if isinstance(snap.get("viewport"), dict):
            tab.viewport = dict(snap["viewport"])
        if isinstance(snap.get("scroll"), dict):
            tab.scroll = dict(snap["scroll"])
        if "page_text" in snap:
            tab.page_text = str(snap.get("page_text") or "")[:6000]
        if "meta_desc" in snap:
            tab.meta_desc = str(snap.get("meta_desc") or "")[:300]
        if isinstance(snap.get("headings"), list):
            tab.headings = list(snap["headings"])[:12]
        if isinstance(snap.get("elements"), list):
            tab.elements = list(snap["elements"])[:36]
        tab.engine = str(snap.get("engine") or tab.engine or "cloud_dom")
        tab.status = "ready"
        tab.updated_at = time.time()

    def _fetch_cloud_page(self, url: str, scroll_y: int = 0) -> Dict[str, Any]:
        """SSRF-protected HTTPS fetch & DOM extractor for cloud/Vercel/fallback mode."""
        opener = urllib.request.build_opener(_SafePublicRedirectHandler())
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        raw_html = ""
        final_url = url
        content_type = "text/html"
        try:
            with opener.open(req, timeout=12) as resp:
                final_url = str(resp.geturl() or url)
                ok_final, reason_final = is_safe_public_url(final_url)
                if not ok_final:
                    raise PermissionError(reason_final)
                content_type = str(resp.headers.get("Content-Type") or "text/html")
                raw_bytes = resp.read(350_000)
                raw_html = raw_bytes.decode("utf-8", errors="replace")
        except PermissionError:
            raise
        except Exception as exc:
            # Return informative cloud render rather than crashing on transient remote error
            err_title = urllib.parse.urlparse(url).netloc or url
            err_text = f"Live remote fetch note for {url}: {exc}"
            thumb = _render_cloud_preview_jpeg(url, err_title, err_text, [], scroll_y=0)
            return {
                "url": url,
                "title": err_title,
                "page_text": err_text,
                "meta_desc": "",
                "headings": [err_title],
                "elements": [],
                "scroll": {"x": 0, "y": 0, "max_y": 0},
                "viewport": dict(VIEWPORT_DEFAULT),
                "screenshot_b64": thumb,
                "engine": "cloud_dom",
            }

        if "html" in content_type.lower() or "<html" in raw_html[:600].lower():
            parser = _DomExtractor(final_url)
            try:
                parser.feed(raw_html)
            except Exception:
                pass
            title = (" ".join(parser.title_parts).strip() or urllib.parse.urlparse(final_url).netloc or final_url)[:160]
            page_text = " ".join(parser.text_parts).strip()[:5000]
            elements = parser.elements[:36]
            headings = parser.headings[:10]
            meta_desc = parser.meta_desc
        else:
            title = urllib.parse.urlparse(final_url).netloc or final_url
            page_text = raw_html[:4000]
            elements = []
            headings = []
            meta_desc = ""

        max_y = max(0, len(page_text) // 2)
        clamped_y = max(0, min(max_y, int(scroll_y)))
        thumb = _render_cloud_preview_jpeg(final_url, title, page_text, elements, scroll_y=clamped_y)
        return {
            "url": final_url,
            "title": title,
            "page_text": page_text,
            "meta_desc": meta_desc,
            "headings": headings,
            "elements": elements,
            "scroll": {"x": 0, "y": clamped_y, "max_y": max_y},
            "viewport": dict(VIEWPORT_DEFAULT),
            "screenshot_b64": thumb,
            "engine": "cloud_dom",
        }

    def navigate(self, user_id: Any, raw_url: str, tab_id: Optional[str] = None) -> Dict[str, Any]:
        uid = self._uid(user_id)
        t0 = time.perf_counter()
        ok, url, err = validate_browser_url(raw_url)
        if not ok:
            LIVE_ACTION_HUB.record(
                uid,
                "browser",
                "navigate",
                f"Blocked unsafe URL: {raw_url[:80]}",
                target=raw_url[:140],
                status="blocked",
                detail=err,
            )
            return {"success": False, "error": err}

        sess = self._get_session(uid)
        with self._lock:
            tab = self._resolve_tab(sess, tab_id)
            sess["active"] = tab.id
            tid = tab.id

        snap: Optional[Dict[str, Any]] = None
        pw_avail, _ = self._pw.is_available()
        if pw_avail:
            try:
                snap = self._pw.call("navigate", {"tab_id": self._worker_tab_key(uid, tid), "url": url})
            except Exception:
                snap = None

        if snap is None:
            try:
                snap = self._fetch_cloud_page(url)
            except PermissionError as exc:
                LIVE_ACTION_HUB.record(
                    uid,
                    "browser",
                    "navigate",
                    f"Blocked unsafe redirect: {url[:80]}",
                    target=url,
                    status="blocked",
                    detail=str(exc),
                    tab_id=tid,
                )
                return {"success": False, "error": str(exc)}

        with self._lock:
            self._apply_snapshot_to_tab(tab, snap, push_history=True)
            title = tab.title
            thumb = tab.screenshot_b64
            eng = tab.engine

        dur = int((time.perf_counter() - t0) * 1000)
        LIVE_ACTION_HUB.record(
            uid,
            "browser",
            "navigate",
            f"Navigated to {title[:56]}",
            target=tab.url,
            status="completed",
            duration_ms=dur,
            thumbnail_b64=thumb,
            tab_id=tid,
            engine=eng,
        )
        return self.get_state(uid)

    def perform_action(
        self,
        user_id: Any,
        action: str,
        *,
        tab_id: Optional[str] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        selector: str = "",
        text: str = "",
        key: str = "",
        delta_y: int = 420,
        delta_x: int = 0,
        submit: bool = False,
        clear: bool = False,
        element_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        uid = self._uid(user_id)
        t0 = time.perf_counter()
        act = str(action or "").strip().lower()
        if act not in ("click", "type", "press", "scroll", "back", "forward", "reload", "screenshot"):
            return {"success": False, "error": f"Unsupported browser action: {act}"}

        sess = self._get_session(uid)
        with self._lock:
            tab = self._resolve_tab(sess, tab_id)
            tid = tab.id

        # Resolve element_index shortcut if supplied
        chosen_el: Optional[Dict[str, Any]] = None
        if element_index is not None:
            for el in tab.elements:
                if int(el.get("index", -1)) == int(element_index):
                    chosen_el = el
                    break
            if chosen_el and x is None and y is None:
                x = chosen_el.get("x")
                y = chosen_el.get("y")

        pw_avail, _ = self._pw.is_available()
        used_playwright = False
        coords_out: Optional[Dict[str, int]] = (
            {"x": int(round(float(x))), "y": int(round(float(y)))}
            if x is not None and y is not None
            else None
        )

        if pw_avail and tab.url.startswith(("http://", "https://")):
            try:
                worker_payload: Dict[str, Any] = {"tab_id": self._worker_tab_key(uid, tid)}
                if act == "click":
                    if selector:
                        worker_payload["selector"] = selector
                    elif text:
                        worker_payload["text"] = text
                    elif x is not None and y is not None:
                        worker_payload["x"] = float(x)
                        worker_payload["y"] = float(y)
                    else:
                        return {"success": False, "error": "Click requires coordinates, selector, text, or element_index."}
                elif act == "type":
                    worker_payload["text"] = text
                    worker_payload["submit"] = bool(submit)
                    worker_payload["clear"] = bool(clear)
                    if selector:
                        worker_payload["selector"] = selector
                    elif x is not None and y is not None:
                        worker_payload["x"] = float(x)
                        worker_payload["y"] = float(y)
                elif act == "press":
                    worker_payload["key"] = key or "Enter"
                elif act == "scroll":
                    worker_payload["delta_y"] = int(delta_y)
                    worker_payload["delta_x"] = int(delta_x)

                snap = self._pw.call(act, worker_payload)
                if isinstance(snap.get("coords"), dict):
                    coords_out = snap["coords"]
                with self._lock:
                    self._apply_snapshot_to_tab(tab, snap, push_history=(snap.get("url") != tab.url))
                used_playwright = True
            except Exception:
                used_playwright = False

        if not used_playwright:
            # Clean cloud/fallback execution for every action
            if act == "back":
                if tab.history_index > 0:
                    tab.history_index -= 1
                    return self.navigate(uid, tab.history[tab.history_index], tab_id=tid)
            elif act == "forward":
                if 0 <= tab.history_index < len(tab.history) - 1:
                    tab.history_index += 1
                    return self.navigate(uid, tab.history[tab.history_index], tab_id=tid)
            elif act == "reload" and tab.url.startswith(("http://", "https://")):
                snap = self._fetch_cloud_page(tab.url, scroll_y=tab.scroll.get("y", 0))
                with self._lock:
                    self._apply_snapshot_to_tab(tab, snap, push_history=False)
            elif act == "scroll":
                cur_y = int(tab.scroll.get("y", 0))
                max_y = int(tab.scroll.get("max_y", 2000))
                new_y = max(0, min(max(max_y, 2400), cur_y + int(delta_y)))
                tab.scroll = {"x": int(delta_x), "y": new_y, "max_y": max(max_y, new_y)}
                tab.screenshot_b64 = _render_cloud_preview_jpeg(
                    tab.url, tab.title, tab.page_text, tab.elements, scroll_y=new_y, cursor=coords_out
                )
            elif act == "click":
                # Follow matching link element if available
                target_el = chosen_el
                if not target_el and text:
                    tl = text.lower()
                    for el in tab.elements:
                        if tl in str(el.get("text") or "").lower():
                            target_el = el
                            break
                if target_el and target_el.get("href"):
                    href = str(target_el["href"])
                    ok_u, _, _ = validate_browser_url(href)
                    if ok_u:
                        return self.navigate(uid, href, tab_id=tid)
                if coords_out:
                    tab.screenshot_b64 = _render_cloud_preview_jpeg(
                        tab.url, tab.title, tab.page_text, tab.elements, scroll_y=tab.scroll.get("y", 0), cursor=coords_out
                    )
            elif act == "type" and text:
                if submit:
                    # Smart site search fallback on cloud
                    host = (urllib.parse.urlparse(tab.url).hostname or "").lower()
                    if "wikipedia.org" in host:
                        search_url = "https://en.wikipedia.org/w/index.php?search=" + urllib.parse.quote_plus(text)
                    elif "github.com" in host:
                        search_url = "https://github.com/search?q=" + urllib.parse.quote_plus(text)
                    else:
                        search_url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(text)
                    return self.navigate(uid, search_url, tab_id=tid)
                tab.screenshot_b64 = _render_cloud_preview_jpeg(
                    tab.url, tab.title, tab.page_text, tab.elements, scroll_y=tab.scroll.get("y", 0), cursor=coords_out
                )
            elif act == "screenshot":
                tab.screenshot_b64 = _render_cloud_preview_jpeg(
                    tab.url, tab.title, tab.page_text, tab.elements, scroll_y=tab.scroll.get("y", 0), cursor=coords_out
                )

        dur = int((time.perf_counter() - t0) * 1000)
        coord_lbl = f"({coords_out['x']}, {coords_out['y']})" if coords_out else "target"
        click_lbl = text or selector or coord_lbl
        summary_map = {
            "click": f"Clicked {click_lbl}",
            "type": f"Typed '{text[:48]}'" + (" + Enter" if submit else ""),
            "press": f"Pressed key {key or 'Enter'}",
            "scroll": f"Scrolled {'down' if int(delta_y) >= 0 else 'up'} {abs(int(delta_y))}px",
            "back": "Navigated Back",
            "forward": "Navigated Forward",
            "reload": "Reloaded page",
            "screenshot": "Captured live page screenshot",
        }
        LIVE_ACTION_HUB.record(
            uid,
            "browser",
            act,
            summary_map.get(act, f"Browser {act}"),
            target=tab.url,
            coords=coords_out,
            duration_ms=dur,
            thumbnail_b64=tab.screenshot_b64,
            tab_id=tid,
            engine=tab.engine,
        )
        return self.get_state(uid)

    def _call_brain_vision(
        self,
        brain: Optional[AuraBrain],
        prompt: str,
        screenshot_b64: str = "",
    ) -> str:
        """Invokes Gemini multimodal vision/text through AuraBrain safely."""
        if brain is None or is_test_runner_active():
            return ""
        parts: List[Dict[str, Any]] = []
        if screenshot_b64 and len(screenshot_b64) < 2_500_000:
            parts.append({"inlineData": {"mimeType": "image/jpeg", "data": screenshot_b64}})
        parts.append({"text": prompt})
        try:
            resp = brain._call_api([{"role": "user", "parts": parts}], tools=None, deadline_override=16.0)
            cands = resp.get("candidates") or []
            if cands:
                out_parts = (cands[0].get("content") or {}).get("parts") or []
                txt = "\n".join(str(p.get("text") or "") for p in out_parts if isinstance(p, dict) and p.get("text")).strip()
                if any(tok in txt.lower() for tok in ("high student traffic", "temporarily throttled", "rate limit")):
                    return ""
                return txt
        except Exception:
            return ""
        return ""

    def understand_page(
        self,
        user_id: Any,
        question: str = "Summarize this page, key sections, and main actions available.",
        brain: Optional[AuraBrain] = None,
        tab_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        uid = self._uid(user_id)
        t0 = time.perf_counter()
        sess = self._get_session(uid)
        with self._lock:
            tab = self._resolve_tab(sess, tab_id)
            tid = tab.id

        if not tab.url.startswith(("http://", "https://")) and not tab.page_text:
            return {
                "success": False,
                "error": "No webpage is currently open in this tab. Navigate to a URL first.",
            }

        el_summary = "\n".join(
            f"[{el.get('index')}] <{el.get('tag')}> {el.get('text', '')} {('-> ' + el['href']) if el.get('href') else ''}"
            for el in tab.elements[:18]
        )
        prompt = (
            f"Analyze this live webpage inside AURA Live Browser.\n"
            f"URL: {tab.url}\nTitle: {tab.title}\n"
            f"User Question: {question}\n\n"
            f"Visible Text Excerpt:\n{tab.page_text[:2800]}\n\n"
            f"Interactive Elements:\n{el_summary}\n\n"
            "Provide a concise, factual visual & structural answer in clean Markdown."
        )
        ai_text = self._call_brain_vision(brain, prompt, tab.screenshot_b64)
        if not ai_text:
            headings_line = ", ".join(tab.headings[:5]) if tab.headings else tab.title
            snippet = (tab.page_text[:520] + "...") if len(tab.page_text) > 520 else tab.page_text
            ai_text = (
                f"### Page Understanding: {tab.title}\n"
                f"- **URL:** {tab.url}\n"
                f"- **Key Sections:** {headings_line}\n"
                f"- **Interactive Elements Detected:** {len(tab.elements)}\n\n"
                f"{snippet or 'Page loaded cleanly in AURA Live Browser.'}"
            )

        dur = int((time.perf_counter() - t0) * 1000)
        LIVE_ACTION_HUB.record(
            uid,
            "vision",
            "understand_page",
            f"Analyzed page: {tab.title[:54]}",
            target=tab.url,
            duration_ms=dur,
            detail=ai_text[:260],
            thumbnail_b64=tab.screenshot_b64,
            tab_id=tid,
            engine=tab.engine,
        )
        return {
            "success": True,
            "analysis": ai_text,
            "url": tab.url,
            "title": tab.title,
            "elements_count": len(tab.elements),
            "state": self.get_state(uid),
        }

    def run_agent_goal(
        self,
        user_id: Any,
        goal: str,
        brain: Optional[AuraBrain] = None,
        tab_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes a synchronized multi-step AI browser workflow from a natural prompt."""
        uid = self._uid(user_id)
        clean_goal = str(goal or "").strip()
        if not clean_goal:
            return {"success": False, "error": "Please provide a browsing instruction or URL."}

        sess = self._get_session(uid)
        with self._lock:
            sess["agent_running"] = True
            sess["last_goal"] = clean_goal

        steps_log: List[Dict[str, Any]] = []
        try:
            LIVE_ACTION_HUB.record(
                uid,
                "browser",
                "agent_start",
                f"AI Browser Task: {clean_goal[:72]}",
                target=clean_goal[:140],
                status="running",
            )

            # 1. Detect explicit URL or well-known destination + optional search query
            url_match = re.search(r"(https?://[^\s'\"<>]+)", clean_goal, re.I)
            domain_match = re.search(
                r"\b([a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|net|io|ai|dev|gov|edu|in|sg|co|app|wiki)(?:/[^\s'\"<>]*)?)\b",
                clean_goal,
                re.I,
            )
            search_match = re.search(r"\b(?:search|find|look\s*up|query)\s+(?:for\s+)?(.+?)(?:\s+on\s+|\s+in\s+|$)", clean_goal, re.I)

            target_url = ""
            if url_match:
                target_url = url_match.group(1).rstrip(".,);")
            elif domain_match:
                target_url = "https://" + domain_match.group(1).rstrip(".,);")
            else:
                gl = clean_goal.lower()
                query_phrase = search_match.group(1).strip() if search_match else re.sub(
                    r"^(?:open|browse|go\s+to|visit|check|show\s+me)\s+", "", clean_goal, flags=re.I
                ).strip()
                if "wikipedia" in gl:
                    target_url = "https://en.wikipedia.org/w/index.php?search=" + urllib.parse.quote_plus(query_phrase or "Artificial intelligence")
                elif "github" in gl:
                    target_url = "https://github.com/search?q=" + urllib.parse.quote_plus(query_phrase or "AI agent")
                elif "hacker news" in gl or "ycombinator" in gl:
                    target_url = "https://news.ycombinator.com/"
                elif "pypi" in gl:
                    target_url = "https://pypi.org/search/?q=" + urllib.parse.quote_plus(query_phrase or "playwright")
                elif "mdn" in gl:
                    target_url = "https://developer.mozilla.org/en-US/search?q=" + urllib.parse.quote_plus(query_phrase or "fetch")
                elif query_phrase:
                    target_url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query_phrase)
                else:
                    target_url = "https://example.com"

            # Step 1: Navigate
            nav_res = self.navigate(uid, target_url, tab_id=tab_id)
            if not nav_res.get("success"):
                return {
                    "success": False,
                    "error": nav_res.get("error", "Navigation blocked"),
                    "steps": steps_log,
                    "state": self.get_state(uid),
                }
            active = nav_res["active_tab"]
            steps_log.append({"step": 1, "action": "navigate", "target": active["url"], "title": active["title"]})

            # Step 2: If goal mentions searching inside the opened site & we landed on homepage, try typing/submitting
            if search_match and (url_match or domain_match):
                q_term = search_match.group(1).strip().strip("\"'")
                if q_term and q_term.lower() not in active["url"].lower():
                    input_el = next(
                        (e for e in active.get("elements", []) if e.get("tag") in ("input", "textarea") and e.get("type") not in ("checkbox", "radio", "submit", "button")),
                        None,
                    )
                    if input_el:
                        type_res = self.perform_action(
                            uid,
                            "type",
                            tab_id=active["id"],
                            x=input_el.get("x"),
                            y=input_el.get("y"),
                            text=q_term,
                            submit=True,
                        )
                        if type_res.get("success"):
                            active = type_res["active_tab"]
                            steps_log.append({"step": 2, "action": "type", "text": q_term, "url": active["url"]})

            # Step 3: If goal asks to scroll, scroll live
            if re.search(r"\b(scroll|bottom|down|read\s+more)\b", clean_goal, re.I):
                scr_res = self.perform_action(uid, "scroll", tab_id=active["id"], delta_y=520)
                if scr_res.get("success"):
                    active = scr_res["active_tab"]
                    steps_log.append({"step": len(steps_log) + 1, "action": "scroll", "delta_y": 520})

            # Step 4: Page understanding synced back to chat
            und_res = self.understand_page(
                uid,
                question=f"Complete this user request based on the live webpage: {clean_goal}",
                brain=brain,
                tab_id=active["id"],
            )
            summary = und_res.get("analysis") or f"Opened {active['title']} ({active['url']})."
            steps_log.append({"step": len(steps_log) + 1, "action": "understand_page", "title": active["title"]})

            LIVE_ACTION_HUB.record(
                uid,
                "browser",
                "agent_complete",
                f"Completed AI Browser task on {active['title'][:48]}",
                target=active["url"],
                status="completed",
                tab_id=active["id"],
                engine=active.get("engine", ""),
            )
            return {
                "success": True,
                "goal": clean_goal,
                "summary": summary,
                "steps": steps_log,
                "state": self.get_state(uid),
            }
        finally:
            with self._lock:
                sess["agent_running"] = False


LIVE_BROWSER = LiveBrowserManager()
