"""
Auction Model
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum
from datetime import datetime
import enum

from app.models import Base


class AuctionStatus(str, enum.Enum):
    """Auction status enum"""
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"


class Auction(Base):
    """Auction database model"""
    
    __tablename__ = "auctions"
    
    auction_id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String)
    starting_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    min_increment = Column(Float, nullable=False)
    start_time = Column(DateTime, default=datetime.now)
    end_time = Column(DateTime, nullable=False)
    status = Column(SQLEnum(AuctionStatus), default=AuctionStatus.ACTIVE)
    current_winner_id = Column(Integer, nullable=True)
    total_bids = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "auction_id": self.auction_id,
            "title": self.title,
            "description": self.description,
            "starting_price": self.starting_price,
            "current_price": self.current_price,
            "min_increment": self.min_increment,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status.value if isinstance(self.status, AuctionStatus) else self.status,
            "current_winner_id": self.current_winner_id,
            "total_bids": self.total_bids,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }