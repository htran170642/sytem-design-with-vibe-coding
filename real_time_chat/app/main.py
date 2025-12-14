"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.config import settings
from app.routers import users, messages, direct_messages, websocket, health

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Real-time chat API with WebSocket support"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router)
app.include_router(messages.router)
app.include_router(direct_messages.router)
app.include_router(websocket.router)
app.include_router(health.router)

# Serve frontend files
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    
    @app.get("/chat")
    def serve_users_chat():
        """Serve users.html"""
        return FileResponse(os.path.join(frontend_path, "users.html"))
    
    @app.get("/room")
    def serve_room_chat():
        """Serve chat.html"""
        return FileResponse(os.path.join(frontend_path, "chat.html"))


@app.get("/")
def read_root():
    """Root endpoint"""
    return {
        "message": f"{settings.APP_NAME} is running",
        "version": settings.APP_VERSION,
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "chat": "/chat",
            "room": "/room"
        }
    }


@app.get("/health")
def health_check():
    """Health check"""
    from app.database import check_database_health, get_pool_status
    from app.utils.websocket_manager import ws_manager
    
    return {
        "status": "healthy",
        "database": "up" if check_database_health() else "down",
        "pool": get_pool_status(),
        "websocket": {
            "active_connections": ws_manager.get_online_count()
        }
    }