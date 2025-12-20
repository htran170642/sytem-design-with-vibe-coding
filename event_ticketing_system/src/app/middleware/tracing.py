"""
Request tracing middleware
"""
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging_config import set_trace_id, generate_trace_id, get_trace_id

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware to add trace ID to all requests"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate or extract trace ID
        trace_id = request.headers.get('X-Trace-ID', generate_trace_id())
        set_trace_id(trace_id)
        
        # Record start time
        start_time = time.time()
        
        # Log request start
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                'trace_id': trace_id,
                'method': request.method,
                'path': request.url.path,
                'client_ip': request.client.host
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log request completion
            logger.info(
                f"Request completed: {request.method} {request.url.path}",
                extra={
                    'trace_id': trace_id,
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': response.status_code,
                    'duration_ms': round(duration_ms, 2)
                }
            )
            
            # Add trace ID to response headers
            response.headers['X-Trace-ID'] = trace_id
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    'trace_id': trace_id,
                    'method': request.method,
                    'path': request.url.path,
                    'duration_ms': round(duration_ms, 2),
                    'error': str(e)
                },
                exc_info=True
            )
            raise