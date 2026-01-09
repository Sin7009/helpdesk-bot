"""
Tests for Agent Memory Service.

Tests the functionality of storing, retrieving, searching, and managing
agent memories in markdown format.
"""
import pytest
import tempfile
from pathlib import Path
from services.agent_memory_service import (
    AgentMemoryService, 
    MemoryCategory, 
    AgentMemory,
    get_memory_service
)


@pytest.fixture
def temp_memory_dir():
    """Create a temporary directory for test memories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def memory_service(temp_memory_dir):
    """Create a memory service instance with temp directory."""
    return AgentMemoryService(memory_dir=temp_memory_dir)


class TestAgentMemoryService:
    """Test suite for AgentMemoryService."""
    
    def test_service_initialization(self, memory_service, temp_memory_dir):
        """Test that service initializes correctly."""
        assert memory_service.memory_dir == temp_memory_dir
        assert memory_service.memory_dir.exists()
    
    def test_store_memory_creates_file(self, memory_service, temp_memory_dir):
        """Test that storing a memory creates the category file."""
        success = memory_service.store_memory(
            subject="Test Subject",
            fact="This is a test fact",
            category=MemoryCategory.CODING_STYLE,
            citations="test_file.py:10",
            reason="This is important for testing",
            tags=["test", "example"]
        )
        
        assert success
        category_file = temp_memory_dir / "coding_style.md"
        assert category_file.exists()
        
        content = category_file.read_text()
        assert "Test Subject" in content
        assert "This is a test fact" in content
        assert "test_file.py:10" in content
        assert "`test`" in content
        assert "`example`" in content
    
    def test_store_multiple_memories(self, memory_service):
        """Test storing multiple memories in same category."""
        memory_service.store_memory(
            subject="Memory 1",
            fact="First fact",
            category=MemoryCategory.ARCHITECTURE,
            citations="file1.py",
            reason="Reason 1"
        )
        
        memory_service.store_memory(
            subject="Memory 2",
            fact="Second fact",
            category=MemoryCategory.ARCHITECTURE,
            citations="file2.py",
            reason="Reason 2"
        )
        
        content = memory_service.get_all_memories(category=MemoryCategory.ARCHITECTURE)
        assert "Memory 1" in content
        assert "Memory 2" in content
        # Check that both memories are stored by looking for unique subjects
        assert content.count("First fact") == 1
        assert content.count("Second fact") == 1
    
    def test_get_all_memories_single_category(self, memory_service):
        """Test retrieving memories from a single category."""
        memory_service.store_memory(
            subject="Security Test",
            fact="Always validate input",
            category=MemoryCategory.SECURITY,
            citations="validators.py",
            reason="Prevent injection attacks"
        )
        
        content = memory_service.get_all_memories(category=MemoryCategory.SECURITY)
        assert "Security Test" in content
        assert "Always validate input" in content
    
    def test_get_all_memories_all_categories(self, memory_service):
        """Test retrieving all memories across categories."""
        memory_service.store_memory(
            subject="Style Rule",
            fact="Use snake_case",
            category=MemoryCategory.CODING_STYLE,
            citations="multiple files",
            reason="Consistency"
        )
        
        memory_service.store_memory(
            subject="Security Rule",
            fact="Escape HTML",
            category=MemoryCategory.SECURITY,
            citations="handlers.py",
            reason="Prevent XSS"
        )
        
        content = memory_service.get_all_memories()
        assert "Style Rule" in content
        assert "Security Rule" in content
    
    def test_list_categories(self, memory_service):
        """Test listing categories with stored memories."""
        assert memory_service.list_categories() == []
        
        memory_service.store_memory(
            subject="Test",
            fact="Test fact",
            category=MemoryCategory.TESTING,
            citations="test.py",
            reason="Testing"
        )
        
        categories = memory_service.list_categories()
        assert "testing" in categories
        assert len(categories) == 1
        
        memory_service.store_memory(
            subject="Deploy",
            fact="Deploy fact",
            category=MemoryCategory.DEPLOYMENT,
            citations="deploy.py",
            reason="Deployment"
        )
        
        categories = memory_service.list_categories()
        assert len(categories) == 2
        assert "testing" in categories
        assert "deployment" in categories
    
    def test_search_memories(self, memory_service):
        """Test searching for memories by term."""
        memory_service.store_memory(
            subject="Async Pattern",
            fact="Always use async/await for I/O operations",
            category=MemoryCategory.CODING_STYLE,
            citations="services/",
            reason="Performance"
        )
        
        memory_service.store_memory(
            subject="Database",
            fact="Use SQLAlchemy 2.0 async",
            category=MemoryCategory.DATABASE,
            citations="database/models.py",
            reason="Modern ORM"
        )
        
        # Search for "async"
        results = memory_service.search_memories("async")
        assert "Async Pattern" in results
        assert "Database" in results
        
        # Search for specific term
        results = memory_service.search_memories("SQLAlchemy")
        assert "Database" in results
        assert "Async Pattern" not in results
        
        # Search for non-existent term
        results = memory_service.search_memories("nonexistent")
        assert "No memories found" in results
    
    def test_search_case_insensitive(self, memory_service):
        """Test that search is case-insensitive."""
        memory_service.store_memory(
            subject="Testing Best Practice",
            fact="Use pytest for testing",
            category=MemoryCategory.TESTING,
            citations="tests/",
            reason="Standard tool"
        )
        
        results_lower = memory_service.search_memories("pytest")
        results_upper = memory_service.search_memories("PYTEST")
        results_mixed = memory_service.search_memories("PyTest")
        
        assert "Testing Best Practice" in results_lower
        assert "Testing Best Practice" in results_upper
        assert "Testing Best Practice" in results_mixed
    
    def test_memory_formatting(self, memory_service, temp_memory_dir):
        """Test that memory entries are properly formatted."""
        memory_service.store_memory(
            subject="Format Test",
            fact="Test formatting",
            category=MemoryCategory.GENERAL,
            citations="test.py:42",
            reason="Ensure proper markdown",
            tags=["format", "markdown"]
        )
        
        content = (temp_memory_dir / "general.md").read_text()
        
        # Check structure
        assert "## Format Test" in content
        assert "**Category:** general" in content
        assert "**Tags:** `format`, `markdown`" in content
        assert "### Fact" in content
        assert "Test formatting" in content
        assert "### Why This Matters" in content
        assert "Ensure proper markdown" in content
        assert "### Source" in content
        assert "test.py:42" in content
        assert "---" in content
    
    def test_memory_without_tags(self, memory_service):
        """Test storing memory without tags."""
        success = memory_service.store_memory(
            subject="No Tags",
            fact="Memory without tags",
            category=MemoryCategory.GENERAL,
            citations="file.py",
            reason="Testing edge case"
        )
        
        assert success
        content = memory_service.get_all_memories(category=MemoryCategory.GENERAL)
        assert "No Tags" in content
        assert "**Tags:** N/A" in content
    
    def test_get_memory_service_singleton(self):
        """Test that get_memory_service returns singleton."""
        service1 = get_memory_service()
        service2 = get_memory_service()
        assert service1 is service2
    
    def test_empty_category(self, memory_service):
        """Test retrieving memories from empty category."""
        content = memory_service.get_all_memories(category=MemoryCategory.API)
        assert content == ""
    
    def test_multiple_tags(self, memory_service, temp_memory_dir):
        """Test memory with multiple tags."""
        memory_service.store_memory(
            subject="Multi Tag Test",
            fact="Testing multiple tags",
            category=MemoryCategory.TESTING,
            citations="test.py",
            reason="Tag functionality",
            tags=["tag1", "tag2", "tag3", "tag4"]
        )
        
        content = (temp_memory_dir / "testing.md").read_text()
        assert "`tag1`" in content
        assert "`tag2`" in content
        assert "`tag3`" in content
        assert "`tag4`" in content


class TestMemoryCategory:
    """Test MemoryCategory enum."""
    
    def test_all_categories_defined(self):
        """Test that all expected categories are defined."""
        expected = [
            "architecture", "coding_style", "security", "testing",
            "deployment", "business_logic", "database", "api", "general"
        ]
        actual = [cat.value for cat in MemoryCategory]
        assert set(expected) == set(actual)
    
    def test_category_values(self):
        """Test category enum values."""
        assert MemoryCategory.ARCHITECTURE.value == "architecture"
        assert MemoryCategory.CODING_STYLE.value == "coding_style"
        assert MemoryCategory.SECURITY.value == "security"
        assert MemoryCategory.TESTING.value == "testing"


class TestAgentMemoryDataclass:
    """Test AgentMemory dataclass."""
    
    def test_memory_creation(self):
        """Test creating an AgentMemory instance."""
        import datetime
        memory = AgentMemory(
            subject="Test",
            fact="Test fact",
            category=MemoryCategory.GENERAL,
            citations="test.py",
            reason="Testing",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            tags=["test"]
        )
        
        assert memory.subject == "Test"
        assert memory.fact == "Test fact"
        assert memory.category == MemoryCategory.GENERAL
        assert memory.citations == "test.py"
        assert memory.reason == "Testing"
        assert memory.tags == ["test"]
        assert isinstance(memory.created_at, datetime.datetime)
