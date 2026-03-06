"""
PDF text extraction using PyMuPDF (fitz).
Falls back to pdfplumber if fitz is unavailable.
"""

from pathlib import Path
from typing import Tuple


def extract_pdf_text(pdf_path: Path) -> Tuple[str, dict]:
    """
    Extract full text from a PDF file.
    Returns (text, metadata_dict).
    """
    text = ""
    metadata = {"pages": 0, "word_count": 0, "title": pdf_path.stem}

    # Try PyMuPDF first (fastest, best layout preservation)
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        metadata["pages"] = len(doc)

        # Extract doc metadata if available
        doc_meta = doc.metadata
        if doc_meta.get("title"):
            metadata["title"] = doc_meta["title"]
        if doc_meta.get("author"):
            metadata["author"] = doc_meta["author"]

        pages_text = []
        for page_num, page in enumerate(doc, 1):
            page_text = page.get_text("text")
            if page_text.strip():
                pages_text.append(f"[Page {page_num}]\n{page_text}")

        text = "\n\n".join(pages_text)
        doc.close()

    except ImportError:
        # Fallback: pdfplumber
        try:
            import pdfplumber

            with pdfplumber.open(str(pdf_path)) as pdf:
                metadata["pages"] = len(pdf.pages)
                pages_text = []
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        pages_text.append(f"[Page {page_num}]\n{page_text}")
                text = "\n\n".join(pages_text)

        except ImportError:
            raise ImportError(
                "No PDF library found. Install one:\n"
                "  pip install pymupdf        (recommended)\n"
                "  pip install pdfplumber     (fallback)"
            )

    metadata["word_count"] = len(text.split())

    if not text.strip():
        raise ValueError(
            "Could not extract text from PDF. "
            "It may be a scanned/image PDF — try OCR first with: ocrmypdf input.pdf output.pdf"
        )

    # Truncate very large PDFs to avoid LLM token limits
    # Keep first 80k words (~100k tokens), enough for most books
    words = text.split()
    if len(words) > 80_000:
        text = " ".join(words[:80_000])
        text += "\n\n[NOTE: PDF truncated at 80,000 words for processing]"

    return text, metadata
