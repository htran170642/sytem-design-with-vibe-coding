"""
RAG Service
Retrieval Augmented Generation - Answer questions using documents
Phase 4, Step 6: Inject retrieved context into AI prompts
Phase 6, Step 3: Cache AI responses for idempotent requests
"""

from typing import List, Optional, Dict, Any

from app.core.config import settings
from app.services.cache_service import CacheService, get_cache_service
from app.services.search_service import get_search_service
from app.services.ai_service import get_ai_service
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class RAGService:
    """
    RAG (Retrieval Augmented Generation) Service
    
    Combines semantic search with LLM to answer questions
    based on document content.
    """
    
    def __init__(self):
        """Initialize RAG service"""
        self.search_service = get_search_service()
        self.ai_service = get_ai_service()
        self._cache = get_cache_service()

        logger.info("RAGService initialized")
    
    def _format_context(
        self,
        search_results: List[Dict[str, Any]]
    ) -> str:
        """
        Format search results as context for LLM
        
        Args:
            search_results: List of search results
            
        Returns:
            Formatted context string
            
        Example:
            >>> context = self._format_context(results)
            >>> print(context)
            [Source 1 - document.pdf, Page 2, Score: 0.89]
            Customers may return items within 30 days...
            
            [Source 2 - document.pdf, Page 3, Score: 0.85]
            Contact support@example.com to initiate...
        """
        if not search_results:
            return "No relevant information found in documents."
        
        context_parts = []
        
        for i, result in enumerate(search_results, 1):
            # Get metadata
            metadata = result.get("metadata", {})
            page = metadata.get("page", "N/A")
            
            # Format source header
            source_header = (
                f"[Source {i} - {result.get('filename', 'unknown')}, "
                f"Page {page}, Score: {result['score']:.2f}]"
            )
            
            # Add source with content
            context_parts.append(
                f"{source_header}\n{result['content']}\n"
            )
        
        return "\n".join(context_parts)
    
    def _build_rag_prompt(
        self,
        question: str,
        context: str,
        system_message: Optional[str] = None,
    ) -> str:
        """
        Build prompt for RAG
        
        Args:
            question: User's question
            context: Retrieved context from documents
            system_message: Optional custom system message
            
        Returns:
            Complete prompt string
        """
        if system_message is None:
            system_message = (
                "You are a helpful AI assistant. Answer questions based on the "
                "provided context from documents. Always cite your sources using "
                "[Source X] format. If the answer is not in the context, say so."
            )
        
        prompt = f"""
{system_message}

Context from documents:
{context}

Question: {question}

Answer (cite sources using [Source X] format):
"""
        return prompt.strip()
    
    async def query(
        self,
        question: str,
        document_ids: Optional[List[int]] = None,
        top_k: int = 5,
        min_score: float = 0.3,
        temperature: float = 0.3,
        fallback_to_general: bool = False,
    ) -> Dict[str, Any]:
        """
        Answer question using RAG with comprehensive edge case handling
        
        Args:
            question: Question to answer
            document_ids: Filter by specific documents
            top_k: Number of chunks to retrieve
            min_score: Minimum similarity score
            temperature: LLM temperature (lower = more factual)
            fallback_to_general: If True, use general knowledge when no results
            
        Returns:
            Dictionary with answer, sources, and metadata
            
        Edge Cases Handled:
        - No search results
        - Low confidence scores
        - Partial matches
        - Empty documents
            
        Example:
            >>> result = await rag_service.query(
            ...     question="What is the refund policy?",
            ...     top_k=5,
            ...     min_score=0.3
            ... )
            >>> print(result["answer"])
            Based on the provided documents, customers may return items 
            within 30 days [Source 1]. Contact support@example.com to 
            initiate a return [Source 2]...
        """
        try:
            logger.info(
                "RAG query started",
                extra={
                    "question": question[:100],
                    "document_ids": document_ids,
                    "top_k": top_k,
                    "min_score": min_score,
                }
            )

            # Step 0: Check response cache
            _cache_key = CacheService.hash_key(
                "ai_response",
                f"{question}:{sorted(document_ids or [])}:{top_k}:{min_score}:{fallback_to_general}",
            )
            _cached = await self._cache.get(_cache_key)
            if _cached is not None:
                logger.debug(
                    "RAG response cache hit",
                    extra={"key": _cache_key, "question": question[:50]},
                )
                _cached["cached"] = True
                return _cached

            # Step 1: Search for relevant chunks
            search_results = await self.search_service.search(
                query=question,
                limit=top_k,
                document_ids=document_ids,
                min_score=min_score,
            )
            
            # ============================================
            # EDGE CASE 1: No search results
            # ============================================
            if not search_results:
                logger.warning("No search results found for query")
                
                if fallback_to_general:
                    # Fallback to general knowledge
                    logger.info("Falling back to general knowledge")
                    answer = await self.ai_service.simple_chat(
                        message=question,
                        temperature=0.7,
                    )

                    result = {
                        "question": question,
                        "answer": answer,
                        "sources": [],
                        "confidence": 0.0,
                        "context_used": "",
                        "fallback_used": True,
                        "warning": "No relevant documents found. Answer based on general knowledge.",
                    }
                    await self._cache.set(_cache_key, result, ttl=settings.CACHE_AI_RESPONSE_TTL)
                    return result
                else:
                    # No results, suggest actions
                    return {
                        "question": question,
                        "answer": (
                            "I couldn't find relevant information in the uploaded documents "
                            "to answer this question. This could mean:\n\n"
                            "1. The information isn't in the uploaded documents\n"
                            "2. Try rephrasing your question\n"
                            "3. Check if the right documents are uploaded\n"
                            "4. The similarity threshold (min_score) might be too high"
                        ),
                        "sources": [],
                        "confidence": 0.0,
                        "context_used": "",
                        "suggestions": [
                            "Rephrase your question",
                            "Upload relevant documents",
                            "Lower the min_score threshold",
                        ]
                    }
            
            # ============================================
            # EDGE CASE 2: Low confidence (all scores < threshold)
            # ============================================
            max_score = max(r["score"] for r in search_results)
            
            if max_score < 0.5:  # Very low confidence
                logger.warning(f"Low confidence results: max_score={max_score}")
                
                # Try with relaxed threshold
                relaxed_results = await self.search_service.search(
                    query=question,
                    limit=top_k,
                    document_ids=document_ids,
                    min_score=0.3,  # Lower threshold
                )
                
                if relaxed_results:
                    context = self._format_context(relaxed_results[:3])  # Use top 3
                    prompt = self._build_rag_prompt(question, context)
                    prompt += (
                        "\n\nNote: The search confidence is low. "
                        "If you're not certain, say so."
                    )

                    answer = await self.ai_service.simple_chat(
                        message=prompt,
                        temperature=temperature,
                    )

                    result = {
                        "question": question,
                        "answer": answer,
                        "sources": relaxed_results[:3],
                        "confidence": max(r["score"] for r in relaxed_results),
                        "context_used": context,
                        "warning": "Low confidence match. Answer may not be accurate.",
                    }
                    await self._cache.set(_cache_key, result, ttl=settings.CACHE_AI_RESPONSE_TTL)
                    return result
            
            # ============================================
            # EDGE CASE 3: Partial matches (some good, some bad)
            # ============================================
            # Filter out very low scores
            good_results = [r for r in search_results if r["score"] >= 0.3]
            
            if len(good_results) < len(search_results):
                logger.info(
                    f"Filtered results: {len(search_results)} → {len(good_results)}"
                )
                search_results = good_results
            
            # ============================================
            # NORMAL CASE: Good results found
            # ============================================
            
            # Step 2: Format context
            context = self._format_context(search_results)
            
            # Step 3: Build prompt
            prompt = self._build_rag_prompt(question, context)
            
            # Add confidence-based instructions
            if max_score < 0.75:
                prompt += (
                    "\n\nNote: Some search results have moderate confidence. "
                    "Cite your sources and acknowledge any uncertainty."
                )
            
            # Step 4: Get answer from LLM
            answer = await self.ai_service.simple_chat(
                message=prompt,
                temperature=temperature,
            )
            
            # Step 5: Calculate confidence
            confidence = max_score
            
            logger.info(
                "RAG query completed",
                extra={
                    "sources_count": len(search_results),
                    "confidence": confidence,
                    "answer_length": len(answer),
                }
            )
            
            result = {
                "question": question,
                "answer": answer,
                "sources": search_results,
                "confidence": confidence,
                "context_used": context,
            }

            # Add warnings for low confidence
            if confidence < 0.75:
                result["warning"] = (
                    "Moderate confidence. Answer may not be completely accurate."
                )

            await self._cache.set(_cache_key, result, ttl=settings.CACHE_AI_RESPONSE_TTL)
            return result
            
        except Exception as e:
            logger.error(f"RAG query error: {e}", exc_info=True)
            
            # ============================================
            # EDGE CASE 4: System error
            # ============================================
            return {
                "question": question,
                "answer": (
                    "I encountered an error while processing your question. "
                    "Please try again. If the problem persists, contact support."
                ),
                "sources": [],
                "confidence": 0.0,
                "context_used": "",
                "error": str(e),
            }
    
    async def query_with_conversation(
        self,
        question: str,
        conversation_history: List[Dict[str, str]],
        document_ids: Optional[List[int]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Answer question with conversation history
        
        Useful for follow-up questions that reference previous context.
        
        Args:
            question: Current question
            conversation_history: Previous messages
            document_ids: Filter by documents
            top_k: Number of chunks to retrieve
            
        Returns:
            Answer with sources
            
        Example:
            >>> history = [
            ...     {"role": "user", "content": "What is the refund policy?"},
            ...     {"role": "assistant", "content": "You can return items..."},
            ... ]
            >>> result = await rag_service.query_with_conversation(
            ...     question="How long do I have?",
            ...     conversation_history=history
            ... )
        """
        # Combine question with recent context for better search
        # Use last 2 exchanges for context
        recent_context = []
        for msg in conversation_history[-4:]:  # Last 2 exchanges
            recent_context.append(msg["content"])
        
        # Enhance query with context
        enhanced_query = f"{' '.join(recent_context[-2:])} {question}"
        
        # Search with enhanced query
        search_results = await self.search_service.search(
            query=enhanced_query,
            limit=top_k,
            document_ids=document_ids,
        )
        
        # Format context
        context = self._format_context(search_results)
        
        # Build messages with conversation history
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant. Answer questions based on "
                    "the provided context and conversation history. Cite sources."
                )
            }
        ]
        
        # Add conversation history
        messages.extend(conversation_history)
        
        # Add current question with context
        messages.append({
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}"
        })
        
        # Get answer
        result = await self.ai_service.chat_completion(messages)
        
        return {
            "question": question,
            "answer": result["message"],
            "sources": search_results,
            "confidence": max(r["score"] for r in search_results) if search_results else 0.0,
        }


# Singleton instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """
    Get or create RAGService instance (singleton)
    
    Returns:
        RAGService instance
    """
    global _rag_service
    
    if _rag_service is None:
        _rag_service = RAGService()
    
    return _rag_service