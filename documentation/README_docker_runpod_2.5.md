# Run LTX-2.5 with ComfyUI provisioning on RunPod

This image runs ComfyUI 0.32.0+ with native LTX-2.5 support. Models, LoRAs,
VAEs, text encoders, upscalers, patches, and workflows can be provisioned at
pod startup through environment variables.

## Features

- Complete LTX-2.x chain
- Public ungated LTX-2.5 model chain from `comfyicu/LTX-2.5`.
- Community Heretic BF16 and int8-convrot text encoder profiles.
- Video and audio VAEs, spatial and temporal latent upscalers, and duration
  head patch.
- CUDA 12.8 runtime with compiled attention and GPU acceleration packages.
- ComfyUI, Code Server, SSH, LoRA Manager, Hugging Face, and CivitAI support.

## RunPod deployment

### Template

- [**👉 One-click Deploy on RunPod LTX-2.5 i2v/t2v vi2v/vt2v dev INT8 ConvRot**](https://console.runpod.io/deploy?template=ka3hvli4kf&ref=se4tkc5o)
- [**👉 One-click Deploy on RunPod LTX-2.3 i2v/t2v vi2v/vt2v dev bf16/fp8**](https://console.runpod.io/deploy?template=p4f6rm9tb4&ref=se4tkc5o)

## GPU and precision selection

The supplied profiles use `VRAM_THRESHOLD=40`. The startup script selects the
HVRAM model set when detected VRAM is greater than this value, so an L40S uses
the HVRAM profile. Both model sets use the comfyicu Dev INT8 ConvRot
transformer. The selection changes only the Heretic text encoder from INT8
ConvRot to BF16.

| Typical GPU | VRAM | Model set | Transformer | Heretic text encoder |
|-------------|------|-----------|-------------|----------------------|
| RTX 3090 / RTX 4090 | 24 GB | LVRAM | comfyicu Dev INT8 ConvRot | INT8 ConvRot |
| RTX 5090 | 32 GB | LVRAM | comfyicu Dev INT8 ConvRot | INT8 ConvRot |
| L40S | 48 GB nominal | HVRAM | comfyicu Dev INT8 ConvRot | BF16 |
| RTX PRO 6000 Blackwell | 96 GB | HVRAM | comfyicu Dev INT8 ConvRot | BF16 |

Every public ungated LTX-2.5 model component comes from
[`comfyicu/LTX-2.5`](https://huggingface.co/comfyicu/LTX-2.5). The uncensored
Heretic BF16 and INT8 ConvRot text encoders remain sourced from
`DeepNeuralNerd`. The private profile requires access to `Lightricks/LTX-2.5`
and a Hugging Face token.

## Storage requirements

The complete selected chain requires approximately:

| Profile components | Model storage guidance |
|--------------------|------------------------|
| Public Dev INT8 ConvRot with Heretic encoder | Allow at least 60 GB |
| Optional prompt enhancer | Additional 10 GB |

Reserve additional `/workspace` capacity for ComfyUI, custom nodes, caches,
input media, and generated videos. A persistent volume of at least 80 GB is a
practical starting point; larger video jobs can require substantially more.

## Documentation

- [Start](https://comfyui.rozenlaan.site/ComfyUI_LTX/)
- [Tutorial](https://comfyui.rozenlaan.site/ComfyUI_LTX_tutorial/)

## Other pods

- [WAN](https://comfyui.rozenlaan.site/ComfyUI_WAN/)
- [Image models](https://comfyui.rozenlaan.site/ComfyUI_image/)
- [MiniMax](https://comfyui.rozenlaan.site/ComfyUI_MiniMax/)
