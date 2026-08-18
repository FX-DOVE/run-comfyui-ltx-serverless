#!/usr/bin/env python3
"""
health.py - Health check module for RunPod Serverless LTX-2.5 ComfyUI worker.
Verifies GPU, VRAM, /workspace FUSE mount, ComfyUI API, and required model files.
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
import requests

logger = logging.getLogger("health")

REQUIRED_MODELS = [
    {
        "category": "diffusion_models",
        "primary": "ltx-2.5-22b-dev-transformer-comfy-int8-convrot.safetensors",
        "alternatives": [
            "ltx-2.5-22b-dev-transformer-bf16.safetensors",
            "ltx-2.5-22b-dev-transformer-fp8.safetensors",
        ],
        "min_size_gb": 15.0,
    },
    {
        "category": "text_encoders",
        "primary": "Gemma-4-12B-it-uncensored-heretic - DeepNeuralNerd -LTX 2.5-ComfyUI-int8convrot.safetensors",
        "alternatives": [
            "Gemma-4-12B-it-uncensored-heretic - DeepNeuralNerd -LTX 2.5-ComfyUI-bf16.safetensors",
            "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
            "gemma4-12b-with-proj-ltx-2.5-bf16.safetensors",
        ],
        "min_size_gb": 10.0,
    },
    {
        "category": "vae",
        "primary": "ltx-2.5-video-vae-conv-bf16.safetensors",
        "alternatives": [
            "ltx-2.5-video-vae-bf16.safetensors",
        ],
        "min_size_mb": 100.0,
    },
]

OPTIONAL_MODELS = [
    {
        "category": "loras",
        "filename": "ltx-2.5-22b-distilled-lora-450-bf16.safetensors",
    },
    {
        "category": "model_patches",
        "filename": "ltx-2.5-duration-head-bf16.safetensors",
    },
    {
        "category": "latent_upscale_models",
        "filename": "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors",
    },
    {
        "category": "latent_upscale_models",
        "filename": "ltx-2.5-latent-temporal-upscaler-x2-bf16-1.0.safetensors",
    },
]


def check_gpu() -> dict:
    gpu_info = {
        "available": False,
        "device_count": 0,
        "device_name": "None",
        "total_vram_gb": 0.0,
        "cuda_version": "None",
    }
    try:
        import torch

        if torch.cuda.is_available():
            gpu_info["available"] = True
            gpu_info["device_count"] = torch.cuda.device_count()
            gpu_info["device_name"] = torch.cuda.get_device_name(0)
            total_bytes = torch.cuda.get_device_properties(0).total_memory
            gpu_info["total_vram_gb"] = round(total_bytes / (1024**3), 2)
            gpu_info["cuda_version"] = torch.version.cuda or "unknown"
    except Exception as exc:
        logger.error(f"Error checking GPU via PyTorch: {exc}")

    return gpu_info


def check_workspace(workspace_dir: str = "/workspace") -> dict:
    ws_path = Path(workspace_dir)
    comfy_path = ws_path / "ComfyUI"
    models_path = comfy_path / "models"

    return {
        "workspace_exists": ws_path.exists(),
        "workspace_is_dir": ws_path.is_dir(),
        "comfyui_exists": comfy_path.exists(),
        "comfyui_models_dir": models_path.exists(),
    }


def check_models(models_dir: str = "/workspace/ComfyUI/models") -> dict:
    base = Path(models_dir)
    results = {"required": {}, "optional": {}, "all_required_present": True}

    if not base.exists():
        results["all_required_present"] = False
        results["error"] = f"Models base directory not found: {models_dir}"
        return results

    for req in REQUIRED_MODELS:
        cat = req["category"]
        primary = req["primary"]
        alts = req.get("alternatives", [])
        found_file = None
        found_size_bytes = 0

        # Check primary
        p_path = base / cat / primary
        if p_path.exists() and p_path.is_file():
            found_file = primary
            found_size_bytes = p_path.stat().st_size
        else:
            # Check alternatives
            for alt in alts:
                alt_path = base / cat / alt
                if alt_path.exists() and alt_path.is_file():
                    found_file = alt
                    found_size_bytes = alt_path.stat().st_size
                    break

        is_ok = found_file is not None
        if not is_ok:
            results["all_required_present"] = False

        results["required"][cat] = {
            "expected_primary": primary,
            "found_file": found_file,
            "size_gb": round(found_size_bytes / (1024**3), 2) if found_file else 0.0,
            "present": is_ok,
        }

    for opt in OPTIONAL_MODELS:
        cat = opt["category"]
        fname = opt["filename"]
        opt_path = base / cat / fname
        present = opt_path.exists() and opt_path.is_file()
        size_mb = round(opt_path.stat().st_size / (1024**2), 2) if present else 0.0
        results["optional"][f"{cat}/{fname}"] = {
            "present": present,
            "size_mb": size_mb,
        }

    return results


def check_comfyui_api(host: str = "127.0.0.1", port: int = 8188) -> dict:
    url = f"http://{host}:{port}/system_stats"
    api_info = {"online": False, "system_stats": None, "error": None}
    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            api_info["online"] = True
            api_info["system_stats"] = resp.json()
        else:
            api_info["error"] = f"Unexpected status code: {resp.status_code}"
    except Exception as exc:
        api_info["error"] = str(exc)

    return api_info


def full_health_check(
    workspace_dir: str = "/workspace", host: str = "127.0.0.1", port: int = 8188
) -> dict:
    gpu = check_gpu()
    ws = check_workspace(workspace_dir)
    models = check_models(f"{workspace_dir}/ComfyUI/models")
    api = check_comfyui_api(host, port)

    healthy = (
        ws["comfyui_models_dir"]
        and models["all_required_present"]
        and api["online"]
    )

    return {
        "healthy": healthy,
        "gpu": gpu,
        "workspace": ws,
        "models": models,
        "comfyui_api": api,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ws_arg = sys.argv[1] if len(sys.argv) > 1 else "/workspace"
    report = full_health_check(workspace_dir=ws_arg)
    import json

    print(json.dumps(report, indent=2))
    sys.exit(0 if report["healthy"] else 1)
