# Create database
docker exec -i postgres psql -U user -d postgres < create_db.sql

# View messages
docker exec -i postgres psql -U user -d chatdb < view_messages.sql

# Clear messages
docker exec -i postgres psql -U user -d chatdb < clear_messages.sql

# Check status
docker exec -i postgres psql -U user -d chatdb < db_status.sql

# Reset database
docker exec -i postgres psql -U user -d postgres < reset_db.sql

# Delete database
docker exec -i postgres psql -U user -d postgres < delete_db.sql

# Insert sample data
docker exec -i postgres psql -U user -d chatdb < sample_data.sql



# Check if PostgreSQL is already running
sudo systemctl status postgresql

# Or check what's using port 5432
sudo lsof -i :5432
```

If PostgreSQL is running, you'll see something like:
```
● postgresql.service - PostgreSQL RDBMS
   Active: active (running)


# Stop PostgreSQL service
sudo systemctl stop postgresql

# Verify it's stopped
sudo systemctl status postgresql



Step 2: Open pgAdmin
Open browser and go to: http://localhost:8080

Email: admin@admin.com
Password: admin

Step 3: Add PostgreSQL Server

Click "Add New Server" (or right-click Servers → Register → Server)
In General tab:

Name: Chat Database


In Connection tab:

Host: postgres (the container name)
Port: 5432
Username: user
Password: pass
Save password: ✓ (check this)