#!/usr/bin/env python3
"""
comfy_client.py - ComfyUI WebSocket & REST API Client.
Provides synchronous and asynchronous queueing, tracking, and retrieval of generated assets.
NO fixed sleeps - event-driven through WebSocket and history polling.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import requests

try:
    import websocket
except ImportError:
    websocket = None

logger = logging.getLogger("comfy_client")


class ComfyUIExecutionError(Exception):
    """Raised when ComfyUI encounters an error during node execution."""
    pass


class ComfyUITimeoutError(Exception):
    """Raised when ComfyUI execution exceeds the specified timeout."""
    pass


class ComfyClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8188,
        client_id: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id or str(uuid.uuid4())
        self.base_url = f"http://{self.host}:{self.port}"
        self.ws_url = f"ws://{self.host}:{self.port}/ws?clientId={self.client_id}"

    def is_ready(self, timeout_seconds: int = 120, poll_interval: float = 2.0) -> bool:
        """Wait until ComfyUI HTTP server is responsive."""
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            for ep in ("/system_stats", "/prompt", "/history", ""):
                try:
                    resp = requests.get(f"{self.base_url}{ep}", timeout=2)
                    if resp.status_code in (200, 302, 307):
                        return True
                except Exception:
                    pass
            time.sleep(poll_interval)
        return False

    def get_system_stats(self) -> dict:
        """Fetch system statistics, GPU VRAM info, and device mappings."""
        resp = requests.get(f"{self.base_url}/system_stats", timeout=5)
        resp.raise_for_status()
        return resp.json()

    def queue_prompt(self, workflow_prompt: dict) -> str:
        """Submit a workflow prompt JSON to ComfyUI and return the prompt_id."""
        payload = {
            "prompt": workflow_prompt,
            "client_id": self.client_id,
        }
        resp = requests.post(
            f"{self.base_url}/prompt",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to queue prompt: HTTP {resp.status_code} - {resp.text}"
            )
        data = resp.json()
        if "prompt_id" not in data:
            raise RuntimeError(f"ComfyUI did not return prompt_id: {data}")
        return data["prompt_id"]

    def interrupt(self) -> None:
        """Interrupt current execution."""
        try:
            requests.post(f"{self.base_url}/interrupt", timeout=2)
        except Exception as exc:
            logger.warning(f"Failed to send interrupt to ComfyUI: {exc}")

    def track_execution(
        self,
        prompt_id: str,
        timeout_seconds: int = 600,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict:
        """
        Track execution of a prompt via WebSocket with graceful fallback to REST polling.
        Returns the execution history entry for the prompt_id.
        """
        start_time = time.time()

        if websocket is not None:
            try:
                return self._track_via_websocket(
                    prompt_id, timeout_seconds, on_progress, start_time
                )
            except Exception as ws_err:
                logger.warning(
                    f"WebSocket tracking encountered issue: {ws_err}. Falling back to REST polling."
                )

        return self._track_via_polling(
            prompt_id, timeout_seconds, on_progress, start_time
        )

    def _track_via_websocket(
        self,
        prompt_id: str,
        timeout_seconds: int,
        on_progress: Optional[Callable[[int, int, str], None]],
        start_time: float,
    ) -> dict:
        ws = websocket.create_connection(self.ws_url, timeout=10)
        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    raise ComfyUITimeoutError(
                        f"Execution timed out after {timeout_seconds}s"
                    )

                ws.settimeout(max(1.0, timeout_seconds - elapsed))
                try:
                    raw_msg = ws.recv()
                except (websocket.WebSocketTimeoutException, TimeoutError):
                    # Check history in case message was missed
                    history = self.get_history(prompt_id)
                    if prompt_id in history:
                        return history[prompt_id]
                    continue

                if not isinstance(raw_msg, str):
                    # Binary preview data (e.g. latent previews)
                    continue

                msg = json.loads(raw_msg)
                msg_type = msg.get("type")
                msg_data = msg.get("data", {})

                if msg_type == "progress":
                    val = msg_data.get("value", 0)
                    max_val = msg_data.get("max", 1)
                    node = msg_data.get("node", "")
                    if on_progress:
                        on_progress(val, max_val, node)

                elif msg_type == "executing":
                    node = msg_data.get("node")
                    p_id = msg_data.get("prompt_id")
                    if p_id == prompt_id and node is None:
                        # Execution complete!
                        history = self.get_history(prompt_id)
                        if prompt_id in history:
                            return history[prompt_id]
                        # Wait briefly for history flush
                        time.sleep(0.5)
                        history = self.get_history(prompt_id)
                        if prompt_id in history:
                            return history[prompt_id]

                elif msg_type == "execution_error":
                    p_id = msg_data.get("prompt_id")
                    if p_id == prompt_id:
                        node_id = msg_data.get("node_id")
                        node_type = msg_data.get("node_type")
                        err_msg = msg_data.get("exception_message")
                        traceback_str = "".join(msg_data.get("traceback", []))
                        raise ComfyUIExecutionError(
                            f"Execution error on node {node_id} ({node_type}): {err_msg}\n{traceback_str}"
                        )
        finally:
            try:
                ws.close()
            except Exception:
                pass

    def _track_via_polling(
        self,
        prompt_id: str,
        timeout_seconds: int,
        on_progress: Optional[Callable[[int, int, str], None]],
        start_time: float,
    ) -> dict:
        poll_interval = 1.0
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                raise ComfyUITimeoutError(
                    f"Execution timed out after {timeout_seconds}s"
                )

            history = self.get_history(prompt_id)
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    messages = status.get("messages", [])
                    raise ComfyUIExecutionError(f"Workflow execution error: {messages}")
                return entry

            time.sleep(poll_interval)

    def get_history(self, prompt_id: Optional[str] = None) -> dict:
        """Fetch history for a specific prompt_id or all history."""
        url = (
            f"{self.base_url}/history/{prompt_id}"
            if prompt_id
            else f"{self.base_url}/history"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def extract_output_files(
        self, history_entry: dict, output_dir: str = "/workspace/ComfyUI/output"
    ) -> List[Dict[str, Any]]:
        """
        Inspect history outputs to find generated media files on disk.
        Returns list of dicts with keys: 'path', 'filename', 'type', 'subfolder'.
        """
        output_files = []
        outputs = history_entry.get("outputs", {})
        base_out = Path(output_dir)

        for node_id, node_outputs in outputs.items():
            # Check videos (VHS_VideoCombine, etc.)
            for media_key in ["videos", "gifs", "images"]:
                if media_key in node_outputs:
                    for item in node_outputs[media_key]:
                        filename = item.get("filename")
                        subfolder = item.get("subfolder", "")
                        item_type = item.get("type", "output")
                        
                        if filename:
                            full_path = (
                                base_out / subfolder / filename
                                if subfolder
                                else base_out / filename
                            )
                            output_files.append({
                                "node_id": node_id,
                                "filename": filename,
                                "subfolder": subfolder,
                                "type": item_type,
                                "media_type": media_key[:-1] if media_key.endswith("s") else media_key,
                                "path": str(full_path),
                                "exists": full_path.exists(),
                                "size_bytes": full_path.stat().st_size if full_path.exists() else 0,
                            })

        return output_files
