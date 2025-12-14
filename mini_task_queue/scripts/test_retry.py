import asyncio
import httpx


async def test_retry():
    """Test retry logic with failing task"""
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        
        # Test 1: Submit a task that will fail and retry
        print("--- Test 1: Submit Failing Task (will retry 3 times) ---")
        response = await client.post(
            f"{base_url}/tasks",
            json={
                "name": "failing_task",
                "args": ["test retry logic"],
                "max_retries": 3
            }
        )
        result = response.json()
        task_id = result["task_id"]
        
        print(f"Task ID: {task_id}")
        print(f"Max retries: {result['max_retries']}\n")
        
        # Wait for retries to happen
        print("Waiting 10 seconds for retries...")
        await asyncio.sleep(10)
        
        # Check final status
        print("\n--- Test 2: Check Final Status ---")
        response = await client.get(f"{base_url}/tasks/{task_id}")
        status = response.json()
        
        print(f"Status: {status['status']}")
        print(f"Retry count: {status['retry_count']}/{status['max_retries']}")
        print(f"Error: {status['error']}\n")
        
        # Check dead-letter queue
        print("--- Test 3: Check Dead-Letter Queue ---")
        response = await client.get(f"{base_url}/queue/dead-letter")
        dlq = response.json()
        
        print(f"Dead-letter queue count: {dlq['count']}")
        for task in dlq['tasks']:
            print(f"  - {task['task_id'][:8]}: {task['name']} (retried {task['retry_count']} times)")
        
        print("\n✅ Retry test completed!")


if __name__ == "__main__":
    print("Make sure API server and worker are running!\n")
    asyncio.run(test_retry())