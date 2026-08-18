#!/usr/bin/env python3
"""
test_health_check.py - Unit test for model detection and health checks.
"""

import os
import sys
import unittest
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "serverless"))

from health import check_models, check_workspace


class TestHealthCheck(unittest.TestCase):
    def test_mock_workspace_model_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir) / "ComfyUI" / "models"
            (models_dir / "diffusion_models").mkdir(parents=True)
            (models_dir / "text_encoders").mkdir(parents=True)
            (models_dir / "vae").mkdir(parents=True)

            # Create mock model files
            diff_file = models_dir / "diffusion_models" / "ltx-2.5-22b-dev-transformer-comfy-int8-convrot.safetensors"
            diff_file.write_bytes(b"0" * 1024)

            text_file = models_dir / "text_encoders" / "Gemma-4-12B-it-uncensored-heretic - DeepNeuralNerd -LTX 2.5-ComfyUI-int8convrot.safetensors"
            text_file.write_bytes(b"0" * 1024)

            vae_file = models_dir / "vae" / "ltx-2.5-video-vae-conv-bf16.safetensors"
            vae_file.write_bytes(b"0" * 1024)

            res = check_models(str(models_dir))
            self.assertTrue(res["all_required_present"])
            self.assertTrue(res["required"]["diffusion_models"]["present"])
            self.assertTrue(res["required"]["text_encoders"]["present"])
            self.assertTrue(res["required"]["vae"]["present"])


if __name__ == "__main__":
    unittest.main()
