"""
Vector Store Service
Manage embeddings in Qdrant vector database
Phase 4, Step 4: Integrate vector database (Qdrant)
"""

from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
import uuid

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.exceptions import VectorDBError

logger = get_logger(__name__)


class VectorStore:
    """
    Manage vector embeddings in Qdrant database
    
    Supports:
    - Creating collections
    - Upserting embeddings
    - Semantic search
    - Filtering by metadata
    """
    
    def __init__(
        self,
        vector_size: int = 1536,
        distance: Distance = Distance.COSINE,
    ):
        """
        Initialize vector store
        
        Args:
            vector_size: Embedding dimensions (1536 for text-embedding-3-small)
            distance: Similarity metric (COSINE, DOT, EUCLIDEAN)
        """
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = vector_size
        self.distance = distance
        
        # Initialize Qdrant client - USE DOCKER SERVICE
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,  # "qdrant" in Docker
            port=settings.QDRANT_PORT,  # 6333
        )
        
        # Create collection if it doesn't exist
        self._ensure_collection_exists()
        
        logger.info(
            "VectorStore initialized",
            extra={
                "collection": self.collection_name,
                "vector_size": vector_size,
                "distance": distance,
                "host": settings.QDRANT_HOST,
                "port": settings.QDRANT_PORT,
            }
        )
    
    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=self.distance,
                    ),
                )
                logger.info(f"Created collection: {self.collection_name}")
            else:
                logger.info(f"Collection exists: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}", exc_info=True)
            raise VectorDBError(
                message="Failed to initialize vector store",
                details={"error": str(e)}
            )
    
    async def upsert_embeddings(
        self,
        embeddings: List[List[float]],
        chunk_ids: List[int],
        metadata: List[Dict[str, Any]],
    ) -> bool:
        """
        Insert or update embeddings in vector database
        
        Args:
            embeddings: List of embedding vectors
            chunk_ids: List of chunk IDs (from database)
            metadata: List of metadata dicts (document_id, content, etc.)
            
        Returns:
            True if successful
            
        Example:
            >>> await vector_store.upsert_embeddings(
            ...     embeddings=[[0.1, 0.2, ...], [0.3, 0.4, ...]],
            ...     chunk_ids=[1, 2],
            ...     metadata=[
            ...         {"document_id": 1, "content": "...", "page": 1},
            ...         {"document_id": 1, "content": "...", "page": 2},
            ...     ]
            ... )
            True
        """
        try:
            if len(embeddings) != len(chunk_ids) != len(metadata):
                raise ValueError("Embeddings, chunk_ids, and metadata must have same length")
            
            # Create points for Qdrant
            points = []
            for i, (embedding, chunk_id, meta) in enumerate(zip(embeddings, chunk_ids, metadata)):
                point = PointStruct(
                    id=str(uuid.uuid4()),  # Unique ID in Qdrant
                    vector=embedding,
                    payload={
                        "chunk_id": chunk_id,
                        "document_id": meta.get("document_id"),
                        "content": meta.get("content", ""),
                        "metadata": meta.get("metadata", {}),
                    }
                )
                points.append(point)
            
            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            
            logger.info(
                "Embeddings upserted",
                extra={
                    "count": len(embeddings),
                    "collection": self.collection_name,
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error upserting embeddings: {e}", exc_info=True)
            raise VectorDBError(
                message="Failed to upsert embeddings",
                details={"error": str(e), "count": len(embeddings)}
            )
    
    async def search(
        self,
        query_embedding: List[float],
        limit: int = 5,
        document_ids: Optional[List[int]] = None,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings
        
        Args:
            query_embedding: Query vector
            limit: Max results to return
            document_ids: Filter by document IDs (optional)
            min_score: Minimum similarity score (0-1)
            
        Returns:
            List of search results with scores and metadata
            
        Example:
            >>> results = await vector_store.search(
            ...     query_embedding=[0.1, 0.2, ...],
            ...     limit=5,
            ...     document_ids=[1, 2],
            ...     min_score=0.7
            ... )
            >>> print(results[0])
            {
                "chunk_id": 5,
                "document_id": 1,
                "content": "Refund policy text...",
                "score": 0.89,
                "metadata": {"page": 2}
            }
        """
        try:
            # Build filter
            query_filter = None
            if document_ids:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=doc_id)
                        )
                        for doc_id in document_ids
                    ]
                )
            
            # Search Qdrant
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                query_filter=query_filter,
                score_threshold=min_score,
            )
            
            # Format results
            results = []
            for result in search_results:
                results.append({
                    "chunk_id": result.payload.get("chunk_id"),
                    "document_id": result.payload.get("document_id"),
                    "content": result.payload.get("content"),
                    "score": result.score,
                    "metadata": result.payload.get("metadata", {}),
                })
            
            logger.info(
                "Vector search completed",
                extra={
                    "results_count": len(results),
                    "limit": limit,
                    "min_score": min_score,
                }
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching vectors: {e}", exc_info=True)
            raise VectorDBError(
                message="Failed to search vectors",
                details={"error": str(e)}
            )
    
    async def delete_by_document_id(self, document_id: int) -> bool:
        """
        Delete all embeddings for a document
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            True if successful
        """
        try:
            # Delete points with matching document_id
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )
            
            logger.info(
                "Embeddings deleted",
                extra={"document_id": document_id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting embeddings: {e}", exc_info=True)
            raise VectorDBError(
                message="Failed to delete embeddings",
                details={"error": str(e), "document_id": document_id}
            )
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        Get collection statistics.

        Uses client.count() for the point total and falls back to known
        instance attributes for config, avoiding a version-mismatch issue
        with client.get_collection() on newer Qdrant servers.

        Returns:
            Collection info (vector count, config, etc.)
        """
        try:
            count_result = self.client.count(self.collection_name, exact=True)
            vector_count = count_result.count
        except Exception as e:
            logger.warning(f"Could not fetch vector count: {e}")
            vector_count = 0

        return {
            "name": self.collection_name,
            "vector_count": vector_count,
            "vector_size": self.vector_size,
            "distance": str(self.distance),
        }


# Singleton instance
_vector_store: Optional[VectorStore] = None


def get_vector_store(
    vector_size: int = 1536,
) -> VectorStore:
    """
    Get or create VectorStore instance (singleton)
    
    Args:
        collection_name: Qdrant collection name
        vector_size: Embedding dimensions
        
    Returns:
        VectorStore instance
    """
    global _vector_store
    
    if _vector_store is None:
        _vector_store = VectorStore(
            vector_size=vector_size,
        )
    
    return _vector_store