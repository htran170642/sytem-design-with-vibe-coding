"""
Comprehensive API Routes Tests

Tests all endpoints:
- Auctions (create, list, get, statistics)
- Bids (place, status, history, user bids, winning)
- Admin (cache, queue, pubsub, health)
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ============================================================================
# AUCTION TESTS
# ============================================================================
class TestAuctionRoutes:
    """Test auction-related endpoints"""
    
    def test_create_auction_success(self):
        """Test creating a valid auction"""
        response = client.post("/auctions", json={
            "title": "Test Auction",
            "description": "Test Description",
            "starting_price": 1000.0,
            "min_increment": 50.0,
            "duration_minutes": 60
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "auction" in data
        assert data["auction"]["title"] == "Test Auction"
        assert data["auction"]["starting_price"] == 1000.0
        assert data["auction"]["status"] == "ACTIVE"
        
        # Store auction_id for other tests
        pytest.auction_id = data["auction"]["auction_id"]
    
    def test_create_auction_invalid_price(self):
        """Test creating auction with invalid price"""
        response = client.post("/auctions", json={
            "title": "Invalid Auction",
            "description": "Test",
            "starting_price": -100.0,  # Invalid!
            "min_increment": 50.0,
            "duration_minutes": 60
        })
        
        assert response.status_code == 400
        assert "positive" in response.json()["detail"].lower()
    
    def test_create_auction_invalid_increment(self):
        """Test creating auction with invalid increment"""
        response = client.post("/auctions", json={
            "title": "Invalid Auction",
            "description": "Test",
            "starting_price": 1000.0,
            "min_increment": -10.0,  # Invalid!
            "duration_minutes": 60
        })
        
        assert response.status_code == 400
    
    def test_list_auctions(self):
        """Test listing all auctions"""
        response = client.get("/auctions")
        
        assert response.status_code == 200
        data = response.json()
        assert "auctions" in data
        assert "total" in data
        assert isinstance(data["auctions"], list)
    
    def test_list_auctions_filter_by_status(self):
        """Test filtering auctions by status"""
        response = client.get("/auctions?status=ACTIVE")
        
        assert response.status_code == 200
        data = response.json()
        
        # All auctions should be ACTIVE
        for auction in data["auctions"]:
            assert auction["status"] == "ACTIVE"
    
    def test_get_auction_by_id(self):
        """Test getting specific auction"""
        # First create an auction
        create_response = client.post("/auctions", json={
            "title": "Get Test Auction",
            "description": "Test",
            "starting_price": 500.0,
            "min_increment": 25.0,
            "duration_minutes": 30
        })
        auction_id = create_response.json()["auction"]["auction_id"]
        
        # Now get it
        response = client.get(f"/auctions/{auction_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "auction" in data
        assert "recent_bids" in data
        assert data["auction"]["auction_id"] == auction_id
    
    def test_get_auction_not_found(self):
        """Test getting non-existent auction"""
        response = client.get("/auctions/99999")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_get_auction_statistics(self):
        """Test getting auction statistics"""
        # Create auction first
        create_response = client.post("/auctions", json={
            "title": "Stats Test",
            "description": "Test",
            "starting_price": 1000.0,
            "min_increment": 50.0,
            "duration_minutes": 60
        })
        auction_id = create_response.json()["auction"]["auction_id"]
        
        # Get statistics
        response = client.get(f"/auctions/{auction_id}/statistics")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_bids" in data
        assert "unique_bidders" in data
        assert "price_increase" in data
        assert data["auction_id"] == auction_id


# ============================================================================
# BID TESTS
# ============================================================================
class TestBidRoutes:
    """Test bid-related endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Create auction before each test"""
        response = client.post("/auctions", json={
            "title": "Bid Test Auction",
            "description": "For bid testing",
            "starting_price": 1000.0,
            "min_increment": 50.0,
            "duration_minutes": 60
        })
        self.auction_id = response.json()["auction"]["auction_id"]
    
    def test_place_bid_success(self):
        """Test placing a valid bid"""
        response = client.post(
            f"/bids/auctions/{self.auction_id}/bids/async",
            json={
                "user_id": 1,
                "bid_amount": 1050.0
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "bid_id" in data
        assert data["status"] == "QUEUED"
        
        # Store bid_id for status test
        pytest.bid_id = data["bid_id"]
    
    def test_place_bid_too_low(self):
        """Test placing bid below minimum"""
        response = client.post(
            f"/bids/auctions/{self.auction_id}/bids/async",
            json={
                "user_id": 1,
                "bid_amount": 1000.0  # Too low (needs starting + increment)
            }
        )
        
        assert response.status_code == 400
        assert "at least" in response.json()["detail"].lower()
    
    def test_place_bid_auction_not_found(self):
        """Test placing bid on non-existent auction"""
        response = client.post(
            "/bids/auctions/99999/bids/async",
            json={
                "user_id": 1,
                "bid_amount": 1050.0
            }
        )
        
        assert response.status_code == 400  # Validation error
    
    def test_get_bid_status(self):
        """Test checking bid status"""
        # Place bid first
        place_response = client.post(
            f"/bids/auctions/{self.auction_id}/bids/async",
            json={
                "user_id": 1,
                "bid_amount": 1050.0
            }
        )
        bid_id = place_response.json()["bid_id"]
        
        # Check status
        response = client.get(f"/bids/{bid_id}/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["QUEUED", "SUCCESS", "REJECTED"]
    
    def test_get_bid_status_not_found(self):
        """Test checking status of non-existent bid"""
        response = client.get("/bids/invalid-bid-id-123/status")
        
        assert response.status_code == 404
    
    def test_get_auction_bids(self):
        """Test getting bid history for auction"""
        response = client.get(f"/bids/auctions/{self.auction_id}/bids")
        
        assert response.status_code == 200
        data = response.json()
        assert "auction_id" in data
        assert "bids" in data
        assert "total_bids" in data
        assert isinstance(data["bids"], list)
    
    def test_get_user_bids(self):
        """Test getting all bids by a user"""
        user_id = 123
        
        response = client.get(f"/bids/users/{user_id}/bids")
        
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert data["user_id"] == user_id
        assert "bids" in data
        assert isinstance(data["bids"], list)
    
    def test_get_user_winning_auctions(self):
        """Test getting auctions where user is winning"""
        user_id = 123
        
        response = client.get(f"/bids/users/{user_id}/winning")
        
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "winning_count" in data
        assert "auctions" in data
        assert isinstance(data["auctions"], list)


# ============================================================================
# ADMIN TESTS
# ============================================================================
class TestAdminRoutes:
    """Test admin/monitoring endpoints"""
    
    def test_cache_stats(self):
        """Test getting cache statistics"""
        response = client.get("/admin/cache-stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "cache_hits" in data
        assert "cache_misses" in data
        assert "hit_rate" in data
        assert "ttl_seconds" in data
    
    def test_queue_stats(self):
        """Test getting queue statistics"""
        response = client.get("/admin/queue-stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_queued" in data
        assert "active_auctions" in data
        assert "details" in data
        assert isinstance(data["details"], list)
    
    def test_pubsub_stats(self):
        """Test getting Pub/Sub statistics"""
        response = client.get("/admin/pubsub-stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "subscriptions" in data
        assert "messages_published" in data or "messages_received" in data
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/admin/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data


# ============================================================================
# ROOT ENDPOINT TEST
# ============================================================================
def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "running"
    assert "features" in data
    assert isinstance(data["features"], list)