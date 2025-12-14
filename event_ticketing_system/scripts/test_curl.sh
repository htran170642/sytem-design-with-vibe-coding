Events API Tests
1. List All Events
bashcurl http://localhost:8000/api/v1/events | jq
Expected Response:
json{
  "events": [
    {
      "id": 1,
      "name": "Taylor Swift - The Eras Tour",
      "venue": "SoFi Stadium",
      "city": "Los Angeles",
      "country": "USA",
      "start_time": "2025-01-09T...",
      "total_seats": 1000,
      "available_seats": 1000,
      "is_sold_out": false,
      "occupancy_rate": 0.0
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 10
}

2. List Events with Pagination
bash# Page 1, 3 items per page
curl "http://localhost:8000/api/v1/events?page=1&page_size=3" | jq

# Page 2
curl "http://localhost:8000/api/v1/events?page=2&page_size=3" | jq

3. Filter Events by City
bash# Los Angeles events
curl "http://localhost:8000/api/v1/events?city=Los%20Angeles" | jq

# New York events
curl "http://localhost:8000/api/v1/events?city=New%20York" | jq

# London events
curl "http://localhost:8000/api/v1/events?city=London" | jq

4. Filter Events by Category
bash# Concerts
curl "http://localhost:8000/api/v1/events?category=concert" | jq

# Sports
curl "http://localhost:8000/api/v1/events?category=sports" | jq

# Theater
curl "http://localhost:8000/api/v1/events?category=theater" | jq

5. Search Events
bash# Search by name
curl "http://localhost:8000/api/v1/events/search?q=taylor" | jq

# Search by venue
curl "http://localhost:8000/api/v1/events/search?q=stadium" | jq

# Search by city
curl "http://localhost:8000/api/v1/events/search?q=los%20angeles" | jq

6. Get Specific Event
bash# Get event 1
curl http://localhost:8000/api/v1/events/1 | jq

# Get event 2
curl http://localhost:8000/api/v1/events/2 | jq

# Get non-existent event (should return 404)
curl http://localhost:8000/api/v1/events/999 | jq

7. Get Seat Map for Event
bash# All seats for event 1
curl http://localhost:8000/api/v1/events/1/seats | jq

# Only VIP section
curl "http://localhost:8000/api/v1/events/1/seats?section=VIP" | jq

# Only Section A
curl "http://localhost:8000/api/v1/events/1/seats?section=A" | jq

8. Filter Seats by Status
bash# Only available seats
curl "http://localhost:8000/api/v1/events/1/seats?status=AVAILABLE" | jq

# Only booked seats
curl "http://localhost:8000/api/v1/events/1/seats?status=BOOKED" | jq

# Only seats on hold
curl "http://localhost:8000/api/v1/events/1/seats?status=HOLD" | jq

9. Get Event Availability by Section
bashcurl http://localhost:8000/api/v1/events/1/availability | jq
Expected Response:
json{
  "event_id": 1,
  "event_name": "Taylor Swift - The Eras Tour",
  "sections": {
    "VIP": {
      "total": 200,
      "available": 200,
      "hold": 0,
      "booked": 0
    },
    "A": {
      "total": 300,
      "available": 300,
      "hold": 0,
      "booked": 0
    }
  },
  "total_seats": 1000,
  "available_seats": 1000
}

🎫 Bookings API Tests
10. Create a Booking (HOLD)
bash# Book 3 seats for user 1
curl -X POST "http://localhost:8000/api/v1/bookings?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": 1,
    "seat_ids": [1, 2, 3]
  }' | jq
Expected Response:
json{
  "id": 1,
  "user_id": 1,
  "event_id": 1,
  "status": "HOLD",
  "total_amount": "450.00",
  "hold_expires_at": "2024-12-10T20:45:00",
  "time_remaining_seconds": 300,
  "seats": [
    {
      "seat_id": 1,
      "section": "VIP",
      "row_number": "1",
      "seat_number": "1",
      "price_at_booking": "150.00",
      "seat_label": "VIP-1-1"
    }
  ]
}

11. Try to Book Already Held Seats (Should Fail)
bash# User 2 tries to book same seats
curl -X POST "http://localhost:8000/api/v1/bookings?user_id=2" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": 1,
    "seat_ids": [1, 2, 3]
  }' | jq
Expected Response (409 Conflict):
json{
  "detail": "Seats {1, 2, 3} are not available"
}

12. Book Different Seats
bash# User 2 books different seats
curl -X POST "http://localhost:8000/api/v1/bookings?user_id=2" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": 1,
    "seat_ids": [4, 5, 6]
  }' | jq

13. Get Booking Details
bash# Get booking 1
curl "http://localhost:8000/api/v1/bookings/1?user_id=1" | jq

# Try to get booking as wrong user (should fail)
curl "http://localhost:8000/api/v1/bookings/1?user_id=2" | jq

14. List User's Bookings
bash# All bookings for user 1
curl "http://localhost:8000/api/v1/bookings?user_id=1" | jq

# Only HOLD bookings
curl "http://localhost:8000/api/v1/bookings?user_id=1&status=HOLD" | jq

# Only CONFIRMED bookings
curl "http://localhost:8000/api/v1/bookings?user_id=1&status=CONFIRMED" | jq

15. Confirm a Booking
bash# Confirm booking 1
curl -X POST "http://localhost:8000/api/v1/bookings/1/confirm?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "pi_test_123456789"
  }' | jq
Expected Response:
json{
  "id": 1,
  "status": "CONFIRMED",
  "payment_id": "pi_test_123456789",
  "confirmed_at": "2024-12-10T20:42:00",
  "hold_expires_at": null,
  "time_remaining_seconds": 0
}

16. Try to Confirm Already Confirmed Booking (Should Fail)
bashcurl -X POST "http://localhost:8000/api/v1/bookings/1/confirm?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "pi_another_123"
  }' | jq

17. Cancel a Booking
bash# Cancel booking 2
curl -X DELETE "http://localhost:8000/api/v1/bookings/2?user_id=2" | jq
Expected Response:
json{
  "id": 2,
  "status": "CANCELLED",
  "cancelled_at": "2024-12-10T20:43:00"
}

18. Try to Book Too Many Seats (Should Fail)
bash# Try to book 11 seats (max is 10)
curl -X POST "http://localhost:8000/api/v1/bookings?user_id=3" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": 1,
    "seat_ids": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
  }' | jq
Expected Response (422 Validation Error):
json{
  "detail": [
    {
      "loc": ["body", "seat_ids"],
      "msg": "ensure this value has at most 10 items"
    }
  ]
}

19. Try to Create Too Many Active Holds (Should Fail)
bash# User 1 creates 3 holds
curl -X POST "http://localhost:8000/api/v1/bookings?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{"event_id": 1, "seat_ids": [7, 8]}' | jq

curl -X POST "http://localhost:8000/api/v1/bookings?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{"event_id": 1, "seat_ids": [9, 10]}' | jq

curl -X POST "http://localhost:8000/api/v1/bookings?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{"event_id": 1, "seat_ids": [11, 12]}' | jq

# 4th hold should fail (max 3 active holds)
curl -X POST "http://localhost:8000/api/v1/bookings?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{"event_id": 1, "seat_ids": [13, 14]}' | jq

20. Test Hold Expiration
bash# Create a booking
curl -X POST "http://localhost:8000/api/v1/bookings?user_id=3" \
  -H "Content-Type: application/json" \
  -d '{"event_id": 2, "seat_ids": [1, 2]}' | jq

# Wait 5+ minutes (or change HOLD_DURATION_MINUTES in .env to 1 minute for testing)
# The background worker will expire it automatically

# Try to confirm expired booking
curl -X POST "http://localhost:8000/api/v1/bookings/X/confirm?user_id=3" \
  -H "Content-Type: application/json" \
  -d '{"payment_id": "pi_test"}' | jq