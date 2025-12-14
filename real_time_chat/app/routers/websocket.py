"""
WebSocket endpoints for real-time messaging
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocal
from app.models import User, DirectMessage
from app.services import UserService, DirectMessageService
from app.utils.websocket_manager import ws_manager

router = APIRouter(tags=["websocket"])


async def set_user_offline(user_id: int):
    """Set user as offline in database"""
    db = SessionLocal()
    try:
        UserService.set_online_status(db, user_id, False)
    finally:
        db.close()


async def broadcast_status_change(user_id: int, username: str, is_online: bool):
    """Broadcast user status change to all connected users"""
    status_message = {
        "type": "status_change",
        "user_id": user_id,
        "username": username,
        "is_online": is_online,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await ws_manager.broadcast(status_message, exclude_user_id=user_id)


@router.websocket("/ws/dm/{username}")
async def direct_message_websocket(websocket: WebSocket, username: str):
    """WebSocket endpoint for real-time direct messages"""
    
    # Get user and validate
    db = SessionLocal()
    user = UserService.get_by_username(db, username)
    
    if not user:
        await websocket.close(code=1008, reason="User not found")
        db.close()
        return
    
    # Extract user data before closing session
    user_id = user.id
    user_username = user.username
    
    # Accept WebSocket connection
    await ws_manager.connect(user_id, websocket)
    
    # Set user online
    UserService.set_online_status(db, user_id, True)
    db.close()
    
    # Broadcast status change
    await broadcast_status_change(user_id, user_username, True)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            receiver_username = data.get('to')
            content = data.get('content')
            
            if not receiver_username or not content:
                await websocket.send_json({
                    "error": "Missing 'to' or 'content' field"
                })
                continue
            
            # Process message in new database session
            db = SessionLocal()
            
            try:
                # Get receiver
                receiver = UserService.get_by_username(db, receiver_username)
                
                if not receiver:
                    await websocket.send_json({
                        "error": f"User '{receiver_username}' not found"
                    })
                    db.close()
                    continue
                
                # Extract receiver data
                receiver_id = receiver.id
                
                # Save message
                dm = DirectMessageService.send_message(
                    db,
                    sender_id=user_id,
                    receiver_id=receiver_id,
                    content=content
                )
                
                # Extract message data before closing session
                dm_id = dm.id
                dm_created_at = dm.created_at.isoformat()
                
            finally:
                db.close()
            
            # Prepare message data (using extracted values)
            message_data = {
                "type": "direct_message",
                "id": dm_id,
                "from": user_username,
                "from_id": user_id,
                "to": receiver_username,
                "to_id": receiver_id,
                "content": content,
                "created_at": dm_created_at,
                "is_read": False
            }
            
            # Send to receiver if online
            if ws_manager.is_online(receiver_id):
                success = await ws_manager.send_personal_message(receiver_id, message_data)
                if success:
                    print(f"📨 {user_username} → {receiver_username}")
                else:
                    print(f"📭 Failed to send to {receiver_username}")
                    await set_user_offline(receiver_id)
            else:
                print(f"📭 {receiver_username} is offline")
            
            # Confirm to sender
            await websocket.send_json({**message_data, "status": "sent"})
    
    except WebSocketDisconnect:
        # Clean up on disconnect
        ws_manager.disconnect(user_id)
        
        print(f"✗ {user_username} disconnected")
        
        # Set user offline
        await set_user_offline(user_id)
        
        # Broadcast status change
        await broadcast_status_change(user_id, user_username, False)


@router.websocket("/ws/{username}")
async def room_chat_websocket(websocket: WebSocket, username: str, room_id: str = "general"):
    """WebSocket endpoint for room chat (group messaging)"""
    
    # Get user
    db = SessionLocal()
    user = UserService.get_by_username(db, username)
    
    if not user:
        await websocket.close(code=1008, reason="User not found")
        db.close()
        return
    
    user_id = user.id
    user_username = user.username
    
    # Accept connection
    await ws_manager.connect(user_id, websocket)
    
    # Set online
    UserService.set_online_status(db, user_id, True)
    db.close()
    
    # Broadcast join notification
    join_message = {
        "type": "user_joined",
        "username": user_username,
        "room_id": room_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    await ws_manager.broadcast(join_message, exclude_user_id=user_id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            
            # Save to database
            db = SessionLocal()
            try:
                from app.services import MessageService
                
                message = MessageService.create_message(
                    db,
                    user_id=user_id,
                    content=data,
                    room_id=room_id
                )
                
                message_id = message.id
                created_at = message.created_at.isoformat()
                
            finally:
                db.close()
            
            # Broadcast to all users in room
            broadcast_data = {
                "type": "message",
                "id": message_id,
                "username": user_username,
                "content": data,
                "room_id": room_id,
                "created_at": created_at
            }
            
            await ws_manager.broadcast(broadcast_data)
    
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
        
        # Set offline
        await set_user_offline(user_id)
        
        # Broadcast leave notification
        leave_message = {
            "type": "user_left",
            "username": user_username,
            "room_id": room_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        await ws_manager.broadcast(leave_message)