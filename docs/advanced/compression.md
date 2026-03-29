# Native Payload Compression

XML and JSON payloads are notoriously verbose. `etl-pycache` includes a native, zero-dependency compression engine using Python's built-in `gzip` library. 

By simply passing `compress=True` to the `set` method, the engine will aggressively compress your data *before* writing it to the local disk or streaming it over the network to AWS S3. 

```python
# A 350MB XML string will be shrunk down to ~70MB on your hard drive or S3 bucket
cache.set("massive_xml_payload", my_xml_string, compress=True)

# The get() method automatically detects the compression flag and decompresses on the fly
data = cache.get("massive_xml_payload")
```

*Note: To ensure memory safety and prevent Out-Of-Memory crashes, stream payloads (`ABCIterator`) deliberately bypass compression.*