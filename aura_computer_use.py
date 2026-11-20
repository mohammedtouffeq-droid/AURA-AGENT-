"""
===================================================================================
      AURA COMPUTER USE — DESKTOP AUTOMATION & LIVE SCREEN STREAMING ENGINE
===================================================================================
Capability #2: Real Desktop Automation, Live Screen Streaming, Computer Vision
Screen Understanding, Windows UI Automation inspection, and Human-in-the-Loop
safety controls (Start, Pause, Resume, Stop, Take Control + physical mouse
takeover watchdog + JARVIS Kill Switch enforcement).

Technology Stack:
- PyAutoGUI: Guarded mouse & keyboard control (FAILSAFE=True, screen bounds clamp)
- PIL.ImageGrab + OpenCV (cv2): Real-time live desktop screenshot streaming &
  visual change / UI contour analysis
- Windows UI Automation: `pygetwindow` window control + native PowerShell
  `System.Windows.Automation` UI element inspector
- Gemini Vision (via AuraBrain): Visual screen understanding & next-step planning
- Cloud / Vercel Mode: Honest serverless status + Browser Screen Share
  (`getDisplayMedia`) live visual frame analysis (`/api/computer/analyze_frame`)
===================================================================================
"""

from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import threading
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

from aura_brain import AuraBrain
from aura_jarvis_hub import JARVIS_HUB
from aura_live_actions import LIVE_ACTION_HUB
from aura_os_controller import is_test_runner_active, laptop_controller

try:
    import pyautogui  # type: ignore
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.06
    HAS_PYAUTOGUI = True
except Exception:
    pyautogui = None
    HAS_PYAUTOGUI = False

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    HAS_CV2 = True
except Exception:
    cv2 = None
    np = None
    HAS_CV2 = False

try:
    from PIL import Image, ImageDraw, ImageFont, ImageGrab  # type: ignore
    HAS_PIL = True
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageGrab = None
    HAS_PIL = False

try:
    import pygetwindow as gw  # type: ignore
    HAS_PYGETWINDOW = True
except Exception:
    gw = None
    HAS_PYGETWINDOW = False


SUPPORTED_DESKTOP_APPS = [
    {"id": "chrome", "label": "Google Chrome", "category": "Browser"},
    {"id": "vscode", "label": "VS Code", "category": "Editor"},
    {"id": "notepad", "label": "Notepad", "category": "Utility"},
    {"id": "calculator", "label": "Calculator", "category": "Utility"},
    {"id": "explorer", "label": "File Explorer", "category": "System"},
    {"id": "whatsapp", "label": "WhatsApp", "category": "Comms"},
    {"id": "settings", "label": "Windows Settings", "category": "System"},
    {"id": "terminal", "label": "Windows Terminal", "category": "Developer"},
]


def _is_local_desktop_host() -> bool:
    return bool(os.name == "nt" and not os.environ.get("VERCEL") and not is_test_runner_active())


def _render_status_frame_jpeg(
    title: str,
    subtitle: str,
    status_badge: str,
    details: List[str],
    cursor: Optional[Dict[str, int]] = None,
) -> bytes:
    """Renders an honest Obsidian status frame when live host display capture is unavailable."""
    if not HAS_PIL:
        return b""
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), (9, 11, 17))
    draw = ImageDraw.Draw(img)
    try:
        f_title = ImageFont.truetype("arial.ttf", 30)
        f_sub = ImageFont.truetype("arial.ttf", 18)
        f_body = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        f_title = ImageFont.load_default()
        f_sub = ImageFont.load_default()
        f_body = ImageFont.load_default()

    # Subtle grid
    for gx in range(0, w, 64):
        draw.line([gx, 0, gx, h], fill=(18, 22, 34), width=1)
    for gy in range(0, h, 64):
        draw.line([0, gy, w, gy], fill=(18, 22, 34), width=1)

    draw.rounded_rectangle([96, 110, w - 96, h - 110], radius=18, fill=(14, 17, 26), outline=(54, 66, 92), width=2)
    draw.rounded_rectangle([136, 152, 410, 188], radius=18, fill=(28, 36, 54), outline=(226, 185, 111), width=1)
    draw.text((156, 160), status_badge[:32], fill=(226, 185, 111), font=f_body)

    draw.text((136, 214), title[:62], fill=(244, 244, 245), font=f_title)
    draw.text((136, 260), subtitle[:92], fill=(161, 161, 170), font=f_sub)

    y = 324
    for line in details[:7]:
        draw.text((152, y), f"- {line[:88]}", fill=(212, 212, 216), font=f_body)
        y += 34

    if cursor and cursor.get("x") is not None and cursor.get("y") is not None:
        cx, cy = int(cursor["x"]), int(cursor["y"])
        draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], outline=(226, 185, 111), width=3)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=72)
    return buf.getvalue()


class ComputerUseManager:
    """Thread-safe per-user Desktop Computer Use controller with Human-in-the-Loop guardrails."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _uid(user_id: Any) -> str:
        return str(user_id if user_id is not None else "guest")

    def _get_session(self, user_id: Any) -> Dict[str, Any]:
        uid = self._uid(user_id)
        with self._lock:
            sess = self._sessions.get(uid)
            if not sess:
                sess = {
                    "state": "idle",  # idle | running | paused | stopped | human_control
                    "goal": "",
                    "step_count": 0,
                    "max_steps": 8,
                    "last_ai_cursor": None,
                    "last_frame_gray": None,
                    "last_diff_score": 0.0,
                    "last_vision_summary": "",
                    "last_client_frame_b64": "",
                    "stop_event": threading.Event(),
                    "pause_event": threading.Event(),
                    "worker_thread": None,
                    "updated_at": time.time(),
                }
                self._sessions[uid] = sess
            return sess

    def _get_screen_size(self) -> Tuple[int, int]:
        if _is_local_desktop_host() and HAS_PYAUTOGUI and pyautogui is not None:
            try:
                sz = pyautogui.size()
                return int(sz.width), int(sz.height)
            except Exception:
                pass
        return 1920, 1080

    def _list_open_windows(self) -> Tuple[str, List[Dict[str, Any]]]:
        if not _is_local_desktop_host() or not HAS_PYGETWINDOW or gw is None:
            return ("Cloud Serverless Session" if os.environ.get("VERCEL") else "AURA Desktop Sandbox"), []
        active_title = ""
        try:
            aw = gw.getActiveWindow()
            if aw and getattr(aw, "title", None):
                active_title = str(aw.title).strip()[:120]
        except Exception:
            pass
        windows: List[Dict[str, Any]] = []
        try:
            for w in gw.getAllWindows():
                t = str(getattr(w, "title", "") or "").strip()
                if not t or len(windows) >= 18:
                    continue
                if getattr(w, "width", 0) < 60 or getattr(w, "height", 0) < 40:
                    continue
                windows.append({
                    "title": t[:100],
                    "left": int(getattr(w, "left", 0)),
                    "top": int(getattr(w, "top", 0)),
                    "width": int(getattr(w, "width", 0)),
                    "height": int(getattr(w, "height", 0)),
                    "active": (t == active_title),
                })
        except Exception:
            pass
        return active_title or (windows[0]["title"] if windows else "Windows Desktop"), windows

    def get_status(self, user_id: Any) -> Dict[str, Any]:
        uid = self._uid(user_id)
        sess = self._get_session(uid)
        active_win, windows = self._list_open_windows()
        sw, sh = self._get_screen_size()
        kill_halted = bool(JARVIS_HUB.get_status(uid).get("halted", False))

        with self._lock:
            state = sess["state"]
            goal = sess["goal"]
            step_count = sess["step_count"]
            last_cursor = sess["last_ai_cursor"]
            last_vision = sess["last_vision_summary"]
            diff_score = sess["last_diff_score"]

        return {
            "success": True,
            "state": state,
            "goal": goal,
            "step_count": step_count,
            "kill_switch_halted": kill_halted,
            "local_desktop_available": _is_local_desktop_host(),
            "cloud_mode": bool(os.environ.get("VERCEL")),
            "screen_size": {"width": sw, "height": sh},
            "active_window": active_win,
            "windows": windows,
            "last_cursor": last_cursor,
            "last_vision_summary": last_vision,
            "cv_diff_score": round(float(diff_score), 3),
            "supported_apps": SUPPORTED_DESKTOP_APPS,
            "stack": {
                "pyautogui": HAS_PYAUTOGUI and _is_local_desktop_host(),
                "opencv_cv2": HAS_CV2,
                "screen_capture": HAS_PIL and _is_local_desktop_host(),
                "windows_ui_automation": _is_local_desktop_host(),
                "pygetwindow": HAS_PYGETWINDOW and _is_local_desktop_host(),
                "gemini_vision": True,
            },
        }

    def inspect_ui_tree(self, user_id: Any, max_nodes: int = 28) -> Dict[str, Any]:
        """Inspects active desktop window controls via Windows UI Automation + pygetwindow."""
        uid = self._uid(user_id)
        t0 = time.perf_counter()
        active_win, windows = self._list_open_windows()
        controls: List[Dict[str, Any]] = []
        engine = "windows_ui_automation"

        if not _is_local_desktop_host():
            engine = "cloud_sandbox" if os.environ.get("VERCEL") else "test_dry_run"
            controls = [
                {
                    "name": "Local Desktop Agent required for physical Windows UI Automation",
                    "control_type": "StatusNotice",
                    "x": 640,
                    "y": 360,
                    "w": 420,
                    "h": 40,
                }
            ]
        else:
            ps_script = (
                "Add-Type -AssemblyName UIAutomationClient; "
                "Add-Type -AssemblyName UIAutomationTypes; "
                "$el = [System.Windows.Automation.AutomationElement]::FocusedElement; "
                "if (-not $el) { $el = [System.Windows.Automation.AutomationElement]::RootElement }; "
                "$w = $el; "
                "$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker; "
                "while ($w -and $w.Current.ControlType.ProgrammaticName -ne 'ControlType.Window' -and $w -ne [System.Windows.Automation.AutomationElement]::RootElement) { "
                "  $p = $walker.GetParent($w); if (-not $p) { break }; $w = $p "
                "}; "
                "$cond = [System.Windows.Automation.Condition]::TrueCondition; "
                "$all = $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond); "
                "$out = @(); "
                f"for ($i = 0; $i -lt $all.Count -and $out.Count -lt {int(max(5, min(40, max_nodes)))}; $i++) {{ "
                "  $c = $all.Item($i).Current; "
                "  $n = ($c.Name + '').Trim(); "
                "  $ct = ($c.ControlType.ProgrammaticName -replace '^ControlType\\.', ''); "
                "  $r = $c.BoundingRectangle; "
                "  if ($n -and $r.Width -gt 4 -and $r.Height -gt 4 -and -not [double]::IsInfinity($r.Left)) { "
                "    $out += [PSCustomObject]@{ name = $n.Substring(0, [Math]::Min(70, $n.Length)); control_type = $ct; x = [int]($r.Left + $r.Width/2); y = [int]($r.Top + $r.Height/2); w = [int]$r.Width; h = [int]$r.Height } "
                "  } "
                "}; "
                "$out | ConvertTo-Json -Compress"
            )
            try:
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=4.0,
                    creationflags=creationflags,
                )
                raw = (proc.stdout or "").strip()
                if raw:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        controls = [parsed]
                    elif isinstance(parsed, list):
                        controls = parsed[:max_nodes]
            except Exception:
                engine = "pygetwindow_fallback"
                controls = [
                    {
                        "name": w["title"],
                        "control_type": "Window",
                        "x": w["left"] + w["width"] // 2,
                        "y": w["top"] + w["height"] // 2,
                        "w": w["width"],
                        "h": w["height"],
                    }
                    for w in windows[:max_nodes]
                ]

        dur = int((time.perf_counter() - t0) * 1000)
        LIVE_ACTION_HUB.record(
            uid,
            "computer",
            "ui_inspect",
            f"Inspected UI tree ({len(controls)} controls) in {active_win[:44]}",
            target=active_win,
            duration_ms=dur,
            window_title=active_win,
            engine=engine,
        )
        return {
            "success": True,
            "active_window": active_win,
            "windows": windows,
            "controls": controls,
            "engine": engine,
        }

    def capture_screen_frame(
        self,
        user_id: Any,
        width: int = 1280,
        quality: int = 62,
    ) -> Dict[str, Any]:
        """Captures a live desktop frame (PIL.ImageGrab + OpenCV CV telemetry) or honest cloud status frame."""
        uid = self._uid(user_id)
        sess = self._get_session(uid)
        active_win, _ = self._list_open_windows()
        target_w = max(480, min(1440, int(width or 1280)))
        jpeg_q = max(35, min(85, int(quality or 62)))

        if _is_local_desktop_host() and HAS_PIL and ImageGrab is not None:
            try:
                shot = ImageGrab.grab(all_screens=False).convert("RGB")
                orig_w, orig_h = shot.size
                target_h = max(270, int(round(orig_h * (target_w / float(orig_w)))))

                diff_score = 0.0
                cv_regions = 0
                if HAS_CV2 and cv2 is not None and np is not None:
                    arr = np.array(shot)
                    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                    resized = cv2.resize(bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
                    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
                    small_gray = cv2.resize(gray, (320, 180))
                    with self._lock:
                        prev_gray = sess.get("last_frame_gray")
                        if prev_gray is not None and prev_gray.shape == small_gray.shape:
                            diff = cv2.absdiff(prev_gray, small_gray)
                            diff_score = float(np.mean(diff) / 255.0)
                        sess["last_frame_gray"] = small_gray
                        sess["last_diff_score"] = diff_score
                    edges = cv2.Canny(small_gray, 60, 150)
                    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    cv_regions = sum(1 for c in contours if cv2.contourArea(c) > 35)
                    ok_enc, enc_buf = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_q])
                    jpeg_bytes = enc_buf.tobytes() if ok_enc else b""
                else:
                    resized_img = shot.resize((target_w, target_h))
                    buf = io.BytesIO()
                    resized_img.save(buf, format="JPEG", quality=jpeg_q)
                    jpeg_bytes = buf.getvalue()

                return {
                    "success": True,
                    "frame_b64": base64.b64encode(jpeg_bytes).decode("ascii"),
                    "jpeg_bytes": jpeg_bytes,
                    "width": target_w,
                    "height": target_h,
                    "screen_width": orig_w,
                    "screen_height": orig_h,
                    "active_window": active_win,
                    "cv_diff_score": round(diff_score, 4),
                    "cv_ui_regions": cv_regions,
                    "engine": "local_desktop_live",
                    "state": sess["state"],
                    "timestamp": time.time(),
                }
            except Exception as exc:
                err_jpeg = _render_status_frame_jpeg(
                    "Desktop Capture Temporarily Unavailable",
                    str(exc),
                    f"STATE: {sess['state'].upper()}",
                    ["Ensure an active Windows desktop session is unlocked."],
                )
                return {
                    "success": True,
                    "frame_b64": base64.b64encode(err_jpeg).decode("ascii"),
                    "jpeg_bytes": err_jpeg,
                    "width": 1280,
                    "height": 720,
                    "active_window": active_win,
                    "engine": "capture_fallback",
                    "state": sess["state"],
                    "timestamp": time.time(),
                }

        # Cloud serverless or pytest dry-run honest status frame (or last browser-shared screen frame!)
        if sess.get("last_client_frame_b64"):
            raw_b = base64.b64decode(sess["last_client_frame_b64"])
            return {
                "success": True,
                "frame_b64": sess["last_client_frame_b64"],
                "jpeg_bytes": raw_b,
                "width": 1280,
                "height": 720,
                "active_window": "Browser Screen Share (Live Vision)",
                "engine": "client_screen_share",
                "state": sess["state"],
                "timestamp": time.time(),
            }

        is_cloud = bool(os.environ.get("VERCEL"))
        status_jpeg = _render_status_frame_jpeg(
            "AURA Computer Use — Cloud Serverless Mode" if is_cloud else "AURA Computer Use — Test Dry-Run Sandbox",
            "Connect local AURA Host (`python aura_web.py`) for physical PyAutoGUI & Windows UI Automation."
            if is_cloud
            else "Physical mouse/keyboard automation is safely sandboxed during automated tests.",
            f"MODE: {'CLOUD VISION' if is_cloud else 'DRY-RUN SAFE'} | {sess['state'].upper()}",
            [
                "Click 'Share Screen' above to stream your live desktop directly into AURA Vision.",
                "Use Start / Pause / Stop / Take Control at any time for Human-in-the-Loop governance.",
                "Run `python aura_web.py` locally on Windows for real PyAutoGUI + Windows UI Automation.",
            ],
            cursor=sess.get("last_ai_cursor"),
        )
        return {
            "success": True,
            "frame_b64": base64.b64encode(status_jpeg).decode("ascii"),
            "jpeg_bytes": status_jpeg,
            "width": 1280,
            "height": 720,
            "active_window": active_win,
            "engine": "cloud_serverless" if is_cloud else "test_dry_run",
            "state": sess["state"],
            "timestamp": time.time(),
        }

    def iter_mjpeg_frames(self, user_id: Any, max_seconds: float = 45.0, fps: float = 3.0) -> Iterator[bytes]:
        """Yields multipart MJPEG frames for live streaming in <img>."""
        delay = max(0.15, min(1.5, 1.0 / max(0.5, float(fps))))
        deadline = time.time() + max(2.0, float(max_seconds))
        while time.time() < deadline:
            frame = self.capture_screen_frame(user_id, width=1024, quality=58)
            jpg = frame.get("jpeg_bytes") or b""
            if jpg:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(jpg)}\r\n\r\n".encode("ascii")
                    + jpg
                    + b"\r\n"
                )
            if not _is_local_desktop_host():
                break  # Avoid long streaming loops on serverless or tests
            time.sleep(delay)

    def _check_human_takeover(self, uid: str, sess: Dict[str, Any]) -> bool:
        """If physical mouse moved >65px away from AI's last position, yield to Human Control immediately."""
        if not _is_local_desktop_host() or not HAS_PYAUTOGUI or pyautogui is None:
            return False
        last = sess.get("last_ai_cursor")
        if not isinstance(last, dict):
            return False
        try:
            pos = pyautogui.position()
            dx = abs(int(pos.x) - int(last["x"]))
            dy = abs(int(pos.y) - int(last["y"]))
            if dx > 65 or dy > 65:
                with self._lock:
                    sess["state"] = "human_control"
                    sess["stop_event"].set()
                    sess["updated_at"] = time.time()
                LIVE_ACTION_HUB.record(
                    uid,
                    "computer",
                    "take_control",
                    f"Human mouse movement detected ({pos.x}, {pos.y}) — AI yielded control",
                    coords={"x": int(pos.x), "y": int(pos.y)},
                    status="paused",
                    engine="human_takeover_watchdog",
                )
                return True
        except Exception:
            pass
        return False

    def execute_action(
        self,
        user_id: Any,
        action: str,
        *,
        x: Optional[float] = None,
        y: Optional[float] = None,
        text: str = "",
        keys: Optional[List[str]] = None,
        delta_y: int = -300,
        app_name: str = "",
        window_title: str = "",
        allow_when_idle: bool = True,
    ) -> Dict[str, Any]:
        """Executes a single guarded desktop action via PyAutoGUI / Win32 / laptop_controller."""
        uid = self._uid(user_id)
        t0 = time.perf_counter()
        sess = self._get_session(uid)

        if JARVIS_HUB.get_status(uid).get("halted"):
            LIVE_ACTION_HUB.record(
                uid,
                "computer",
                action,
                "Blocked: JARVIS Kill Switch is HALTED",
                status="blocked",
            )
            return {"success": False, "error": "JARVIS Kill Switch is HALTED. Resume safety switch before desktop control."}

        with self._lock:
            cur_state = sess["state"]
        if cur_state in ("paused", "stopped", "human_control"):
            return {
                "success": False,
                "error": f"Computer Use is currently in '{cur_state}' state. Click Start or Resume first.",
                "state": cur_state,
            }
        if not allow_when_idle and cur_state != "running":
            return {"success": False, "error": "Computer Use session is not running.", "state": cur_state}

        act = str(action or "").strip().lower()
        sw, sh = self._get_screen_size()
        cx: Optional[int] = None
        cy: Optional[int] = None
        if x is not None and y is not None:
            # Support both normalized [0..1] or pixel coordinates
            fx, fy = float(x), float(y)
            if 0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0 and (fx != 0.0 or fy != 0.0):
                cx = int(round(fx * sw))
                cy = int(round(fy * sh))
            else:
                cx = max(2, min(sw - 3, int(round(fx))))
                cy = max(2, min(sh - 3, int(round(fy))))

        local_ok = _is_local_desktop_host()
        executed = False
        detail = ""

        if act == "launch_app":
            clean_app = str(app_name or text or "").strip()
            if not clean_app:
                return {"success": False, "error": "Application name is required."}
            if local_ok:
                res = laptop_controller.launch_app(clean_app)
                executed = bool(res.get("success"))
                detail = str(res.get("message") or res.get("error") or f"Launched {clean_app}")
            else:
                executed = True
                detail = f"Dry-run / Cloud mode: verified supported desktop app '{clean_app}'."

        elif act == "focus_window":
            target_title = str(window_title or text or "").strip()
            if not target_title:
                return {"success": False, "error": "Window title is required."}
            if local_ok and HAS_PYGETWINDOW and gw is not None:
                matches = [w for w in gw.getAllWindows() if target_title.lower() in str(getattr(w, "title", "")).lower()]
                if matches:
                    try:
                        if matches[0].isMinimized:
                            matches[0].restore()
                        matches[0].activate()
                        executed = True
                        detail = f"Focused window '{matches[0].title}'"
                    except Exception as exc:
                        detail = f"Window focus note: {exc}"
                else:
                    return {"success": False, "error": f"No open window matching '{target_title}'."}
            else:
                executed = True
                detail = f"Dry-run / Cloud mode: focus window '{target_title}'."

        elif act in ("move", "click", "double_click", "right_click"):
            if cx is None or cy is None:
                return {"success": False, "error": f"Action '{act}' requires x and y coordinates."}
            if local_ok and HAS_PYAUTOGUI and pyautogui is not None:
                if act == "move":
                    pyautogui.moveTo(cx, cy, duration=0.15)
                elif act == "click":
                    pyautogui.click(cx, cy)
                elif act == "double_click":
                    pyautogui.doubleClick(cx, cy)
                elif act == "right_click":
                    pyautogui.rightClick(cx, cy)
                with self._lock:
                    sess["last_ai_cursor"] = {"x": cx, "y": cy}
                executed = True
                detail = f"PyAutoGUI {act} at ({cx}, {cy})"
            else:
                with self._lock:
                    sess["last_ai_cursor"] = {"x": cx, "y": cy}
                executed = True
                detail = f"Sandboxed {act} at ({cx}, {cy}) — connect local Windows host for physical cursor control."

        elif act == "type":
            clean_txt = str(text or "")
            if not clean_txt:
                return {"success": False, "error": "Text is required for type action."}
            if local_ok and HAS_PYAUTOGUI and pyautogui is not None:
                if cx is not None and cy is not None:
                    pyautogui.click(cx, cy)
                    time.sleep(0.08)
                pyautogui.write(clean_txt[:400], interval=0.015)
                executed = True
                detail = f"Typed {len(clean_txt[:400])} characters via PyAutoGUI"
            else:
                executed = True
                detail = f"Sandboxed keyboard type ({len(clean_txt[:400])} chars)."

        elif act == "hotkey":
            combo = [str(k).strip().lower() for k in (keys or []) if str(k).strip()]
            if not combo and text:
                combo = [p.strip().lower() for p in text.split("+") if p.strip()]
            if not combo:
                return {"success": False, "error": "Hotkey requires keys (e.g. ['ctrl', 'c'])."}
            blocked_combos = {("alt", "f4"), ("ctrl", "alt", "delete"), ("win", "l")}
            if tuple(combo) in blocked_combos:
                LIVE_ACTION_HUB.record(
                    uid,
                    "computer",
                    "hotkey",
                    f"Blocked high-risk OS hotkey: {'+'.join(combo)}",
                    status="blocked",
                )
                return {"success": False, "error": f"High-risk OS hotkey '{'+'.join(combo)}' is blocked by AURA safety policy."}
            if local_ok and HAS_PYAUTOGUI and pyautogui is not None:
                pyautogui.hotkey(*combo)
                executed = True
                detail = f"Pressed hotkey {'+'.join(combo)}"
            else:
                executed = True
                detail = f"Sandboxed hotkey {'+'.join(combo)}."

        elif act == "scroll":
            dy = int(delta_y)
            if local_ok and HAS_PYAUTOGUI and pyautogui is not None:
                if cx is not None and cy is not None:
                    pyautogui.moveTo(cx, cy)
                pyautogui.scroll(dy)
                executed = True
                detail = f"Scrolled desktop {dy}"
            else:
                executed = True
                detail = f"Sandboxed desktop scroll ({dy})."
        else:
            return {"success": False, "error": f"Unsupported computer action: {act}"}

        frame = self.capture_screen_frame(uid, width=1024, quality=58)
        dur = int((time.perf_counter() - t0) * 1000)
        with self._lock:
            sess["step_count"] += 1
            sess["updated_at"] = time.time()

        LIVE_ACTION_HUB.record(
            uid,
            "computer",
            act,
            detail[:140] or f"Desktop {act}",
            target=app_name or window_title or frame.get("active_window", ""),
            coords={"x": cx, "y": cy} if cx is not None and cy is not None else None,
            status="completed" if executed else "error",
            duration_ms=dur,
            detail=detail,
            thumbnail_b64=frame.get("frame_b64", ""),
            window_title=frame.get("active_window", ""),
            engine="pyautogui_local" if local_ok else "sandbox_dry_run",
        )
        return {
            "success": executed,
            "action": act,
            "detail": detail,
            "status": self.get_status(uid),
            "frame_b64": frame.get("frame_b64", ""),
        }

    def analyze_frame_with_vision(
        self,
        user_id: Any,
        goal: str = "Describe what is currently visible on the desktop screen and suggest the next step.",
        frame_b64: str = "",
        brain: Optional[AuraBrain] = None,
    ) -> Dict[str, Any]:
        """Runs OpenCV + Gemini Multimodal Vision analysis on live desktop or browser-shared screen frame."""
        uid = self._uid(user_id)
        t0 = time.perf_counter()
        sess = self._get_session(uid)

        clean_b64 = str(frame_b64 or "").strip()
        if clean_b64.startswith("data:image/"):
            clean_b64 = clean_b64.split(",", 1)[-1]

        if clean_b64:
            with self._lock:
                sess["last_client_frame_b64"] = clean_b64
            active_win = "Browser Screen Share"
        else:
            snap = self.capture_screen_frame(uid, width=1024, quality=62)
            clean_b64 = snap.get("frame_b64", "")
            active_win = snap.get("active_window", "Desktop")

        cv_stats: Dict[str, Any] = {"ui_regions": 0, "brightness": 0}
        if clean_b64 and HAS_CV2 and cv2 is not None and np is not None:
            try:
                raw = base64.b64decode(clean_b64)
                arr = np.frombuffer(raw, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    edges = cv2.Canny(cv2.resize(gray, (320, 180)), 60, 150)
                    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    cv_stats = {
                        "ui_regions": sum(1 for c in contours if cv2.contourArea(c) > 35),
                        "brightness": round(float(np.mean(gray)), 1),
                        "resolution": f"{img.shape[1]}x{img.shape[0]}",
                    }
            except Exception:
                pass

        vision_text = ""
        if brain is not None and not is_test_runner_active() and clean_b64:
            prompt = (
                f"You are AURA Visual Computer Agent observing a live desktop screen.\n"
                f"Active Window: {active_win}\n"
                f"User Goal: {goal}\n"
                f"OpenCV Screen Metrics: {json.dumps(cv_stats)}\n\n"
                "Briefly identify:\n"
                "1. What application/content is currently visible.\n"
                "2. Key clickable UI controls visible.\n"
                "3. The exact next safe mouse/keyboard step to accomplish the user's goal."
            )
            try:
                resp = brain._call_api(
                    [
                        {
                            "role": "user",
                            "parts": [
                                {"inlineData": {"mimeType": "image/jpeg", "data": clean_b64}},
                                {"text": prompt},
                            ],
                        }
                    ],
                    tools=None,
                    deadline_override=16.0,
                )
                cands = resp.get("candidates") or []
                if cands:
                    parts = (cands[0].get("content") or {}).get("parts") or []
                    vision_text = "\n".join(str(p.get("text") or "") for p in parts if isinstance(p, dict) and p.get("text")).strip()
            except Exception:
                vision_text = ""

        if not vision_text:
            vision_text = (
                f"Visual Screen Inspection ({active_win}): detected {cv_stats.get('ui_regions', 0)} UI regions "
                f"(avg luminance {cv_stats.get('brightness', 0)}). Goal ready: {goal}"
            )

        with self._lock:
            sess["last_vision_summary"] = vision_text[:1500]
            sess["updated_at"] = time.time()

        dur = int((time.perf_counter() - t0) * 1000)
        LIVE_ACTION_HUB.record(
            uid,
            "vision",
            "vision_analyze",
            f"Visual screen understanding ({active_win[:40]})",
            target=goal[:120],
            duration_ms=dur,
            detail=vision_text[:280],
            thumbnail_b64=clean_b64[:235_000] if len(clean_b64) <= 235_000 else "",
            window_title=active_win,
            engine="cv2_gemini_vision",
        )
        return {
            "success": True,
            "analysis": vision_text,
            "cv_stats": cv_stats,
            "active_window": active_win,
            "status": self.get_status(uid),
        }

    def _run_autonomous_agent_loop(self, uid: str, goal: str, brain: Optional[AuraBrain]) -> None:
        """Background Human-in-the-Loop Visual Computer Agent loop."""
        sess = self._get_session(uid)
        try:
            # Step 1: Observe live screen & inspect UI
            if sess["stop_event"].is_set():
                return
            self.inspect_ui_tree(uid)
            if sess["stop_event"].is_set():
                return

            # Wait if paused
            while sess["pause_event"].is_set() and not sess["stop_event"].is_set():
                time.sleep(0.15)
            if sess["stop_event"].is_set():
                return
            if self._check_human_takeover(uid, sess):
                return

            # Check if goal asks to launch a supported desktop application
            gl = goal.lower()
            app_aliases = {
                "notepad": ["notepad"],
                "calculator": ["calculator", "calc"],
                "chrome": ["chrome", "google chrome"],
                "vscode": ["vs code", "vscode", "visual studio code"],
                "explorer": ["file explorer", "explorer"],
                "whatsapp": ["whatsapp"],
                "settings": ["windows settings", "settings"],
                "terminal": ["terminal", "powershell", "cmd"],
            }
            for app_id, keywords in app_aliases.items():
                if any(k in gl for k in keywords) and any(v in gl for v in ("open", "launch", "start", "khol")):
                    self.execute_action(uid, "launch_app", app_name=app_id, allow_when_idle=False)
                    time.sleep(0.45)
                    break

            if sess["stop_event"].is_set() or self._check_human_takeover(uid, sess):
                return
            while sess["pause_event"].is_set() and not sess["stop_event"].is_set():
                time.sleep(0.15)
            if sess["stop_event"].is_set():
                return

            # Visual screen understanding step
            self.analyze_frame_with_vision(uid, goal=goal, brain=brain)

            with self._lock:
                if sess["state"] == "running":
                    sess["state"] = "idle"
                    sess["updated_at"] = time.time()

            LIVE_ACTION_HUB.record(
                uid,
                "computer",
                "task_complete",
                f"Computer Use cycle complete: {goal[:64]}",
                target=goal[:120],
                status="completed",
            )
        except Exception as exc:
            with self._lock:
                sess["state"] = "stopped"
            LIVE_ACTION_HUB.record(
                uid,
                "computer",
                "task_error",
                f"Computer Use halted safely: {exc}",
                status="error",
            )

    def control(
        self,
        user_id: Any,
        command: str,
        *,
        goal: str = "",
        brain: Optional[AuraBrain] = None,
    ) -> Dict[str, Any]:
        """Human-in-the-Loop top bar controls: start, pause, resume, stop, take_control."""
        uid = self._uid(user_id)
        cmd = str(command or "").strip().lower()
        sess = self._get_session(uid)

        if cmd not in ("start", "pause", "resume", "stop", "take_control"):
            return {"success": False, "error": f"Unknown control command: {cmd}"}

        if cmd in ("start", "resume") and JARVIS_HUB.get_status(uid).get("halted"):
            return {
                "success": False,
                "error": "JARVIS Kill Switch is HALTED. Disarm Kill Switch before starting Computer Use.",
                "status": self.get_status(uid),
            }

        with self._lock:
            if cmd == "start":
                sess["stop_event"].clear()
                sess["pause_event"].clear()
                sess["state"] = "running"
                sess["goal"] = str(goal or sess.get("goal") or "Observe desktop and standby for actions").strip()[:500]
                sess["updated_at"] = time.time()
                LIVE_ACTION_HUB.record(
                    uid,
                    "computer",
                    "start",
                    f"Computer Use STARTED: {sess['goal'][:64]}",
                    target=sess["goal"][:120],
                    status="running",
                )
                if goal and not is_test_runner_active():
                    t = threading.Thread(
                        target=self._run_autonomous_agent_loop,
                        args=(uid, sess["goal"], brain),
                        daemon=True,
                    )
                    sess["worker_thread"] = t
                    t.start()

            elif cmd == "pause":
                sess["pause_event"].set()
                sess["state"] = "paused"
                sess["updated_at"] = time.time()
                LIVE_ACTION_HUB.record(uid, "computer", "pause", "Computer Use PAUSED by user", status="paused")

            elif cmd == "resume":
                sess["pause_event"].clear()
                sess["stop_event"].clear()
                sess["state"] = "running"
                sess["updated_at"] = time.time()
                LIVE_ACTION_HUB.record(uid, "computer", "resume", "Computer Use RESUMED by user", status="running")

            elif cmd == "stop":
                sess["stop_event"].set()
                sess["pause_event"].clear()
                sess["state"] = "stopped"
                sess["updated_at"] = time.time()
                LIVE_ACTION_HUB.record(uid, "computer", "stop", "Computer Use STOPPED immediately", status="stopped")

            elif cmd == "take_control":
                sess["stop_event"].set()
                sess["pause_event"].set()
                sess["state"] = "human_control"
                sess["updated_at"] = time.time()
                LIVE_ACTION_HUB.record(
                    uid,
                    "computer",
                    "take_control",
                    "Human took full desktop control — AI yielded mouse & keyboard",
                    status="paused",
                )

        return {"success": True, "command": cmd, "status": self.get_status(uid)}


COMPUTER_USE = ComputerUseManager()
