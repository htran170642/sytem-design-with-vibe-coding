"""
Redis management script
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from redis_client import redis_client, get_stats, clear_all

def show_all_keys():
    """Show all keys in Redis"""
    keys = redis_client.keys("*")
    
    if not keys:
        print("No keys found")
        return
    
    print(f"\n=== All Keys ({len(keys)}) ===\n")
    
    for key in sorted(keys):
        key_type = redis_client.type(key)
        ttl = redis_client.ttl(key)
        
        ttl_str = f"{ttl}s" if ttl > 0 else "no expiry" if ttl == -1 else "expired"
        
        print(f"{key:50} | Type: {key_type:10} | TTL: {ttl_str}")


def show_cache_keys():
    """Show cache keys"""
    keys = redis_client.keys("messages:*")
    
    print(f"\n=== Cache Keys ({len(keys)}) ===\n")
    
    for key in sorted(keys):
        ttl = redis_client.ttl(key)
        print(f"{key} (expires in {ttl}s)")


def show_rate_limit_keys():
    """Show rate limit keys"""
    keys = redis_client.keys("rate_limit:*")
    
    print(f"\n=== Rate Limit Keys ({len(keys)}) ===\n")
    
    for key in sorted(keys):
        count = redis_client.get(key)
        ttl = redis_client.ttl(key)
        print(f"{key}: {count} requests (resets in {ttl}s)")


def clear_cache():
    """Clear cache keys only"""
    keys = redis_client.keys("messages:*")
    if keys:
        deleted = redis_client.delete(*keys)
        print(f"✓ Deleted {deleted} cache keys")
    else:
        print("No cache keys to delete")


def clear_rate_limits():
    """Clear rate limit keys"""
    keys = redis_client.keys("rate_limit:*")
    if keys:
        deleted = redis_client.delete(*keys)
        print(f"✓ Deleted {deleted} rate limit keys")
    else:
        print("No rate limit keys to delete")


if __name__ == "__main__":
    print("\n=== Redis Manager ===\n")
    print("1) Show all keys")
    print("2) Show cache keys")
    print("3) Show rate limit keys")
    print("4) Show Redis stats")
    print("5) Clear cache keys")
    print("6) Clear rate limit keys")
    print("7) Clear ALL Redis data")
    
    choice = input("\nChoice: ")
    
    if choice == "1":
        show_all_keys()
    elif choice == "2":
        show_cache_keys()
    elif choice == "3":
        show_rate_limit_keys()
    elif choice == "4":
        stats = get_stats()
        print("\n=== Redis Stats ===\n")
        for key, value in stats.items():
            print(f"{key:20} {value}")
    elif choice == "5":
        clear_cache()
    elif choice == "6":
        clear_rate_limits()
    elif choice == "7":
        confirm = input("Clear ALL Redis data? (yes/no): ")
        if confirm == "yes":
            clear_all()