"""
Text Extractor
Routes to appropriate extractor based on file type
Phase 4, Step 2: Document parsing and text chunking
"""

from pathlib import Path
from typing import Tuple, Dict, Any

from app.services.extractors.pdf_extractor import extract_text_from_pdf
from app.services.extractors.docx_extractor import extract_text_from_docx
from app.services.extractors.txt_extractor import extract_text_from_txt
from app.services.extractors.html_extractor import extract_text_from_html
from app.services.extractors.markdown_extractor import extract_text_from_markdown
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def extract_text(file_path: Path, file_type: str) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text from document based on file type
    
    Args:
        file_path: Path to file
        file_type: Type of file (pdf, docx, txt, html, md)
        
    Returns:
        Tuple of (text_content, metadata)
        
    Raises:
        ValueError: If file type is not supported
        Exception: If extraction fails
        
    Example:
        >>> text, metadata = extract_text("doc.pdf", "pdf")
        >>> print(len(text))
        5000
    """
    extractors = {
        "pdf": extract_text_from_pdf,
        "docx": extract_text_from_docx,
        "txt": extract_text_from_txt,
        "html": extract_text_from_html,
        "md": extract_text_from_markdown,
    }
    
    if file_type not in extractors:
        raise ValueError(f"Unsupported file type: {file_type}")
    
    logger.info(
        "Extracting text",
        extra={"file": file_path.name, "type": file_type}
    )
    
    extractor = extractors[file_type]
    return extractor(file_path)