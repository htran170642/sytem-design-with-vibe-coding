"""
Prometheus metrics for monitoring
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# ==================== HTTP Metrics ====================

http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# ==================== Booking Metrics ====================

bookings_created_total = Counter(
    'bookings_created_total',
    'Total bookings created',
    ['status']  # HOLD, CONFIRMED
)

bookings_confirmed_total = Counter(
    'bookings_confirmed_total',
    'Total bookings confirmed'
)

bookings_cancelled_total = Counter(
    'bookings_cancelled_total',
    'Total bookings cancelled'
)

bookings_expired_total = Counter(
    'bookings_expired_total',
    'Total bookings expired'
)

booking_creation_duration_seconds = Histogram(
    'booking_creation_duration_seconds',
    'Time to create a booking',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

booking_confirmation_duration_seconds = Histogram(
    'booking_confirmation_duration_seconds',
    'Time to confirm a booking',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

# ==================== Seat Metrics ====================

seats_held_gauge = Gauge(
    'seats_held_gauge',
    'Number of seats currently on HOLD',
    ['event_id']
)

seats_booked_gauge = Gauge(
    'seats_booked_gauge',
    'Number of seats currently BOOKED',
    ['event_id']
)

# ==================== WebSocket Metrics ====================

websocket_connections_total = Gauge(
    'websocket_connections_total',
    'Current WebSocket connections',
    ['event_id']
)

websocket_messages_sent_total = Counter(
    'websocket_messages_sent_total',
    'Total WebSocket messages sent',
    ['event_id', 'message_type']
)

websocket_broadcast_duration_seconds = Histogram(
    'websocket_broadcast_duration_seconds',
    'Time to broadcast WebSocket message',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

# ==================== Waiting Room Metrics ====================

waiting_room_queue_size_gauge = Gauge(
    'waiting_room_queue_size',
    'Current queue size',
    ['event_id']
)

waiting_room_active_sessions_gauge = Gauge(
    'waiting_room_active_sessions',
    'Current active sessions',
    ['event_id']
)

waiting_room_admissions_total = Counter(
    'waiting_room_admissions_total',
    'Total users admitted',
    ['event_id']
)

waiting_room_admission_duration_seconds = Histogram(
    'waiting_room_admission_duration_seconds',
    'Time user spent in queue before admission',
    buckets=[0, 5, 10, 30, 60, 120, 300, 600]
)

# ==================== Rate Limiting Metrics ====================

rate_limit_hits_total = Counter(
    'rate_limit_hits_total',
    'Total rate limit hits',
    ['endpoint']
)

# ==================== Helper Functions ====================

def track_time(metric: Histogram):
    """Decorator to track execution time"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                metric.observe(duration)
        return wrapper
    return decorator


def record_booking_metrics(booking, operation: str):
    """Record booking-related metrics"""
    if operation == 'create':
        bookings_created_total.labels(status=booking.status).inc()
    elif operation == 'confirm':
        bookings_confirmed_total.inc()
    elif operation == 'cancel':
        bookings_cancelled_total.inc()
    elif operation == 'expire':
        bookings_expired_total.inc()


def update_seat_gauges(event_id: int, held_count: int, booked_count: int):
    """Update seat gauge metrics"""
    seats_held_gauge.labels(event_id=str(event_id)).set(held_count)
    seats_booked_gauge.labels(event_id=str(event_id)).set(booked_count)


def update_waiting_room_gauges(event_id: int, queue_size: int, active_sessions: int):
    """Update waiting room gauge metrics"""
    waiting_room_queue_size_gauge.labels(event_id=str(event_id)).set(queue_size)
    waiting_room_active_sessions_gauge.labels(event_id=str(event_id)).set(active_sessions)


def record_websocket_broadcast(event_id: int, message_type: str, duration_seconds: float):
    """Record WebSocket broadcast metrics"""
    websocket_messages_sent_total.labels(
        event_id=str(event_id),
        message_type=message_type
    ).inc()
    
    websocket_broadcast_duration_seconds.observe(duration_seconds)


def get_metrics():
    """Get current metrics in Prometheus format"""
    return generate_latest()