from __future__ import annotations
from functools import lru_cache
from fastapi import Depends
import boto3
from .config import LocalSettings, load_local_settings
from .bedrock import Bedrock
from .providers import BedrockEmbedding, BedrockLLM
from .qdrant_client import make_qdrant
from .services.metrics import get_cloudwatch_metrics
from .services.feedback_service import FeedbackService


@lru_cache()
def get_settings() -> LocalSettings:
    return load_local_settings()


def get_bedrock(settings: LocalSettings = Depends(get_settings)) -> Bedrock:
    metrics = get_cloudwatch_metrics(
        namespace=settings.cloudwatch_namespace, enabled=settings.enable_cloudwatch_metrics
    )
    return Bedrock(settings.aws_region, metrics=metrics)


def get_qdrant(settings: LocalSettings = Depends(get_settings)):
    return make_qdrant(settings.qdrant_url, settings.qdrant_api_key)


def get_feedback_service(settings: LocalSettings = Depends(get_settings)) -> FeedbackService:
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = dynamodb.Table(settings.feedback_table_name)
    return FeedbackService(table, ttl_days=settings.feedback_ttl_days)


def get_embedding_provider(bedrock: Bedrock = Depends(get_bedrock)) -> BedrockEmbedding:
    return BedrockEmbedding(bedrock)


def get_llm_provider(bedrock: Bedrock = Depends(get_bedrock)) -> BedrockLLM:
    return BedrockLLM(bedrock)
