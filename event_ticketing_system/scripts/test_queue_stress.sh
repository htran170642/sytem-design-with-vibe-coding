#!/bin/bash

echo "=== Enable waiting room (5 concurrent users) ==="
curl -s -X POST "http://localhost:8000/api/v1/events/1/waiting-room/enable?max_concurrent=5&session_duration=60" | jq

echo -e "\n=== Add 20 users to queue ==="
declare -a TOKENS
for user_id in {1..20}; do
  TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/events/1/waiting-room/join?user_id=$user_id" | jq -r '.token')
  TOKENS[$user_id]=$TOKEN
  echo "User $user_id: Token=${TOKEN:0:8}..."
done

echo -e "\n=== Check stats ==="
curl -s "http://localhost:8000/api/v1/events/1/waiting-room/stats" | jq

echo -e "\n=== Admit first 5 users ==="
for user_id in {1..5}; do
  echo "User $user_id checking status..."
  curl -s "http://localhost:8000/api/v1/events/1/waiting-room/status?token=${TOKENS[$user_id]}" | jq -c '{admitted, status}'
done

echo -e "\n=== Check stats after admission ==="
curl -s "http://localhost:8000/api/v1/events/1/waiting-room/stats" | jq

echo -e "\n=== User 6 tries to book (should be waiting) ==="
curl -s "http://localhost:8000/api/v1/events/1/waiting-room/status?token=${TOKENS[6]}" | jq

echo -e "\n=== User 1 creates booking with valid token ==="
curl -X POST "http://localhost:8000/api/v1/bookings?user_id=1" \
  -H "Content-Type: application/json" \
  -H "X-Waiting-Room-Token: ${TOKENS[1]}" \
  -d '{
    "event_id": 1,
    "seat_ids": [310, 311]
  }' | jq '{id, status, user_id}'

echo -e "\n=== User 6 tries to book without being admitted ==="
curl -X POST "http://localhost:8000/api/v1/bookings?user_id=6" \
  -H "Content-Type: application/json" \
  -H "X-Waiting-Room-Token: ${TOKENS[6]}" \
  -d '{
    "event_id": 1,
    "seat_ids": [312, 313]
  }' | jq

echo -e "\n=== Final stats ==="
curl -s "http://localhost:8000/api/v1/events/1/waiting-room/stats" | jq
