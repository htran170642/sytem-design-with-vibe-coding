#!/usr/bin/env python3
"""
Phase 0 POC: What is Scaling?
Simple demonstration of the core scaling concept
"""

import time
import threading
from typing import List

class SimpleWebServer:
    """Simulates a simple web server processing requests"""
    
    def __init__(self, name: str, processing_time: float = 0.1):
        self.name = name
        self.processing_time = processing_time
        self.requests_processed = 0
    
    def handle_request(self, request_id: int) -> str:
        """Process a single request"""
        start_time = time.time()
        
        # Simulate processing time
        time.sleep(self.processing_time)
        
        self.requests_processed += 1
        processing_duration = time.time() - start_time
        
        return f"Request {request_id} handled by {self.name} in {processing_duration:.2f}s"

def single_server_demo(num_requests: int = 10):
    """Demonstrate single server handling requests"""
    print("🖥️  Single Server Demo")
    print("=" * 30)
    
    server = SimpleWebServer("Server-1")
    start_time = time.time()
    
    print(f"Processing {num_requests} requests sequentially...")
    
    for i in range(num_requests):
        result = server.handle_request(i + 1)
        print(f"  {result}")
    
    total_time = time.time() - start_time
    
    print(f"\n📊 Results:")
    print(f"  • Total time: {total_time:.2f} seconds")
    print(f"  • Requests processed: {server.requests_processed}")
    print(f"  • Average time per request: {total_time/num_requests:.2f}s")
    print(f"  • Throughput: {num_requests/total_time:.1f} requests/second")
    
    return total_time

def multi_server_demo(num_requests: int = 10, num_servers: int = 3):
    """Demonstrate multiple servers handling requests in parallel"""
    print(f"\n🖥️ 🖥️ 🖥️  Multi-Server Demo ({num_servers} servers)")
    print("=" * 40)
    
    servers = [SimpleWebServer(f"Server-{i+1}") for i in range(num_servers)]
    start_time = time.time()
    
    print(f"Processing {num_requests} requests in parallel...")
    
    threads = []
    results = []
    
    # Distribute requests across servers
    for i in range(num_requests):
        server = servers[i % num_servers]  # Simple round-robin
        
        def process_request(srv, req_id):
            result = srv.handle_request(req_id)
            results.append(result)
            print(f"  {result}")
        
        thread = threading.Thread(target=process_request, args=(server, i + 1))
        threads.append(thread)
        thread.start()
    
    # Wait for all requests to complete
    for thread in threads:
        thread.join()
    
    total_time = time.time() - start_time
    total_processed = sum(server.requests_processed for server in servers)
    
    print(f"\n📊 Results:")
    print(f"  • Total time: {total_time:.2f} seconds")
    print(f"  • Requests processed: {total_processed}")
    print(f"  • Load distribution: {[s.requests_processed for s in servers]}")
    print(f"  • Throughput: {num_requests/total_time:.1f} requests/second")
    
    return total_time

def scaling_comparison():
    """Compare single vs multi-server performance"""
    print("🎯 Phase 0: Understanding Scaling")
    print("=" * 35)
    print("Let's see what happens when we scale from 1 server to multiple servers...\n")
    
    num_requests = 12  # Divisible by common server counts
    
    # Test single server
    single_time = single_server_demo(num_requests)
    
    # Test multiple servers
    multi_time = multi_server_demo(num_requests, num_servers=3)
    
    # Show the improvement
    improvement = ((single_time - multi_time) / single_time) * 100
    speedup = single_time / multi_time
    
    print(f"\n🚀 Scaling Impact:")
    print(f"  • Time reduction: {improvement:.1f}%")
    print(f"  • Speed improvement: {speedup:.1f}x faster")
    print(f"  • This is HORIZONTAL SCALING - adding more servers")
    
    print(f"\n💡 Key Insights:")
    print(f"  • Single server: processes requests one by one (sequential)")
    print(f"  • Multiple servers: process requests simultaneously (parallel)")
    print(f"  • More servers = higher throughput (requests/second)")
    print(f"  • But also more complexity (coordination, load balancing)")

def vertical_scaling_demo():
    """Demonstrate vertical scaling concept"""
    print(f"\n⬆️  Vertical Scaling Demo")
    print("=" * 30)
    print("What if instead of adding servers, we make our server faster?")
    
    # Slower server
    slow_server = SimpleWebServer("Slow-Server", processing_time=0.2)
    
    # Faster server (2x capacity)
    fast_server = SimpleWebServer("Fast-Server", processing_time=0.1)
    
    num_requests = 5
    
    print(f"\nTesting {num_requests} requests:")
    
    # Test slow server
    start_time = time.time()
    for i in range(num_requests):
        slow_server.handle_request(i + 1)
    slow_time = time.time() - start_time
    
    # Test fast server  
    start_time = time.time()
    for i in range(num_requests):
        fast_server.handle_request(i + 1)
    fast_time = time.time() - start_time
    
    print(f"  • Slow server (0.2s per request): {slow_time:.2f}s total")
    print(f"  • Fast server (0.1s per request): {fast_time:.2f}s total")
    print(f"  • Improvement: {fast_time/slow_time:.1f}x faster")
    
    print(f"\n💡 This is VERTICAL SCALING:")
    print(f"  • Same number of servers, but more powerful")
    print(f"  • Upgrade CPU, RAM, or storage")
    print(f"  • Simpler than horizontal scaling")
    print(f"  • But has limits - can't scale infinitely")

if __name__ == "__main__":
    scaling_comparison()
    vertical_scaling_demo()
    
    print(f"\n🎓 What We Just Learned:")
    print(f"  • HORIZONTAL SCALING: Add more servers (scale out)")
    print(f"  • VERTICAL SCALING: Make servers more powerful (scale up)")
    print(f"  • Both approaches help handle more load")
    print(f"  • Each has different trade-offs and limitations")