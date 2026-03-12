"""
URL content extraction.
Fetches and extracts text from web pages.
Follows the same interface as pdf_extractor.py for consistency.
"""

from typing import Tuple
import re


def extract_url_text(url: str) -> Tuple[str, dict]:
    """
    Extract full text from a URL.
    Returns (text, metadata_dict).
    
    Metadata includes:
    - url: the URL that was fetched
    - title: page title (from <title> or <h1>)
    - word_count: word count of extracted text
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError(
            "URL extraction requires additional packages:\n"
            "  pip install requests beautifulsoup4\n"
            "Install these or use a PDF instead."
        )
    
    metadata = {"url": url, "title": url, "word_count": 0}
    text = ""
    
    try:
        # Fetch the page with a reasonable timeout
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Extract title
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text().strip()
        else:
            h1_tag = soup.find("h1")
            if h1_tag:
                metadata["title"] = h1_tag.get_text().strip()
        
        # Remove script and style tags
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
        
        # Extract text
        raw_text = soup.get_text(separator="\n", strip=True)
        
        # Clean up excessive whitespace while preserving structure
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        text = "\n\n".join(lines)
        
        # Limit to reasonable size (same as PDF: 80k words)
        words = text.split()
        if len(words) > 80_000:
            text = " ".join(words[:80_000])
            text += "\n\n[NOTE: URL content truncated at 80,000 words for processing]"
        
        metadata["word_count"] = len(words)
        
        if not text.strip():
            raise ValueError("Could not extract text from URL — page may be empty or JavaScript-heavy")
        
        return text, metadata
    
    except requests.ConnectionError as e:
        raise ValueError(f"Could not connect to URL: {e}\nCheck your internet connection and URL validity")
    except requests.Timeout:
        raise ValueError(f"Request timed out for URL: {url}\nThe page took too long to load")
    except requests.HTTPError as e:
        raise ValueError(f"HTTP error for URL: {e.response.status_code}\nURL may be blocked or not found")
    except Exception as e:
        raise ValueError(f"Error extracting URL: {e}")
