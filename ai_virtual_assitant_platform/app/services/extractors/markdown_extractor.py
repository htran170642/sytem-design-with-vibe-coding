"""
Markdown Text Extractor
Extract text from Markdown files
Phase 4, Step 2: Document parsing and text chunking
"""

from pathlib import Path
from typing import Tuple, Dict, Any
import markdown
from bs4 import BeautifulSoup

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def extract_text_from_markdown(file_path: Path) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text from Markdown file
    
    Args:
        file_path: Path to MD file
        
    Returns:
        Tuple of (text_content, metadata)
        
    Example:
        >>> text, metadata = extract_text_from_markdown("README.md")
        >>> print(metadata["headings"])
        5
    """
    try:
        # Read markdown
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            md_content = f.read()
        
        # Convert to HTML
        html = markdown.markdown(md_content)
        
        # Parse HTML to extract text
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        
        # Count headings
        headings = md_content.count("\n#")
        
        # Extract metadata
        metadata = {
            "headings": headings,
            "word_count": len(text.split()),
        }
        
        # Try to extract title (first H1)
        first_h1 = soup.find("h1")
        if first_h1:
            metadata["title"] = first_h1.get_text()
        
        logger.info(
            "Markdown extracted",
            extra={
                "file": file_path.name,
                "headings": headings,
                "word_count": metadata["word_count"],
            }
        )
        
        return text, metadata
        
    except Exception as e:
        logger.error(f"Error extracting Markdown: {e}", exc_info=True)
        raise Exception(f"Failed to extract Markdown: {str(e)}")