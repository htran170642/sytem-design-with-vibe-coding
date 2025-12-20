"""
Structured logging configuration with trace IDs
"""
import logging
import json
import time
from typing import Any, Dict
from pythonjsonlogger import jsonlogger
import contextvars
from datetime import datetime

# Context variable to store trace ID across async calls
trace_id_var = contextvars.ContextVar('trace_id', default=None)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with trace ID and additional fields"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add trace ID if available
        trace_id = trace_id_var.get()
        if trace_id:
            log_record['trace_id'] = trace_id
        
        # Add service info
        log_record['service'] = 'event-ticketing'
        log_record['environment'] = 'development'
        
        # Add custom fields from extra
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        if hasattr(record, 'event_id'):
            log_record['event_id'] = record.event_id
        if hasattr(record, 'booking_id'):
            log_record['booking_id'] = record.booking_id
        if hasattr(record, 'duration_ms'):
            log_record['duration_ms'] = record.duration_ms


def setup_logging():
    """Configure structured JSON logging"""
    
    # Create formatter
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    
    # Console handler (JSON for production, readable for development)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # File handler (JSON logs)
    file_handler = logging.FileHandler('logs/app.json')
    file_handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Reduce noise from libraries
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.INFO)
    
    return root_logger


def get_trace_id() -> str:
    """Get current trace ID"""
    return trace_id_var.get()


def set_trace_id(trace_id: str):
    """Set trace ID for current context"""
    trace_id_var.set(trace_id)


def generate_trace_id() -> str:
    """Generate a new trace ID"""
    import uuid
    return str(uuid.uuid4())