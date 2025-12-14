curl -X POST "http://localhost:8000/users/register?username=Alice&email=alice@example.com"

docker exec -it redis redis-cli


# Connect to Redis
docker exec -it redis redis-cli

# Show all keys
KEYS *

# Get a specific value
GET "messages:general:50:latest"

# Check TTL (time to live)
TTL "messages:general:50:latest"

# Monitor commands in real-time
MONITOR

# Exit
exit


# See what's in cache
docker exec -it redis redis-cli KEYS "messages:*"

# See rate limit keys
docker exec -it redis redis-cli KEYS "rate_limit:*"

# Count all keys
docker exec -it redis redis-cli DBSIZE