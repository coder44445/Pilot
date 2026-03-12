"""
Typed configuration dataclasses.

Replaces the raw dicts that were being passed around everywhere.
Single source of truth for all config shapes.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class LLMConfig:
    provider:   Literal["openai", "ollama"] = "ollama"
    model:      str  = ""          # empty = use provider default
    ollama_url: str  = "http://localhost:11434"
    timeout:    int  = 600         # seconds for OpenAI hard cap

    def resolved_model(self) -> str:
        if self.model:
            return self.model
        return "gpt-4o" if self.provider == "openai" else "llama3.1"


@dataclass
class UserProfile:
    total_days:          int   = 14
    hours_per_day:       int   = 2
    skill_level:         Literal["beginner", "basics", "intermediate", "advanced"] = "beginner"
    goal:                Literal["exam_prep", "practical_project", "deep_understanding", "quick_overview"] = "practical_project"
    learning_style:      Literal["theory_first", "examples_first", "mixed"] = "mixed"
    hard_topics:         list  = field(default_factory=list)
    easy_topics:         list  = field(default_factory=list)
    include_quizzes:     bool  = True
    include_summaries:   bool  = True

    @property
    def total_hours(self) -> int:
        return self.total_days * self.hours_per_day

    def to_dict(self) -> dict:
        return {
            "total_days":        self.total_days,
            "hours_per_day":     self.hours_per_day,
            "total_hours":       self.total_hours,
            "skill_level":       self.skill_level,
            "goal":              self.goal,
            "learning_style":    self.learning_style,
            "hard_topics":       self.hard_topics,
            "easy_topics":       self.easy_topics,
            "include_quizzes":   self.include_quizzes,
            "include_summaries": self.include_summaries,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UserProfile":
        return cls(
            total_days=        d.get("total_days", 14),
            hours_per_day=     d.get("hours_per_day", 2),
            skill_level=       d.get("skill_level", "beginner"),
            goal=              d.get("goal", "practical_project"),
            learning_style=    d.get("learning_style", "mixed"),
            hard_topics=       d.get("hard_topics", []),
            easy_topics=       d.get("easy_topics", []),
            include_quizzes=   d.get("include_quizzes", True),
            include_summaries= d.get("include_summaries", True),
        )
