"""
Database management utilities
"""
from sqlalchemy import text, inspect
from app.database import engine, SessionLocal
from app.models import Base
import logging

logger = logging.getLogger(__name__)


def init_db():
    """
    Initialize database - create all tables
    """
    print("\n" + "="*60)
    print("INITIALIZING DATABASE")
    print("="*60)
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        print("\n✅ Database tables created successfully!")
        
        # List created tables
        print("\nCreated tables:")
        for table in Base.metadata.sorted_tables:
            print(f"  - {table.name}")
        
        # Show indexes
        print("\nIndexes:")
        for table in Base.metadata.sorted_tables:
            for index in table.indexes:
                print(f"  - {table.name}.{index.name}")
        
        print("\n" + "="*60)
        print("DATABASE INITIALIZATION COMPLETE")
        print("="*60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return False


def drop_db():
    """
    Drop all database tables (DANGEROUS!)
    """
    print("\n" + "="*60)
    print("⚠️  WARNING: DROPPING ALL DATABASE TABLES")
    print("="*60)
    
    # Ask for confirmation
    confirmation = input("\nType 'YES' to confirm dropping all tables: ")
    
    if confirmation != "YES":
        print("\n❌ Operation cancelled")
        return False
    
    try:
        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        
        print("\n✅ All tables dropped successfully!")
        
        print("\n" + "="*60)
        print("DATABASE TABLES DROPPED")
        print("="*60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error dropping database: {e}")
        import traceback
        traceback.print_exc()
        return False


def reset_db():
    """
    Reset database - drop and recreate all tables
    """
    print("\n" + "="*60)
    print("RESETTING DATABASE")
    print("="*60)
    
    # Drop tables
    if drop_db():
        # Recreate tables
        return init_db()
    
    return False


def check_db():
    """
    Check database connection and show table info
    """
    print("\n" + "="*60)
    print("DATABASE STATUS CHECK")
    print("="*60)
    
    try:
        db = SessionLocal()
        
        # Test connection
        result = db.execute(text("SELECT version()"))
        pg_version = result.fetchone()[0]
        print(f"\n✓ PostgreSQL Version: {pg_version.split(',')[0]}")
        
        # Get database name
        result = db.execute(text("SELECT current_database()"))
        db_name = result.fetchone()[0]
        print(f"✓ Database Name: {db_name}")
        
        # Get current user
        result = db.execute(text("SELECT current_user"))
        db_user = result.fetchone()[0]
        print(f"✓ Database User: {db_user}")
        
        # Get schema
        result = db.execute(text("SELECT current_schema()"))
        db_schema = result.fetchone()[0]
        print(f"✓ Schema: {db_schema}")
        
        # Get table count
        result = db.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """))
        table_count = result.fetchone()[0]
        print(f"✓ Tables: {table_count}")
        
        # List all tables
        if table_count > 0:
            print("\nExisting tables:")
            result = db.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            for row in result:
                print(f"  - {row[0]}")
        
        # Get row counts for each table
        print("\nRow counts:")
        tables = ['users', 'messages', 'direct_messages']
        for table in tables:
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.fetchone()[0]
                print(f"  ✓ {table}: {count:,} rows")
            except Exception as e:
                print(f"  ✗ {table}: not found or error ({e})")
        
        # Get database size
        result = db.execute(text("""
            SELECT pg_size_pretty(pg_database_size(current_database()))
        """))
        db_size = result.fetchone()[0]
        print(f"\n✓ Database Size: {db_size}")
        
        # Get index information
        print("\nIndexes:")
        result = db.execute(text("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """))
        for row in result:
            print(f"  ✓ {row[1]}.{row[2]}")
        
        # Get connection count
        result = db.execute(text("""
            SELECT count(*) 
            FROM pg_stat_activity 
            WHERE datname = current_database()
        """))
        conn_count = result.fetchone()[0]
        print(f"\n✓ Active Connections: {conn_count}")
        
        # Check for foreign keys
        print("\nForeign Keys:")
        result = db.execute(text("""
            SELECT
                tc.table_name, 
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name 
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' 
                AND tc.table_schema = 'public'
            ORDER BY tc.table_name
        """))
        for row in result:
            print(f"  ✓ {row[0]}.{row[1]} → {row[2]}.{row[3]}")
        
        db.close()
        
        print("\n" + "="*60)
        print("✅ DATABASE CHECK COMPLETE")
        print("="*60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_table_info(table_name: str):
    """
    Show detailed information about a specific table
    
    Args:
        table_name: Name of the table
    """
    print("\n" + "="*60)
    print(f"TABLE INFO: {table_name}")
    print("="*60)
    
    try:
        db = SessionLocal()
        
        # Check if table exists
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = :table_name
            )
        """), {"table_name": table_name})
        
        exists = result.fetchone()[0]
        
        if not exists:
            print(f"\n❌ Table '{table_name}' does not exist")
            db.close()
            return False
        
        # Get column information
        print("\nColumns:")
        result = db.execute(text("""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = :table_name
            ORDER BY ordinal_position
        """), {"table_name": table_name})
        
        for row in result:
            nullable = "NULL" if row[2] == "YES" else "NOT NULL"
            default = f" DEFAULT {row[3]}" if row[3] else ""
            print(f"  ✓ {row[0]}: {row[1]} {nullable}{default}")
        
        # Get row count
        result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        row_count = result.fetchone()[0]
        print(f"\n✓ Row Count: {row_count:,}")
        
        # Get table size
        result = db.execute(text("""
            SELECT pg_size_pretty(pg_total_relation_size(:table_name))
        """), {"table_name": table_name})
        table_size = result.fetchone()[0]
        print(f"✓ Table Size: {table_size}")
        
        # Get indexes
        print("\nIndexes:")
        result = db.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = :table_name
        """), {"table_name": table_name})
        
        for row in result:
            print(f"  ✓ {row[0]}")
            print(f"    {row[1]}")
        
        db.close()
        
        print("\n" + "="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error getting table info: {e}")
        import traceback
        traceback.print_exc()
        return False


def vacuum_analyze():
    """
    Run VACUUM ANALYZE on all tables to update statistics
    """
    print("\n" + "="*60)
    print("RUNNING VACUUM ANALYZE")
    print("="*60)
    
    try:
        # Note: VACUUM cannot run inside a transaction block
        # We need to use autocommit mode
        from sqlalchemy import create_engine
        from app.config import settings
        
        # Create engine with autocommit
        temp_engine = create_engine(
            settings.DATABASE_URL,
            isolation_level="AUTOCOMMIT"
        )
        
        with temp_engine.connect() as conn:
            # Get all tables
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            
            tables = [row[0] for row in result]
            
            print(f"\nVacuuming {len(tables)} table(s)...")
            
            for table in tables:
                print(f"  ✓ VACUUM ANALYZE {table}...")
                conn.execute(text(f"VACUUM ANALYZE {table}"))
            
            print("\n✅ VACUUM ANALYZE complete!")
        
        temp_engine.dispose()
        
        print("\n" + "="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error running VACUUM ANALYZE: {e}")
        import traceback
        traceback.print_exc()
        return False


def export_schema():
    """
    Export database schema as SQL
    """
    print("\n" + "="*60)
    print("EXPORTING SCHEMA")
    print("="*60)
    
    try:
        db = SessionLocal()
        
        # Get CREATE TABLE statements
        result = db.execute(text("""
            SELECT 
                'CREATE TABLE ' || table_name || E'\n(\n' ||
                array_to_string(
                    array_agg(
                        '  ' || column_name || ' ' || 
                        data_type || 
                        CASE 
                            WHEN character_maximum_length IS NOT NULL 
                            THEN '(' || character_maximum_length || ')' 
                            ELSE '' 
                        END ||
                        CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END
                    ),
                    E',\n'
                ) || E'\n);'
            FROM information_schema.columns
            WHERE table_schema = 'public'
            GROUP BY table_name
            ORDER BY table_name
        """))
        
        schema_file = "schema_export.sql"
        
        with open(schema_file, 'w') as f:
            f.write("-- Database Schema Export\n")
            f.write(f"-- Generated: {__import__('datetime').datetime.now()}\n\n")
            
            for row in result:
                f.write(row[0])
                f.write("\n\n")
        
        db.close()
        
        print(f"\n✅ Schema exported to: {schema_file}")
        print("\n" + "="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error exporting schema: {e}")
        import traceback
        traceback.print_exc()
        return False