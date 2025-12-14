
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import time
import random
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import User, Message

DATABASE_URL = "postgresql://user:pass@localhost:5432/chatdb"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def insert_test_data(num_users=10, messages_per_user=1000):
    """Insert test data"""
    db = SessionLocal()
    
    print(f"Inserting {num_users} users...")
    users = []
    for i in range(num_users):
        user = User(
            username=f"user_{i}",
            email=f"user_{i}@test.com"
        )
        db.add(user)
        users.append(user)
    
    db.commit()
    
    print(f"Inserting {num_users * messages_per_user} messages...")
    for user in users:
        for j in range(messages_per_user):
            msg = Message(
                user_id=user.id,
                room_id="general",
                content=f"Test message {j} from {user.username}"
            )
            db.add(msg)
        
        if (users.index(user) + 1) % 2 == 0:
            db.commit()
            print(f"  Inserted messages for {users.index(user) + 1}/{num_users} users")
    
    db.commit()
    db.close()
    print("✓ Test data inserted!")

def test_query_performance():
    """Test query performance with and without index"""
    db = SessionLocal()
    
    # Test 1: Query with composite index
    print("\nTest 1: Query using composite index (room_id, created_at)")
    start = time.time()
    result = db.execute(text("""
        SELECT * FROM messages 
        WHERE room_id = 'general' 
        ORDER BY created_at DESC 
        LIMIT 50
    """))
    result.fetchall()
    elapsed = time.time() - start
    print(f"  Time: {elapsed*1000:.2f}ms")
    
    # Test 2: Pagination query
    print("\nTest 2: Cursor-based pagination")
    start = time.time()
    result = db.execute(text("""
        SELECT * FROM messages 
        WHERE room_id = 'general' AND id < 5000
        ORDER BY created_at DESC 
        LIMIT 50
    """))
    result.fetchall()
    elapsed = time.time() - start
    print(f"  Time: {elapsed*1000:.2f}ms")
    
    # Test 3: Count query
    print("\nTest 3: Count messages per user")
    start = time.time()
    result = db.execute(text("""
        SELECT user_id, COUNT(*) 
        FROM messages 
        GROUP BY user_id
    """))
    result.fetchall()
    elapsed = time.time() - start
    print(f"  Time: {elapsed*1000:.2f}ms")
    
    db.close()

if __name__ == "__main__":
    choice = input("1) Insert test data\n2) Test performance\nChoice: ")
    
    if choice == "1":
        insert_test_data(num_users=10, messages_per_user=1000)
    elif choice == "2":
        test_query_performance()