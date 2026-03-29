import json
import os

from etl_pycache.local_cache import LocalDiskCache


def test_xml_payload_compression(tmp_path):
    """
    Verifies that setting compress=True significantly reduces the disk footprint
    of large XML string payloads, and seamlessly decompresses on read.
    """
    cache = LocalDiskCache(cache_dir=str(tmp_path))
    key = "massive_xml_payload"

    # Generate a massive string containing a sort of XML
    xml_lines = ["<dataset>"]
    for i in range(50000):
        xml_lines.append(
            f"  <record id='{i}'><status>active</status><value>data_{i}</value></record>"
        )
    xml_lines.append("</dataset>")

    massive_xml_string = "\n".join(xml_lines)

    # Calculate the raw size in bytes (before compression)
    raw_size_bytes = len(massive_xml_string.encode("utf-8"))

    # Write to cache with the new compress=True flag
    cache.set(key, massive_xml_string, compress=True)

    # Verify the file sizes
    cache_file_path = cache._get_file_path(key)
    meta_file_path = cache_file_path.with_suffix(".meta")

    assert cache_file_path.exists(), "Cache file was not created"
    assert meta_file_path.exists(), "Meta file was not created (needed to store compress flag)"

    compressed_size_bytes = os.path.getsize(cache_file_path)

    # The compressed file should be AT LEAST 70% smaller than the raw XML string
    assert compressed_size_bytes < (raw_size_bytes * 0.3), (
        f"Compression failed! Raw: {raw_size_bytes}b, Compressed: {compressed_size_bytes}b"
    )

    # Verify the .meta file correctly stored the flag
    meta_data = json.loads(meta_file_path.read_text(encoding="utf-8"))
    assert meta_data.get("compressed") is True, (
        "The .meta file did not store the 'compressed': true flag"
    )

    # Read it back and verify data integrity
    retrieved_payload = cache.get(key)
    assert retrieved_payload == massive_xml_string, (
        "Decompressed XML payload does not match the original!"
    )
