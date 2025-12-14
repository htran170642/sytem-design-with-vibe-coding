import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        database="chatdb",
        user="user",
        password="pass"
    )
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM messages;")
    count = cursor.fetchone()[0]
    
    print(f"✓ Connected! Messages count: {count}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"✗ Connection failed: {e}")