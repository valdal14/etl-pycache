import os
from collections.abc import Iterator as ABCIterator
from dataclasses import dataclass
from typing import Any

import boto3
import pytest
from moto import mock_aws

from etl_pycache.s3_cache import S3Cache

# NOTE: - FIXTURES (The Moto Mocking Engine) ######################################################


@pytest.fixture(autouse=True)
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    # Tell boto3 to stop searching for an EC2 server
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"


@pytest.fixture
def s3_client(aws_credentials):
    """Yields a mocked boto3 S3 client."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        yield client


@pytest.fixture
def setup_s3_cache(s3_client):
    """Creates a mock bucket and returns our S3Cache engine."""
    bucket_name = "test-etl-cache-bucket"
    s3_client.create_bucket(Bucket=bucket_name)
    return S3Cache(bucket_name=bucket_name, client=s3_client)


# NOTE: - Tests ###################################################################################


def test_s3_set_and_get_xml_string(setup_s3_cache):
    sut = make_sut(setup_s3_cache)

    sut.cache.set(sut.key, sut.payload)
    res = sut.cache.get(sut.key)

    assert res == sut.payload


def test_s3_set_and_get_stream_payload(setup_s3_cache):
    # Generator expression mimicking a massive file chunking
    mock_stream = (b"<chunk>" + str(i).encode("utf-8") + b"</chunk>" for i in range(3))
    sut = make_sut(setup_s3_cache, "massive_stream", mock_stream)

    sut.cache.set(sut.key, sut.payload)
    res_stream = sut.cache.get_stream(sut.key)

    assert isinstance(res_stream, ABCIterator)
    assert b"".join(res_stream) == b"<chunk>0</chunk><chunk>1</chunk><chunk>2</chunk>"


def test_s3_delete_removes_object_from_bucket(setup_s3_cache):
    sut = make_sut(setup_s3_cache)
    sut.cache.set(sut.key, sut.payload)

    sut.cache.delete(sut.key)
    res = sut.cache.get(sut.key)

    assert res is None


def test_s3_get_returns_none_if_ttl_expired(setup_s3_cache):
    sut = make_sut(setup_s3_cache)

    # Set with a negative TTL so it expires instantly in the past
    sut.cache.set(sut.key, sut.payload, ttl_seconds=-1)

    # The interceptor should catch the expired metadata and return None
    res = sut.cache.get(sut.key)
    assert res is None


# NOTE: - Test's Helpers ##########################################################################


@dataclass
class SUT:
    cache: S3Cache
    key: str
    payload: Any


def make_sut(cache_instance: S3Cache, key: str = "anaplan_export", payload: Any = None) -> SUT:
    default_payload = payload or "<DataExchange><Status>Success</Status></DataExchange>"
    return SUT(cache=cache_instance, key=key, payload=default_payload)
