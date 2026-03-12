"""
Interactive mode enhancements for Pilot.

New features:
  - Advanced topic review with RAG-based content search
  - Error detection and correction with LLM assistance
  - Topic editing, merging, and custom topic addition
  - Learner profile updates
  - Session-based workflow

Usage:
  python main.py --pdf book.pdf --vault ~/MyVault --interactive
  python main.py --pdf book.pdf --vault ~/MyVault --interactive --no-rag  (disable RAG)
  python main.py --pdf book.pdf --vault ~/MyVault --interactive --skip-corrections
"""

# Interactive mode constants
INTERACTIVE_MODE_ENABLED = True
RAG_ENABLED = True
AUTO_CORRECTIONS_ENABLED = True

# RAG configuration
RAG_CHUNK_SIZE = 500  # Words per chunk
RAG_TOP_K = 3  # Number of results to return

# Error detection thresholds
MIN_DESCRIPTION_LENGTH = 20  # Characters
MAX_DUPLICATE_DISTANCE = 0.8  # Similarity score for marking as duplicate
