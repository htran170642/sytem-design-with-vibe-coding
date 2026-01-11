"""API routes for the ingestion service.

This module defines the FastAPI endpoints that receive logs and metrics
from collection agents.
"""
from typing import Dict, Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from observability.common.logger import get_logger
from observability.common.models import LogBatch, MetricBatch
from observability.ingestion.auth import verify_api_key
from observability.ingestion.kafka_producer import BaseProducer, get_producer
from observability.ingestion.rate_limiter import check_rate_limit

logger = get_logger(__name__)

# Create router
router = APIRouter()


@router.post(
    "/logs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Dict[str, Any],
    summary="Ingest log batch",
    description="Receives a batch of logs from collection agents and writes to Kafka",
)
async def ingest_logs(
    request: Request,
    batch: LogBatch,
    api_key: str = Depends(verify_api_key),
    producer: BaseProducer = Depends(get_producer),
) -> Dict[str, any]:
    """Ingest a batch of logs.
    
    This endpoint:
    1. Validates API key (via dependency)
    2. Checks rate limit (via dependency)
    3. Validates log batch schema (via Pydantic)
    4. Writes to Kafka
    5. Returns success response
    
    Args:
        request: FastAPI request object
        batch: Log batch from agent
        api_key: Validated API key (injected by dependency)
        producer: Kafka producer (injected by dependency)
        
    Returns:
        Success response with batch info
        
    Raises:
        HTTPException 401: Invalid API key
        HTTPException 422: Invalid batch schema
        HTTPException 429: Rate limit exceeded
        HTTPException 500: Internal server error
        
    Example request:
        ```
        POST /logs
        Headers:
            X-API-Key: your-api-key-here
            Content-Type: application/json
        Body:
            {
              "entries": [
                {
                  "timestamp": "2024-01-11T10:00:00Z",
                  "level": "INFO",
                  "message": "User login successful",
                  "service": "auth-service",
                  "host": "web-01"
                }
              ],
              "agent_version": "0.1.0"
            }
        ```
        
    Example response:
        ```
        HTTP 202 Accepted
        {
          "status": "accepted",
          "logs_received": 1,
          "service": "auth-service",
          "message": "Log batch accepted for processing"
        }
        ```
    """
    # Rate limit check happens automatically via middleware
    # But we can also do it here explicitly if needed
    await check_rate_limit(request, api_key)
    
    # Log the ingestion request
    logger.info(
        "Log batch received",
        num_logs=len(batch.entries),
        service=batch.entries[0].service if batch.entries else "unknown",
        api_key_prefix=api_key[:8] if len(api_key) >= 8 else "***",
    )
    
    try:
        # Send to Kafka (or mock)
        await producer.send_logs(batch)
        
        # Return success response
        return {
            "status": "accepted",
            "logs_received": len(batch.entries),
            "service": batch.entries[0].service if batch.entries else None,
            "message": "Log batch accepted for processing",
        }
        
    except Exception as e:
        logger.error(
            "Failed to send logs to Kafka",
            error=str(e),
            num_logs=len(batch.entries),
        )
        # Return 500 error
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Failed to process log batch",
                "error": str(e),
            },
        )


@router.post(
    "/metrics",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Dict[str, Any],
    summary="Ingest metric batch",
    description="Receives a batch of metrics from collection agents and writes to Kafka",
)
async def ingest_metrics(
    request: Request,
    batch: MetricBatch,
    api_key: str = Depends(verify_api_key),
    producer: BaseProducer = Depends(get_producer),
) -> Dict[str, any]:
    """Ingest a batch of metrics.
    
    This endpoint:
    1. Validates API key (via dependency)
    2. Checks rate limit (via dependency)
    3. Validates metric batch schema (via Pydantic)
    4. Writes to Kafka
    5. Returns success response
    
    Args:
        request: FastAPI request object
        batch: Metric batch from agent
        api_key: Validated API key (injected by dependency)
        producer: Kafka producer (injected by dependency)
        
    Returns:
        Success response with batch info
        
    Raises:
        HTTPException 401: Invalid API key
        HTTPException 422: Invalid batch schema
        HTTPException 429: Rate limit exceeded
        HTTPException 500: Internal server error
        
    Example request:
        ```
        POST /metrics
        Headers:
            X-API-Key: your-api-key-here
            Content-Type: application/json
        Body:
            {
              "entries": [
                {
                  "timestamp": "2024-01-11T10:00:00Z",
                  "name": "system.cpu.usage_percent",
                  "value": 45.2,
                  "metric_type": "GAUGE",
                  "service": "web-server",
                  "host": "web-01"
                }
              ],
              "agent_version": "0.1.0"
            }
        ```
        
    Example response:
        ```
        HTTP 202 Accepted
        {
          "status": "accepted",
          "metrics_received": 1,
          "service": "web-server",
          "message": "Metric batch accepted for processing"
        }
        ```
    """
    # Rate limit check
    await check_rate_limit(request, api_key)
    
    # Log the ingestion request
    logger.info(
        "Metric batch received",
        num_metrics=len(batch.entries),
        service=batch.entries[0].service if batch.entries else "unknown",
        api_key_prefix=api_key[:8] if len(api_key) >= 8 else "***",
    )
    
    try:
        # Send to Kafka (or mock)
        await producer.send_metrics(batch)
        
        # Return success response
        return {
            "status": "accepted",
            "metrics_received": len(batch.entries),
            "service": batch.entries[0].service if batch.entries else None,
            "message": "Metric batch accepted for processing",
        }
        
    except Exception as e:
        logger.error(
            "Failed to send metrics to Kafka",
            error=str(e),
            num_metrics=len(batch.entries),
        )
        # Return 500 error
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Failed to process metric batch",
                "error": str(e),
            },
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, Any],
    summary="Health check",
    description="Returns the health status of the ingestion service",
)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint.
    
    This endpoint can be used by:
    - Load balancers (to check if instance is healthy)
    - Monitoring systems (to track uptime)
    - Kubernetes liveness/readiness probes
    
    No authentication required.
    
    Returns:
        Health status
        
    Example response:
        ```
        HTTP 200 OK
        {
          "status": "healthy",
          "service": "ingestion-service",
          "version": "0.1.0"
        }
        ```
    """
    return {
        "status": "healthy",
        "service": "ingestion-service",
        "version": "0.1.0",
    }


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, Any],
    summary="Service info",
    description="Returns information about the ingestion service",
)
async def root() -> Dict[str, Any]:
    """Root endpoint with service information.
    
    Returns:
        Service information
        
    Example response:
        ```
        HTTP 200 OK
        {
          "service": "observability-ingestion",
          "version": "0.1.0",
          "endpoints": {
            "logs": "POST /logs",
            "metrics": "POST /metrics",
            "health": "GET /health"
          }
        }
        ```
    """
    return {
        "service": "observability-ingestion",
        "version": "0.1.0",
        "description": "Ingestion service for logs and metrics",
        "endpoints": {
            "logs": "POST /logs - Ingest log batches",
            "metrics": "POST /metrics - Ingest metric batches",
            "health": "GET /health - Health check",
            "docs": "GET /docs - Interactive API documentation",
        },
    }


@router.get(
    "/stats",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, Any],
    summary="Service statistics",
    description="Returns statistics about the ingestion service",
)
async def get_stats(
    api_key: str = Depends(verify_api_key),
    producer: BaseProducer = Depends(get_producer),
) -> Dict[str, Any]:
    """Get service statistics.
    
    Requires authentication.
    
    Args:
        api_key: Validated API key
        producer: Kafka producer instance
        
    Returns:
        Service statistics
        
    Example response:
        ```
        HTTP 200 OK
        {
          "status": "ok",
          "producer_type": "MockKafkaProducer",
          "logs_sent": 1234,
          "metrics_sent": 5678
        }
        ```
    """
    from observability.ingestion.kafka_producer import MockKafkaProducer
    
    stats = {
        "status": "ok",
        "producer_type": type(producer).__name__,
    }
    
    # If using mock producer, include sent counts
    if isinstance(producer, MockKafkaProducer):
        stats["logs_sent"] = len(producer.get_sent_logs())
        stats["metrics_sent"] = len(producer.get_sent_metrics())
    
    return stats