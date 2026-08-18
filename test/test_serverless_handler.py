#!/usr/bin/env python3
"""
test_serverless_handler.py - Unit test for input validation and handler logic.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "serverless"))

from handler import validate_and_parse_input


class TestServerlessHandler(unittest.TestCase):
    def test_valid_input(self):
        job_input = {
            "prompt": "An astronaut walking on Mars at sunset",
            "negative_prompt": "blurry, dark",
            "width": 768,
            "height": 432,
            "frames": 49,
            "fps": 24,
            "steps": 25,
            "cfg": 3.5,
            "seed": 9999,
            "return_base64": True,
        }
        parsed = validate_and_parse_input(job_input)
        self.assertEqual(parsed["prompt"], "An astronaut walking on Mars at sunset")
        self.assertEqual(parsed["negative_prompt"], "blurry, dark")
        self.assertEqual(parsed["width"], 768)
        self.assertEqual(parsed["height"], 432)
        self.assertEqual(parsed["num_frames"], 49)
        self.assertEqual(parsed["fps"], 24)
        self.assertEqual(parsed["steps"], 25)
        self.assertEqual(parsed["cfg"], 3.5)
        self.assertEqual(parsed["seed"], 9999)
        self.assertTrue(parsed["return_base64"])

    def test_missing_prompt(self):
        with self.assertRaises(ValueError):
            validate_and_parse_input({"prompt": ""})
        with self.assertRaises(ValueError):
            validate_and_parse_input({})

    def test_clamping_bounds(self):
        job_input = {
            "prompt": "test",
            "width": 5000,
            "height": 100,
            "frames": 1000,
            "steps": 500,
            "cfg": 50.0,
        }
        parsed = validate_and_parse_input(job_input)
        self.assertEqual(parsed["width"], 1920)
        self.assertEqual(parsed["height"], 256)
        self.assertEqual(parsed["num_frames"], 257)
        self.assertEqual(parsed["steps"], 100)
        self.assertEqual(parsed["cfg"], 20.0)


if __name__ == "__main__":
    unittest.main()
