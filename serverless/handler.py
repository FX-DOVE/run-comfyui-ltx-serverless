#!/usr/bin/env python3
"""
handler.py - RunPod Serverless Handler for LTX-2.5 ComfyUI Worker.
Handles job requests, constructs and queues workflows, monitors generation, and returns video URLs.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict

# Ensure ComfyUI modules can be resolved from workspace and container
for p in ("/workspace/ComfyUI", "/ComfyUI"):
    if p not in sys.path:
        sys.path.insert(0, p)

import runpod

from comfy_client import ComfyClient, ComfyUIExecutionError, ComfyUITimeoutError
from health import full_health_check
from storage import StorageManager
from workflow import (
    DEFAULT_DIFFUSION_MODEL,
    DEFAULT_LORA,
    DEFAULT_TEXT_ENCODER,
    DEFAULT_VAE,
    build_ltx25_t2v_workflow,
    find_existing_model_name,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("runpod_handler")

# Concurrency lock to ensure one inference at a time per GPU worker
worker_lock = threading.Lock()

COMFY_HOST = os.getenv("COMFYUI_HOST", "127.0.0.1")
COMFY_PORT = int(os.getenv("COMFYUI_PORT", "8188"))
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "/workspace")
COMFY_OUTPUT_DIR = os.getenv("COMFYUI_OUTPUT_DIR", f"{WORKSPACE_DIR}/ComfyUI/output")

client = ComfyClient(host=COMFY_HOST, port=COMFY_PORT)
storage = StorageManager()


def sanitize_workflow_prompt(workflow: Dict[str, Any], models_dir: str = f"{WORKSPACE_DIR}/ComfyUI/models") -> Dict[str, Any]:
    """
    Sanitizes workflow graph to prevent ComfyUI validation errors:
    1. Ensures required VHS_VideoCombine parameters (e.g., pingpong) are present.
    2. Replaces any dummy placeholder filenames (e.g. 'put_diffusion_model_files_here') with real model filenames found on disk.
    """
    import copy
    wf = copy.deepcopy(workflow)

    for node_id, node_data in wf.items():
        if not isinstance(node_data, dict):
            continue

        class_type = node_data.get("class_type", "")
        inputs = node_data.get("inputs", {})
        if not isinstance(inputs, dict):
            continue

        # 1. Fix VHS_VideoCombine missing required inputs
        if class_type == "VHS_VideoCombine":
            if "pingpong" not in inputs:
                inputs["pingpong"] = False
            if "save_output" not in inputs:
                inputs["save_output"] = True

        # 2. Fix UNETLoader placeholder
        elif class_type in ("UNETLoader", "UNETLoaderGGUF"):
            unet_name = str(inputs.get("unet_name", ""))
            if not unet_name or unet_name.startswith("put_") or unet_name == "undefined":
                resolved = find_existing_model_name("diffusion_models", DEFAULT_DIFFUSION_MODEL, models_dir)
                logger.info(f"Resolved placeholder unet_name '{unet_name}' -> '{resolved}'")
                inputs["unet_name"] = resolved

        # 3. Fix CLIPLoader placeholder
        elif class_type in ("CLIPLoader", "CLIPLoaderGGUF"):
            clip_name = str(inputs.get("clip_name", ""))
            if not clip_name or clip_name.startswith("put_") or clip_name == "undefined":
                resolved = find_existing_model_name("text_encoders", DEFAULT_TEXT_ENCODER, models_dir)
                logger.info(f"Resolved placeholder clip_name '{clip_name}' -> '{resolved}'")
                inputs["clip_name"] = resolved

        # 4. Fix VAELoader placeholder
        elif class_type == "VAELoader":
            vae_name = str(inputs.get("vae_name", ""))
            if not vae_name or vae_name.startswith("put_") or vae_name == "undefined":
                resolved = find_existing_model_name("vae", DEFAULT_VAE, models_dir)
                logger.info(f"Resolved placeholder vae_name '{vae_name}' -> '{resolved}'")
                inputs["vae_name"] = resolved

        # 5. Fix LoraLoader placeholder
        elif class_type in ("LoraLoaderModelOnly", "LoraLoader"):
            lora_name = str(inputs.get("lora_name", ""))
            if not lora_name or lora_name.startswith("put_") or lora_name == "undefined":
                resolved = find_existing_model_name("loras", DEFAULT_LORA, models_dir)
                logger.info(f"Resolved placeholder lora_name '{lora_name}' -> '{resolved}'")
                inputs["lora_name"] = resolved

    return wf


def get_vram_peak_gb() -> float:
    """Measure peak allocated CUDA memory in GB."""
    try:
        import torch

        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / (1024**3), 2)
    except Exception:
        pass
    return 0.0


def reset_vram_stats() -> None:
    """Reset CUDA peak memory stats."""
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def validate_and_parse_input(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize user input parameters."""
    prompt = job_input.get("prompt")
    if not prompt or not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Field 'prompt' is required and must be a non-empty string.")

    negative_prompt = job_input.get(
        "negative_prompt",
        "worst quality, inconsistent motion, blurry, low resolution, distorted, jitter, static",
    )

    width = int(job_input.get("width", 768))
    height = int(job_input.get("height", 432))
    num_frames = int(job_input.get("num_frames", job_input.get("frames", 49)))
    fps = int(job_input.get("fps", 24))
    steps = int(job_input.get("steps", 20))
    cfg = float(job_input.get("cfg", 3.0))
    seed = job_input.get("seed")
    if seed is not None:
        seed = int(seed)

    sampler_name = job_input.get("sampler_name", "euler")
    scheduler = job_input.get("scheduler", "simple")
    use_distilled_lora = bool(job_input.get("use_distilled_lora", True))
    lora_strength = float(job_input.get("lora_strength", 1.0))
    return_base64 = bool(job_input.get("return_base64", False))
    upload_s3 = job_input.get("upload_s3")

    # Clamping & Sanity Bounds
    width = max(256, min(1920, width))
    height = max(256, min(1080, height))
    num_frames = max(9, min(257, num_frames))
    steps = max(1, min(100, steps))
    cfg = max(1.0, min(20.0, cfg))

    return {
        "prompt": prompt.strip(),
        "negative_prompt": str(negative_prompt).strip(),
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "fps": fps,
        "steps": steps,
        "cfg": cfg,
        "seed": seed,
        "sampler_name": sampler_name,
        "scheduler": scheduler,
        "use_distilled_lora": use_distilled_lora,
        "lora_strength": lora_strength,
        "return_base64": return_base64,
        "upload_s3": upload_s3,
    }


def ensure_comfyui_running(timeout_seconds: int = 90) -> bool:
    """Ensure ComfyUI process is running and responsive on HTTP API."""
    if client.is_ready(timeout_seconds=2):
        return True

    logger.info("ComfyUI not immediately responsive, checking/spawning process...")
    import subprocess
    import psutil

    if os.path.exists("/workspace/ComfyUI/main.py") and os.path.exists("/workspace/ComfyUI/comfy/options.py"):
        comfy_entry = "/workspace/ComfyUI/main.py"
    elif os.path.exists("/ComfyUI/main.py"):
        comfy_entry = "/ComfyUI/main.py"
    else:
        comfy_entry = "/workspace/ComfyUI/main.py"

    cmd = [
        sys.executable,
        comfy_entry,
        "--listen",
        "--enable-manager",
        "--preview-method",
        "latent2rgb"
    ]

    found = False
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = p.info.get('cmdline') or []
            if any('main.py' in str(c) for c in cmdline):
                found = True
                break
        except Exception:
            pass

    if not found and os.path.exists(comfy_entry):
        logger.info(f"Spawning ComfyUI process: {' '.join(cmd)}")
        spawn_env = os.environ.copy()
        spawn_env["PYTHONPATH"] = f"/workspace/ComfyUI:/ComfyUI:{spawn_env.get('PYTHONPATH', '')}"
        subprocess.Popen(cmd, env=spawn_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return client.is_ready(timeout_seconds=timeout_seconds, poll_interval=2.0)


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """RunPod Serverless Job Handler."""
    job_id = job.get("id", "local_job")
    job_input = job.get("input", {})

    logger.info(f"Received job {job_id}")

    # Support explicit health check request
    if job_input.get("health_check") or job_input.get("action") in ("health", "health_check", "status"):
        report = full_health_check(workspace_dir=WORKSPACE_DIR, host=COMFY_HOST, port=COMFY_PORT)
        return {"status": "ok" if report["healthy"] else "degraded", "health": report}

    with worker_lock:
        start_time = time.time()
        reset_vram_stats()

        try:
            # 1. Input parsing
            params = validate_and_parse_input(job_input)

            # 2. Check ComfyUI server readiness (watchdog + generous 90s cold start allowance)
            if not ensure_comfyui_running(timeout_seconds=90):
                raise RuntimeError("ComfyUI server is not responding at 127.0.0.1:8188 after 90s")

            # 3. Build workflow graph
            custom_workflow = job_input.get("workflow")
            if custom_workflow and isinstance(custom_workflow, dict):
                logger.info(f"Using custom workflow provided in request for job {job_id}")
                workflow_prompt = custom_workflow
            else:
                workflow_prompt = build_ltx25_t2v_workflow(
                    prompt=params["prompt"],
                    negative_prompt=params["negative_prompt"],
                    width=params["width"],
                    height=params["height"],
                    num_frames=params["num_frames"],
                    fps=params["fps"],
                    seed=params["seed"],
                    steps=params["steps"],
                    cfg=params["cfg"],
                    sampler_name=params["sampler_name"],
                    scheduler=params["scheduler"],
                    use_distilled_lora=params["use_distilled_lora"],
                    lora_strength=params["lora_strength"],
                    models_dir=f"{WORKSPACE_DIR}/ComfyUI/models",
                )

            # 3.5 Sanitize workflow prompt to ensure all required parameters (e.g. pingpong) and model paths are valid
            workflow_prompt = sanitize_workflow_prompt(
                workflow_prompt, models_dir=f"{WORKSPACE_DIR}/ComfyUI/models"
            )

            # 4. Queue workflow prompt
            queue_start = time.time()
            prompt_id = client.queue_prompt(workflow_prompt)
            queue_duration = time.time() - queue_start
            logger.info(f"Queued prompt {prompt_id} for job {job_id} in {queue_duration:.2f}s")

            # 5. Track execution to completion
            def on_progress(val, max_val, node):
                logger.info(f"[{job_id}] Progress: {val}/{max_val} (Node: {node})")

            gen_start = time.time()
            history_entry = client.track_execution(
                prompt_id=prompt_id,
                timeout_seconds=int(os.getenv("JOB_TIMEOUT_SECONDS", "900")),
                on_progress=on_progress,
            )
            gen_duration = time.time() - gen_start
            logger.info(f"Generation completed for prompt {prompt_id} in {gen_duration:.2f}s")

            # 6. Extract output files
            raw_files = client.extract_output_files(history_entry, output_dir=COMFY_OUTPUT_DIR)
            if not raw_files:
                raise RuntimeError(
                    f"ComfyUI completed prompt {prompt_id} but produced no output files. History: {history_entry}"
                )

            # 7. Process files (S3 upload / base64 / local path)
            processed_files = []
            primary_url = None

            for file_info in raw_files:
                processed = storage.process_output_file(
                    file_info=file_info,
                    return_base64=params["return_base64"],
                    upload_s3=params["upload_s3"],
                )
                processed_files.append(processed)
                if not primary_url and "url" in processed:
                    primary_url = processed["url"]

            total_duration = time.time() - start_time
            peak_vram = get_vram_peak_gb()

            response = {
                "status": "success",
                "prompt_id": prompt_id,
                "video_url": primary_url or (processed_files[0]["local_path"] if processed_files else None),
                "output_files": processed_files,
                "metrics": {
                    "total_duration_seconds": round(total_duration, 2),
                    "queue_duration_seconds": round(queue_duration, 2),
                    "generation_duration_seconds": round(gen_duration, 2),
                    "vram_peak_gb": peak_vram,
                },
                "params": params,
            }

            logger.info(f"Job {job_id} succeeded in {total_duration:.2f}s (VRAM peak: {peak_vram} GB)")
            return response

        except (ComfyUIExecutionError, ComfyUITimeoutError, ValueError, RuntimeError) as exc:
            total_duration = time.time() - start_time
            logger.error(f"Job {job_id} failed: {exc}", exc_info=True)
            return {
                "status": "failed",
                "error": str(exc),
                "error_type": exc.__class__.__name__,
                "metrics": {
                    "total_duration_seconds": round(total_duration, 2),
                    "vram_peak_gb": get_vram_peak_gb(),
                },
            }
        except Exception as exc:
            total_duration = time.time() - start_time
            logger.error(f"Job {job_id} unexpected exception: {exc}", exc_info=True)
            return {
                "status": "failed",
                "error": f"Internal error: {str(exc)}",
                "error_type": exc.__class__.__name__,
                "metrics": {
                    "total_duration_seconds": round(total_duration, 2),
                    "vram_peak_gb": get_vram_peak_gb(),
                },
            }


if __name__ == "__main__":
    logger.info("Initializing RunPod Serverless LTX-2.5 Worker...")
    # Cold start health check verification
    try:
        report = full_health_check(workspace_dir=WORKSPACE_DIR, host=COMFY_HOST, port=COMFY_PORT)
        logger.info(f"Worker Health Report: {report['healthy']}")
    except Exception as exc:
        logger.warning(f"Initial health check failed: {exc}")

    logger.info("Starting runpod.serverless loop...")
    runpod.serverless.start({"handler": handler})
