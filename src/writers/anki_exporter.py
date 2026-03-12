"""
Anki flashcard exporter.
Parses quiz sections from study notes and exports to Anki CSV format.
"""

import csv
import re
from pathlib import Path
from typing import List, Tuple, Dict


def parse_quiz_section(notes_text: str) -> List[str]:
    """
    Extract quiz questions from notes.
    Looks for "Quiz Yourself" section with numbered questions.
    
    Returns list of question strings.
    """
    questions = []
    
    # Find the Quiz Yourself section
    quiz_pattern = r"###\s+Quiz Yourself.*?(?=###|\Z)"
    quiz_match = re.search(quiz_pattern, notes_text, re.DOTALL | re.IGNORECASE)
    
    if not quiz_match:
        return questions
    
    quiz_section = quiz_match.group(0)
    
    # Extract numbered questions (1. 2. 3. etc.)
    question_pattern = r"^\s*\d+\.\s+(.+?)$"
    for line in quiz_section.split("\n"):
        match = re.match(question_pattern, line.strip())
        if match:
            question = match.group(1).strip()
            if question:
                questions.append(question)
    
    return questions


def generate_anki_csv(
    notes_map: Dict[str, str],
    topic_map: Dict[str, dict],
    output_path: Path
) -> bool:
    """
    Generate Anki-compatible CSV file from extracted quizzes.
    
    Format: Front (question) | Back (topic reference)
    
    Returns True on success, False on failure.
    """
    try:
        rows = []
        
        for topic_id, notes_text in notes_map.items():
            topic = topic_map.get(topic_id, {})
            topic_title = topic.get("title", "Unknown")
            
            # Extract questions from this topic's notes
            questions = parse_quiz_section(notes_text)
            
            for question in questions:
                rows.append({
                    'Front': question,
                    'Back': f"Answer this from: {topic_title}",
                    'Topic': topic_title,
                })
        
        if not rows:
            return False  # No quizzes found
        
        # Write CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Front', 'Back', 'Topic'])
            writer.writeheader()
            writer.writerows(rows)
        
        return True
    
    except Exception as e:
        print(f"Error generating Anki CSV: {e}")
        return False


def export_anki_deck(
    notes_map: Dict[str, str],
    topic_map: Dict[str, dict],
    vault_path: Path,
    deck_name: str = "Study Plan"
) -> Path:
    """
    Export quiz flashcards to Anki CSV format.
    
    Returns path to generated CSV file, or None if no quizzes found.
    """
    from src.vault_writer import sanitize_filename
    
    subject = vault_path.name
    anki_dir = vault_path / ".anki"
    anki_dir.mkdir(exist_ok=True)
    
    csv_path = anki_dir / f"{sanitize_filename(deck_name)}_Flashcards.csv"
    
    if generate_anki_csv(notes_map, topic_map, csv_path):
        return csv_path
    
    return None
