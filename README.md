# 🚀 RunPod Serverless & Interactive LTX-2.5 ComfyUI Worker

An enterprise-ready, high-performance adaptation of `run-comfyui-ltx` supporting **RunPod Serverless** inference and **Interactive Pod** sessions using persistent RunPod Network Volumes (`/workspace`).

---

## ⚡ Key Highlights

1. **Existing Network Volume Preservation**:
   - Seamlessly uses existing model weights on `/workspace/ComfyUI/models/` without redownloading.
   - Automatically skips downloads if model files (INT8 ConvRot transformer, Gemma 4 Heretic encoder, VAEs, LoRAs) exist.
   - Non-destructively synchronizes custom nodes from Docker image into `/workspace/ComfyUI/custom_nodes`.

2. **Dual Execution Modes**:
   - **`MODE=serverless`**: Starts ComfyUI as a headless daemon, launches the RunPod Serverless handler (`serverless/handler.py`), processes generation jobs via WebSocket/REST with sub-second queueing and zero sleep loops, and returns video URLs.
   - **`MODE=interactive`**: Starts ComfyUI Web UI (port 8188) and Code Server (port 9000) for interactive workflow creation, debugging, and experimentation.

3. **Event-Driven Progress & Zero Fixed Sleeps**:
   - Tracks node execution events in real time using ComfyUI WebSockets and the `/history` API.
   - Provides granular progress reporting, VRAM tracking, and timing metrics.

4. **Configurable Output Storage**:
   - `OUTPUT_BACKEND=local`: Returns local file paths and optional base64 encoded videos.
   - `OUTPUT_BACKEND=s3`: Uploads `.mp4` outputs directly to S3 / Cloudflare R2 / AWS S3 and returns presigned download URLs.

---

## 🏗️ Architecture Overview

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        RunPod Serverless Worker                        │
│                                                                        │
│   ┌──────────────────────┐         ┌───────────────────────────────┐   │
│   │   RunPod Handler     │         │       ComfyUI Engine          │   │
│   │ (serverless/handler) │ ──WS──> │ (127.0.0.1:8188 - CUDA/Torch) │   │
│   └──────────┬───────────┘         └───────────────┬───────────────┘   │
│              │                                     │                   │
│              ▼                                     ▼                   │
│   ┌──────────────────────┐         ┌───────────────────────────────┐   │
│   │    StorageManager    │         │       Network Volume          │   │
│   │ (Local / S3 Presign) │         │     (/workspace/ComfyUI)      │   │
│   └──────────────────────┘         └───────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📥 RunPod Serverless API Specification

### Endpoint Request Payload

```json
{
  "input": {
    "prompt": "A majestic golden eagle soaring over snow-covered pine mountains during golden hour, cinematic lighting, 4k photorealistic, smooth slow motion",
    "negative_prompt": "worst quality, blurry, low resolution, distorted, jitter, static",
    "width": 768,
    "height": 432,
    "frames": 49,
    "fps": 24,
    "steps": 20,
    "cfg": 3.0,
    "seed": 42,
    "use_distilled_lora": true,
    "lora_strength": 1.0,
    "upload_s3": true,
    "return_base64": false
  }
}
```

### Endpoint Response Payload

```json
{
  "status": "success",
  "prompt_id": "b1827402-2735-46f9-bbbe-e55598fa2032",
  "video_url": "https://<bucket>.s3.<region>.amazonaws.com/outputs/LTX25_T2V_00001_.mp4?X-Amz-Signature=...",
  "output_files": [
    {
      "filename": "LTX25_T2V_00001_.mp4",
      "media_type": "video",
      "file_size_bytes": 14258900,
      "local_path": "/workspace/ComfyUI/output/LTX25_T2V_00001_.mp4",
      "url": "https://..."
    }
  ],
  "metrics": {
    "total_duration_seconds": 18.42,
    "queue_duration_seconds": 0.05,
    "generation_duration_seconds": 17.85,
    "vram_peak_gb": 18.72
  },
  "params": {
    "prompt": "A majestic golden eagle...",
    "width": 768,
    "height": 432,
    "num_frames": 49,
    "fps": 24,
    "steps": 20,
    "cfg": 3.0,
    "seed": 42
  }
}
```

### Health Check Request

Send `{"input": {"health_check": true}}` to verify worker readiness, GPU VRAM, workspace mount, and model presence.

---

## 🛠️ Environment Variables

| Variable | Description | Default |
|---|---|---|
| `MODE` | Container mode: `serverless` or `interactive` | `interactive` |
| `OUTPUT_BACKEND` | Storage destination: `local` or `s3` | `local` |
| `S3_BUCKET_NAME` | S3 bucket for video uploads | Optional |
| `S3_ENDPOINT_URL` | Custom S3 endpoint (e.g. Cloudflare R2) | Optional |
| `S3_ACCESS_KEY_ID` | S3 access key ID | Optional |
| `S3_SECRET_ACCESS_KEY` | S3 secret access key | Optional |
| `PRESIGNED_URL_TTL_SECONDS` | Presigned URL expiration in seconds | `86400` (24h) |
| `JOB_TIMEOUT_SECONDS` | Max job execution timeout | `900` (15m) |

---

## 📦 Building and Deploying

```bash
# 1. Build Docker image
docker build -t <your_dockerhub_username>/run-comfyui-ltx:serverless .

# 2. Push to Docker Hub
docker push <your_dockerhub_username>/run-comfyui-ltx:serverless

# 3. Deploy RunPod Serverless Endpoint
# - Select Container Image: <your_dockerhub_username>/run-comfyui-ltx:serverless
# - Attach Network Volume: responsible_tomato_hyena_volume -> Mount to /workspace
# - Set Environment Variable: MODE=serverless
# - GPU Recommended: 24GB+ (RTX 4090 / L40S / A100)
```

---

## 🧪 Testing

Run test suites locally:
```bash
python test/test_workflow_builder.py
python test/test_serverless_handler.py
python test/test_storage_manager.py
python test/test_health_check.py
```
