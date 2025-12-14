"""
Data management script for the chat application
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.database import SessionLocal
from app.models import User, Message

def truncate_all():
    """Truncate all tables"""
    db = SessionLocal()
    try:
        # Using TRUNCATE is faster than DELETE
        db.execute(text("TRUNCATE TABLE messages RESTART IDENTITY CASCADE"))
        db.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        db.commit()
        print("✓ All tables truncated")
    except Exception as e:
        print(f"✗ Error: {e}")
        db.rollback()
    finally:
        db.close()


def delete_old_messages(days=7):
    """Delete messages older than N days"""
    db = SessionLocal()
    try:
        deleted = db.execute(text(f"""
            DELETE FROM messages 
            WHERE created_at < NOW() - INTERVAL '{days} days'
        """))
        db.commit()
        print(f"✓ Deleted {deleted.rowcount} messages older than {days} days")
    except Exception as e:
        print(f"✗ Error: {e}")
        db.rollback()
    finally:
        db.close()


def vacuum_database():
    """Reclaim space after deletions"""
    db = SessionLocal()
    try:
        # Close current connection
        db.close()
        
        # Need a separate connection for VACUUM
        from sqlalchemy import create_engine
        engine = create_engine("postgresql://user:pass@localhost:5432/chatdb")
        conn = engine.connect()
        conn.execution_options(isolation_level="AUTOCOMMIT")
        
        print("Running VACUUM ANALYZE...")
        conn.execute(text("VACUUM ANALYZE messages"))
        conn.execute(text("VACUUM ANALYZE users"))
        conn.close()
        
        print("✓ Database vacuumed")
    except Exception as e:
        print(f"✗ Error: {e}")


def show_table_sizes():
    """Show size of each table"""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                table_name,
                pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) as size
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY pg_total_relation_size(quote_ident(table_name)) DESC
        """))
        
        print("\n=== Table Sizes ===")
        for row in result:
            print(f"{row[0]:20} {row[1]}")
        
    finally:
        db.close()


if __name__ == "__main__":
    print("\n=== Data Management ===\n")
    print("1) Truncate all data")
    print("2) Delete messages older than 7 days")
    print("3) Delete messages older than 30 days")
    print("4) Show table sizes")
    print("5) Vacuum database (reclaim space)")
    
    choice = input("\nChoice: ")
    
    if choice == "1":
        confirm = input("Delete ALL data? (yes/no): ")
        if confirm == 'yes':
            truncate_all()
    elif choice == "2":
        delete_old_messages(7)
        vacuum_database()
    elif choice == "3":
        delete_old_messages(30)
        vacuum_database()
    elif choice == "4":
        show_table_sizes()
    elif choice == "5":
        vacuum_database()