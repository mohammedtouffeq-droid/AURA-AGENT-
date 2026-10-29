"""
===================================================================================
                     AURA AGENT - MULTI-USER WORKSPACE SERVER
===================================================================================
Enterprise-grade HTTP Server supporting:
- Multi-user authentication & token sessions (SQLite aura_workspace.db)
- Isolated threads, renaming, pinning, and message history
- Per-user memory vault & settings management
- Direct Gemini 3.1 ReAct execution loop with hardware tools
- 0.0.0.0 cloud / LAN host binding for universal deployment
Author: AURA Technologies Inc.
===================================================================================
"""

import os
import sys
import json
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add root folder to sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import aura_db
from aura_brain import AuraBrain
from aura_settings import AuraSettingsManager

BRAIN = AuraBrain()
SETTINGS = AuraSettingsManager()
HOST = os.environ.get("AURA_HOST", "0.0.0.0")
PORT = int(os.environ.get("AURA_PORT", 5050))


class AuraWebHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: Dict[str, Any], status: int = 200):
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.end_headers()
        self.wfile.write(encoded)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.end_headers()

    def _get_auth_user(self) -> Optional[Dict[str, Any]]:
        auth_header = self.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        if not token:
            token = self.headers.get("X-Auth-Token", "").strip()
        if not token:
            # Query param fallback
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            token = qs.get("token", [""])[0]

        if not token:
            return None
        return aura_db.authenticate_token(token)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/" or path == "/index.html" or path == "":
            html_file = ROOT / "index.html"
            if html_file.exists():
                data = html_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404, "index.html not found")

        elif path == "/api/auth/me":
            user = self._get_auth_user()
            if not user:
                self._send_json({"authenticated": False}, status=401)
            else:
                self._send_json({"authenticated": True, "user": user})

        elif path == "/api/threads":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            threads = aura_db.get_user_threads(user_id)
            self._send_json({"success": True, "threads": threads})

        elif path == "/api/threads/messages":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            thread_id = query.get("thread_id", [""])[0]
            if not thread_id:
                self._send_json({"success": False, "error": "thread_id required"}, status=400)
                return
            messages = aura_db.get_thread_messages(user_id, thread_id)
            self._send_json({"success": True, "messages": messages})

        elif path == "/api/memory":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            memories = aura_db.get_user_memories(user_id)
            self._send_json({"success": True, "memories": memories})

        elif path == "/api/settings":
            user = self._get_auth_user()
            config = dict(SETTINGS.config)
            if user and user.get("settings"):
                config["user_custom"] = user["settings"]
            self._send_json(config)

        elif path == "/api/projects":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            projects = aura_db.get_user_projects(user_id)
            self._send_json({"success": True, "projects": projects})

        elif path == "/api/system/test_browser":
            from aura_brain import tool_open_browser
            res = tool_open_browser("https://www.google.com")
            self._send_json(res)

        elif path == "/api/system/safety_status":
            from aura_brain import SAFE_WORKSPACE_ROOTS, STRICTLY_FORBIDDEN_PATHS
            self._send_json({
                "success": True,
                "sandbox_active": True,
                "safe_workspaces": [str(p) for p in SAFE_WORKSPACE_ROOTS],
                "strictly_forbidden_paths": [str(p) for p in STRICTLY_FORBIDDEN_PATHS],
                "hardware_control": "Protected Foreground Subprocess",
                "powershell_sandbox": "Command Pattern Filter + Review Gate",
                "multimodal_tools": ["tool_generate_image", "tool_generate_video", "tool_get_weather", "tool_open_browser"]
            })

        elif path == "/api/engines":
            from aura_engine_mesh import AURA_ENGINE_MESH
            mesh_status = AURA_ENGINE_MESH.get_mesh_status()
            self._send_json({
                "success": True,
                "status": "ALL_63_ENGINES_AWAKENED",
                "total_engines": mesh_status["total_engines"],
                "awakened_engines": mesh_status["awakened_engines"],
                "total_files": mesh_status["total_files"],
                "supervisor_alive": mesh_status["supervisor_alive"],
                "timestamp": mesh_status["timestamp"],
                "engines": mesh_status["engines"]
            })

        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        elif path == "/api/engines/search":
            from aura_agent import AuraAgent
            agent_inst = AuraAgent()
            keyword = body.get("keyword", "")
            target_engine = body.get("engine", None)
            res = agent_inst.search_mesh_code(keyword, target_engine=target_engine)
            self._send_json({"success": True, "results": res})

        elif path == "/api/workspace/tree":
            ws = ROOT / "workspace"
            ws.mkdir(parents=True, exist_ok=True)
            files = []
            for f in ws.rglob("*"):
                if f.is_file() and not f.name.startswith("."):
                    files.append({
                        "name": f.name,
                        "rel_path": str(f.relative_to(ws)),
                        "size_kb": round(f.stat().st_size / 1024, 2),
                        "ext": f.suffix.lower()
                    })
            self._send_json({"success": True, "workspace": str(ws), "total_files": len(files), "files": files})

        elif path == "/api/workspace/file":
            query = parsed.query
            params = urllib.parse.parse_qs(query)
            file_rel = params.get("path", [""])[0]
            ws = ROOT / "workspace"
            target_p = (ws / file_rel).resolve()
            if ws in target_p.parents or target_p == ws or str(target_p).startswith(str(ws)):
                if target_p.exists() and target_p.is_file():
                    try:
                        content = target_p.read_text(encoding="utf-8", errors="ignore")
                        self._send_json({"success": True, "path": file_rel, "content": content})
                    except Exception as e:
                        self._send_json({"success": False, "error": str(e)}, status=500)
                else:
                    self._send_json({"success": False, "error": "File not found"}, status=404)
            else:
                self._send_json({"success": False, "error": "Path traversal restricted"}, status=403)

        elif path == "/api/cyberheist/status":
            ch_dir = Path(r"C:\Users\hp\cyberheist")
            status = {"success": True, "mounted": ch_dir.exists(), "path": str(ch_dir)}
            if ch_dir.exists():
                try:
                    sims = json.loads((ch_dir / "simulations.json").read_text(encoding="utf-8"))
                    missions = json.loads((ch_dir / "missions.json").read_text(encoding="utf-8"))
                    status["missions_count"] = len(missions.get("missions", []))
                    status["labs_count"] = len(sims.get("labs", []))
                    status["tabletops_count"] = len(sims.get("tabletops", []))
                    status["glossary_count"] = len(sims.get("glossary", []))
                except Exception as e:
                    status["error"] = str(e)
            self._send_json(status)
        elif path == "/api/permission/pending":
            from aura_permission_system import permission_manager
            pending = permission_manager.get_pending()
            self._send_json({"success": True, "pending": pending, "count": len(pending)})

        elif path == "/api/permission/history":
            from aura_permission_system import permission_manager
            self._send_json({"success": True, "history": permission_manager.history})

        elif path == "/api/os/telemetry":
            from aura_os_controller import laptop_controller
            self._send_json({"success": True, "telemetry": laptop_controller.get_system_telemetry()})

        elif path == "/api/game/status":
            from aura_game_engine import AURA_GAME_STUDIO
            self._send_json({"success": True, "status": AURA_GAME_STUDIO.get_status()})

        elif path == "/api/godot/status":
            from godot_engine_manager import AURA_GODOT_MANAGER
            self._send_json({
                "success": True,
                "installed": AURA_GODOT_MANAGER.is_installed(),
                "version": AURA_GODOT_MANAGER.get_version(),
                "binary_size_mb": AURA_GODOT_MANAGER.get_binary_size_mb(),
                "binary_path": str(AURA_GODOT_MANAGER.exe_path)
            })

        elif path == "/api/godot/projects":
            from godot_engine_manager import GAMES_WORKSPACE
            projects = []
            for item in GAMES_WORKSPACE.iterdir():
                if item.is_dir() and (item / "project.godot").exists():
                    projects.append({
                        "name": item.name,
                        "path": str(item),
                        "has_web_mirror": (item / "play_crafting_car.html").exists()
                    })
            self._send_json({"success": True, "projects": projects})

        elif path == "/api/media/status":
            from aura_media_engine import AURA_CINEMA
            self._send_json({"success": True, "status": AURA_CINEMA.get_status()})

        elif path == "/api/coderx/status":
            from coderx_engine import ROUTER
            self._send_json({
                "success": True,
                "engine": "CoderX Enterprise v2.0",
                "gemini_active": bool(ROUTER.gemini_key),
                "ollama_active": ROUTER.is_ollama_available(),
                "ollama_models": ROUTER.list_ollama_models() if ROUTER.is_ollama_available() else []
            })

        elif path == "/api/coderx/ast":
            from coderx_engine import CodebaseAstMapper
            ws = ROOT / "workspace"
            repo_map = CodebaseAstMapper.generate_repo_map(ws)
            self._send_json({"success": True, "repo_map": repo_map})
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            body = json.loads(post_data) if post_data else {}
        except Exception:
            body = {}

        path = urllib.parse.urlparse(self.path).path

        # 1. AUTH ROUTES
        if path == "/api/auth/register":
            username = body.get("username", "")
            password = body.get("password", "")
            res = aura_db.register_user(username, password)
            status = 200 if res.get("success") else 400
            self._send_json(res, status=status)

        elif path == "/api/auth/login":
            username = body.get("username", "")
            password = body.get("password", "")
            res = aura_db.login_user(username, password)
            status = 200 if res.get("success") else 401
            self._send_json(res, status=status)

        # 2. THREADS ROUTES
        elif path == "/api/threads/new":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            title = body.get("title", "New Session")
            thread = aura_db.create_user_thread(user_id, title)
            self._send_json({"success": True, "thread": thread})

        elif path == "/api/threads/rename":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            thread_id = body.get("thread_id", "")
            new_title = body.get("title", "").strip()
            if not thread_id or not new_title:
                self._send_json({"success": False, "error": "thread_id and title required"}, status=400)
                return
            ok = aura_db.rename_user_thread(user_id, thread_id, new_title)
            self._send_json({"success": ok})

        elif path == "/api/threads/pin":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            thread_id = body.get("thread_id", "")
            is_pinned = body.get("is_pinned", False)
            ok = aura_db.pin_user_thread(user_id, thread_id, is_pinned)
            self._send_json({"success": ok})

        elif path == "/api/threads/delete":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            thread_id = body.get("thread_id", "")
            ok = aura_db.delete_user_thread(user_id, thread_id)
            self._send_json({"success": ok})

        # 2B. CODING PROJECTS ROUTES
        elif path == "/api/projects/new":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            name = body.get("name", "New Project")
            company = body.get("company", "")
            stack = body.get("stack", "Python")
            proj_path = body.get("path", "")
            description = body.get("description", "")
            proj = aura_db.create_user_project(user_id, name, company, stack, proj_path, description)
            self._send_json({"success": True, "project": proj})

        elif path == "/api/projects/pin":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            proj_id = body.get("project_id", "")
            is_pinned = body.get("is_pinned", False)
            ok = aura_db.pin_user_project(user_id, proj_id, is_pinned)
            self._send_json({"success": ok})

        elif path == "/api/projects/rename":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            proj_id = body.get("project_id", "")
            new_name = body.get("name", "").strip()
            ok = aura_db.rename_user_project(user_id, proj_id, new_name)
            self._send_json({"success": ok})

        elif path == "/api/projects/delete":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            proj_id = body.get("project_id", "")
            ok = aura_db.delete_user_project(user_id, proj_id)
            self._send_json({"success": ok})

        # 3. CHAT DISPATCH
        elif path == "/api/chat":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            prompt = body.get("prompt", "").strip()
            thread_id = body.get("thread_id", "default")
            attachments = body.get("attachments", [])
            permission_mode = body.get("mode", "auto_pilot")
            approved = body.get("approved", False)

            if not prompt and not attachments:
                self._send_json({"reply": "Please enter an instruction or attach a file."}, status=400)
                return

            # Save user turn with attachment summary
            display_prompt = prompt
            if attachments:
                att_names = [a.get("name", "attachment") for a in attachments]
                display_prompt += f"\n[📎 {len(attachments)} Attachment(s): {', '.join(att_names)}]"

            aura_db.save_message(user_id, thread_id, "user", display_prompt)

            print(f"[*] AURA Runtime: User {user_id} in thread '{thread_id}' -> '{prompt}' (Mode: {permission_mode}, Attachments: {len(attachments)})")
            reply = BRAIN.think_and_act(prompt, attachments=attachments, permission_mode=permission_mode, approved=approved)
            tools_used = getattr(BRAIN, "last_tools", [])

            # Save assistant response
            aura_db.save_message(user_id, thread_id, "assistant", reply, tools_used)

            self._send_json({
                "reply": reply,
                "tools": tools_used,
                "status": "completed"
            })

        # 4. MEMORY ROUTES
        elif path == "/api/memory/add":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            key = body.get("key", "").strip()
            val = body.get("value", "").strip()
            if not key or not val:
                self._send_json({"success": False, "error": "Key and value required"}, status=400)
                return
            ok = aura_db.save_user_memory(user_id, key, val)
            self._send_json({"success": ok, "key": key, "value": val})

        elif path == "/api/memory/delete":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            key = body.get("key", "").strip()
            ok = aura_db.delete_user_memory(user_id, key)
            self._send_json({"success": ok, "deleted": key})

        # 5. SETTINGS ROUTE
        elif path == "/api/settings":
            user = self._get_auth_user()
            if user:
                aura_db.save_user_settings(user["id"], body)
            for cat, opts in body.items():
                if cat in SETTINGS.config and isinstance(opts, dict):
                    SETTINGS.config[cat].update(opts)
            SETTINGS.save_settings()
            self._send_json({"success": True, "config": SETTINGS.config})

        elif path == "/api/engines/search":
            from aura_agent import AuraAgent
            agent_inst = AuraAgent()
            keyword = body.get("keyword", "")
            target_engine = body.get("engine", None)
            res = agent_inst.search_mesh_code(keyword, target_engine=target_engine)
            self._send_json({"success": True, "results": res})

        elif path == "/api/workspace/save":
            file_rel = body.get("path", "")
            file_content = body.get("content", "")
            ws = ROOT / "workspace"
            target_p = (ws / file_rel).resolve()
            if str(target_p).startswith(str(ws)):
                target_p.parent.mkdir(parents=True, exist_ok=True)
                target_p.write_text(file_content, encoding="utf-8")
                self._send_json({"success": True, "saved_path": str(target_p), "bytes": len(file_content)})
            else:
                self._send_json({"success": False, "error": "Save path outside workspace is forbidden"}, status=403)

        elif path == "/api/terminal/exec":
            cmd = body.get("command", "")
            ws = ROOT / "workspace"
            ws.mkdir(parents=True, exist_ok=True)
            if not cmd:
                self._send_json({"success": False, "error": "Command is required"}, status=400)
            else:
                import subprocess
                try:
                    proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                                          cwd=str(ws), capture_output=True, text=True, timeout=30)
                    self._send_json({
                        "success": True,
                        "command": cmd,
                        "exit_code": proc.returncode,
                        "stdout": proc.stdout,
                        "stderr": proc.stderr
                    })
                except Exception as e:
                    self._send_json({"success": False, "command": cmd, "error": str(e), "exit_code": 1})

        elif path == "/api/game/world/generate":
            theme = body.get("theme", "gta_city")
            chunks = body.get("chunks", 4)
            seed = body.get("seed", 42)
            from aura_game_engine import OpenWorldProceduralGenerator
            res = OpenWorldProceduralGenerator.generate_world(theme=theme, chunks=chunks, seed=seed)
            self._send_json(res)

        elif path == "/api/game/physics/simulate":
            steps = body.get("steps", 60)
            name = body.get("name", "car")
            mass = body.get("mass", 1200.0)
            pos_y = body.get("pos_y", 3.0)
            from aura_game_engine import JoltPhysicsEngine
            jolt = JoltPhysicsEngine()
            jolt.add_body(name, mass=mass, pos=(0, pos_y, 0), restitution=0.3)
            self._send_json(jolt.simulate(steps=steps))

        elif path == "/api/game/navmesh/pathfind":
            sx = body.get("start_x", 0)
            sy = body.get("start_y", 0)
            gx = body.get("goal_x", 10)
            gy = body.get("goal_y", 10)
            from aura_game_engine import RecastNavMeshRouter
            res = RecastNavMeshRouter.find_path(start=(sx, sy), goal=(gx, gy))
            self._send_json(res)

        elif path == "/api/game/agent/train":
            episodes = body.get("episodes", 5)
            from aura_game_engine import MLAgentsCarlaTrainer
            res = MLAgentsCarlaTrainer.train_driving_agent(episodes=episodes)
            self._send_json(res)

        elif path == "/api/game/multiplayer/sync":
            count = body.get("player_count", 100)
            from aura_game_engine import AgonesNetcodeSynchronizer
            res = AgonesNetcodeSynchronizer.simulate_100_player_tick(player_count=count)
            self._send_json(res)

        elif path == "/api/game/project/export":
            proj = body.get("project_name", "open_world_demo")
            from aura_game_engine import EngineProjectExporter
            res = EngineProjectExporter.export_project(project_name=proj)
            self._send_json(res)

        elif path == "/api/godot/build":
            proj = body.get("project_name", "CyberCraft3D")
            from godot_engine_manager import GodotCarCraftingProjectBuilder
            res = GodotCarCraftingProjectBuilder.build_project(project_name=proj)
            self._send_json(res)

        elif path == "/api/godot/verify":
            proj = body.get("project_name", "CyberCraft3D")
            from godot_engine_manager import AURA_GODOT_TRAINER
            res = AURA_GODOT_TRAINER.train_and_verify(project_name=proj)
            self._send_json(res)

        elif path == "/api/godot/launch":
            proj = body.get("project_name", "CyberCraft3D")
            from godot_engine_manager import AURA_GODOT_MANAGER, GAMES_WORKSPACE
            proj_dir = GAMES_WORKSPACE / proj
            res = AURA_GODOT_MANAGER.launch_windowed_game(proj_dir)
            self._send_json(res)

        elif path == "/api/media/image/generate":
            prompt = body.get("prompt", "")
            style = body.get("style", "auto")
            aspect_ratio = body.get("aspect_ratio", "1:1")
            from aura_media_engine import AURA_CINEMA
            res = AURA_CINEMA.create_cinematic_image(prompt, camera_style=style, aspect_ratio=aspect_ratio)
            self._send_json(res)

        elif path == "/api/media/image/transform":
            img_path = body.get("image_path", "")
            instruction = body.get("instruction", "iPhone portrait")
            from aura_media_engine import AURA_CINEMA
            res = AURA_CINEMA.transform_existing_image(img_path, instruction)
            self._send_json(res)

        elif path == "/api/media/image/remove_bg":
            img_path = body.get("image_path", "")
            from aura_media_engine import NativeSegmentationEngine
            inp = Path(img_path)
            out = inp.parent / f"{inp.stem}_nobg.png"
            res = NativeSegmentationEngine.remove_background(inp, out)
            self._send_json(res)

        elif path == "/api/media/video/generate":
            prompt = body.get("prompt", "")
            duration = body.get("duration_sec", 5)
            fps = body.get("fps", 24)
            motion = body.get("camera_motion", "dolly_zoom")
            aspect = body.get("aspect_ratio", "16:9")
            from aura_media_engine import AURA_CINEMA
            res = AURA_CINEMA.create_cinematic_video(prompt, duration_sec=duration, fps=fps, camera_motion=motion, aspect_ratio=aspect)
            self._send_json(res)

        elif path == "/api/coderx/execute":
            goal = body.get("goal", "")
            filename = body.get("filename", "coderx_script.py")
            cmd = body.get("test_command", "")
            max_iter = body.get("max_iterations", 5)
            from coderx_engine import CODERX
            res = CODERX.run(goal=goal, target_filename=filename, test_command=cmd, max_iterations=max_iter)
            self._send_json(res)

        elif path == "/api/coderx/patch":
            file_rel = body.get("path", "")
            patch_text = body.get("patch", "")
            ws = ROOT / "workspace"
            target_p = (ws / file_rel).resolve()
            from coderx_engine import AiderDiffPatcher
            res = AiderDiffPatcher.apply_patch_string(target_p, patch_text)
            self._send_json(res)

        elif path == "/api/autonomous/mission":
            goal = body.get("goal", "")
            filename = body.get("filename", "mission_script.py")
            from aura_autonomous_loop import AURA_LOOP
            from aura_brain import tool_autonomous_code_loop
            res = tool_autonomous_code_loop(goal=goal, target_filename=filename)
            self._send_json(res)

        elif path == "/api/engines/invoke":
            engine_key = body.get("engine", "")
            action = body.get("action", "run")
            params = body.get("params", {})
            from aura_engine_mesh import AURA_ENGINE_MESH
            res = AURA_ENGINE_MESH.invoke(engine_key, action=action, **params)
            self._send_json(res)
        elif path == "/api/permission/respond":
            req_id = body.get("id", "")
            decision = body.get("decision", "DENY")
            from aura_permission_system import permission_manager
            ok = permission_manager.respond_request(req_id, decision)
            self._send_json({"success": ok, "id": req_id, "decision": decision})

        elif path == "/api/permission/mode":
            mode = body.get("mode", "PROMPT_HIGH_RISK")
            from aura_permission_system import permission_manager
            ok = permission_manager.set_security_mode(mode)
            self._send_json({"success": ok, "mode": mode})

        elif path == "/api/os/execute":
            cmd = body.get("command", "")
            as_admin = body.get("as_admin", False)
            from aura_os_controller import laptop_controller
            res = laptop_controller.execute_powershell(cmd, as_admin=as_admin)
            self._send_json(res)

        elif path == "/api/os/read_file":
            filepath = body.get("path", "")
            from aura_os_controller import laptop_controller
            res = laptop_controller.read_file(filepath)
            self._send_json(res)

        elif path == "/api/os/write_file":
            filepath = body.get("path", "")
            file_content = body.get("content", "")
            from aura_os_controller import laptop_controller
            res = laptop_controller.write_file(filepath, file_content)
            self._send_json(res)

        elif path == "/api/os/screenshot":
            from aura_os_controller import laptop_controller
            res = laptop_controller.capture_screenshot()
            self._send_json(res)
        else:
            self.send_error(404, "Not Found")


def make_server(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), AuraWebHandler)


def run():
    httpd = make_server(HOST, PORT)
    url = f"http://127.0.0.1:{PORT}"
    print("=" * 65)
    print("        AURA AGENT - MULTI-USER CLOUD & LOCAL WORKSPACE")
    print("                    AURA Technologies Inc.")
    print("=" * 65)
    print(f"[*] Workspace Server Binding : {HOST}:{PORT}")
    print(f"[*] Local Access URL         : {url}")
    print("[*] Multi-User Auth SQLite   : ACTIVE (aura_workspace.db)")
    print("[*] Security Sandbox Guard   : ACTIVE (PathGuard & CommandGuard)")
    print("[*] ReAct Gemini Brain       : READY (Multimodal & 63 Engines)")
    print("-" * 65)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server shutdown gracefully.")


if __name__ == "__main__":
    run()
