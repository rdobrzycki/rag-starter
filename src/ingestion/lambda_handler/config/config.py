"""Configuration retrieval from AWS SSM and Secrets Manager."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mypy_boto3_ssm import SSMClient
    from mypy_boto3_secretsmanager import SecretsManagerClient
else:
    SSMClient = Any
    SecretsManagerClient = Any

from ..exceptions import ConfigurationError
from ..models import IngestionConfig

logger = logging.getLogger(__name__)


def get_ssm_parameter(ssm_client: SSMClient, name: str) -> str:
    """Retrieve a single SSM parameter.

    Args:
        ssm_client: SSM client
        name: Parameter name

    Returns:
        Parameter value

    Raises:
        ConfigurationError: If parameter retrieval fails
    """
    try:
        response = ssm_client.get_parameter(Name=name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        raise ConfigurationError(f"Failed to retrieve SSM parameter {name}: {e}") from e


def get_configuration(
    *,
    ssm_client: SSMClient,
    secrets_client: SecretsManagerClient,
    ssm_prefix: str,
    secret_id: str,
) -> IngestionConfig:
    """Retrieve configuration from AWS SSM and Secrets Manager.

    Args:
        ssm_client: boto3 SSM client
        secrets_client: boto3 Secrets Manager client
        ssm_prefix: SSM parameter prefix
        secret_id: Secrets Manager secret ID for Qdrant credentials (url + api_key)

    Returns:
        Configuration dictionary

    Raises:
        ConfigurationError: If configuration retrieval fails
    """
    import json

    try:
        logger.debug("Retrieving configuration from SSM prefix: %s", ssm_prefix)

        collection = get_ssm_parameter(ssm_client, f"{ssm_prefix}/qdrant/collection")
        embed_model_id = get_ssm_parameter(ssm_client, f"{ssm_prefix}/bedrock/embed-model-id")

        # Get Qdrant credentials from Secrets Manager (JSON with url and api_key)
        qdrant_secret_string = secrets_client.get_secret_value(
            SecretId=secret_id,
        )["SecretString"]
        qdrant_credentials = json.loads(qdrant_secret_string)
        qdrant_url = qdrant_credentials.get("url", "")
        qdrant_api_key = qdrant_credentials.get("api_key", "")

        # Log credential retrieval (for debugging 403 issues)
        logger.info(
            "Qdrant credentials retrieved from Secrets Manager",
            extra={
                "secret_id": secret_id,
                "url": qdrant_url,
                "api_key_length": len(qdrant_api_key) if qdrant_api_key else 0,
                "api_key_present": bool(qdrant_api_key),
            },
        )

        config = {
            "qdrant_url": qdrant_url,
            "qdrant_api_key": qdrant_api_key,
            "collection": collection,
            "embed_model_id": embed_model_id,
        }

        # Validate configuration values
        for key in config:
            value = config.get(key, "")
            if not value or not value.strip():
                raise ConfigurationError(f"{key} is empty or invalid (ssm_prefix: {ssm_prefix})")

        logger.info(
            "Configuration retrieved and validated successfully",
            extra={
                "qdrant_url": qdrant_url,
                "collection": collection,
                "embed_model_id": embed_model_id,
            },
        )
        return config

    except ConfigurationError:
        raise
    except Exception as e:
        logger.error("Failed to retrieve configuration: %s", e)
        raise ConfigurationError(f"Configuration retrieval failed: {e}") from e
