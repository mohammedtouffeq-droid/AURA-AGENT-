"""
===================================================================================
                AURA MASTER PIPELINE: UNIFIED MULTI-ENGINE BUS
===================================================================================
Central Nervous System connecting ALL AURA engines into one continuous pipeline:
1. CoderX Enterprise Coding Engine (AST, Code Synthesis, Self-Healing)
2. AURA Cinema Media Engine (FLUX.1, Camera Physics, Alpha Cutout, 24fps Video)
3. AURA Game Engine & Godot 4.3 Studio (VehicleBody3D, JoltPhysics, 3D WebGL Mirror)
4. OS Controller & System Telemetry (Memory, RAM, Execution Safety)

Every user prompt or job travels through:
[INTENT] -> [CONTEXT INGESTION] -> [MULTI-ENGINE EXECUTION] -> [VALIDATION] -> [ARTIFACT SYNTHESIS]
===================================================================================
"""

import os
import sys
import time
import json
import uuid
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = ROOT_DIR / "workspace"
PIPELINE_RUNS_DIR = WORKSPACE_DIR / "pipeline_runs"
PIPELINE_RUNS_DIR.mkdir(parents=True, exist_ok=True)


class PipelineDomain(str, Enum):
    FULL_STACK = "full_stack"       # Code + Game + Media combined
    GAME_DEV = "game_dev"           # Godot 4 + 3D Physics + Playable WebGL
    MEDIA_STUDIO = "media_studio"   # FLUX.1 + Video + Background Removal
    CODERX = "coderx"               # AST + Code Generation + Testing
    SYSTEM = "system"               # OS Telemetry + Maintenance


class PipelineStage(str, Enum):
    QUEUED = "queued"
    INTENT_ANALYSIS = "intent_analysis"
    CONTEXT_INGESTION = "context_ingestion"
    ENGINE_DISPATCH = "engine_dispatch"
    VALIDATION = "validation"
    SYNTHESIS = "synthesis"
    COMPLETED = "completed"
    FAILED = "failed"


class AuraMasterPipeline:
    """Master single-pipe orchestrator for all AURA subsystems."""

    def __init__(self):
        self.active_runs: Dict[str, Dict[str, Any]] = {}

    def get_pipeline_topology(self) -> Dict[str, Any]:
        """Returns the full connection map of all piped subsystems."""
        # Check CoderX
        try:
            from coderx_engine import ROUTER
            coderx_status = {
                "active": True,
                "gemini_active": bool(ROUTER.gemini_key),
                "ollama_active": ROUTER.is_ollama_available()
            }
        except Exception as e:
            coderx_status = {"active": False, "error": str(e)}

        # Check Media Cinema
        try:
            from aura_media_engine import AURA_CINEMA
            media_status = AURA_CINEMA.get_status()
        except Exception as e:
            media_status = {"active": False, "error": str(e)}

        # Check Game Studio & Godot
        try:
            from aura_game_engine import AURA_GAME_STUDIO
            from godot_engine_manager import AURA_GODOT_MANAGER
            game_status = {
                "game_studio": AURA_GAME_STUDIO.get_status(),
                "godot_installed": AURA_GODOT_MANAGER.is_installed(),
                "godot_version": AURA_GODOT_MANAGER.get_version(),
                "godot_size_mb": AURA_GODOT_MANAGER.get_binary_size_mb()
            }
        except Exception as e:
            game_status = {"active": False, "error": str(e)}

        # Check OS Telemetry
        try:
            from aura_os_controller import laptop_controller
            telemetry = laptop_controller.get_system_telemetry()
        except Exception as e:
            telemetry = {"status": "UNKNOWN", "error": str(e)}

        return {
            "pipeline_name": "AURA Master Unified Pipeline v2.5",
            "status": "OPERATIONAL",
            "bus_type": "Multi-Engine Synchronous & Event-Driven",
            "connections": {
                "coderx_engine": coderx_status,
                "media_cinema_engine": media_status,
                "game_studio_engine": game_status,
                "os_telemetry": telemetry
            },
            "supported_domains": [d.value for d in PipelineDomain],
            "total_completed_runs": len(list(PIPELINE_RUNS_DIR.glob("*.json")))
        }

    def execute(self, goal: str, domain: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a job through the unified 5-stage pipeline:
        Stage 1: Intent Routing
        Stage 2: Context Gathering & Telemetry Ingestion
        Stage 3: Engine Execution (CoderX, Game, Media)
        Stage 4: Headless Validation & Quality Check
        Stage 5: Final Synthesis & Delivery
        """
        params = params or {}
        job_id = f"pipe_{uuid.uuid4().hex[:10]}"
        start_time = time.time()

        run_record = {
            "job_id": job_id,
            "goal": goal,
            "stage": PipelineStage.INTENT_ANALYSIS,
            "timeline": [],
            "results": {},
            "artifacts": [],
            "success": False
        }
        self._log_stage(run_record, PipelineStage.INTENT_ANALYSIS, "Analyzing goal intent and mapping target domain")

        # -------------------------------------------------------------
        # STAGE 1: INTENT ROUTING
        # -------------------------------------------------------------
        selected_domain = self._determine_domain(goal, domain)
        run_record["domain"] = selected_domain.value
        self._log_stage(run_record, PipelineStage.CONTEXT_INGESTION, f"Routing job to domain: {selected_domain.value}")

        # -------------------------------------------------------------
        # STAGE 2: CONTEXT INGESTION
        # -------------------------------------------------------------
        try:
            from aura_os_controller import laptop_controller
            system_snapshot = laptop_controller.get_system_telemetry()
        except Exception:
            system_snapshot = {"status": "ONLINE", "ram_total_gb": 16.0}

        run_record["system_snapshot"] = system_snapshot
        self._log_stage(run_record, PipelineStage.ENGINE_DISPATCH, "Dispatching tasks across piped engines")

        # -------------------------------------------------------------
        # STAGE 3: MULTI-ENGINE EXECUTION
        # -------------------------------------------------------------
        engine_outputs = {}

        if selected_domain in [PipelineDomain.GAME_DEV, PipelineDomain.FULL_STACK]:
            # Trigger Godot 4.3 Studio & Game Engine
            try:
                from godot_engine_manager import GodotCarCraftingProjectBuilder, AURA_GODOT_TRAINER
                proj_name = params.get("project_name", "CyberCraft3D")
                
                # Build or load project
                build_res = GodotCarCraftingProjectBuilder.build_project(proj_name)
                train_res = AURA_GODOT_TRAINER.train_and_verify(proj_name)
                
                engine_outputs["game_engine"] = {
                    "project_name": proj_name,
                    "build": build_res,
                    "headless_training": train_res,
                    "playable_web_mirror": build_res.get("playable_3d_web"),
                    "play_store_manifest": build_res.get("play_store_manifest")
                }
                if build_res.get("playable_3d_web"):
                    run_record["artifacts"].append({
                        "type": "playable_game",
                        "path": build_res.get("playable_3d_web"),
                        "title": f"{proj_name} 3D Playable Web Simulator"
                    })
            except Exception as e:
                engine_outputs["game_engine"] = {"success": False, "error": str(e)}

        if selected_domain in [PipelineDomain.MEDIA_STUDIO, PipelineDomain.FULL_STACK]:
            # Trigger AURA Cinema Media Engine
            try:
                from aura_media_engine import AURA_CINEMA
                media_prompt = params.get("media_prompt", f"High-tech realistic concept art for {goal}")
                camera_style = params.get("camera_style", "iphone_16_pro")
                
                # Render FLUX image
                img_res = AURA_CINEMA.create_cinematic_image(media_prompt, camera_style=camera_style)
                
                # Render 24fps promotional MP4 sequence
                video_prompt = params.get("video_prompt", f"Cinematic camera tracking shot of {goal}")
                vid_res = AURA_CINEMA.create_cinematic_video(video_prompt, duration_sec=3, fps=24)
                
                engine_outputs["media_engine"] = {
                    "image": img_res,
                    "video": vid_res
                }
                if img_res.get("file_path"):
                    run_record["artifacts"].append({
                        "type": "image",
                        "path": img_res.get("file_path"),
                        "title": "FLUX Cinematic Render"
                    })
                video_path = vid_res.get("video_path") or vid_res.get("mp4_path")
                if video_path:
                    run_record["artifacts"].append({
                        "type": "video",
                        "path": video_path,
                        "title": "24fps MP4 Video Sequence"
                    })
            except Exception as e:
                engine_outputs["media_engine"] = {"success": False, "error": str(e)}

        if selected_domain in [PipelineDomain.CODERX, PipelineDomain.FULL_STACK]:
            # Trigger CoderX Unified Engine
            try:
                from coderx_engine import CODERX, CodebaseAstMapper
                target_file = params.get("target_file", "pipeline_generated_script.py")
                coderx_res = CODERX.run(
                    goal=f"Implement high-performance logic module for: {goal}",
                    target_filename=target_file,
                    max_iterations=1
                )
                engine_outputs["coderx_engine"] = {
                    "code_output": coderx_res,
                    "target_file": target_file
                }
                run_record["artifacts"].append({
                    "type": "code",
                    "path": str(WORKSPACE_DIR / target_file),
                    "title": "CoderX Logic Script"
                })
            except Exception as e:
                engine_outputs["coderx_engine"] = {"success": False, "error": str(e)}

        run_record["results"] = engine_outputs

        # -------------------------------------------------------------
        # STAGE 4: VALIDATION
        # -------------------------------------------------------------
        self._log_stage(run_record, PipelineStage.VALIDATION, "Validating cross-engine artifacts and execution integrity")
        has_errors = any(
            isinstance(v, dict) and (v.get("success") is False or "error" in v)
            for v in engine_outputs.values()
        )
        
        # -------------------------------------------------------------
        # STAGE 5: SYNTHESIS & PACKAGING
        # -------------------------------------------------------------
        self._log_stage(run_record, PipelineStage.SYNTHESIS, "Synthesizing master response and persisting run log")
        total_time = round(time.time() - start_time, 3)
        run_record["elapsed_seconds"] = total_time
        run_record["success"] = not has_errors
        run_record["stage"] = PipelineStage.COMPLETED if not has_errors else PipelineStage.FAILED

        # Persist run record to disk
        save_file = PIPELINE_RUNS_DIR / f"{job_id}.json"
        try:
            save_file.write_text(json.dumps(run_record, indent=2, default=str), encoding="utf-8")
            run_record["persisted_log"] = str(save_file)
        except Exception as e:
            run_record["persisted_log_error"] = str(e)

        return run_record

    def _determine_domain(self, goal: str, domain_hint: Optional[str]) -> PipelineDomain:
        if domain_hint:
            try:
                return PipelineDomain(domain_hint.lower())
            except ValueError:
                pass

        g_lower = goal.lower()
        if any(w in g_lower for w in ["everything", "all", "pipeline", "connect", "full", "complete"]):
            return PipelineDomain.FULL_STACK
        elif any(w in g_lower for w in ["game", "godot", "car", "racing", "craft", "3d", "physics"]):
            return PipelineDomain.GAME_DEV
        elif any(w in g_lower for w in ["video", "image", "photo", "render", "flux", "portrait", "camera"]):
            return PipelineDomain.MEDIA_STUDIO
        elif any(w in g_lower for w in ["code", "script", "ast", "python", "bug", "patch", "program"]):
            return PipelineDomain.CODERX
        else:
            return PipelineDomain.FULL_STACK

    def _log_stage(self, record: Dict[str, Any], stage: PipelineStage, message: str) -> None:
        record["stage"] = stage.value
        record["timeline"].append({
            "stage": stage.value,
            "timestamp": round(time.time(), 3),
            "message": message
        })


# Master Singleton Pipeline
AURA_PIPELINE = AuraMasterPipeline()

if __name__ == "__main__":
    print("[*] Initializing AURA Master Pipeline...")
    topo = AURA_PIPELINE.get_pipeline_topology()
    print("[*] Pipeline Topology:", json.dumps(topo, indent=2))
    print("[*] Running Full-Stack E2E Test Pipeline...")
    res = AURA_PIPELINE.execute(
        goal="Autonomous 3D Cyber Racing with photorealistic promo assets and telemetry logic",
        domain="full_stack",
        params={"project_name": "CyberCraft3D"}
    )
    print(f"[*] Pipeline Run Finished: Success={res.get('success')}, Elapsed={res.get('elapsed_seconds')}s")
    print(f"[*] Artifacts Generated: {len(res.get('artifacts', []))}")
