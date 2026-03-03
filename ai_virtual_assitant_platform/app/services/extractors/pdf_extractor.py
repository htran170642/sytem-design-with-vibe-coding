"""
PDF Text Extractor
Extract text and metadata from PDF files
Phase 4, Step 2: Document parsing and text chunking
"""

from pathlib import Path
from typing import Tuple, Dict, Any
import pypdf

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def extract_text_from_pdf(file_path: Path) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text and metadata from PDF file
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Tuple of (text_content, metadata)
        
    Raises:
        Exception: If PDF cannot be read
        
    Example:
        >>> text, metadata = extract_text_from_pdf("document.pdf")
        >>> print(metadata["pages"])
        10
    """
    try:
        text_parts = []
        metadata = {
            "pages": 0,
            "author": None,
            "title": None,
            "created_date": None,
        }
        
        # Open PDF
        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            
            # Get page count
            metadata["pages"] = len(reader.pages)
            
            # Extract metadata
            if reader.metadata:
                metadata["author"] = reader.metadata.get("/Author")
                metadata["title"] = reader.metadata.get("/Title")
                metadata["created_date"] = reader.metadata.get("/CreationDate")
            
            # Extract text from each page
            for page_num, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    if text.strip():
                        # Add page marker
                        text_parts.append(f"[Page {page_num + 1}]\n{text}\n")
                except Exception as e:
                    logger.warning(
                        f"Failed to extract text from page {page_num + 1}: {e}"
                    )
                    continue
        
        # Combine all text
        full_text = "\n".join(text_parts)
        
        # Add word count
        metadata["word_count"] = len(full_text.split())
        
        logger.info(
            "PDF extracted",
            extra={
                "file": file_path.name,
                "pages": metadata["pages"],
                "word_count": metadata["word_count"],
            }
        )
        
        return full_text, metadata
        
    except Exception as e:
        logger.error(f"Error extracting PDF: {e}", exc_info=True)
        raise Exception(f"Failed to extract PDF: {str(e)}")