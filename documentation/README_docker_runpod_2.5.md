# Run LTX-2.5 with ComfyUI provisioning on RunPod

This image runs ComfyUI 0.32.0+ with native LTX-2.5 support. Models, LoRAs,
VAEs, text encoders, upscalers, patches, and workflows can be provisioned at
pod startup through environment variables.

## Features

- Complete LTX-2.x chain
- Automatic BF16 or ComfyUI int8-convrot transformer selection by GPU VRAM.
- Community Heretic BF16 and int8-convrot text encoder profiles.
- Video and audio VAEs, spatial and temporal latent upscalers, and duration
  head patch.
- CUDA 12.8 runtime with compiled attention and GPU acceleration packages.
- ComfyUI, Code Server, SSH, LoRA Manager, Hugging Face, and CivitAI support.

## RunPod deployment

### Template

- [**👉 One-click Deploy on RunPod LTX-2.5 i2v/t2v vi2v/vt2v dev bf16/int8 convrot**](https://console.runpod.io/deploy?template=ka3hvli4kf&ref=se4tkc5o)
- [**👉 One-click Deploy on RunPod LTX-2.3 i2v/t2v vi2v/vt2v dev bf16/fp8**](https://console.runpod.io/deploy?template=p4f6rm9tb4&ref=se4tkc5o)

## GPU and precision selection

The supplied profiles use `VRAM_THRESHOLD=48`. The startup script selects the
HVRAM model only when detected VRAM is greater than this value. GPUs at or
below the threshold receive the int8-convrot transformer.

| Typical GPU | VRAM | Transformer selected | Recommended text encoder |
|-------------|------|----------------------|--------------------------|
| RTX 3090 / RTX 4090 | 24 GB | int8-convrot | Heretic |
| RTX 5090 | 32 GB | int8-convrot | Heretic |
| L40S | 48 GB nominal | int8-convrot | Heretic |
| RTX PRO 6000 Blackwell | 96 GB | BF16 | Heretic |

## Storage requirements

The complete selected chain requires approximately:

| Profile components | Model storage |
|--------------------|---------------|
| BF16 dev transformer and BF16 text encoder | 82 GB |
| int8-convrot dev transformer and text encoder | 51 GB |
| Optional prompt enhancer | additional 10 GB |

Reserve additional `/workspace` capacity for ComfyUI, custom nodes, caches,
input media, and generated videos. A persistent volume of at least 120 GB is a
practical starting point; larger video jobs can require substantially more.

## Documentation

- [Start](https://comfyui.rozenlaan.site/ComfyUI_LTX/)
- [Tutorial](https://comfyui.rozenlaan.site/ComfyUI_LTX_tutorial/)

## Other pods

- [WAN](https://comfyui.rozenlaan.site/ComfyUI_WAN/)
- [Image models](https://comfyui.rozenlaan.site/ComfyUI_image/)
- [MiniMax](https://comfyui.rozenlaan.site/ComfyUI_MiniMax/)
