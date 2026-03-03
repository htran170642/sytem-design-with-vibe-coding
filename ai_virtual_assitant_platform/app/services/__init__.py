"""
Services Module
Exports all service classes and getter functions
Phase 3: AI/LLM services
Phase 4: Document processing & RAG services
"""

# ============================================
# Phase 3: AI/LLM Services
# ============================================

# OpenAI Client
from app.services.openai_client import (
    OpenAIClient,
    get_openai_client,
)

# AI Service (Main orchestration)
from app.services.ai_service import (
    AIService,
    get_ai_service,
)

# LangChain Service
from app.services.langchain_service import (
    LangChainService,
    get_langchain_service,
)

# Prompt Templates
from app.services.prompt_templates import (
    PromptTemplate,
    PromptTemplateManager,
    PromptRole,
    build_conversation_messages,
    format_context_for_rag,
)

# Token Tracker
from app.services.token_tracker import (
    TokenTracker,
    TokenUsage,
    get_token_tracker,
    TOKEN_PRICING,
)

# ============================================
# Phase 4: Document Processing & RAG Services
# ============================================

# Text Extractors
from app.services.extractors import extract_text
from app.services.extractors.pdf_extractor import extract_text_from_pdf
from app.services.extractors.docx_extractor import extract_text_from_docx
from app.services.extractors.txt_extractor import extract_text_from_txt
from app.services.extractors.html_extractor import extract_text_from_html
from app.services.extractors.markdown_extractor import extract_text_from_markdown

# Text Chunker
from app.services.text_chunker import (
    TextChunker,
    get_text_chunker,
)

# Embedding Service
from app.services.embedding_service import (
    EmbeddingService,
    get_embedding_service,
)

# Vector Store
from app.services.vector_store import (
    VectorStore,
    get_vector_store,
)

# Search Service
from app.services.search_service import (
    SearchService,
    get_search_service,
)

from app.services.rag_service import (
    RAGService,
    get_rag_service
)

__all__ = [
    # ============================================
    # Phase 3: AI/LLM Services
    # ============================================
    
    # OpenAI Client
    "OpenAIClient",
    "get_openai_client",
    
    # AI Service
    "AIService",
    "get_ai_service",
    
    # LangChain Service
    "LangChainService",
    "get_langchain_service",
    
    # Prompt Templates
    "PromptTemplate",
    "PromptTemplateManager",
    "PromptRole",
    "build_conversation_messages",
    "format_context_for_rag",
    
    # Token Tracker
    "TokenTracker",
    "TokenUsage",
    "get_token_tracker",
    "TOKEN_PRICING",
    
    # ============================================
    # Phase 4: Document Processing & RAG Services
    # ============================================
    
    # Text Extractors
    "extract_text",
    "extract_text_from_pdf",
    "extract_text_from_docx",
    "extract_text_from_txt",
    "extract_text_from_html",
    "extract_text_from_markdown",
    
    # Text Chunker
    "TextChunker",
    "get_text_chunker",
    
    # Embedding Service
    "EmbeddingService",
    "get_embedding_service",
    
    # Vector Store
    "VectorStore",
    "get_vector_store",
    
    # Search Service
    "SearchService",
    "get_search_service",
    
    # Rag Service
    "RAGService",
    "get_rag_service",
]