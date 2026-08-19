#!/usr/bin/env python3
"""
workflow.py - LTX-2.5 ComfyUI Workflow Generator & Builder.
Constructs executable API-format prompt payloads tailored for LTX-2.5 INT8/BF16 models.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("workflow")

DEFAULT_DIFFUSION_MODEL = "ltx-2.5-22b-dev-transformer-comfy-int8-convrot.safetensors"
DEFAULT_TEXT_ENCODER = (
    "Gemma-4-12B-it-uncensored-heretic - DeepNeuralNerd -LTX 2.5-ComfyUI-int8convrot.safetensors"
)
DEFAULT_VAE = "ltx-2.5-video-vae-conv-bf16.safetensors"
DEFAULT_LORA = "ltx-2.5-22b-distilled-lora-450-bf16.safetensors"


def find_existing_model_name(category: str, preferred: str, models_dir: str = "/workspace/ComfyUI/models") -> str:
    """
    Check if the preferred model exists, or pick the best available in the category directory.
    Searches across all possible volume mount paths and category aliases, ignoring dummy placeholder files.
    """
    category_aliases = {
        "diffusion_models": ["diffusion_models", "unet", "checkpoints"],
        "text_encoders": ["text_encoders", "clip"],
        "vae": ["vae"],
        "loras": ["loras", "lora"],
        "model_patches": ["model_patches"],
        "latent_upscale_models": ["latent_upscale_models"],
    }
    
    aliases = category_aliases.get(category, [category])
    
    # Candidate base directories
    base_dirs = [
        Path(models_dir),
        Path("/workspace/ComfyUI/models"),
        Path("/runpod-volume/ComfyUI/models"),
        Path("/workspace/models"),
        Path("/runpod-volume/models"),
        Path("/ComfyUI/models"),
    ]
    
    # 1. Check if preferred exists in any candidate location
    for base in base_dirs:
        for alias in aliases:
            p = base / alias / preferred
            if p.exists() and p.is_file() and not p.name.startswith("put_"):
                return preferred

    # 2. Search for valid model files (*.safetensors, *.ckpt, *.pt, *.bin)
    candidate_files = []
    for base in base_dirs:
        for alias in aliases:
            cat_dir = base / alias
            if cat_dir.exists() and cat_dir.is_dir():
                for f in cat_dir.iterdir():
                    if (
                        f.is_file()
                        and not f.name.startswith("put_")
                        and not f.name.startswith(".")
                        and f.suffix.lower() in (".safetensors", ".ckpt", ".pt", ".bin", ".gguf")
                    ):
                        candidate_files.append(f.name)

    if candidate_files:
        # Prioritize files with matching keywords
        for f in candidate_files:
            if "ltx" in f.lower() or "gemma" in f.lower():
                return f
        return candidate_files[0]

    return preferred


def build_ltx25_t2v_workflow(
    prompt: str,
    negative_prompt: str = "worst quality, inconsistent motion, blurry, low resolution, artifacts, distorted, jitter",
    width: int = 768,
    height: int = 432,
    num_frames: int = 49,
    fps: int = 24,
    seed: Optional[int] = None,
    steps: int = 20,
    cfg: float = 3.0,
    sampler_name: str = "euler",
    scheduler: str = "simple",
    use_distilled_lora: bool = True,
    lora_strength: float = 1.0,
    models_dir: str = "/workspace/ComfyUI/models",
) -> Dict[str, Any]:
    """
    Build a standard LTX-2.5 Text-to-Video ComfyUI API prompt dictionary.
    """
    if seed is None or seed < 0:
        seed = random.randint(1, 2**63 - 1)

    # Resolution rounding to multiple of 32 for video latent compatibility
    width = (width // 32) * 32
    height = (height // 32) * 32

    # Frame count validation (LTX-2.5 standard is typically 8k + 1, e.g. 49, 97, 121)
    if num_frames < 1:
        num_frames = 49

    diffusion_model = find_existing_model_name("diffusion_models", DEFAULT_DIFFUSION_MODEL, models_dir)
    text_encoder = find_existing_model_name("text_encoders", DEFAULT_TEXT_ENCODER, models_dir)
    vae_model = find_existing_model_name("vae", DEFAULT_VAE, models_dir)
    lora_model = find_existing_model_name("loras", DEFAULT_LORA, models_dir)

    workflow: Dict[str, Any] = {
        # 1. Load UNET (LTX-2.5 Transformer)
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": diffusion_model,
                "weight_dtype": "default"
            }
        },
        # 2. Load Text Encoder (Gemma Heretic)
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": text_encoder,
                "type": "ltxv"
            }
        },
        # 3. Load VAE
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": vae_model
            }
        },
    }

    current_model_node = "1"

    # 4. Optional Distilled LoRA
    if use_distilled_lora:
        workflow["4"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": [current_model_node, 0],
                "lora_name": lora_model,
                "strength_model": lora_strength
            }
        }
        current_model_node = "4"

    # 5. Positive Prompt
    workflow["5"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["2", 0],
            "text": prompt
        }
    }

    # 6. Negative Prompt
    workflow["6"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["2", 0],
            "text": negative_prompt
        }
    }

    # 7. Empty Latent Video
    workflow["7"] = {
        "class_type": "EmptyLTXVLatentVideo",
        "inputs": {
            "width": width,
            "height": height,
            "length": num_frames,
            "batch_size": 1
        }
    }

    # 8. KSampler
    workflow["8"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": [current_model_node, 0],
            "positive": ["5", 0],
            "negative": ["6", 0],
            "latent_image": ["7", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "denoise": 1.0
        }
    }

    # 9. VAE Decode
    workflow["9"] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["8", 0],
            "vae": ["3", 0]
        }
    }

    # 10. Video Combine (VHS Video Helper Suite)
    workflow["10"] = {
        "class_type": "VHS_VideoCombine",
        "inputs": {
            "images": ["9", 0],
            "frame_rate": fps,
            "loop_count": 0,
            "filename_prefix": "LTX25_T2V",
            "format": "video/h264-mp4",
            "pingpong": False,
            "save_output": True,
            "pix_fmt": "yuv420p",
            "crf": 19
        }
    }

    return workflow


def load_custom_workflow_from_file(
    file_path: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Load a custom ComfyUI API workflow JSON and inject user parameters."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Workflow template file not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # Dynamic replacement helper
    for node_id, node_data in workflow.items():
        inputs = node_data.get("inputs", {})
        node_class = node_data.get("class_type", "")

        if node_class == "CLIPTextEncode":
            if "prompt" in params and inputs.get("text") == "__PROMPT__":
                inputs["text"] = params["prompt"]
            elif "negative_prompt" in params and inputs.get("text") == "__NEGATIVE_PROMPT__":
                inputs["text"] = params["negative_prompt"]

        elif node_class in ("KSampler", "KSamplerAdvanced"):
            if "seed" in params:
                inputs["seed"] = params["seed"]
            if "steps" in params:
                inputs["steps"] = params["steps"]
            if "cfg" in params:
                inputs["cfg"] = params["cfg"]

        elif node_class == "EmptyLTXVLatentVideo":
            if "width" in params:
                inputs["width"] = (params["width"] // 32) * 32
            if "height" in params:
                inputs["height"] = (params["height"] // 32) * 32
            if "num_frames" in params or "length" in params:
                inputs["length"] = params.get("num_frames", params.get("length", 49))

        elif node_class == "VHS_VideoCombine":
            if "fps" in params or "frame_rate" in params:
                inputs["frame_rate"] = params.get("fps", params.get("frame_rate", 24))

    return workflow
