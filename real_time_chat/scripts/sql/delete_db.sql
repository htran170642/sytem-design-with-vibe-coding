-- Terminate all connections to chatdb
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = 'chatdb'
  AND pid <> pg_backend_pid();

-- Drop the database
DROP DATABASE IF EXISTS chatdb;

-- Display success message
SELECT 'Database deleted successfully!' AS status;

-- List remaining databases
\l