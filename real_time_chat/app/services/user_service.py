"""
User service - business logic for user operations
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from datetime import datetime

from app.models import User
from app.schemas.user import UserCreate, UserListItem


class UserService:
    """Service for user operations"""
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        """
        Create a new user
        
        Args:
            db: Database session
            user_data: User creation data
            
        Returns:
            Created user
            
        Raises:
            ValueError: If username or email already exists
        """
        # Check if username exists
        if UserService.get_by_username(db, user_data.username):
            raise ValueError("Username already exists")
        
        # Check if email exists
        if UserService.get_by_email(db, user_data.email):
            raise ValueError("Email already exists")
        
        # Create user
        user = User(
            username=user_data.username,
            email=user_data.email
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[User]:
        """Get user by username"""
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def get_all_users(
        db: Session,
        exclude_username: Optional[str] = None,
        online_only: bool = False
    ) -> List[User]:
        """
        Get all users with optional filters
        
        Args:
            db: Database session
            exclude_username: Username to exclude from results
            online_only: If True, only return online users
            
        Returns:
            List of users
        """
        query = db.query(User)
        
        if exclude_username:
            query = query.filter(User.username != exclude_username)
        
        if online_only:
            query = query.filter(User.is_online == True)
        
        return query.order_by(
            User.is_online.desc(),
            User.last_seen.desc()
        ).all()
    
    @staticmethod
    def get_online_users(db: Session) -> List[User]:
        """Get all online users"""
        return db.query(User).filter(User.is_online == True).all()
    
    @staticmethod
    def search_users(
        db: Session,
        search_query: str,
        exclude_username: Optional[str] = None,
        limit: int = 20
    ) -> List[User]:
        """
        Search users by username
        
        Args:
            db: Database session
            search_query: Search string
            exclude_username: Username to exclude
            limit: Maximum results
            
        Returns:
            List of matching users
        """
        query = db.query(User).filter(
            User.username.ilike(f"%{search_query}%")
        )
        
        if exclude_username:
            query = query.filter(User.username != exclude_username)
        
        return query.limit(limit).all()
    
    @staticmethod
    def set_online_status(db: Session, user_id: int, is_online: bool) -> bool:
        """
        Set user online/offline status
        
        Args:
            db: Database session
            user_id: User ID
            is_online: Online status
            
        Returns:
            True if successful
        """
        user = UserService.get_by_id(db, user_id)
        if not user:
            return False
        
        user.is_online = is_online
        user.last_seen = datetime.utcnow()
        db.commit()
        
        return True
    
    @staticmethod
    def update_last_seen(db: Session, user_id: int) -> bool:
        """
        Update user's last_seen timestamp
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            True if successful
        """
        user = UserService.get_by_id(db, user_id)
        if not user:
            return False
        
        user.last_seen = datetime.utcnow()
        db.commit()
        
        return True
    
    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        """
        Delete a user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            True if successful
        """
        user = UserService.get_by_id(db, user_id)
        if not user:
            return False
        
        db.delete(user)
        db.commit()
        
        return True