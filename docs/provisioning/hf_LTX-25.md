# Manual provisioning LTX-2.5

This guide installs the complete ComfyUI chain for the LTX-2.5 22B dev
transformer with the distilled LoRA. The component list follows the
[LTX-2.5 release overview](https://comfyui-wiki.com/en/news/2026-08-11-ltx-2-5-open-weights-release)
and was verified against the
[official Lightricks model repository](https://huggingface.co/Lightricks/LTX-2.5).

The complete selected chain requires approximately 82 GB with the BF16 dev
transformer and text encoder, or approximately 51 GB with both ComfyUI
int8-convrot variants. The optional prompt enhancer adds approximately 10 GB.
These estimates do not include ComfyUI, custom nodes, or generated outputs.

## Public ungated community provisioning

```bash
hf download dummy9996/LTX-2.5-22b-ungate \
  ltx-2.5-22b-dev-transformer-bf16.safetensors \
  ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors \
  --local-dir /workspace/ComfyUI/models/diffusion_models/

hf download dummy9996/LTX-2.5-22b-ungate \
  ltx-2.5-22b-distilled-lora-450-bf16.safetensors \
  --local-dir /workspace/ComfyUI/models/loras/

hf download dummy9996/LTX-2.5-22b-ungate \
  ltx-2.5-video-vae-conv-bf16.safetensors \
  ltx-2.5-audio-vae-bf16.safetensors \
  --local-dir /workspace/ComfyUI/models/vae/

hf download dummy9996/LTX-2.5-22b-ungate \
  ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors \
  ltx-2.5-latent-temporal-upscaler-x2-bf16-1.0.safetensors \
  --local-dir /workspace/ComfyUI/models/latent_upscale_models/

hf download dummy9996/LTX-2.5-22b-ungate \
  ltx-2.5-duration-head-bf16.safetensors \
  --local-dir /workspace/ComfyUI/models/model_patches/
```

## Diffusion model

### Dev BF16

```bash
hf download Lightricks/LTX-2.5 \
  diffusion_models/ltx-2.5-22b-dev-transformer-bf16.safetensors \
  --local-dir /workspace/ComfyUI/models/diffusion_models/
```

### Dev int8-convrot for ComfyUI

```bash
hf download Lightricks/LTX-2.5 \
  diffusion_models/ltx-2.5-22b-dev-transformer-comfy-int8-convrot.safetensors \
  --local-dir /workspace/ComfyUI/models/diffusion_models/
```

## Distilled LoRA

Use this LoRA with the dev transformer. It converts the dev sampling path to
the distilled few-step behavior without replacing the dev model.

```bash
hf download Lightricks/LTX-2.5 \
  loras/ltx-2.5-22b-distilled-lora-450-bf16.safetensors \
  --local-dir /workspace/ComfyUI/models/loras/
```

## Text encoder

### BF16

```bash
hf download Lightricks/LTX-2.5 \
  text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors \
  --local-dir /workspace/ComfyUI/models/text_encoders/
```

### int8-convrot for ComfyUI

```bash
hf download Lightricks/LTX-2.5 \
  text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors \
  --local-dir /workspace/ComfyUI/models/text_encoders/
```

### Community Heretic encoders

T#### Heretic BF16

```bash
hf download \
  DeepNeuralNerd/Gemma-4-12B-it-uncensored-heretic-DeepNeuralNerd-LTX_2.5_ComfyUI \
  "Gemma-4-12B-it-uncensored-heretic - DeepNeuralNerd -LTX 2.5-ComfyUI-bf16.safetensors" \
  --local-dir /workspace/ComfyUI/models/text_encoders/
```

#### Heretic int8-convrot

```bash
hf download \
  DeepNeuralNerd/Gemma-4-12B-it-uncensored-heretic-DeepNeuralNerd-LTX_2.5_ComfyUI \
  "Gemma-4-12B-it-uncensored-heretic - DeepNeuralNerd -LTX 2.5-ComfyUI-int8convrot.safetensors" \
  --local-dir /workspace/ComfyUI/models/text_encoders/
```

### Prompt enhancer

The prompt enhancer is optional, but it is included in the full RunPod profile.

```bash
hf download Comfy-Org/gemma-4 \
  text_encoders/gemma4_e2b_it_bf16.safetensors \
  --local-dir /workspace/ComfyUI/models/text_encoders/
```

## Video and audio VAEs

### Diffusion video decoder

Higher quality and heavier than the convolutional decoder.

```bash
hf download Lightricks/LTX-2.5 \
  vae/ltx-2.5-video-vae-bf16.safetensors \
  --local-dir /workspace/ComfyUI/models/vae/
```

### Convolutional video decoder

Faster and lighter at inference time. The complete RunPod profile downloads
both video decoders so either workflow variant can be selected.

```bash
hf download Lightricks/LTX-2.5 \
  vae/ltx-2.5-video-vae-conv-bf16.safetensors \
  --local-dir /workspace/ComfyUI/models/vae/
```

### Audio VAE and vocoder

```bash
hf download Lightricks/LTX-2.5 \
  vae/ltx-2.5-audio-vae-bf16.safetensors \
  --local-dir /workspace/ComfyUI/models/vae/
```

## Latent upscalers

### Spatial 2x

```bash
hf download Lightricks/LTX-2.5 \
  latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors \
  --local-dir /workspace/ComfyUI/models/latent_upscale_models/
```

### Temporal 2x

```bash
hf download Lightricks/LTX-2.5 \
  latent_upscale_models/ltx-2.5-latent-temporal-upscaler-x2-bf16-1.0.safetensors \
  --local-dir /workspace/ComfyUI/models/latent_upscale_models/
```

## Duration-head patch

```bash
hf download Lightricks/LTX-2.5 \
  model_patches/ltx-2.5-duration-head-bf16.safetensors \
  --local-dir /workspace/ComfyUI/models/model_patches/
```
