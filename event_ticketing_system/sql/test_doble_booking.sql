UPDATE event_seats SET status = 'AVAILABLE', current_booking_id = NULL WHERE id IN (1,2,3,4,5);

SELECT id, status, current_booking_id 
            FROM event_seats 
            WHERE id IN (1,2,3,4,5)
            ORDER BY id;

select * from users;


INSERT INTO users (id, email, full_name, password_hash, created_at, updated_at) 
SELECT 
    generate_series AS id,
    'test_user_' || generate_series || '@example.com' AS email,
    'Test User ' || generate_series AS full_name,
    'test_hash_' || generate_series AS password_hash,
    NOW() AS created_at, NOW() AS updated_at
FROM generate_series(1, 100)
ON CONFLICT (id) DO NOTHING;


// remember to flushdb in redis berore running this test