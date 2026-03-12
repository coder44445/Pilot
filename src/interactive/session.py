"""
Interactive Interface — advanced topic review, editing, querying, and error correction.

Features:
  - Topic review with detailed editing (title, difficulty, description)
  - RAG-based content querying and search
  - Error detection and LLM-assisted correction
  - Topic merging and creation
  - Session replay from checkpoints
"""

from typing import Optional
from src.display import console
from .rag import RAGEngine
from src.llm import LLMClient
import json


class InteractiveSession:
    """Manage an interactive editing session with RAG and correction features."""
    
    def __init__(
        self,
        pdf_text: str,
        topics: list,
        user_profile: dict,
        llm_client: Optional[LLMClient] = None,
        enable_rag: bool = True,
        enable_corrections: bool = True,
    ):
        """
        Initialize interactive session.
        
        Args:
            pdf_text: Full extracted PDF text
            topics: List of extracted topics
            user_profile: User profile dictionary
            llm_client: Optional LLMClient for enhanced features
            enable_rag: Enable RAG-based search and querying
            enable_corrections: Enable error detection and correction
        """
        self.pdf_text = pdf_text
        self.topics = list(topics)  # Mutable copy
        self.user_profile = user_profile
        self.llm_client = llm_client
        self.enable_rag = enable_rag
        self.enable_corrections = enable_corrections
        
        # Initialize RAG engine if enabled
        self.rag = RAGEngine(pdf_text, self.topics, llm_client) if enable_rag else None
        
        # Session state
        self.modified = False
        self.correction_log = []
    
    def run_interactive_loop(self) -> tuple[list, dict, bool]:
        """
        Run main interactive menu loop.
        
        Returns:
            (approved_topics, updated_user_profile, should_continue)
        """
        console.print("\n" + "─" * 70)
        console.print("[bold cyan]🎓 Interactive Learning Session[/bold cyan]")
        console.print("─" * 70)
        console.print(f"\n[dim]Found {len(self.topics)} topics from PDF extraction.[/dim]")
        console.print("[dim]You can review, edit, query, and correct them below.[/dim]\n")
        
        while True:
            self._print_menu()
            choice = input("\n[bold]Select option:[/bold] ").strip().lower()
            
            if choice in ["1", "review"]:
                self._review_topics()
            elif choice in ["2", "query"]:
                self._query_content()
            elif choice in ["3", "edit"]:
                self._edit_topics()
            elif choice in ["4", "correct"]:
                self._correct_mistakes()
            elif choice in ["5", "add"]:
                self._add_custom_topic()
            elif choice in ["6", "merge"]:
                self._merge_topics()
            elif choice in ["7", "profile"]:
                self._update_profile()
            elif choice in ["8", "save"]:
                console.print("[green]✓ Changes saved![/green]")
                return self.topics, self.user_profile, True
            elif choice in ["9", "abort"]:
                console.print("[yellow]⚠ Aborting without saving changes[/yellow]")
                return self.topics, self.user_profile, False
            else:
                console.print("[yellow]Invalid option[/yellow]")
    
    def _print_menu(self) -> None:
        """Print main menu."""
        status = " [yellow](modified)[/yellow]" if self.modified else ""
        console.print(f"\n[bold]Menu{status}[/bold]")
        console.print("  [bold cyan]1[/bold cyan]  Review topics")
        if self.enable_rag:
            console.print("  [bold cyan]2[/bold cyan]  Query content (RAG)")
        console.print("  [bold cyan]3[/bold cyan]  Edit topic details")
        if self.enable_corrections and self.llm_client:
            console.print("  [bold cyan]4[/bold cyan]  Correct LLM mistakes")
        console.print("  [bold cyan]5[/bold cyan]  Add custom topic")
        console.print("  [bold cyan]6[/bold cyan]  Merge topics")
        console.print("  [bold cyan]7[/bold cyan]  Update learner profile")
        console.print("  [bold cyan]8[/bold cyan]  Save and continue")
        console.print("  [bold cyan]9[/bold cyan]  Abort (discard changes)")
    
    def _review_topics(self) -> None:
        """Display and review all extracted topics."""
        console.print("\n" + "─" * 70)
        console.print("[bold cyan]📋 Topic Review[/bold cyan]")
        console.print("─" * 70 + "\n")
        
        if not self.topics:
            console.print("[yellow]No topics extracted yet[/yellow]")
            return
        
        self._print_topic_list(self.topics)
        
        console.print("\n  [dim]Select a topic number to view details, or Enter to go back[/dim]")
        choice = input("[dim]Topic #:[/dim] ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(self.topics):
                self._show_topic_details(idx)
    
    def _show_topic_details(self, topic_idx: int) -> None:
        """Show detailed view of a topic with RAG context."""
        topic = self.topics[topic_idx]
        topic_id = topic.get("id", f"t{topic_idx + 1}")
        
        console.print("\n" + "─" * 70)
        console.print(f"[bold cyan]📌 {topic['title']}[/bold cyan]")
        console.print("─" * 70 + "\n")
        
        console.print(f"[bold]Difficulty:[/bold] {topic.get('difficulty', '?')}")
        console.print(f"[bold]Estimated Hours:[/bold] {topic.get('estimated_hours', 1.5)}")
        console.print(f"[bold]ID:[/bold] {topic_id}\n")
        
        if topic.get("description"):
            console.print(f"[bold]Description:[/bold] {topic['description']}\n")
        
        if topic.get("subtopics"):
            console.print(f"[bold]Subtopics:[/bold]")
            for sub in topic["subtopics"]:
                console.print(f"  • {sub}")
            console.print()
        
        # Show RAG context if enabled and LLM is available
        if self.enable_rag and self.rag and self.llm_client:
            console.print("[dim]Retrieving relevant content from PDF...[/dim]")
            context = self.rag.get_topic_context(topic_id, use_llm=True)
            
            if context and context["enhanced_description"]:
                console.print(f"\n[bold]📚 Enhanced Context:[/bold]")
                console.print(f"{context['enhanced_description']}\n")
            
            # Show related topics
            related = self.rag.suggest_related_topics(topic["title"])
            if related:
                console.print(f"[bold]🔗 Related Topics:[/bold]")
                for rel in related:
                    console.print(f"  • {rel['title']} (match: {rel['match_score']:.0%})")
                console.print()
        
        input("\n[dim]Press Enter to continue[/dim]")
    
    def _query_content(self) -> None:
        """Interactive RAG query interface."""
        if not self.enable_rag or not self.rag:
            console.print("[yellow]RAG features are disabled[/yellow]")
            return
        
        console.print("\n" + "─" * 70)
        console.print("[bold cyan]🔍 Query Content (RAG)[/bold cyan]")
        console.print("─" * 70)
        console.print("[dim]Ask a question about the PDF content to find relevant topics and excerpts[/dim]\n")
        
        while True:
            question = input("[bold]Question (or 'back'):[/bold] ").strip()
            
            if question.lower() in ["back", "exit", "q"]:
                break
            
            if not question:
                continue
            
            # Perform RAG query
            result = self.rag.query(question, top_k=3)
            
            console.print("\n[bold]Relevant Topics:[/bold]")
            if result["relevant_topics"]:
                for topic in result["relevant_topics"]:
                    console.print(
                        f"  • [cyan]{topic['title']}[/cyan] "
                        f"[dim](match: {topic['match_score']:.0%})[/dim]"
                    )
            else:
                console.print("  [dim]No matching topics[/dim]")
            
            if result["relevant_chunks"]:
                console.print("\n[bold]Relevant Content Excerpts:[/bold]")
                for i, chunk in enumerate(result["relevant_chunks"], 1):
                    console.print(f"  [{i}] [dim]{chunk['text'][:150]}...[/dim]")
            
            if result["answer"]:
                console.print(f"\n[bold]Answer:[/bold] {result['answer']}")
            
            console.print()
    
    def _edit_topics(self) -> None:
        """Edit details of specific topics."""
        console.print("\n" + "─" * 70)
        console.print("[bold cyan]✏️  Edit Topic[/bold cyan]")
        console.print("─" * 70 + "\n")
        
        self._print_topic_list(self.topics)
        
        choice = input("\n[dim]Topic # to edit (or 'back'):[/dim] ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(self.topics):
                self._edit_topic_fields(idx)
                self.modified = True
    
    def _edit_topic_fields(self, topic_idx: int) -> None:
        """Edit individual fields of a topic."""
        topic = self.topics[topic_idx]
        
        console.print(f"\n[bold]Editing: {topic['title']}[/bold]\n")
        console.print("  1. Title")
        console.print("  2. Difficulty")
        console.print("  3. Estimated hours")
        console.print("  4. Description")
        console.print("  5. Back")
        
        choice = input("\n[dim]Field to edit:[/dim] ").strip()
        
        if choice == "1":
            new_title = input("New title: ").strip()
            if new_title:
                topic["title"] = new_title
                console.print("[green]✓ Title updated[/green]")
        
        elif choice == "2":
            console.print("  Options: beginner, intermediate, advanced")
            new_diff = input("New difficulty: ").strip().lower()
            if new_diff in ["beginner", "intermediate", "advanced"]:
                topic["difficulty"] = new_diff
                console.print("[green]✓ Difficulty updated[/green]")
        
        elif choice == "3":
            try:
                new_hours = float(input("New estimated hours: ").strip())
                topic["estimated_hours"] = new_hours
                console.print("[green]✓ Hours updated[/green]")
            except ValueError:
                console.print("[red]Invalid number[/red]")
        
        elif choice == "4":
            new_desc = input("New description: ").strip()
            if new_desc:
                topic["description"] = new_desc
                console.print("[green]✓ Description updated[/green]")
    
    def _correct_mistakes(self) -> None:
        """Identify and correct potential LLM mistakes."""
        if not self.enable_corrections:
            console.print("[yellow]Automatic error correction is disabled[/yellow]")
            return
        
        console.print("\n" + "─" * 70)
        console.print("[bold cyan]🔧 Correct Mistakes[/bold cyan]")
        console.print("─" * 70 + "\n")
        
        if not self.llm_client:
            console.print("[yellow]LLM not available for corrections[/yellow]")
            return
        
        console.print("[dim]Analyzing topics for potential errors...[/dim]\n")
        
        # Check for common issues
        issues = self._detect_issues()
        
        if not issues:
            console.print("[green]✓ No obvious issues detected[/green]")
            return
        
        console.print(f"[bold]Found {len(issues)} potential issues:[/bold]\n")
        
        for i, issue in enumerate(issues, 1):
            console.print(f"  {i}. {issue['description']}")
            console.print(f"     Topic: {issue['topic']['title']}")
            console.print(f"     [dim]Severity: {issue['severity']}[/dim]\n")
        
        console.print("  [dim]Select issue # to correct, or 'back' to go back[/dim]")
        choice = input("[dim]Issue #:[/dim] ").strip()
        
        if choice.isdigit():
            issue_idx = int(choice) - 1
            if 0 <= issue_idx < len(issues):
                self._fix_issue(issues[issue_idx])
    
    def _detect_issues(self) -> list:
        """Detect potential issues with extracted topics."""
        issues = []
        
        # Check for duplicate topics
        titles = {}
        for i, topic in enumerate(self.topics):
            title_lower = topic["title"].lower()
            if title_lower in titles:
                issues.append({
                    "description": f"Duplicate topic detected",
                    "type": "duplicate",
                    "topic": topic,
                    "severity": "medium",
                    "topic_idx": i,
                    "original_idx": titles[title_lower]
                })
            else:
                titles[title_lower] = i
        
        # Check for missing descriptions
        for i, topic in enumerate(self.topics):
            if not topic.get("description"):
                issues.append({
                    "description": "Missing description",
                    "type": "missing_field",
                    "topic": topic,
                    "severity": "low",
                    "topic_idx": i,
                })
        
        # Check for inconsistent difficulty
        difficulties = set(t.get("difficulty", "intermediate") for t in self.topics)
        if len(difficulties) > 3 or "unknown" in difficulties:
            for i, topic in enumerate(self.topics):
                if topic.get("difficulty") not in ["beginner", "intermediate", "advanced"]:
                    issues.append({
                        "description": f"Invalid difficulty: '{topic.get('difficulty')}'",
                        "type": "invalid_field",
                        "topic": topic,
                        "severity": "medium",
                        "topic_idx": i,
                    })
        
        return issues
    
    def _fix_issue(self, issue: dict) -> None:
        """Fix a specific issue with LLM assistance."""
        issue_type = issue["type"]
        topic_idx = issue["topic_idx"]
        topic = self.topics[topic_idx]
        
        console.print(f"\n[bold]Fixing: {issue['description']}[/bold]\n")
        
        if issue_type == "duplicate":
            original_idx = issue["original_idx"]
            original = self.topics[original_idx]
            
            console.print(f"Original: {original['title']}")
            console.print(f"Duplicate: {topic['title']}\n")
            
            choice = input("[dim]Merge (m), Keep first (1), Keep second (2), Skip (s):[/dim] ").strip().lower()
            
            if choice == "m":
                # Merge subtopics
                original["subtopics"] = list(
                    set(original.get("subtopics", []) + topic.get("subtopics", []))
                )
                # Remove duplicate
                self.topics.pop(topic_idx)
                console.print("[green]✓ Merged and removed duplicate[/green]")
                self.modified = True
            
            elif choice == "1":
                self.topics.pop(topic_idx)
                console.print("[green]✓ Kept original, removed duplicate[/green]")
                self.modified = True
            
            elif choice == "2":
                self.topics.pop(original_idx)
                console.print("[green]✓ Kept second, removed first[/green]")
                self.modified = True
        
        elif issue_type == "missing_field":
            field = issue.get("field", "description")
            
            # Use RAG to generate suggestion
            console.print("[dim]Using RAG to suggest fill-in...[/dim]")
            chunks = self.rag._search_chunks(topic["title"], top_k=2)
            
            if chunks:
                suggestion = self.llm_client.chat(
                    system_prompt="You provide helpful suggestions for topic descriptions.",
                    user_prompt=f"Provide a concise one-sentence description for the topic '{topic['title']}' based on this content:\n\n{chunks[0]['text'][:300]}",
                    json_mode=False
                )
                
                console.print(f"\n[bold]Suggested description:[/bold]")
                console.print(f"  {suggestion}\n")
                
                accept = input("[dim]Use this description? (y/n):[/dim] ").strip().lower()
                if accept == "y":
                    topic["description"] = suggestion
                    console.print("[green]✓ Description added[/green]")
                    self.modified = True
        
        elif issue_type == "invalid_field":
            console.print(f"[yellow]Current difficulty: {topic.get('difficulty')}[/yellow]\n")
            new_diff = input("[dim]Set to (beginner/intermediate/advanced):[/dim] ").strip().lower()
            
            if new_diff in ["beginner", "intermediate", "advanced"]:
                topic["difficulty"] = new_diff
                console.print("[green]✓ Difficulty corrected[/green]")
                self.modified = True
    
    def _add_custom_topic(self) -> None:
        """Add a new topic manually."""
        console.print("\n" + "─" * 70)
        console.print("[bold cyan]➕ Add Custom Topic[/bold cyan]")
        console.print("─" * 70 + "\n")
        
        title = input("[bold]Topic title:[/bold] ").strip()
        if not title:
            console.print("[yellow]Cancelled[/yellow]")
            return
        
        console.print("\n[dim]Difficulty: beginner | intermediate | advanced[/dim]")
        difficulty = input("[bold]Difficulty:[/bold] ").strip().lower() or "intermediate"
        
        try:
            hours = float(input("[bold]Estimated hours:[/bold] ").strip() or "1.5")
        except ValueError:
            hours = 1.5
        
        description = input("[bold]Description (optional):[/bold] ").strip()
        
        # Search for related content in PDF
        related_chunks = self.rag._search_chunks(title, top_k=2)
        
        new_topic = {
            "id": f"t{len(self.topics) + 1}",
            "title": title,
            "difficulty": difficulty,
            "estimated_hours": hours,
            "description": description,
            "subtopics": [],
        }
        
        if related_chunks:
            console.print("\n[dim]Found related content in PDF. Generate subtopics? (y/n):[/dim] ")
            if input().strip().lower() == "y":
                # Use LLM to suggest subtopics
                context = related_chunks[0]["text"][:300]
                subtopics_json = self.llm_client.chat(
                    system_prompt="You suggest subtopics. Return only a JSON list of strings.",
                    user_prompt=f"Suggest 3-5 subtopics for '{title}' based on:\n\n{context}",
                    json_mode=True
                )
                
                try:
                    import json
                    subs = json.loads(subtopics_json).get("subtopics", [])
                    if subs:
                        new_topic["subtopics"] = subs
                        console.print("[green]✓ Subtopics added[/green]")
                except:
                    pass
        
        self.topics.append(new_topic)
        self.modified = True
        console.print(f"\n[green]✓ Topic '{title}' added[/green]")
    
    def _merge_topics(self) -> None:
        """Merge two topics together."""
        console.print("\n" + "─" * 70)
        console.print("[bold cyan]🔀 Merge Topics[/bold cyan]")
        console.print("─" * 70 + "\n")
        
        self._print_topic_list(self.topics)
        
        first = input("\n[dim]First topic #:[/dim] ").strip()
        second = input("[dim]Second topic #:[/dim] ").strip()
        
        if first.isdigit() and second.isdigit():
            idx1, idx2 = int(first) - 1, int(second) - 1
            
            if 0 <= idx1 < len(self.topics) and 0 <= idx2 < len(self.topics) and idx1 != idx2:
                t1, t2 = self.topics[idx1], self.topics[idx2]
                
                console.print(f"\n[bold]Merging:[/bold]")
                console.print(f"  1. {t1['title']}")
                console.print(f"  2. {t2['title']}\n")
                
                # Merge t2 into t1
                t1["description"] = t1.get("description", "") + " " + t2.get("description", "")
                t1["subtopics"] = list(set(t1.get("subtopics", []) + t2.get("subtopics", [])))
                
                # Remove t2
                if idx2 > idx1:
                    self.topics.pop(idx2)
                else:
                    self.topics.pop(idx2)
                
                console.print(f"[green]✓ Merged into '{t1['title']}'[/green]")
                self.modified = True
    
    def _update_profile(self) -> None:
        """Update user learner profile."""
        console.print("\n" + "─" * 70)
        console.print("[bold cyan]👤 Update Profile[/bold cyan]")
        console.print("─" * 70 + "\n")
        
        console.print(f"[bold]Current profile:[/bold]")
        for key, value in self.user_profile.items():
            console.print(f"  {key}: {value}")
        
        console.print("\n[dim]Edit fields: hard_topics, easy_topics, time_available, learning_style[/dim]")
        field = input("[dim]Field to update (or 'back'):[/dim] ").strip()
        
        if field in self.user_profile:
            value = input(f"New value for '{field}': ").strip()
            
            if value.lower() in ["true", "false"]:
                self.user_profile[field] = value.lower() == "true"
            else:
                try:
                    self.user_profile[field] = float(value)
                except ValueError:
                    self.user_profile[field] = value
            
            console.print(f"[green]✓ Updated {field}[/green]")
            self.modified = True
    
    def _print_topic_list(self, topics: list) -> None:
        """Print formatted topic list."""
        if not topics:
            console.print("[dim]No topics[/dim]")
            return
        
        diff_colors = {"beginner": "green", "intermediate": "yellow", "advanced": "red"}
        
        for i, t in enumerate(topics, 1):
            color = diff_colors.get(t.get("difficulty", "intermediate"), "white")
            console.print(
                f"  [bold]{i:2d}.[/bold] [{color}]{t['title']}[/{color}]"
                f"  [dim]~{t.get('estimated_hours', 1.5)}h · {t.get('difficulty', '?')}[/dim]"
            )
            if t.get("description"):
                console.print(f"       [dim]{t['description'][:80]}[/dim]")
