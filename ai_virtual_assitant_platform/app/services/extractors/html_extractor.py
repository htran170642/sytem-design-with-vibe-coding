"""
HTML Text Extractor
Extract text from HTML files
Phase 4, Step 2: Document parsing and text chunking
"""

from pathlib import Path
from typing import Tuple, Dict, Any
from bs4 import BeautifulSoup

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def extract_text_from_html(file_path: Path) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text from HTML file
    
    Args:
        file_path: Path to HTML file
        
    Returns:
        Tuple of (text_content, metadata)
        
    Example:
        >>> text, metadata = extract_text_from_html("page.html")
        >>> print(metadata["title"])
        "My Page Title"
    """
    try:
        # Read HTML
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            html_content = f.read()
        
        # Parse HTML
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text
        text = soup.get_text(separator="\n", strip=True)
        
        # Extract metadata
        metadata = {
            "title": soup.title.string if soup.title else None,
            "word_count": len(text.split()),
        }
        
        # Try to get meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            metadata["description"] = meta_desc.get("content")
        
        logger.info(
            "HTML extracted",
            extra={
                "file": file_path.name,
                "title": metadata["title"],
                "word_count": metadata["word_count"],
            }
        )
        
        return text, metadata
        
    except Exception as e:
        logger.error(f"Error extracting HTML: {e}", exc_info=True)
        raise Exception(f"Failed to extract HTML: {str(e)}")