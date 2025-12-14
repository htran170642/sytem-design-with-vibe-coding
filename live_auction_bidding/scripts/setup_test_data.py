"""
Setup Test Data

Creates test auctions and bids for performance testing.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime, timedelta
from app.infrastructure.database import SessionLocal
from app.models import Auction, Bid
from sqlalchemy import text


def setup_test_data(num_auctions: int = 100, num_bids: int = 1000):
    """
    Create test data for performance testing
    
    Args:
        num_auctions: Number of auctions to create
        num_bids: Number of bids to create
    """
    print(f"\n🔧 Setting up test data...")
    print(f"   Auctions: {num_auctions}")
    print(f"   Bids: {num_bids}")
    
    db = SessionLocal()
    
    try:
        # Clear existing test data
        print("\n🗑️  Clearing existing data...")
        db.execute(text("DELETE FROM bids"))
        db.execute(text("DELETE FROM auctions"))
        db.commit()
        
        # Create auctions
        print(f"\n📝 Creating {num_auctions} auctions...")
        auction_ids = []
        
        for i in range(num_auctions):
            auction = Auction(
                title=f"Performance Test Auction {i+1}",
                description=f"Test auction for performance benchmarking - ID {i+1}",
                starting_price=1000 + (i * 10),
                current_price=1000 + (i * 10),
                min_increment=10,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=24),
                status="ACTIVE",
                total_bids=0,
                current_winner_id=None
            )
            db.add(auction)
            db.flush()
            auction_ids.append(auction.auction_id)
            
            if (i + 1) % 10 == 0:
                print(f"   Created {i+1}/{num_auctions} auctions")
        
        db.commit()
        print(f"   ✅ Created {num_auctions} auctions")
        
        # Create bids
        print(f"\n💰 Creating {num_bids} bids...")
        
        for i in range(num_bids):
            auction_id = auction_ids[i % len(auction_ids)]
            
            bid = Bid(
                auction_id=auction_id,
                user_id=(i % 100) + 1,  # 100 different users
                bid_amount=1100 + (i * 5),
                previous_price=1000 + (i * 5)
            )
            db.add(bid)
            
            if (i + 1) % 100 == 0:
                print(f"   Created {i+1}/{num_bids} bids")
        
        db.commit()
        print(f"   ✅ Created {num_bids} bids")
        
        # Update auction totals
        print("\n📊 Updating auction totals...")
        for auction_id in auction_ids:
            bid_count = db.query(Bid).filter(Bid.auction_id == auction_id).count()
            
            auction = db.query(Auction).filter(Auction.auction_id == auction_id).first()
            if auction:
                auction.total_bids = bid_count
        
        db.commit()
        
        print("\n" + "=" * 70)
        print("✅ Test data setup complete!")
        print("=" * 70)
        print(f"Total Auctions: {num_auctions}")
        print(f"Total Bids: {num_bids}")
        print(f"Auction IDs: {auction_ids[0]} to {auction_ids[-1]}")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("🔧 Performance Test Data Setup")
    print("\nThis will:")
    print("  1. Delete all existing auctions and bids")
    print("  2. Create 100 test auctions")
    print("  3. Create 1,000 test bids")
    
    confirm = input("\nContinue? (yes/no): ").strip().lower()
    
    if confirm == "yes":
        setup_test_data(num_auctions=100, num_bids=1000)
    else:
        print("Cancelled.")