"""AWS client management with caching and LocalStack support."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config

if TYPE_CHECKING:
    pass
else:
    pass

from .bedrock import Bedrock

# Module-level client cache for reuse across invocations
_client_cache: dict[str, Any] = {}
_bedrock_cache: dict[str, Bedrock] = {}

# Short timeouts for config retrieval (fail fast on missing/unreachable config)
_CONFIG_CONNECT_TIMEOUT = 3
_CONFIG_READ_TIMEOUT = 5


def get_boto3_client(service: str, region_name: str | None = None) -> Any:
    """Create or reuse boto3 client with LocalStack support.

    Clients are cached and reused across Lambda invocations for efficiency.

    Args:
        service: AWS service name (s3, ssm, secretsmanager, etc.)
        region_name: AWS region name (optional)

    Returns:
        Configured boto3 client
    """
    cache_key = f"{service}:{region_name or 'default'}"
    if cache_key in _client_cache:
        return _client_cache[cache_key]

    localstack_services = {"s3", "ssm", "secretsmanager"}
    localstack_endpoint = os.environ.get("LOCALSTACK_ENDPOINT")

    kwargs = {}
    if region_name:
        kwargs["region_name"] = region_name

    if service in localstack_services and localstack_endpoint:
        kwargs["endpoint_url"] = localstack_endpoint
        kwargs["aws_access_key_id"] = os.environ.get("LOCALSTACK_AWS_ACCESS_KEY_ID", "test")
        kwargs["aws_secret_access_key"] = os.environ.get("LOCALSTACK_AWS_SECRET_ACCESS_KEY", "test")
        if service == "s3":
            from botocore.config import Config

            kwargs["config"] = Config(s3={"addressing_style": "path"})

    client = boto3.client(service, **kwargs)
    _client_cache[cache_key] = client
    return client


def get_config_client(service: str, region: str) -> Any:
    """Create boto3 client with short timeout for config retrieval.

    Used for SSM and Secrets Manager during Lambda initialization to ensure
    the function fails quickly if config is missing or unreachable.

    Args:
        service: AWS service name (ssm, secretsmanager)
        region: AWS region name

    Returns:
        Boto3 client with short connect/read timeouts
    """
    fast_config = Config(
        connect_timeout=_CONFIG_CONNECT_TIMEOUT,
        read_timeout=_CONFIG_READ_TIMEOUT,
    )
    return boto3.client(service, region_name=region, config=fast_config)


def get_or_create_bedrock_client(region: str) -> Bedrock:
    """Get or create cached Bedrock client.

    Args:
        region: AWS region name

    Returns:
        Cached Bedrock client instance
    """
    if region in _bedrock_cache:
        return _bedrock_cache[region]

    client = Bedrock(region=region)
    _bedrock_cache[region] = client
    return client
