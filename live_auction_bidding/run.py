"""
Application Entry Point
"""
import uvicorn
from app.core.config import get_settings

settings = get_settings()

if __name__ == "__main__":
    print("=" * 70)
    print(f"🎯 {settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 70)
    print("✅ Features:")
    print("   - Message Queue System")
    print("   - Redis Pub/Sub")
    print("   - Caching Layer")
    print("   - WebSocket Real-Time Updates")
    print("\n🌐 Server:")
    print(f"   URL: http://{settings.HOST}:{settings.PORT}")
    print(f"   Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print("=" * 70)
    print("\n🚀 Starting server...\n")
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )