"""
Agent Memory Service - Store and retrieve agent memories in markdown format.

This service allows storing facts, conventions, and learnings about the codebase
in structured markdown files that can be referenced by GitHub Copilot agents.
"""
import logging
import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MemoryCategory(str, Enum):
    """Categories for organizing agent memories."""
    ARCHITECTURE = "architecture"
    CODING_STYLE = "coding_style"
    SECURITY = "security"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    BUSINESS_LOGIC = "business_logic"
    DATABASE = "database"
    API = "api"
    GENERAL = "general"


@dataclass
class AgentMemory:
    """Represents a single memory entry."""
    subject: str
    fact: str
    category: MemoryCategory
    citations: str
    reason: str
    created_at: datetime.datetime
    tags: List[str]


class AgentMemoryService:
    """Service for managing agent memories stored in markdown files."""
    
    def __init__(self, memory_dir: Optional[Path] = None):
        """Initialize the memory service.
        
        Args:
            memory_dir: Directory to store memory files. Defaults to .github/agents/memories
        """
        if memory_dir is None:
            # Default to .github/agents/memories relative to project root
            project_root = Path(__file__).parent.parent
            memory_dir = project_root / ".github" / "agents" / "memories"
        
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Agent memory service initialized at {self.memory_dir}")
    
    def _get_category_file(self, category: MemoryCategory) -> Path:
        """Get the markdown file path for a category.
        
        Args:
            category: Memory category
            
        Returns:
            Path to the category markdown file
        """
        return self.memory_dir / f"{category.value}.md"
    
    def _format_memory_entry(self, memory: AgentMemory) -> str:
        """Format a memory entry as markdown.
        
        Args:
            memory: Memory entry to format
            
        Returns:
            Formatted markdown string
        """
        tags_str = ", ".join([f"`{tag}`" for tag in memory.tags]) if memory.tags else "N/A"
        
        return f"""
## {memory.subject}

**Category:** {memory.category.value}  
**Tags:** {tags_str}  
**Created:** {memory.created_at.strftime('%Y-%m-%d %H:%M:%S')}

### Fact
{memory.fact}

### Why This Matters
{memory.reason}

### Source
{memory.citations}

---
"""
    
    def store_memory(
        self,
        subject: str,
        fact: str,
        category: MemoryCategory,
        citations: str,
        reason: str,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Store a new memory entry.
        
        Args:
            subject: Topic of the memory (1-2 words)
            fact: The fact to remember (< 500 chars recommended)
            category: Category for organizing the memory
            citations: Source references (file paths, line numbers, etc.)
            reason: Explanation of why this is important
            tags: Optional list of tags for searchability
            
        Returns:
            True if successful, False otherwise
        """
        try:
            memory = AgentMemory(
                subject=subject,
                fact=fact,
                category=category,
                citations=citations,
                reason=reason,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                tags=tags or []
            )
            
            category_file = self._get_category_file(category)
            
            # Create file with header if it doesn't exist
            if not category_file.exists():
                header = f"""# Agent Memories: {category.value.replace('_', ' ').title()}

This file contains agent memories related to {category.value.replace('_', ' ')}.
These memories help GitHub Copilot agents understand conventions, patterns, and important facts about this codebase.

---
"""
                category_file.write_text(header, encoding="utf-8")
            
            # Append the new memory
            with category_file.open("a", encoding="utf-8") as f:
                f.write(self._format_memory_entry(memory))
            
            logger.info(f"Stored memory: {subject} in {category.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return False
    
    def get_all_memories(self, category: Optional[MemoryCategory] = None) -> str:
        """Retrieve all memories, optionally filtered by category.
        
        Args:
            category: Optional category filter
            
        Returns:
            Concatenated markdown content of memories
        """
        try:
            if category:
                # Read single category
                category_file = self._get_category_file(category)
                if category_file.exists():
                    return category_file.read_text(encoding="utf-8")
                return ""
            else:
                # Read all categories
                all_content = ["# All Agent Memories\n\n"]
                for cat in MemoryCategory:
                    category_file = self._get_category_file(cat)
                    if category_file.exists():
                        all_content.append(f"\n## {cat.value.replace('_', ' ').title()}\n\n")
                        all_content.append(category_file.read_text(encoding="utf-8"))
                return "".join(all_content)
        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return ""
    
    def list_categories(self) -> List[str]:
        """List all categories that have stored memories.
        
        Returns:
            List of category names with stored memories
        """
        categories = []
        for cat in MemoryCategory:
            category_file = self._get_category_file(cat)
            if category_file.exists():
                categories.append(cat.value)
        return categories
    
    def search_memories(self, query: str) -> str:
        """Search for memories containing a specific term.
        
        Args:
            query: Search term
            
        Returns:
            Markdown content of matching memories
        """
        query_lower = query.lower()
        results = []
        
        for cat in MemoryCategory:
            category_file = self._get_category_file(cat)
            if not category_file.exists():
                continue
            
            content = category_file.read_text(encoding="utf-8")
            # Split by memory entries (separated by ---)
            entries = content.split("---")
            
            for entry in entries:
                if query_lower in entry.lower():
                    results.append(entry.strip())
        
        if results:
            return "# Search Results\n\n" + "\n\n---\n\n".join(results)
        return f"No memories found matching '{query}'"


# Global instance for easy access
_memory_service = None


def get_memory_service() -> AgentMemoryService:
    """Get or create the global memory service instance.
    
    Returns:
        AgentMemoryService instance
    """
    global _memory_service
    if _memory_service is None:
        _memory_service = AgentMemoryService()
    return _memory_service
