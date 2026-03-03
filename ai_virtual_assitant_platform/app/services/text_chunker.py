"""
Text Chunker
Split text into chunks with overlap for better context
Phase 4, Step 2: Document parsing and text chunking
"""

from typing import List, Dict, Any, Optional
import tiktoken
import re

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class TextChunker:
    """
    Split text into chunks for embedding and search
    
    Uses token-based chunking with overlap to preserve context
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",  # For GPT-3.5/GPT-4
    ):
        """
        Initialize text chunker
        
        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
            encoding_name: Tokenizer encoding to use
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding(encoding_name)
        
        logger.info(
            "TextChunker initialized",
            extra={
                "chunk_size": chunk_size,
                "overlap": chunk_overlap,
                "encoding": encoding_name,
            }
        )
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text
        
        Args:
            text: Text to count
            
        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))
    
    def split_text_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences
        
        Args:
            text: Text to split
            
        Returns:
            List of sentences
        """
        # Simple sentence splitter (can be improved with NLTK)
        sentences = re.split(r'[.!?]+\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Chunk text into smaller pieces with overlap
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to include in chunks
            
        Returns:
            List of chunks with metadata
            
        Example:
            >>> chunker = TextChunker(chunk_size=500, chunk_overlap=50)
            >>> chunks = chunker.chunk_text("Long text here...")
            >>> print(len(chunks))
            10
            >>> print(chunks[0])
            {
                "text": "...",
                "index": 0,
                "tokens": 500,
                "metadata": {"page": 1}
            }
        """
        if not text or not text.strip():
            return []
        
        # Split into sentences first
        sentences = self.split_text_into_sentences(text)
        
        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            
            # If single sentence is too large, split it
            if sentence_tokens > self.chunk_size:
                # If we have accumulated text, save it first
                if current_chunk:
                    chunks.append({
                        "text": " ".join(current_chunk),
                        "index": chunk_index,
                        "tokens": current_tokens,
                        "metadata": metadata or {},
                    })
                    chunk_index += 1
                    current_chunk = []
                    current_tokens = 0
                
                # Split large sentence by words
                words = sentence.split()
                temp_chunk = []
                temp_tokens = 0
                
                for word in words:
                    word_tokens = self.count_tokens(word + " ")
                    if temp_tokens + word_tokens > self.chunk_size:
                        chunks.append({
                            "text": " ".join(temp_chunk),
                            "index": chunk_index,
                            "tokens": temp_tokens,
                            "metadata": metadata or {},
                        })
                        chunk_index += 1
                        # Keep overlap
                        overlap_words = temp_chunk[-10:] if len(temp_chunk) > 10 else temp_chunk
                        temp_chunk = overlap_words + [word]
                        temp_tokens = self.count_tokens(" ".join(temp_chunk))
                    else:
                        temp_chunk.append(word)
                        temp_tokens += word_tokens
                
                # Add remaining
                if temp_chunk:
                    current_chunk = temp_chunk
                    current_tokens = temp_tokens
                
                continue
            
            # Check if adding sentence exceeds chunk size
            if current_tokens + sentence_tokens > self.chunk_size:
                # Save current chunk
                if current_chunk:
                    chunks.append({
                        "text": " ".join(current_chunk),
                        "index": chunk_index,
                        "tokens": current_tokens,
                        "metadata": metadata or {},
                    })
                    chunk_index += 1
                
                # Start new chunk with overlap
                # Keep last few sentences for overlap
                overlap_size = 0
                overlap_sentences = []
                for prev_sent in reversed(current_chunk):
                    sent_tokens = self.count_tokens(prev_sent)
                    if overlap_size + sent_tokens <= self.chunk_overlap:
                        overlap_sentences.insert(0, prev_sent)
                        overlap_size += sent_tokens
                    else:
                        break
                
                current_chunk = overlap_sentences + [sentence]
                current_tokens = self.count_tokens(" ".join(current_chunk))
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
        
        # Add final chunk
        if current_chunk:
            chunks.append({
                "text": " ".join(current_chunk),
                "index": chunk_index,
                "tokens": current_tokens,
                "metadata": metadata or {},
            })
        
        logger.info(
            "Text chunked",
            extra={
                "total_chunks": len(chunks),
                "avg_tokens": sum(c["tokens"] for c in chunks) / len(chunks) if chunks else 0,
            }
        )
        
        return chunks


# Singleton instance
_text_chunker: Optional[TextChunker] = None


def get_text_chunker(
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> TextChunker:
    """
    Get or create TextChunker instance
    
    Args:
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks
        
    Returns:
        TextChunker instance
    """
    global _text_chunker
    
    if _text_chunker is None:
        _text_chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    
    return _text_chunker