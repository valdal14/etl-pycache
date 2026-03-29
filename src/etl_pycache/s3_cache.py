import gzip
import json
import time
from collections.abc import Iterator as ABCIterator
from typing import Any

import boto3
from botocore.exceptions import ClientError

from etl_pycache.interfaces import BaseCache, PayloadType


class _IteratorReader:
    """
    An adapter that wraps a Python Iterator[bytes] and provides a .read() method.
    This tricks boto3 into thinking our generator is a physical file it can stream.
    """

    def __init__(self, iterator: ABCIterator):
        self._iterator = iterator
        self._buffer = bytearray()

    def read(self, size: int = -1) -> bytes:
        try:
            while len(self._buffer) < size or size == -1:
                self._buffer.extend(next(self._iterator))
        except StopIteration:
            pass

        if size == -1:
            result = bytes(self._buffer)
            self._buffer.clear()
        else:
            result = bytes(self._buffer[:size])
            del self._buffer[:size]

        return result


class S3Cache(BaseCache):
    """
    An AWS S3 backend for the caching engine.
    Supports polymorphic payloads, massive streaming, TTL expiration, and native compression.
    """

    def __init__(self, bucket_name: str, client: Any = None):
        """
        Initializes the S3 Cache instance.
        """
        self.bucket_name = bucket_name
        self.client = client or boto3.client("s3")

    def set(
        self, key: str, payload: PayloadType, ttl_seconds: int | None = None, compress: bool = False
    ) -> None:
        """
        Orchestrates the serialization and upload of polymorphic payloads to S3.

        Args:
            key (str): The unique identifier for the cache entry.
            payload (PayloadType): The string, dict, bytes, or stream to upload.
            ttl_seconds (int | None, optional): The Time-To-Live in seconds.
            compress (bool, optional): If True, natively compresses the payload before
                network transmission to save S3 storage costs. Defaults to False.
        """
        metadata = self._prepare_metadata(ttl_seconds, compress)

        if isinstance(payload, ABCIterator):
            # Streams deliberately bypass compression to maintain memory safety
            self._upload_stream(key, payload, metadata)
        else:
            self._upload_in_memory(key, payload, metadata, compress)

    def get(self, key: str) -> Any | None:
        """
        Retrieves the object from S3, enforcing TTL expiration and automatic decompression.
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code in ["NoSuchKey", "404"]:
                return None
            raise e

        # Enforce TTL Expiration
        metadata = response.get("Metadata", {})
        if self._is_expired(metadata):
            self.delete(key)
            return None

        # Read the body into memory
        raw_bytes = response["Body"].read()

        # Decompress if the S3 Object Metadata contains the compression flag
        if metadata.get("compressed") == "true":
            raw_bytes = gzip.decompress(raw_bytes)

        # Deserialize based on payload type
        try:
            decoded_str = raw_bytes.decode("utf-8")
            try:
                return json.loads(decoded_str)
            except json.JSONDecodeError:
                return decoded_str
        except UnicodeDecodeError:
            return raw_bytes

    def get_stream(self, key: str) -> ABCIterator | None:
        """
        Retrieves a streaming connection to the S3 object, enforcing TTL expiration.
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code in ["NoSuchKey", "404"]:
                return None
            raise e

        metadata = response.get("Metadata", {})
        if self._is_expired(metadata):
            self.delete(key)
            return None

        return response["Body"]

    def delete(self, key: str) -> None:
        """Deletes the object from the S3 bucket."""
        self.client.delete_object(Bucket=self.bucket_name, Key=key)

    # NOTE: - Internal Helper Methods #################################################################

    def _prepare_metadata(self, ttl_seconds: int | None, compress: bool) -> dict:
        """
        Calculates the expiration timestamp and formats the metadata dict for S3.
        S3 Metadata values MUST be strings.
        """
        metadata = {}
        if ttl_seconds is not None:
            expiration_timestamp = time.time() + ttl_seconds
            metadata["expires_at"] = str(expiration_timestamp)

        if compress:
            metadata["compressed"] = "true"

        return metadata

    def _upload_stream(self, key: str, payload: ABCIterator, metadata: dict) -> None:
        """Wraps an iterator in a file-like adapter and streams it directly to S3."""
        file_adapter = _IteratorReader(payload)

        self.client.upload_fileobj(
            Fileobj=file_adapter,
            Bucket=self.bucket_name,
            Key=key,
            ExtraArgs={"Metadata": metadata} if metadata else None,
        )

    def _upload_in_memory(
        self, key: str, payload: PayloadType, metadata: dict, compress: bool
    ) -> None:
        """
        Serializes, optionally compresses, and uploads static payloads.
        """
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload)

        if isinstance(payload, str):
            payload = payload.encode("utf-8")

        if compress:
            payload = gzip.compress(payload)

        self.client.put_object(Bucket=self.bucket_name, Key=key, Body=payload, Metadata=metadata)

    def _is_expired(self, metadata: dict) -> bool:
        """Checks if the S3 Object's metadata indicates it has expired."""
        expires_at_str = metadata.get("expires_at")

        if not expires_at_str:
            return False

        return time.time() >= float(expires_at_str)
