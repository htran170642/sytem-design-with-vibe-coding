 python3 ./tests/concurrency/test_double_booking.py 
INFO:__main__:✅ Server is running
INFO:__main__:🧹 Resetting test seats...
✅ Found .env at: /home/hieptt/dev/practice/python/vide_coding_python/event_ticketing_system/.env
INFO:__main__:✅ Reset 5 seats to AVAILABLE
INFO:__main__:🚀 Starting concurrent booking test with 100 users
INFO:__main__:📍 Target seats: [1, 2, 3, 4, 5]
INFO:__main__:⚡ Sending 100 concurrent requests...
INFO:__main__:✅ All requests completed in 1.82s
INFO:__main__:============================================================
INFO:__main__:📊 TEST RESULTS
INFO:__main__:============================================================
INFO:__main__:Total requests: 100
INFO:__main__:Successful bookings: 1
INFO:__main__:Failed bookings: 99
INFO:__main__:
INFO:__main__:Status codes:
INFO:__main__:  201: 1
INFO:__main__:  409: 99
INFO:__main__:
INFO:__main__:Response times:
INFO:__main__:  Average: 1433.20ms
INFO:__main__:  Min: 1136.86ms
INFO:__main__:  Max: 1817.32ms
INFO:__main__:
INFO:__main__:Throughput: 54.85 req/s
INFO:__main__:============================================================
INFO:__main__:
INFO:__main__:🔍 VALIDATION:
INFO:__main__:✅ PASS: Exactly 1 booking succeeded (no double booking!)
INFO:__main__:   Winner: User 10
INFO:__main__:   Booking ID: 149
INFO:__main__:✅ PASS: Good number of conflicts (99)
INFO:__main__:============================================================
ERROR:__main__:❌ SQLAlchemy verification failed: greenlet_spawn has not been called; can't call await_only() here. Was IO attempted in an unexpected place? (Background on this error at: https://sqlalche.me/e/20/xd2s)
INFO:__main__:
INFO:__main__:🎉 ALL TESTS PASSED!