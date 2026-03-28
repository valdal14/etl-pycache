import json
import time
import boto3
from typing import Any
from botocore.exceptions import ClientError
from collections.abc import Iterator as ABCIterator
from etl_pycache.interfaces import BaseCache, PayloadType

class _IteratorReader:
    """
    An adapter that wraps a Python Iterator[bytes] and provides a .read() method.
    This tricks boto3 into thinking our generator is a physical file it can stream.
    """
    def __init__(self, iterator: ABCIterator):
        """
        Initializes the adapter with the underlying byte generator.
        
        Args:
            iterator (ABCIterator): The generator yielding chunks of bytes.
        """
        self._iterator = iterator
        self._buffer = bytearray()

    def read(self, size: int = -1) -> bytes:
        """
        Reads a specific number of bytes from the underlying iterator.
        
        Args:
            size (int, optional): The number of bytes to read. Defaults to -1 (read all).
            
        Returns:
            bytes: The extracted chunk of bytes.
        """
        # Boto3 will call this repeatedly asking for a specific `size` of bytes.
        try:
            while len(self._buffer) < size or size == -1:
                self._buffer.extend(next(self._iterator))
        except StopIteration:
            # The generator is empty, proceed to return whatever is left
            pass 

        if size == -1:
            # If boto3 asks for everything at once (fallback)
            result = bytes(self._buffer)
            self._buffer.clear()
        else:
            # Return exactly the chunk size boto3 requested
            result = bytes(self._buffer[:size])
            del self._buffer[:size]
            
        return result


class S3Cache(BaseCache):
    """
    An AWS S3 backend for the caching engine. 
    Supports polymorphic payloads, massive streaming, and TTL expiration via S3 Metadata.
    """

    def __init__(self, bucket_name: str, client: Any = None):
        """
        Initializes the S3 Cache instance.
        
        Args:
            bucket_name (str): The name of the target AWS S3 bucket.
            client (Any, optional): An injected boto3 S3 client. If None, creates a default client.
        """
        self.bucket_name = bucket_name
        self.client = client or boto3.client("s3")

    def set(self, key: str, payload: PayloadType, ttl_seconds: int | None = None) -> None:
        """
        Orchestrates the serialization and upload of polymorphic payloads to S3.
        
        Args:
            key (str): The unique identifier for the cache entry.
            payload (PayloadType): The string, dict, bytes, or stream to upload.
            ttl_seconds (int | None, optional): The Time-To-Live in seconds.
        """
        metadata = self._prepare_metadata(ttl_seconds)

        if isinstance(payload, ABCIterator):
            self._upload_stream(key, payload, metadata)
        else:
            self._upload_in_memory(key, payload, metadata)

    def get(self, key: str) -> Any | None:
        """
        Retrieves the object from S3, enforcing TTL expiration.
        Deserializes JSON or Strings automatically.
        
        Args:
            key (str): The unique identifier for the cache entry.
            
        Returns:
            Any | None: The parsed dictionary, raw string/XML, raw bytes, 
                        or None if the object doesn't exist or is expired.
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            # Safely handle the case where the key doesn't exist
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code in ["NoSuchKey", "404"]:
                return None
            # Reraise if it's an actual permissions or network issue
            raise e 

        # Enforce TTL Expiration
        metadata = response.get("Metadata", {})
        if self._is_expired(metadata):
            self.delete(key)
            return None

        # Read the body into memory
        raw_bytes = response["Body"].read()

        # Deserialize based on payload type
        try:
            decoded_str = raw_bytes.decode("utf-8")
            try:
                # Try to parse it as a dictionary
                return json.loads(decoded_str)
            except json.JSONDecodeError:
                # If it's a raw XML string, JSON parsing will fail, return the string.
                return decoded_str
        except UnicodeDecodeError:
            # If it's pure binary data, return raw bytes
            return raw_bytes

    def get_stream(self, key: str) -> ABCIterator | None:
        """
        Retrieves a streaming connection to the S3 object, enforcing TTL expiration.
        
        Args:
            key (str): The unique identifier for the cache entry.
            
        Returns:
            ABCIterator | None: The boto3 StreamingBody natively yielding bytes, 
                                or None if missing/expired.
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

        # Return the boto3 StreamingBody natively
        return response["Body"]

    def delete(self, key: str) -> None:
        """
        Deletes the object from the S3 bucket.
        
        Args:
            key (str): The unique identifier for the cache entry to delete.
        """
        self.client.delete_object(Bucket=self.bucket_name, Key=key)

    # NOTE: - Internal Helper Methods #################################################################

    def _prepare_metadata(self, ttl_seconds: int | None) -> dict:
        """
        Calculates the expiration timestamp and formats it for S3.
        
        Args:
            ttl_seconds (int | None): The user-provided TTL duration.
            
        Returns:
            dict: The metadata dictionary formatted with string values for AWS.
        """
        if ttl_seconds is None:
            return {}
            
        expiration_timestamp = time.time() + ttl_seconds
        # S3 Metadata MUST be strings!
        return {"expires_at": str(expiration_timestamp)}

    def _upload_stream(self, key: str, payload: ABCIterator, metadata: dict) -> None:
        """
        Wraps an iterator in a file-like adapter and streams it directly to S3.
        
        Args:
            key (str): The destination object key.
            payload (ABCIterator): The raw byte generator.
            metadata (dict): The S3 object metadata containing expiration info.
        """
        # Wrap our generator in the adapter
        file_adapter = _IteratorReader(payload)
        
        # upload_fileobj streams the data in 8MB chunks automatically
        self.client.upload_fileobj(
            Fileobj=file_adapter,
            Bucket=self.bucket_name,
            Key=key,
            ExtraArgs={"Metadata": metadata} if metadata else None
        )

    def _upload_in_memory(self, key: str, payload: PayloadType, metadata: dict) -> None:
        """
        Serializes and uploads static payloads (dicts, lists, strings, bytes).
        
        Args:
            key (str): The destination object key.
            payload (PayloadType): The static data to cache.
            metadata (dict): The S3 object metadata containing expiration info.
        """
        # Convert dicts and lists to JSON strings
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload)
            
        # Convert strings to raw bytes
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
            
        # Upload directly using put_object
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=payload,
            Metadata=metadata
        )
     
    def _is_expired(self, metadata: dict) -> bool:
        """
        Helper method to check if the S3 Object's metadata indicates it has expired.
        
        Args:
            metadata (dict): The parsed Metadata dictionary returned by boto3.
            
        Returns:
            bool: True if the current time has surpassed the expires_at timestamp.
        """
        # AWS automatically lowercases metadata keys
        expires_at_str = metadata.get("expires_at")
        
        if not expires_at_str:
            return False
            
        return time.time() >= float(expires_at_str)