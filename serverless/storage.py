#!/usr/bin/env python3
"""
storage.py - Storage & Asset Management for RunPod Serverless LTX-2.5.
Supports Local disk returns, S3 / Cloudflare R2 / AWS S3 upload with presigned URLs, and base64.
"""

from __future__ import annotations

import base64
import logging
import os
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("storage")


class StorageManager:
    def __init__(
        self,
        backend: Optional[str] = None,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        presigned_ttl: int = 86400,
    ):
        self.backend = (backend or os.getenv("OUTPUT_BACKEND", "local")).lower()
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME") or os.getenv("BUCKET_NAME")
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL") or os.getenv("ENDPOINT_URL")
        self.region_name = region_name or os.getenv("S3_REGION_NAME") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.access_key_id = (
            access_key_id
            or os.getenv("S3_ACCESS_KEY_ID")
            or os.getenv("AWS_ACCESS_KEY_ID")
            or os.getenv("RUNPOD_S3_ACCESS_KEY_ID")
        )
        self.secret_access_key = (
            secret_access_key
            or os.getenv("S3_SECRET_ACCESS_KEY")
            or os.getenv("AWS_SECRET_ACCESS_KEY")
            or os.getenv("RUNPOD_S3_SECRET_ACCESS_KEY")
        )
        self.presigned_ttl = int(os.getenv("PRESIGNED_URL_TTL_SECONDS", str(presigned_ttl)))
        self._s3_client = None

    def _get_s3_client(self):
        if self._s3_client is None:
            try:
                import boto3
                from botocore.config import Config

                config = Config(signature_version="s3v4", s3={"addressing_style": "path"})
                self._s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    region_name=self.region_name,
                    config=config,
                )
            except Exception as exc:
                logger.error(f"Failed to initialize S3 client: {exc}")
                raise
        return self._s3_client

    def upload_to_s3(self, local_path: Path, object_key: Optional[str] = None) -> Dict[str, Any]:
        """Upload a file to S3 and generate a presigned download URL."""
        if not self.bucket_name:
            raise ValueError("S3 bucket name is not configured (set S3_BUCKET_NAME).")

        client = self._get_s3_client()
        key = object_key or f"outputs/{local_path.name}"
        content_type, _ = mimetypes.guess_type(str(local_path))
        content_type = content_type or "application/octet-stream"

        extra_args = {"ContentType": content_type}
        client.upload_file(str(local_path), self.bucket_name, key, ExtraArgs=extra_args)

        # Generate presigned download URL
        presigned_url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": key},
            ExpiresIn=self.presigned_ttl,
        )

        return {
            "bucket": self.bucket_name,
            "key": key,
            "url": presigned_url,
            "content_type": content_type,
            "expires_in_seconds": self.presigned_ttl,
        }

    def process_output_file(
        self,
        file_info: Dict[str, Any],
        return_base64: bool = False,
        upload_s3: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Process a generated output file according to configured backend and job flags.
        """
        path_str = file_info["path"]
        path = Path(path_str)

        result: Dict[str, Any] = {
            "filename": file_info.get("filename", path.name),
            "media_type": file_info.get("media_type", "video"),
            "file_size_bytes": path.stat().st_size if path.exists() else 0,
            "local_path": path_str,
        }

        should_upload = upload_s3 if upload_s3 is not None else (self.backend == "s3")

        if should_upload and path.exists():
            try:
                s3_res = self.upload_to_s3(path)
                result["s3"] = s3_res
                result["url"] = s3_res["url"]
            except Exception as exc:
                logger.error(f"S3 upload failed for {path}: {exc}. Retaining local path.")
                result["s3_error"] = str(exc)

        if return_base64 and path.exists():
            with open(path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
            result["base64"] = b64_data

        return result
