# Clear Redis
redis-cli FLUSHDB

# Enable waiting room with ONLY 2 slots
curl -X POST "http://localhost:8000/api/v1/events/1/waiting-room/enable?max_concurrent=2&session_duration=60" | jq

# Terminal: Add 5 users via API
for i in {1..5}; do
  echo "User $i joining..."
  curl -s -X POST "http://localhost:8000/api/v1/events/1/waiting-room/join?user_id=$i" | jq -c "{user: $i, position: .position, estimated_wait: .estimated_wait_seconds}"
done

(base) hieptt@hieptt:~$ curl -X POST "http://localhost:8000/api/v1/events/1/waiting-room/enable?max_concurrent=2&session_duration=60" | jq
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   101  100   101    0     0  25193      0 --:--:-- --:--:-- --:--:-- 33666
{
  "message": "Waiting room enabled for event 1",
  "max_concurrent_users": 2,
  "session_duration_seconds": 60
}
(base) hieptt@hieptt:~$ for i in {1..5}; do
  echo "User $i joining..."
  curl -s -X POST "http://localhost:8000/api/v1/events/1/waiting-room/join?user_id=$i" | jq -c "{user: $i, position: .position, estimated_wait: .estimated_wait_seconds}"
done
User 1 joining...
{"user":1,"position":1,"estimated_wait":0}
User 2 joining...
{"user":2,"position":2,"estimated_wait":0}
User 3 joining...
{"user":3,"position":3,"estimated_wait":60}
User 4 joining...
{"user":4,"position":4,"estimated_wait":60}
User 5 joining...
{"user":5,"position":5,"estimated_wait":120}
(base) hieptt@hieptt:~$ curl -s http://localhost:8000/api/v1/events/1/waiting-room/stats | jq
{
  "event_id": 1,
  "queue_size": 3,
  "active_sessions": 2,
  "max_concurrent": 2,
  "slots_available": 0
}
(base) hieptt@hieptt:~$ curl -s http://localhost:8000/api/v1/events/1/waiting-room/stats | jq
{
  "event_id": 1,
  "queue_size": 1,
  "active_sessions": 2,
  "max_concurrent": 2,
  "slots_available": 0
}
