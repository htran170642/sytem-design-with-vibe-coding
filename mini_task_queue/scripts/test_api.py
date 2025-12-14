import asyncio
import httpx
import time


async def test_api():
    """Test the API endpoints"""
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        
        # Test 1: Health check
        print("--- Test 1: Health Check ---")
        response = await client.get(f"{base_url}/")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}\n")
        
        # Test 2: Submit task
        print("--- Test 2: Submit Task ---")
        task_data = {
            "name": "multiply",
            "args": [6, 7]
        }
        response = await client.post(f"{base_url}/tasks", json=task_data)
        result = response.json()
        task_id = result["task_id"]
        print(f"Task ID: {task_id}")
        print(f"Status: {result['status']}\n")
        
        # Test 3: Check status immediately
        print("--- Test 3: Check Status (Immediately) ---")
        response = await client.get(f"{base_url}/tasks/{task_id}")
        status = response.json()
        print(f"Status: {status['status']}")
        print(f"Result: {status['result']}\n")
        
        # Test 4: Wait and check again
        print("--- Test 4: Wait 2 seconds and check again ---")
        await asyncio.sleep(2)
        response = await client.get(f"{base_url}/tasks/{task_id}")
        status = response.json()
        print(f"Status: {status['status']}")
        print(f"Result: {status['result']}\n")
        
        # Test 5: Submit multiple tasks
        print("--- Test 5: Submit Multiple Tasks ---")
        tasks_to_submit = [
            {"name": "add", "args": [i, i+1]}
            for i in range(5)
        ]
        
        # Use asyncio.gather for concurrent submission
        responses = await asyncio.gather(*[
            client.post(f"{base_url}/tasks", json=task)
            for task in tasks_to_submit
        ])
        
        task_ids = [r.json()["task_id"] for r in responses]
        print(f"Submitted {len(task_ids)} tasks\n")
        
        # Test 6: Queue stats
        print("--- Test 6: Queue Stats ---")
        response = await client.get(f"{base_url}/queue/stats")
        stats = response.json()
        print(f"Queue length: {stats['queue_length']}")
        print(f"Queue name: {stats['queue_name']}\n")
        
        # Test 7: Check all tasks after worker processes them
        print("--- Test 7: Wait 3 seconds and check all tasks ---")
        await asyncio.sleep(3)
        
        for i, tid in enumerate(task_ids):
            response = await client.get(f"{base_url}/tasks/{tid}")
            status = response.json()
            print(f"Task {i}: {status['status']} - Result: {status['result']}")
        
        print("\n✅ All API tests completed!")


if __name__ == "__main__":
    print("Make sure API server is running: python run_api.py")
    print("And worker is running: python -m app.worker\n")
    asyncio.run(test_api())