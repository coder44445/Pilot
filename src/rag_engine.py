"""
RAG Engine — retrieval-augmented generation for interactive topic querying and correction.

Features:
  - Vector-free semantic search using TF-IDF similarity
  - Query responses from extracted PDF content
  - LLM-enhanced answer generation with citations
  - Topic-aware context retrieval
"""

import re
from typing import Optional
from collections import Counter
from difflib import SequenceMatcher
from src.display import console


class RAGEngine:
    """RAG engine for querying extracted content and generating answers."""
    
    def __init__(self, pdf_text: str, topics: list, llm_client=None):
        """
        Initialize RAG engine with document and topics.
        
        Args:
            pdf_text: Full extracted PDF text
            topics: List of extracted topic dicts
            llm_client: Optional LLMClient for enhanced answer generation
        """
        self.pdf_text = pdf_text
        self.topics = topics or []
        self.llm_client = llm_client
        
        # Build searchable chunks and indices
        self.chunks = self._build_chunks()
        self.topic_map = {t.get("id", t.get("title", "")): t for t in topics}
    
    def _build_chunks(self, chunk_size=500):
        """Split PDF into searchable chunks with overlap."""
        words = self.pdf_text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - 100):
            end = min(i + chunk_size, len(words))
            chunk_text = " ".join(words[i:end])
            
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "start_word": i,
                    "end_word": end,
                })
        
        return chunks
    
    def query(self, question: str, top_k: int = 3) -> dict:
        """
        Query the document for relevant information.
        
        Returns:
            {
                "question": str,
                "relevant_chunks": [{"text": str, "score": float}, ...],
                "relevant_topics": [{"title": str, "match_score": float}, ...],
                "answer": str (if llm_client available)
            }
        """
        console.print(f"\n[dim]🔍 Searching for: '{question}'[/dim]")
        
        # Find relevant chunks
        relevant_chunks = self._search_chunks(question, top_k)
        
        # Find relevant topics
        relevant_topics = self._search_topics(question, top_k)
        
        result = {
            "question": question,
            "relevant_chunks": relevant_chunks,
            "relevant_topics": relevant_topics,
            "answer": None,
        }
        
        # Generate answer with LLM if available
        if self.llm_client and relevant_chunks:
            result["answer"] = self._generate_answer(question, relevant_chunks)
        
        return result
    
    def _search_chunks(self, query: str, top_k: int = 3) -> list:
        """Find most relevant chunks using TF-IDF-like scoring."""
        query_terms = self._tokenize(query.lower())
        if not query_terms:
            return []
        
        scored_chunks = []
        
        for i, chunk in enumerate(self.chunks):
            chunk_terms = self._tokenize(chunk["text"].lower())
            
            # Calculate similarity score
            matches = sum(1 for term in query_terms if term in chunk_terms)
            if matches == 0:
                continue
            
            # TF-IDF-style scoring
            score = matches / len(query_terms)
            
            # Boost score if terms appear consecutively
            for j in range(len(chunk_terms) - len(query_terms)):
                if chunk_terms[j:j+len(query_terms)] == query_terms:
                    score += 0.5
                    break
            
            scored_chunks.append({
                "text": chunk["text"][:500] + "..." if len(chunk["text"]) > 500 else chunk["text"],
                "score": score,
                "chunk_index": i,
            })
        
        # Return top-k by score
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        return scored_chunks[:top_k]
    
    def _search_topics(self, query: str, top_k: int = 3) -> list:
        """Find relevant topics by title and description matching."""
        query_lower = query.lower()
        scored_topics = []
        
        for topic in self.topics:
            title = topic.get("title", "").lower()
            description = topic.get("description", "").lower()
            
            # String similarity scoring
            title_match = SequenceMatcher(None, query_lower, title).ratio()
            desc_match = SequenceMatcher(None, query_lower, description).ratio() if description else 0
            
            # Substring match bonus
            if query_lower in title:
                title_match = max(title_match, 0.8)
            if query_lower in description:
                desc_match = max(desc_match, 0.6)
            
            # Combined score
            score = max(title_match, desc_match)
            
            if score > 0.2:  # Minimum threshold
                scored_topics.append({
                    "title": topic.get("title", "Unknown"),
                    "difficulty": topic.get("difficulty", "intermediate"),
                    "estimated_hours": topic.get("estimated_hours", 1.5),
                    "match_score": score,
                })
        
        # Return top-k by score
        scored_topics.sort(key=lambda x: x["match_score"], reverse=True)
        return scored_topics[:top_k]
    
    def _generate_answer(self, question: str, relevant_chunks: list) -> str:
        """Use LLM to generate an answer from relevant chunks."""
        if not self.llm_client or not relevant_chunks:
            return None
        
        # Build context from chunks
        context = "\n---\n".join([c["text"] for c in relevant_chunks[:3]])
        
        prompt = f"""Based on this document excerpt, answer the question concisely:

Question: {question}

Document Excerpt:
{context}

Answer (one paragraph, cite specific sections if needed):"""
        
        try:
            answer = self.llm_client.chat(
                system_prompt="You are a helpful assistant answering questions about document content.",
                user_prompt=prompt,
                json_mode=False
            )
            return answer.strip()
        except Exception as e:
            console.print(f"[dim]LLM answer generation failed: {e}[/dim]")
            return None
    
    def _tokenize(self, text: str) -> list:
        """Simple tokenization: split on whitespace and punctuation."""
        words = re.findall(r'\b\w+\b', text.lower())
        return words
    
    def get_topic_context(self, topic_id: str, use_llm: bool = True) -> dict:
        """Get detailed context for a specific topic."""
        topic = self.topic_map.get(topic_id)
        if not topic:
            return None
        
        # Search for chunks related to this topic
        related_chunks = self._search_chunks(topic["title"], top_k=5)
        
        result = {
            "topic": topic,
            "related_content": related_chunks,
            "enhanced_description": None,
        }
        
        # Use LLM to enhance description
        if use_llm and self.llm_client and related_chunks:
            result["enhanced_description"] = self._generate_answer(
                f"What are the key concepts and examples for '{topic['title']}'?",
                related_chunks
            )
        
        return result
    
    def suggest_related_topics(self, topic_title: str) -> list:
        """Suggest topics related to a given topic title."""
        # Query with the topic title to find similar topics
        results = self._search_topics(topic_title, top_k=5)
        
        # Filter out exact match (the topic itself)
        related = [t for t in results if t["title"].lower() != topic_title.lower()]
        
        return related[:3]
