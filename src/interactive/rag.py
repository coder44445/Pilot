"""
RAG Engine — retrieval-augmented generation for interactive topic querying.

Features:
  - Lightweight TF-IDF style semantic search
  - Stopword removal
  - Precomputed chunk tokens for faster retrieval
  - Topic-aware search
  - Optional LLM answer generation
"""

import re
from typing import Optional, List, Dict
from difflib import SequenceMatcher
from src.display import console


STOPWORDS = {
    "the","is","a","an","of","to","in","and","for","on","with",
    "that","this","as","by","it","are","be","or","from","at"
}


class RAGEngine:
    """RAG engine for querying extracted document content."""

    def __init__(self, pdf_text: str, topics: list, llm_client=None):
        """
        Initialize RAG engine.

        Args:
            pdf_text: extracted PDF text
            topics: list of topic dictionaries
            llm_client: optional LLM client
        """

        self.pdf_text = pdf_text
        self.topics = topics or []
        self.llm_client = llm_client

        # Build chunks
        self.chunks = self._build_chunks()

        # Precompute tokens (performance boost)
        self.chunk_tokens = [
            self._tokenize(chunk["text"]) for chunk in self.chunks
        ]

        # Topic map
        self.topic_map = {
            t.get("id", t.get("title", "")): t for t in self.topics
        }

    
    # Chunking
    def _build_chunks(self, chunk_size: int = 250, overlap: int = 50):
        """Split document into overlapping chunks."""

        words = self.pdf_text.split()
        chunks = []

        step = chunk_size - overlap

        for i in range(0, len(words), step):
            end = min(i + chunk_size, len(words))
            chunk_text = " ".join(words[i:end])

            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "start_word": i,
                    "end_word": end
                })

        return chunks

    
    # Query Interface
    def query(self, question: str, top_k: int = 3) -> Dict:
        """
        Query the document.

        Returns dictionary with:
            question
            relevant_chunks
            relevant_topics
            answer
        """

        console.print(f"\n[dim]🔍 Searching: '{question}'[/dim]")

        relevant_chunks = self._search_chunks(question, top_k)
        relevant_topics = self._search_topics(question, top_k)

        result = {
            "question": question,
            "relevant_chunks": relevant_chunks,
            "relevant_topics": relevant_topics,
            "answer": None
        }

        if self.llm_client and relevant_chunks:
            result["answer"] = self._generate_answer(question, relevant_chunks)

        return result

    
    # Chunk Search
    def _search_chunks(self, query: str, top_k: int = 3) -> List[Dict]:
        """Find most relevant chunks."""

        query_terms = self._tokenize(query)

        if not query_terms:
            return []

        scored_chunks = []

        for i, chunk in enumerate(self.chunks):

            chunk_terms = self.chunk_tokens[i]

            matches = sum(
                1 for term in query_terms if term in chunk_terms
            )

            if matches == 0:
                continue

            score = matches / len(query_terms)

            # bonus for consecutive match
            for j in range(len(chunk_terms) - len(query_terms) + 1):
                if chunk_terms[j:j+len(query_terms)] == query_terms:
                    score += 0.4
                    break

            score = min(score, 1.0)

            scored_chunks.append({
                "text": chunk["text"][:500] + "..." if len(chunk["text"]) > 500 else chunk["text"],
                "score": round(score, 3),
                "chunk_index": i
            })

        scored_chunks.sort(key=lambda x: x["score"], reverse=True)

        return scored_chunks[:top_k]

    
    # Topic Search
    def _search_topics(self, query: str, top_k: int = 3) -> List[Dict]:

        query_lower = query.lower()
        scored_topics = []

        for topic in self.topics:

            title = topic.get("title", "").lower()
            description = topic.get("description", "").lower()

            title_score = SequenceMatcher(None, query_lower, title).ratio()
            desc_score = SequenceMatcher(None, query_lower, description).ratio() if description else 0

            if query_lower in title:
                title_score = max(title_score, 0.8)

            if query_lower in description:
                desc_score = max(desc_score, 0.6)

            score = max(title_score, desc_score)

            if score > 0.25:

                scored_topics.append({
                    "title": topic.get("title", "Unknown"),
                    "difficulty": topic.get("difficulty", "intermediate"),
                    "estimated_hours": topic.get("estimated_hours", 1.5),
                    "match_score": round(score, 3)
                })

        scored_topics.sort(key=lambda x: x["match_score"], reverse=True)

        return scored_topics[:top_k]

    
    # Answer Generation
    def _generate_answer(self, question: str, relevant_chunks: List[Dict]) -> Optional[str]:

        if not self.llm_client:
            return None

        context = "\n---\n".join([
            chunk["text"] for chunk in relevant_chunks[:3]
        ])

        prompt = f"""
            Answer the question using the document context.

            Question:
            {question}

            Context:
            {context}

            Answer in one concise paragraph and reference the context if needed.
            """

        try:

            answer = self.llm_client.chat(
                system_prompt="You answer questions about document content.",
                user_prompt=prompt,
                json_mode=False
            )

            return answer.strip()

        except Exception as e:

            console.print(f"[dim]LLM generation failed: {e}[/dim]")
            return None

    
    # Tokenization
    def _tokenize(self, text: str) -> List[str]:

        words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())

        return [
            w for w in words
            if w not in STOPWORDS
        ]

    
    # Topic Context
    def get_topic_context(self, topic_id: str, use_llm: bool = True):

        topic = self.topic_map.get(topic_id)

        if not topic:
            return None

        related_chunks = self._search_chunks(topic["title"], top_k=5)

        result = {
            "topic": topic,
            "related_content": related_chunks,
            "enhanced_description": None
        }

        if use_llm and self.llm_client and related_chunks:

            result["enhanced_description"] = self._generate_answer(
                f"What are the key concepts of '{topic['title']}'?",
                related_chunks
            )

        return result

    
    # Related Topics
    def suggest_related_topics(self, topic_title: str):

        results = self._search_topics(topic_title, top_k=5)

        related = [
            r for r in results
            if r["title"].lower() != topic_title.lower()
        ]

        return related[:3]