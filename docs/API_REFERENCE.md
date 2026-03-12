"""
API Reference for Interactive Components

This module provides the public APIs and interfaces for the interactive
components, RAG engine, and error correction features.
"""

# ============================================================================
# RAGEngine API
# ============================================================================

class RAGEngine:
    """
    Retrieval-Augmented Generation engine for semantic search and querying.
    
    Usage:
        from src.rag_engine import RAGEngine
        
        rag = RAGEngine(pdf_text, topics, llm_client)
        
        # Query for information
        result = rag.query("What are the main concepts?")
        print(result["answer"])
        
        # Get context for a topic
        context = rag.get_topic_context("t1", use_llm=True)
        print(context["enhanced_description"])
        
        # Find related topics
        related = rag.suggest_related_topics("Machine Learning")
    """
    
    def __init__(self, pdf_text: str, topics: list, llm_client = None):
        """
        Initialize RAG engine with document and topics.
        
        Args:
            pdf_text (str): Full extracted PDF text
            topics (list): List of extracted topic dictionaries
            llm_client (LLMClient, optional): Client for LLM operations
        """
        pass
    
    def query(self, question: str, top_k: int = 3) -> dict:
        """
        Query the document for relevant information.
        
        Args:
            question (str): Natural language question
            top_k (int): Number of results to return (default: 3)
        
        Returns:
            dict: {
                "question": str,
                "relevant_chunks": [{"text": str, "score": float}, ...],
                "relevant_topics": [{"title": str, "match_score": float}, ...],
                "answer": str (LLM-generated if llm_client available)
            }
        
        Example:
            result = rag.query("What is machine learning?")
            if result["answer"]:
                print(result["answer"])
        """
        pass
    
    def get_topic_context(self, topic_id: str, use_llm: bool = True) -> dict:
        """
        Get detailed context and related content for a specific topic.
        
        Args:
            topic_id (str): Topic ID (e.g., "t1", "t2")
            use_llm (bool): Whether to generate enhanced description
        
        Returns:
            dict: {
                "topic": dict,  # Full topic data
                "related_content": [{"text": str, "score": float}, ...],
                "enhanced_description": str (if use_llm=True)
            }
        """
        pass
    
    def suggest_related_topics(self, topic_title: str) -> list:
        """
        Suggest topics related to a given topic.
        
        Args:
            topic_title (str): Title of reference topic
        
        Returns:
            list: Up to 3 related topics:
                [{"title": str, "difficulty": str, "match_score": float}, ...]
        """
        pass


# ============================================================================
# InteractiveSession API
# ============================================================================

class InteractiveSession:
    """
    Advanced interactive topic review session with RAG and error correction.
    
    Usage:
        from src.interactive import InteractiveSession
        
        session = InteractiveSession(
            pdf_text=pdf_text,
            topics=topics,
            user_profile=profile,
            llm_client=llm,
            enable_rag=True,
            enable_corrections=True
        )
        
        approved, updated_profile, should_continue = session.run_interactive_loop()
    """
    
    def __init__(
        self,
        pdf_text: str,
        topics: list,
        user_profile: dict,
        llm_client = None,
        enable_rag: bool = True,
        enable_corrections: bool = True,
    ):
        """
        Initialize interactive review session.
        
        Args:
            pdf_text (str): Full extracted PDF text
            topics (list): List of extracted topics
            user_profile (dict): User profile with preferences
            llm_client (LLMClient, optional): For enhanced features
            enable_rag (bool): Enable RAG features (search/query)
            enable_corrections (bool): Enable error detection/correction
        """
        pass
    
    def run_interactive_loop(self) -> tuple:
        """
        Run the main interactive menu loop.
        
        Returns:
            tuple: (approved_topics, updated_user_profile, should_continue)
                - approved_topics (list): Final list of topics after edits
                - updated_user_profile (dict): Updated user profile
                - should_continue (bool): Whether user saved or aborted
        
        This method:
        1. Displays main menu
        2. Processes user selections
        3. Calls appropriate handlers for each menu option
        4. Returns when user selects "Save and continue" or "Abort"
        """
        pass
    
    # Public methods for menu operations
    
    def _review_topics(self):
        """Display all topics with option to view details of specific topics."""
        pass
    
    def _query_content(self):
        """
        Interactive RAG query interface.
        
        Allows user to ask questions about PDF content.
        Displays matching topics, content excerpts, and LLM-generated answers.
        """
        pass
    
    def _edit_topics(self):
        """
        Edit details of specific topics.
        
        Options:
        - Title
        - Difficulty (beginner/intermediate/advanced)
        - Estimated hours
        - Description
        """
        pass
    
    def _correct_mistakes(self):
        """
        Identify and correct potential LLM mistakes.
        
        Auto-detects:
        - Duplicate topics (merges them)
        - Missing descriptions (suggests from PDF)
        - Invalid field values (offers corrections)
        
        Requires: enable_corrections=True and llm_client
        """
        pass
    
    def _add_custom_topic(self):
        """
        Manually create a new topic.
        
        User enters:
        - Title (required)
        - Difficulty
        - Estimated hours
        - Description
        
        RAG searches for related content and can suggest subtopics
        """
        pass
    
    def _merge_topics(self):
        """
        Merge two topics into one.
        
        Combines:
        - Descriptions (concatenated)
        - Subtopics (merged and deduplicated)
        
        Removes duplicate topic from list
        """
        pass
    
    def _update_profile(self):
        """
        Update user learner profile.
        
        Editable fields:
        - hard_topics (list)
        - easy_topics (list)
        - time_available (float/hours per week)
        - learning_style (string)
        """
        pass


# ============================================================================
# Integration with Graph Pipeline
# ============================================================================

def node_human_review(state: dict) -> dict:
    """
    LangGraph node for interactive topic review.
    
    This node:
    1. Checks if in MCP mode (returns awaiting_review)
    2. Otherwise, runs InteractiveSession
    3. Returns approved topics and updated profile
    
    Input state keys:
        - topics (list)
        - pdf_text (str)
        - user_profile (dict)
        - llm_provider (str)
        - llm_model (str)
        - ollama_url (str)
        - _mcp_mode (bool)
        - _enable_rag (bool)
        - _enable_corrections (bool)
    
    Output:
        dict with:
        - approved_topics (list)
        - user_profile (dict)
        - status (str): "reviewed"
    """
    pass


# ============================================================================
# Configuration
# ============================================================================

"""
Interactive mode configuration in src/interactive_config.py

INTERACTIVE_MODE_ENABLED = True           # Enable interactive interface
RAG_ENABLED = True                        # Enable RAG features by default
AUTO_CORRECTIONS_ENABLED = True           # Enable auto-corrections by default

# RAG configuration
RAG_CHUNK_SIZE = 500                      # Words per search chunk
RAG_TOP_K = 3                             # Number of search results

# Error detection thresholds
MIN_DESCRIPTION_LENGTH = 20               # Minimum description chars
MAX_DUPLICATE_DISTANCE = 0.8              # Similarity threshold
"""

# ============================================================================
# Command-line Usage
# ============================================================================

"""
Enable interactive mode when running Pilot:

    # All features enabled
    python main.py --pdf book.pdf --vault ~/MyVault --interactive
    
    # Disable RAG features
    python main.py --pdf book.pdf --vault ~/MyVault --interactive --no-rag
    
    # Disable auto-corrections
    python main.py --pdf book.pdf --vault ~/MyVault --interactive --skip-corrections
    
    # Both disabled
    python main.py --pdf book.pdf --vault ~/MyVault --interactive --no-rag --skip-corrections
"""

# ============================================================================
# Data Structures
# ============================================================================

"""
Topic Dictionary Structure:
{
    "id": "t1",                           # Unique identifier
    "title": "Machine Learning",          # Topic name
    "difficulty": "intermediate",         # beginner | intermediate | advanced
    "estimated_hours": 2.5,               # Estimated study time
    "description": "Learn ML algorithms", # Summary
    "subtopics": ["Supervised", "Unsupervised"]  # Sub-concepts
}

RAG Query Result:
{
    "question": "What is ML?",
    "relevant_chunks": [
        {
            "text": "Machine learning is...",
            "score": 0.95,
            "chunk_index": 5
        }
    ],
    "relevant_topics": [
        {
            "title": "Machine Learning Basics",
            "difficulty": "beginner",
            "estimated_hours": 2.0,
            "match_score": 0.92
        }
    ],
    "answer": "Machine learning is... (LLM generated)"
}

Error Detection Result:
[
    {
        "description": "Duplicate topic detected",
        "type": "duplicate",
        "topic": {...},
        "severity": "medium",
        "topic_idx": 5,
        "original_idx": 2
    }
]

User Profile:
{
    "time_available": 2.0,                # Hours per week
    "learning_style": "visual",           # Learning preference
    "hard_topics": ["Calculus"],          # Difficult topics
    "easy_topics": ["Basics"]             # Easy topics
}
"""

# ============================================================================
# Examples
# ============================================================================

"""
# Example 1: Query RAG Engine

from src.rag_engine import RAGEngine
from src.llm import LLMClient

llm = LLMClient(provider="openai", model="gpt-4o")
rag = RAGEngine(pdf_text, topics, llm)

# Ask a question
result = rag.query("What are the main algorithms discussed?")
print("Answer:", result["answer"])

# Get topic context
context = rag.get_topic_context("t1")
print("Enhanced description:", context["enhanced_description"])

# Find related topics
related = rag.suggest_related_topics("Machine Learning")
for topic in related:
    print(f"- {topic['title']} ({topic['match_score']:.0%} match)")


# Example 2: Run Interactive Session

from src.interactive import InteractiveSession

session = InteractiveSession(
    pdf_text=pdf_text,
    topics=topics,
    user_profile={"time_available": 3.0, "learning_style": "visual"},
    llm_client=llm,
    enable_rag=True,
    enable_corrections=True
)

approved_topics, updated_profile, should_continue = session.run_interactive_loop()

if should_continue:
    print(f"User approved {len(approved_topics)} topics")
    print(f"Updated profile: {updated_profile}")


# Example 3: Custom Error Detection

from src.interactive import InteractiveSession

session = InteractiveSession(pdf_text, topics, profile, llm)
issues = session._detect_issues()

for issue in issues:
    print(f"{issue['severity']}: {issue['description']}")
    print(f"  Topic: {issue['topic']['title']}")
"""
