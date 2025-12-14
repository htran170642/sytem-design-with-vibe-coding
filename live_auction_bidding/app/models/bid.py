"""
Bid Model
"""
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from datetime import datetime

from app.models import Base


class Bid(Base):
    """Bid database model"""
    
    __tablename__ = "bids"
    
    bid_id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("auctions.auction_id"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    bid_amount = Column(Float, nullable=False)
    previous_price = Column(Float, nullable=False)
    bid_time = Column(DateTime, default=datetime.now, index=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "bid_id": self.bid_id,
            "auction_id": self.auction_id,
            "user_id": self.user_id,
            "bid_amount": self.bid_amount,
            "previous_price": self.previous_price,
            "bid_time": self.bid_time.isoformat() if self.bid_time else None,
        }