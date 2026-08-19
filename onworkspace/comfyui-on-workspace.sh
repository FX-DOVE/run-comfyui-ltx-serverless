#!/bin/bash

move_with_progress() {
    local source="$1"
    local destination="$2"
    local temporary_destination="${destination}.moving"
    local total_bytes
    local copied_bytes
    local previous_bytes=-1
    local unchanged_seconds=0
    local elapsed_seconds=0
    local status_interval="${MOVE_STATUS_INTERVAL:-5}"
    local stall_timeout="${MOVE_STALL_TIMEOUT:-300}"
    local copy_pid

    total_bytes="$(du -sb "$source" | awk '{print $1}')"
    rm -rf "$temporary_destination"
    mkdir -p "$temporary_destination"

    echo "ℹ️ Moving $source to $destination"
    echo "ℹ️ Around 3.0 Gb"
    echo "ℹ️ Status interval: ${status_interval}s; stall timeout: ${stall_timeout}s"

    cp -a "$source"/. "$temporary_destination"/ &
    copy_pid=$!

    while kill -0 "$copy_pid" 2>/dev/null; do
        copied_bytes="$(du -sb "$temporary_destination" 2>/dev/null | awk '{print $1}')"
        copied_bytes="${copied_bytes:-0}"
        elapsed_seconds=$(( elapsed_seconds + status_interval ))

        if (( copied_bytes != previous_bytes )); then
            previous_bytes="$copied_bytes"
            unchanged_seconds=0
            echo "Moving ComfyUI: active after ${elapsed_seconds}s; copied approximately $(numfmt --to=iec-i --suffix=B "$copied_bytes")"
        else
            unchanged_seconds=$(( unchanged_seconds + status_interval ))
            echo "Moving ComfyUI: waiting after ${elapsed_seconds}s; no size change for ${unchanged_seconds}s"
        fi

        if (( unchanged_seconds >= stall_timeout )); then
            echo "❌ Move stalled: no size change for ${stall_timeout}s. Stopping copy."
            kill "$copy_pid" 2>/dev/null || true
            wait "$copy_pid" 2>/dev/null || true
            rm -rf "$temporary_destination"
            return 1
        fi

        sleep "$status_interval"
    done

    if ! wait "$copy_pid"; then
        echo "❌ Failed to copy $source to $destination; source was preserved."
        rm -rf "$temporary_destination"
        return 1
    fi

    mv "$temporary_destination" "$destination"
    rm -rf "$source"
    echo "✅ Move completed"
}

# Ensure we have /workspace in all scenarios
mkdir -p /workspace

if [[ -d /runpod-volume/ComfyUI && ! -d /workspace/ComfyUI ]]; then
    echo "ℹ️ [RUNPOD-VOLUME DETECTED] Linking /runpod-volume/ComfyUI to /workspace/ComfyUI"
    ln -s /runpod-volume/ComfyUI /workspace/ComfyUI
elif [[ ! -d /workspace/ComfyUI ]]; then
    move_with_progress /ComfyUI /workspace/ComfyUI || exit 1
    # Set permissions right for directory
    chmod -R 777 /workspace/ComfyUI/user 2>/dev/null || true
else
    echo "✅ [EXISTING ComfyUI DETECTED] Preserving /workspace/ComfyUI"
    if [[ -d /ComfyUI/custom_nodes && -d /workspace/ComfyUI/custom_nodes ]]; then
        echo "ℹ️ Syncing any missing custom nodes to /workspace/ComfyUI/custom_nodes (non-destructive)..."
        cp -rn /ComfyUI/custom_nodes/* /workspace/ComfyUI/custom_nodes/ 2>/dev/null || true
    fi
    rm -rf /ComfyUI
fi

# Ensure essential runtime directories exist
mkdir -p /workspace/ComfyUI/output /workspace/ComfyUI/input /workspace/ComfyUI/models
mkdir -p /workspace/ComfyUI/models/diffusion_models \
         /workspace/ComfyUI/models/text_encoders \
         /workspace/ComfyUI/models/vae \
         /workspace/ComfyUI/models/loras \
         /workspace/ComfyUI/models/model_patches \
         /workspace/ComfyUI/models/latent_upscale_models \
         /workspace/ComfyUI/models/clip \
         /workspace/ComfyUI/models/unet \
         /workspace/ComfyUI/models/checkpoints

# Remove dummy placeholder files (put_*) so ComfyUI doesn't treat them as valid models
find /workspace/ComfyUI/models -type f -name "put_*" -delete 2>/dev/null || true

if [[ "$MODE" == "serverless" ]]; then
    if [[ -d "/workspace/ComfyUI/custom_nodes/ComfyUI-Login" ]]; then
        echo "ℹ️ [MODE=serverless] Disabling ComfyUI-Login custom node to allow local API access..."
        mv "/workspace/ComfyUI/custom_nodes/ComfyUI-Login" "/workspace/ComfyUI/custom_nodes/ComfyUI-Login.disabled" 2>/dev/null || true
    fi
fi

# Linking root /ComfyUI
if [[ ! -e /ComfyUI ]]; then
    ln -s /workspace/ComfyUI /ComfyUI
fi


