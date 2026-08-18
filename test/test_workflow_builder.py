#!/usr/bin/env python3
"""
test_workflow_builder.py - Unit test for LTX-2.5 ComfyUI workflow generation.
"""

import os
import sys
import unittest
from pathlib import Path

# Add serverless module to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "serverless"))

from workflow import build_ltx25_t2v_workflow, find_existing_model_name


class TestWorkflowBuilder(unittest.TestCase):
    def test_workflow_structure(self):
        wf = build_ltx25_t2v_workflow(
            prompt="A cinematic drone shot over snow-capped mountains",
            negative_prompt="blurry, low quality",
            width=768,
            height=432,
            num_frames=49,
            fps=24,
            seed=12345,
            steps=20,
            cfg=3.0,
            use_distilled_lora=True,
            lora_strength=1.0,
            models_dir="/tmp/dummy_models",
        )

        self.assertIn("1", wf)  # UNETLoader
        self.assertEqual(wf["1"]["class_type"], "UNETLoader")
        self.assertIn("2", wf)  # CLIPLoader
        self.assertEqual(wf["2"]["class_type"], "CLIPLoader")
        self.assertEqual(wf["2"]["inputs"]["type"], "ltxv")
        self.assertIn("3", wf)  # VAELoader
        self.assertEqual(wf["3"]["class_type"], "VAELoader")
        self.assertIn("4", wf)  # LoraLoaderModelOnly
        self.assertEqual(wf["4"]["class_type"], "LoraLoaderModelOnly")
        self.assertIn("5", wf)  # CLIPTextEncode (pos)
        self.assertEqual(wf["5"]["inputs"]["text"], "A cinematic drone shot over snow-capped mountains")
        self.assertIn("6", wf)  # CLIPTextEncode (neg)
        self.assertEqual(wf["6"]["inputs"]["text"], "blurry, low quality")
        self.assertIn("7", wf)  # EmptyLTXVLatentVideo
        self.assertEqual(wf["7"]["inputs"]["width"], 768)
        self.assertEqual(wf["7"]["inputs"]["height"], 416)  # Rounded to 32 multiple
        self.assertEqual(wf["7"]["inputs"]["length"], 49)
        self.assertIn("8", wf)  # KSampler
        self.assertEqual(wf["8"]["inputs"]["steps"], 20)
        self.assertEqual(wf["8"]["inputs"]["cfg"], 3.0)
        self.assertEqual(wf["8"]["inputs"]["seed"], 12345)
        self.assertIn("9", wf)  # VAEDecode
        self.assertIn("10", wf)  # VHS_VideoCombine
        self.assertEqual(wf["10"]["inputs"]["frame_rate"], 24)

    def test_resolution_rounding(self):
        wf = build_ltx25_t2v_workflow(
            prompt="test",
            width=750,
            height=450,
            models_dir="/tmp/dummy_models",
        )
        # 750 // 32 * 32 = 736, 450 // 32 * 32 = 448
        self.assertEqual(wf["7"]["inputs"]["width"], 736)
        self.assertEqual(wf["7"]["inputs"]["height"], 448)


if __name__ == "__main__":
    unittest.main()
