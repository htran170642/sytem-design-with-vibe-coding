"""
Watch the connection pool grow under load
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from database import engine, SessionLocal, get_pool_status, print_pool_status
from sqlalchemy import text
import time

print("=== Initial Pool Status ===")
print_pool_status()

print("\n=== Creating 10 concurrent connections ===\n")

connections = []

for i in range(10):
    conn = engine.connect()
    connections.append(conn)
    
    status = get_pool_status()
    print(f"Connection {i+1}: size={status['pool_size']}, "
          f"checked_in={status['checked_in']}, "
          f"checked_out={status['checked_out']}")
    
    time.sleep(0.1)

print("\n=== After Creating Connections ===")
print_pool_status()

print("\n=== Closing all connections ===\n")

for i, conn in enumerate(connections):
    conn.close()
    
    status = get_pool_status()
    print(f"Closed {i+1}: size={status['pool_size']}, "
          f"checked_in={status['checked_in']}, "
          f"checked_out={status['checked_out']}")

print("\n=== Final Pool Status ===")
print_pool_status()

print("\n=== Key Insight ===")
status = get_pool_status()
print(f"Pool grew from 1 to {status['pool_size']} connections")
print(f"All {status['checked_in']} connections are now available for reuse")
print("✓ This is normal and efficient behavior!")