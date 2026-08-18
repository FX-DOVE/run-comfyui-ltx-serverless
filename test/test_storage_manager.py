#!/usr/bin/env python3
"""
test_storage_manager.py - Unit test for storage manager.
"""

import sys
import unittest
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "serverless"))

from storage import StorageManager


class TestStorageManager(unittest.TestCase):
    def test_local_storage_process(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"fake video data")
            tf_path = tf.name

        try:
            sm = StorageManager(backend="local")
            file_info = {
                "path": tf_path,
                "filename": Path(tf_path).name,
                "media_type": "video",
            }
            res = sm.process_output_file(file_info, return_base64=True, upload_s3=False)
            self.assertEqual(res["filename"], Path(tf_path).name)
            self.assertEqual(res["file_size_bytes"], len(b"fake video data"))
            self.assertIn("base64", res)
            self.assertEqual(res["local_path"], tf_path)
        finally:
            Path(tf_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
