import asyncio
import websockets
import json
import httpx


async def watch_task(task_id: str):
    """Connect to WebSocket and watch task progress"""
    
    uri = f"ws://localhost:8000/ws/tasks/{task_id}"
    
    print(f"🔌 Connecting to WebSocket for task {task_id[:8]}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected! Waiting for events...\n")
            
            # Receive messages
            async for message in websocket:
                data = json.loads(message)
                
                event = data.get("event", "unknown")
                
                if event == "connected":
                    print(f"📡 {data['message']}")
                    print(f"   Current status: {data['current_status']}\n")
                
                elif event == "started":
                    print(f"🚀 Task started")
                    print(f"   Worker: {data['data']['worker_id']}")
                    print(f"   Task: {data['data']['task_name']}\n")
                
                elif event == "progress":
                    progress = data['data']
                    print(f"📊 Progress: {progress['step']}/{progress['total_steps']} ({progress['progress_percent']:.0f}%)")
                    print(f"   {progress['message']}\n")
                
                elif event == "completed":
                    print(f"✅ Task completed!")
                    print(f"   Result: {data['data']['result']}")
                    print(f"   Duration: {data['data']['duration']:.2f}s")
                    print(f"   Worker: {data['data']['worker_id']}\n")
                
                elif event == "failed":
                    print(f"❌ Task failed!")
                    print(f"   Error: {data['data']['error']}\n")
                
                elif event == "stream_end":
                    print(f"👋 {data['message']}")
                    break
                
                else:
                    print(f"📨 Unknown event: {data}")
    
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def submit_and_watch():
    """Submit a long task and watch it in real-time"""
    
    base_url = "http://localhost:8000"
    
    # Submit a long task
    async with httpx.AsyncClient() as client:
        print("📤 Submitting long_task with 5 steps...")
        response = await client.post(
            f"{base_url}/tasks",
            json={"name": "long_task", "args": [5]}
        )
        
        result = response.json()
        task_id = result["task_id"]
        
        print(f"✅ Task submitted: {task_id}\n")
    
    # Watch the task
    await watch_task(task_id)


if __name__ == "__main__":
    print("Make sure API server and worker are running!\n")
    asyncio.run(submit_and_watch())