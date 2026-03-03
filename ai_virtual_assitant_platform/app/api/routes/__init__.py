"""
API Routes package
Contains all route modules
"""

from app.api.routes import health, ai, documents, auth

__all__ = ["health", "ai", "documents", "auth"]