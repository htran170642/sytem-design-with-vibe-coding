"""
User endpoints - updated to use service layer
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import User
from app.schemas.user import UserCreate, UserResponse, UserListItem
from app.services import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate = Body(...), db: Session = Depends(get_db)):
    """
        Register a new user
        Request body:
        {
            "username": "alice",
            "email": "alice@example.com"
        }
    """
    try:
        new_user = UserService.create_user(db, user)
        return new_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list")
def get_all_users(
    current_username: Optional[str] = None,
    online_only: bool = False,
    db: Session = Depends(get_db)
):
    """Get list of all users"""
    users = UserService.get_all_users(
        db,
        exclude_username=current_username,
        online_only=online_only
    )
    
    return {
        "users": [UserListItem.from_orm(u) for u in users],
        "count": len(users),
        "online_count": sum(1 for u in users if u.is_online)
    }


@router.get("/online")
def get_online_users(db: Session = Depends(get_db)):
    """Get online users"""
    users = UserService.get_online_users(db)
    
    return {
        "online_users": [UserListItem.from_orm(u) for u in users],
        "count": len(users)
    }


@router.get("/search")
def search_users(
    query: str,
    current_username: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Search users"""
    users = UserService.search_users(
        db,
        search_query=query,
        exclude_username=current_username
    )
    
    return {
        "users": [UserListItem.from_orm(u) for u in users],
        "count": len(users)
    }


@router.get("/{username}", response_model=UserResponse)
def get_user(username: str, db: Session = Depends(get_db)):
    """Get specific user"""
    user = UserService.get_by_username(db, username)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user