"""
Database migration script
Drops old tables and creates new ones with proper indexes
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.utils.db_utils import init_db, drop_db

from app.models import Base

def migrate():
    """Run database migration"""
    print("Starting database migration...")
    
    # Drop all tables
    print("Dropping old tables...")
    drop_db()
    
    # Create new tables with indexes
    print("Creating new tables with indexes...")
    init_db()
    
    print("✓ Migration complete!")
    print("\nNew tables created:")
    print("  - users (with indexes on: id, username, email)")
    print("  - messages (with indexes on: id, user_id, room_id, created_at)")
    print("  - Composite index: (room_id, created_at)")


if __name__ == "__main__":
    response = input("WARNING: This will delete all existing data. Continue? (yes/no): ")
    if response.lower() == 'yes':
        migrate()
    else:
        print("Migration cancelled.")