curl http://localhost:8000/auctions
clear
curl -X GET "http://localhost:8000/" | jq
sudo apt install jq
curl -X GET "http://localhost:8000/" | jq
curl -X POST "http://localhost:8000/auctions"   -H "Content-Type: application/json"   -d '{
    "title": "Vintage Rolex Watch",
    "description": "Rare 1960s Submariner",
    "starting_price": 5000,
    "min_increment": 100,
    "duration_minutes": 120
  }' | jq
 curl -X POST "http://localhost:8000/auctions"   -H "Content-Type: application/json"   -d '{
    "title": "MacBook Pro M3",
    "description": "Brand new sealed",
    "starting_price": 2000,
    "min_increment": 50,
    "duration_minutes": 60
  }' | jq
curl -X POST "http://localhost:8000/auctions"   -H "Content-Type: application/json"   -d '{
    "title": "Signed Basketball",
    "description": "Michael Jordan autograph",
    "starting_price": 1000,
    "min_increment": 25,
    "duration_minutes": 90
  }' | jq
 curl -X POST "http://localhost:8000/auctions"   -H "Content-Type: application/json"   -d '{
    "title": "Invalid Auction",
    "description": "Should fail",
    "starting_price": -100,
    "min_increment": 10,
    "duration_minutes": 60
  }' | jq
curl -X GET "http://localhost:8000/auctions" | jq
curl -X GET "http://localhost:8000/auctions?status=ACTIVE" | jq
curl -X GET "http://localhost:8000/auctions/13" | jq
curl -X GET "http://localhost:8000/auctions/13/statistics" | jq
curl -X GET "http://localhost:8000/auctions/99999" | jq
curl -X POST "http://localhost:8000/bids/auctions/15/bids/async"   -H "Content-Type: application/json"   -d '{
    "user_id": 101,
    "bid_amount": 5100
  }' | jq
curl -X POST "http://localhost:8000/bids/auctions/15/bids/async"   -H "Content-Type: application/json"   -d '{
    "user_id": 102,
    "bid_amount": 5200
  }' | jq
curl -X POST "http://localhost:8000/bids/auctions/15/bids/async"   -H "Content-Type: application/json"   -d '{
    "user_id": 101,
    "bid_amount": 5300
  }' | jq
curl -X POST "http://localhost:8000/bids/auctions/15/bids/async"   -H "Content-Type: application/json"   -d '{
    "user_id": 104,
    "bid_amount": 5000
  }' | jq
curl -X POST "http://localhost:8000/bids/auctions/99999/bids/async"   -H "Content-Type: application/json"   -d '{
    "user_id": 101,
    "bid_amount": 1000
  }' | jq
curl -X GET "http://localhost:8000/bids/15/status" | jq
curl -X GET "http://localhost:8000/bids/9819ca54-05d4-482f-b976-8025b45111df/status" | jq
curl -X GET "http://localhost:8000/bids/auctions/15/bids" | jq
curl -X GET "http://localhost:8000/bids/users/101/bids" | jq
curl -X GET "http://localhost:8000/bids/users/102/bids" | jq
curl -X GET "http://localhost:8000/bids/users/101/winning" | jq
curl -X GET "http://localhost:8000/bids/users/103/winning" | jq
curl -X GET "http://localhost:8000/admin/cache-stats" | jq
curl -X GET "http://localhost:8000/admin/queue-stats" | jq
curl -X GET "http://localhost:8000/admin/pubsub-stats" | jq