"""
TXT Text Extractor
Extract text from plain text files
Phase 4, Step 2: Document parsing and text chunking
"""

from pathlib import Path
from typing import Tuple, Dict, Any
import chardet

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def extract_text_from_txt(file_path: Path) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text from plain text file
    
    Args:
        file_path: Path to TXT file
        
    Returns:
        Tuple of (text_content, metadata)
        
    Example:
        >>> text, metadata = extract_text_from_txt("document.txt")
        >>> print(metadata["encoding"])
        utf-8
    """
    try:
        # Detect encoding
        with open(file_path, "rb") as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result["encoding"] or "utf-8"
        
        # Read with detected encoding
        with open(file_path, "r", encoding=encoding, errors="replace") as f:
            text = f.read()
        
        # Extract metadata
        lines = text.split("\n")
        metadata = {
            "encoding": encoding,
            "lines": len(lines),
            "word_count": len(text.split()),
        }
        
        logger.info(
            "TXT extracted",
            extra={
                "file": file_path.name,
                "encoding": encoding,
                "lines": metadata["lines"],
                "word_count": metadata["word_count"],
            }
        )
        
        return text, metadata
        
    except Exception as e:
        logger.error(f"Error extracting TXT: {e}", exc_info=True)
        raise Exception(f"Failed to extract TXT: {str(e)}")