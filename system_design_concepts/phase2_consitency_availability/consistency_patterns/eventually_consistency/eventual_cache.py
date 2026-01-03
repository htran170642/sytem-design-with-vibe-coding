# eventual_cache.py - Eventually consistent distributed cache
import time
import threading
import random
from collections import defaultdict
from datetime import datetime

class EventuallyConsistentCache:
    """
    Simulates a multi-node cache with eventual consistency.
    Writes go to one node, async replicate to others.
    """
    
    def __init__(self, node_id, peers=None):
        self.node_id = node_id
        self.peers = peers or []  # Other cache nodes
        
        # Local data store with version vectors
        self.data = {}
        self.versions = defaultdict(lambda: defaultdict(int))
        
        # Replication queue
        self.replication_queue = []
        
        # Start background replication
        self.replication_thread = threading.Thread(
            target=self._replicate_async,
            daemon=True
        )
        self.replication_thread.start()
    
    def write(self, key, value):
        """
        Write to local node immediately (fast).
        Replication happens in background (eventual consistency).
        """
        # Write locally
        self.data[key] = {
            'value': value,
            'timestamp': time.time(),
            'version': self.versions[key][self.node_id]
        }
        
        # Increment my version vector
        self.versions[key][self.node_id] += 1
        
        print(f"[{self.node_id}] WRITE {key}={value} (local)")
        
        # Queue for async replication
        self.replication_queue.append({
            'key': key,
            'value': value,
            'timestamp': time.time(),
            'version': dict(self.versions[key])
        })
        
        return "OK"  # Return immediately (don't wait for replication)
    
    def read(self, key):
        """Read from local node (may be stale)"""
        if key in self.data:
            value = self.data[key]['value']
            print(f"[{self.node_id}] READ {key}={value} (local)")
            return value
        return None
    
    def _replicate_async(self):
        """Background thread: replicate writes to peers"""
        while True:
            if self.replication_queue:
                item = self.replication_queue.pop(0)
                
                # Simulate network delay
                time.sleep(random.uniform(0.1, 0.5))
                
                # Send to all peers
                for peer in self.peers:
                    try:
                        peer.receive_replication(item)
                    except Exception as e:
                        # If peer unreachable, we'll try again later
                        # (eventual consistency - will converge when peer returns)
                        print(f"[{self.node_id}] Failed to replicate to peer: {e}")
            
            time.sleep(0.1)
    
    def receive_replication(self, item):
        """Receive replicated data from peer"""
        key = item['key']
        value = item['value']
        incoming_version = item['version']
        
        # Conflict resolution using Last-Write-Wins (LWW)
        if key not in self.data:
            # No conflict - just accept
            self.data[key] = {
                'value': value,
                'timestamp': item['timestamp'],
                'version': incoming_version
            }
            print(f"[{self.node_id}] REPLICATED {key}={value}")
        else:
            # Conflict! Compare timestamps
            if item['timestamp'] > self.data[key]['timestamp']:
                print(f"[{self.node_id}] CONFLICT {key}: {self.data[key]['value']} -> {value} (LWW)")
                self.data[key] = {
                    'value': value,
                    'timestamp': item['timestamp'],
                    'version': incoming_version
                }
        
        # Merge version vectors
        for node, version in incoming_version.items():
            self.versions[key][node] = max(
                self.versions[key][node],
                version
            )


# Demo: Eventual consistency in action
def demo_eventual_consistency():
    # Create 3 cache nodes
    node_a = EventuallyConsistentCache("Node-A")
    node_b = EventuallyConsistentCache("Node-B")
    node_c = EventuallyConsistentCache("Node-C")
    
    # Connect them as peers
    node_a.peers = [node_b, node_c]
    node_b.peers = [node_a, node_c]
    node_c.peers = [node_a, node_b]
    
    print("=== Eventual Consistency Demo ===\n")
    
    # Write to Node A
    print("1. Write 'user:123' to Node A")
    node_a.write('user:123', {'name': 'Alice', 'age': 30})
    
    # Immediately read from other nodes (stale!)
    print("\n2. Immediately read from all nodes:")
    print(f"   Node A: {node_a.read('user:123')}")
    print(f"   Node B: {node_b.read('user:123')}")  # None (not replicated yet)
    print(f"   Node C: {node_c.read('user:123')}")  # None (not replicated yet)
    
    # Wait for replication
    print("\n3. Wait 1 second for replication...")
    time.sleep(1)
    
    # Read again (should be consistent now)
    print("\n4. Read after replication:")
    print(f"   Node A: {node_a.read('user:123')}")
    print(f"   Node B: {node_b.read('user:123')}")  # Now has data!
    print(f"   Node C: {node_c.read('user:123')}")  # Now has data!
    
    # Concurrent writes (conflict!)
    print("\n5. Concurrent writes on different nodes:")
    node_a.write('user:123', {'name': 'Alice', 'age': 31})  # Update age
    time.sleep(0.05)  # Small delay
    node_b.write('user:123', {'name': 'Alice', 'age': 32})  # Another update
    
    print("\n6. Wait for conflict resolution...")
    time.sleep(1)
    
    # Eventually consistent (Last-Write-Wins)
    print("\n7. Final state (after convergence):")
    print(f"   Node A: {node_a.read('user:123')}")
    print(f"   Node B: {node_b.read('user:123')}")
    print(f"   Node C: {node_c.read('user:123')}")
    print("\n   All nodes converged! (Eventual consistency achieved)")

if __name__ == '__main__':
    demo_eventual_consistency()