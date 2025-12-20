"""
Load testing for event ticketing system
Tests concurrent booking scenarios
"""
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import random
import time
import logging

logger = logging.getLogger(__name__)

# Test configuration
EVENT_ID = 1
SEAT_IDS = list(range(1, 1001))  # 1000 seats available


class TicketBuyerUser(HttpUser):
    """Simulates a user trying to buy tickets"""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Called when a simulated user starts"""
        self.user_id = random.randint(1, 10000)
        self.waiting_room_token = None
        self.selected_seats = []
        self.booking_id = None
        
        # Try to join waiting room
        self.join_waiting_room()
    
    def join_waiting_room(self):
        """Join waiting room if enabled"""
        try:
            response = self.client.get(
                f"/api/v1/events/{EVENT_ID}/waiting-room/stats",
                name="/waiting-room/stats"
            )
            
            if response.status_code == 200:
                stats = response.json()
                if stats.get('enabled'):
                    # Waiting room is enabled
                    join_response = self.client.post(
                        f"/api/v1/events/{EVENT_ID}/waiting-room/join?user_id={self.user_id}",
                        name="/waiting-room/join"
                    )
                    
                    if join_response.status_code == 200:
                        self.waiting_room_token = join_response.json().get('token')
                        logger.info(f"User {self.user_id} joined waiting room")
        
        except Exception as e:
            logger.error(f"Error joining waiting room: {e}")
    
    @task(10)
    def view_seats(self):
        """View available seats"""
        params = {}
        if self.waiting_room_token:
            params['wr_token'] = self.waiting_room_token
        
        response = self.client.get(
            f"/api/v1/events/{EVENT_ID}/seats",
            params=params,
            name="/events/seats"
        )
        
        if response.status_code == 200:
            data = response.json()
            available_seats = [
                seat['id'] for seat in data['seats']
                if seat['status'] == 'AVAILABLE'
            ]
            
            if available_seats:
                # Select random seats
                self.selected_seats = random.sample(
                    available_seats,
                    min(2, len(available_seats))
                )
    
    @task(5)
    def create_booking(self):
        """Create a booking (HOLD)"""
        if not self.selected_seats:
            return
        
        headers = {"Content-Type": "application/json"}
        if self.waiting_room_token:
            headers["X-Waiting-Room-Token"] = self.waiting_room_token
        
        response = self.client.post(
            f"/api/v1/bookings?user_id={self.user_id}",
            json={
                "event_id": EVENT_ID,
                "seat_ids": self.selected_seats
            },
            headers=headers,
            name="/bookings [CREATE]"
        )
        
        if response.status_code == 201:
            self.booking_id = response.json()['id']
            logger.info(f"User {self.user_id} created booking {self.booking_id}")
        else:
            logger.warning(f"User {self.user_id} failed to create booking: {response.status_code}")
    
    @task(3)
    def confirm_booking(self):
        """Confirm a booking"""
        if not self.booking_id:
            return
        
        response = self.client.post(
            f"/api/v1/bookings/{self.booking_id}/confirm?user_id={self.user_id}",
            json={"payment_id": f"pi_{int(time.time())}"},
            name="/bookings/confirm"
        )
        
        if response.status_code == 200:
            logger.info(f"User {self.user_id} confirmed booking {self.booking_id}")
            self.booking_id = None
            self.selected_seats = []
    
    @task(1)
    def cancel_booking(self):
        """Cancel a booking"""
        if not self.booking_id:
            return
        
        response = self.client.delete(
            f"/api/v1/bookings/{self.booking_id}?user_id={self.user_id}",
            name="/bookings/cancel"
        )
        
        if response.status_code == 204:
            logger.info(f"User {self.user_id} cancelled booking {self.booking_id}")
            self.booking_id = None
            self.selected_seats = []


class ConcurrentSameSeatUser(HttpUser):
    """
    Simulates multiple users targeting the SAME seats
    Tests race condition handling
    """
    
    wait_time = between(0.1, 0.5)
    
    # All users target these seats
    TARGET_SEATS = [1, 2, 3, 4, 5]
    
    def on_start(self):
        self.user_id = random.randint(1, 10000)
    
    @task
    def try_book_same_seats(self):
        """Try to book the same seats as everyone else"""
        response = self.client.post(
            f"/api/v1/bookings?user_id={self.user_id}",
            json={
                "event_id": EVENT_ID,
                "seat_ids": self.TARGET_SEATS
            },
            headers={"Content-Type": "application/json"},
            name="/bookings [RACE CONDITION TEST]"
        )
        
        if response.status_code == 201:
            logger.info(f"✅ User {self.user_id} WON the race!")
        elif response.status_code == 409:
            logger.info(f"❌ User {self.user_id} lost (seats taken)")
        else:
            logger.warning(f"⚠️ User {self.user_id} unexpected: {response.status_code}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts"""
    logger.info("🚀 Load test starting...")
    logger.info(f"Target: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops"""
    logger.info("🛑 Load test completed")
    
    # Print summary
    stats = environment.stats
    logger.info(f"Total requests: {stats.total.num_requests}")
    logger.info(f"Total failures: {stats.total.num_failures}")
    logger.info(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"Requests per second: {stats.total.total_rps:.2f}")