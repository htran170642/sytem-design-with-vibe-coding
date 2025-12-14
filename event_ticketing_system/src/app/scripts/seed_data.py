"""
Seed script to populate database with sample data for testing

Usage:
    python -m app.scripts.seed_data
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from passlib.context import CryptContext
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, init_db
from app.models import User, Event, EventSeat, SeatStatus

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_sample_users(db):
    """Create sample users"""
    users_data = [
        {
            "email": "john@example.com",
            "full_name": "John Doe",
            "password": "password123",
        },
        {
            "email": "jane@example.com",
            "full_name": "Jane Smith",
            "password": "password123",
        },
        {
            "email": "bob@example.com",
            "full_name": "Bob Johnson",
            "password": "password123",
        },
    ]
    
    users = []
    for user_data in users_data:
        # Check if user already exists
        result = await db.execute(
            select(User).where(User.email == user_data["email"])
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"User {user_data['email']} already exists, skipping...")
            users.append(existing_user)
            continue
        
        user = User(
            email=user_data["email"],
            full_name=user_data["full_name"],
            password_hash=pwd_context.hash(user_data["password"]),
        )
        db.add(user)
        users.append(user)
        print(f"Created user: {user.email}")
    
    await db.commit()
    return users


async def create_sample_events(db):
    """Create sample events"""
    now = datetime.utcnow()
    
    events_data = [
        {
            "name": "Taylor Swift - The Eras Tour",
            "description": "Experience the musical journey of a lifetime with Taylor Swift performing her greatest hits from every era.",
            "venue": "SoFi Stadium",
            "city": "Los Angeles",
            "country": "USA",
            "start_time": now + timedelta(days=30),
            "category": "concert",
            "total_seats": 1000,
            "image_url": "https://example.com/taylor-swift.jpg",
        },
        {
            "name": "Lakers vs Warriors",
            "description": "NBA Western Conference showdown between the Los Angeles Lakers and Golden State Warriors.",
            "venue": "Crypto.com Arena",
            "city": "Los Angeles",
            "country": "USA",
            "start_time": now + timedelta(days=15),
            "category": "sports",
            "total_seats": 800,
            "image_url": "https://example.com/lakers.jpg",
        },
        {
            "name": "Hamilton - The Musical",
            "description": "Lin-Manuel Miranda's award-winning musical about Alexander Hamilton and the founding fathers.",
            "venue": "Richard Rodgers Theatre",
            "city": "New York",
            "country": "USA",
            "start_time": now + timedelta(days=45),
            "category": "theater",
            "total_seats": 500,
            "image_url": "https://example.com/hamilton.jpg",
        },
        {
            "name": "Ed Sheeran World Tour",
            "description": "Ed Sheeran brings his Mathematics Tour with hits from his latest albums.",
            "venue": "Wembley Stadium",
            "city": "London",
            "country": "UK",
            "start_time": now + timedelta(days=60),
            "category": "concert",
            "total_seats": 1200,
            "image_url": "https://example.com/ed-sheeran.jpg",
        },
        {
            "name": "Stand-up Comedy Night",
            "description": "An evening of laughs with top comedians from around the country.",
            "venue": "Comedy Store",
            "city": "Los Angeles",
            "country": "USA",
            "start_time": now + timedelta(days=7),
            "category": "comedy",
            "total_seats": 300,
            "image_url": "https://example.com/comedy.jpg",
        },
    ]
    
    events = []
    for event_data in events_data:
        # Check if event already exists
        result = await db.execute(
            select(Event).where(
                Event.name == event_data["name"],
                Event.start_time == event_data["start_time"]
            )
        )
        existing_event = result.scalar_one_or_none()
        
        if existing_event:
            print(f"Event '{event_data['name']}' already exists, skipping...")
            events.append(existing_event)
            continue
        
        event = Event(
            **{k: v for k, v in event_data.items() if k != 'total_seats'},
            total_seats=0,  # Will be updated after seats are created
            available_seats=0,
        )
        db.add(event)
        await db.flush()  # Get event ID
        
        # Create seats for this event
        seats_created = await create_seats_for_event(db, event, event_data['total_seats'])
        
        # Update total and available seats
        event.total_seats = seats_created
        event.available_seats = seats_created
        
        events.append(event)
        print(f"Created event: {event.name} with {seats_created} seats")
    
    await db.commit()
    return events


async def create_seats_for_event(db, event: Event, total_seats: int):
    """
    Create seats for an event with realistic section/row/seat structure.
    
    Seat layout:
    - VIP section (20% of seats): $150
    - Section A (30% of seats): $100
    - Section B (30% of seats): $75
    - Section C (20% of seats): $50
    """
    sections = [
        {"name": "VIP", "percentage": 0.20, "price": Decimal("150.00"), "rows": 5},
        {"name": "A", "percentage": 0.30, "price": Decimal("100.00"), "rows": 8},
        {"name": "B", "percentage": 0.30, "price": Decimal("75.00"), "rows": 8},
        {"name": "C", "percentage": 0.20, "price": Decimal("50.00"), "rows": 5},
    ]
    
    seats_created = 0
    
    for section in sections:
        section_seats = int(total_seats * section["percentage"])
        seats_per_row = max(1, section_seats // section["rows"])
        
        for row in range(1, section["rows"] + 1):
            for seat in range(1, seats_per_row + 1):
                seat_obj = EventSeat(
                    event_id=event.id,
                    section=section["name"],
                    row_number=str(row),
                    seat_number=str(seat),
                    price=section["price"],
                    status=SeatStatus.AVAILABLE,
                )
                db.add(seat_obj)
                seats_created += 1
                
                if seats_created >= total_seats:
                    break
            
            if seats_created >= total_seats:
                break
    
    return seats_created


async def seed_database():
    """Main seeding function"""
    print("Starting database seeding...")
    
    async with AsyncSessionLocal() as db:
        try:
            # Create users
            print("\n=== Creating Users ===")
            users = await create_sample_users(db)
            
            # Create events and seats
            print("\n=== Creating Events and Seats ===")
            events = await create_sample_events(db)
            
            print("\n=== Seeding Complete! ===")
            print(f"Created {len(users)} users")
            print(f"Created {len(events)} events")
            
            # Print summary
            for event in events:
                result = await db.execute(
                    select(EventSeat).where(EventSeat.event_id == event.id)
                )
                seats = result.scalars().all()
                print(f"  - {event.name}: {len(seats)} seats")
            
        except Exception as e:
            print(f"Error during seeding: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(seed_database())
