"""
Search Service
Semantic search using embeddings and vector database
Phase 4, Step 5: Implement semantic search / similarity retrieval
"""

from typing import List, Optional, Dict, Any

from app.services.embedding_service import get_embedding_service
from app.services.vector_store import get_vector_store
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class SearchService:
    """
    Semantic search service
    
    Converts queries to embeddings and searches vector database
    for similar content.
    """
    
    def __init__(self):
        """Initialize search service"""
        self.embedding_service = get_embedding_service()
        self.vector_store = get_vector_store()
        
        logger.info("SearchService initialized")
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        document_ids: Optional[List[int]] = None,
        min_score: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search
        
        Args:
            query: Search query text
            limit: Maximum results to return
            document_ids: Filter by specific documents (optional)
            min_score: Minimum similarity score (0-1)
            
        Returns:
            List of search results with scores
            
        Example:
            >>> results = await search_service.search(
            ...     query="What is the refund policy?",
            ...     limit=5,
            ...     document_ids=[1, 2],
            ...     min_score=0.5
            ... )
            >>> print(results[0])
            {
                "chunk_id": 5,
                "document_id": 1,
                "content": "Customers may return items...",
                "score": 0.89,
                "metadata": {"page": 2}
            }
        """
        try:
            logger.info(
                "Performing semantic search",
                extra={
                    "query": query[:100],  # Truncate for logging
                    "limit": limit,
                    "document_ids": document_ids,
                    "min_score": min_score,
                }
            )
            
            # Step 1: Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query)
            
            # Step 2: Search vector database
            results = await self.vector_store.search(
                query_embedding=query_embedding,
                limit=limit,
                document_ids=document_ids,
                min_score=min_score,
            )
            
            logger.info(
                "Search completed",
                extra={
                    "results_count": len(results),
                    "top_score": results[0]["score"] if results else 0,
                }
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            # Return empty results on error (graceful degradation)
            return []
    
    async def search_by_chunk_text(
        self,
        chunk_text: str,
        limit: int = 5,
        exclude_chunk_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find similar chunks to a given chunk
        
        Useful for:
        - "More like this" feature
        - Finding related content
        - Duplicate detection
        
        Args:
            chunk_text: Text to find similar chunks for
            limit: Maximum results
            exclude_chunk_ids: Chunk IDs to exclude (e.g., the source chunk)
            
        Returns:
            List of similar chunks
        """
        try:
            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(chunk_text)
            
            # Search
            results = await self.vector_store.search(
                query_embedding=embedding,
                limit=limit + len(exclude_chunk_ids or []),  # Get extra to filter
                min_score=0.5,  # Lower threshold for similarity
            )
            
            # Filter out excluded chunks
            if exclude_chunk_ids:
                results = [
                    r for r in results
                    if r["chunk_id"] not in exclude_chunk_ids
                ]
            
            # Return only requested limit
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Similarity search error: {e}", exc_info=True)
            return []


# Singleton instance
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """
    Get or create SearchService instance (singleton)
    
    Returns:
        SearchService instance
    """
    global _search_service
    
    if _search_service is None:
        _search_service = SearchService()
    
    return _search_service