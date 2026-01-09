# Agent Memory Storage System

## Overview

This system provides a structured way to store and retrieve agent memories (facts, conventions, and learnings) about the codebase in markdown format. These memories help GitHub Copilot agents understand important patterns, conventions, and best practices specific to this project.

## Purpose

The agent memory system serves several key purposes:

1. **Knowledge Persistence**: Important facts about the codebase are stored in a structured, searchable format
2. **Agent Assistance**: GitHub Copilot agents can reference these memories to provide better code suggestions
3. **Onboarding**: New developers and agents can quickly understand project conventions
4. **Documentation**: Serves as living documentation of important patterns and decisions

## Architecture

### Directory Structure

```
.github/agents/memories/
├── architecture.md       # Architectural patterns and design decisions
├── coding_style.md       # Code style conventions and best practices
├── security.md          # Security-related conventions and requirements
├── testing.md           # Testing patterns and requirements
├── deployment.md        # Deployment and infrastructure knowledge
├── business_logic.md    # Domain-specific business logic patterns
├── database.md          # Database patterns and conventions
├── api.md              # API design and conventions
└── general.md          # General facts that don't fit other categories
```

### Components

1. **AgentMemoryService** (`services/agent_memory_service.py`)
   - Core service for managing agent memories
   - Handles storing, retrieving, and searching memories
   - Organizes memories by category
   - Formats memories as structured markdown

2. **manage_memories.py** (CLI Tool)
   - Command-line interface for memory management
   - Commands: `init`, `store`, `list`, `view`, `search`
   - Provides easy access to memory operations

3. **Memory Categories** (Enum)
   - ARCHITECTURE: System design and structure
   - CODING_STYLE: Code conventions and patterns
   - SECURITY: Security requirements and best practices
   - TESTING: Testing patterns and requirements
   - DEPLOYMENT: Deployment and infrastructure
   - BUSINESS_LOGIC: Domain-specific patterns
   - DATABASE: Database patterns and conventions
   - API: API design patterns
   - GENERAL: Miscellaneous facts

## Usage

### Initialize Default Memories

When first setting up the project, initialize with default memories about the codebase:

```bash
python manage_memories.py init
```

This will create 15+ default memories covering:
- Async/await patterns
- Type hints requirements
- Security practices (HTML escaping)
- Error handling conventions
- Database patterns
- Testing requirements
- And more...

### Store a New Memory

Store a new memory when you learn something important about the codebase:

```bash
python manage_memories.py store \
  "Subject" \
  "Detailed fact about the codebase" \
  --category coding_style \
  --citations "file.py:42, other_file.py" \
  --reason "Why this is important for future work" \
  --tags "tag1,tag2,tag3"
```

**Example:**
```bash
python manage_memories.py store \
  "Naming Convention" \
  "Use snake_case for all variable and function names" \
  --category coding_style \
  --citations "Multiple files across the codebase" \
  --reason "Consistency with Python PEP 8 style guide" \
  --tags "naming,style,pep8"
```

### View Memories

View all memories in a specific category:

```bash
python manage_memories.py view coding_style
```

View all memories across all categories:

```bash
python manage_memories.py view
```

### List Categories

See which categories have stored memories:

```bash
python manage_memories.py list
```

Output:
```
📚 Stored memory categories:
  • architecture
  • coding_style
  • security
  • testing
  • database
  • business_logic
  • deployment
```

### Search Memories

Search for memories containing a specific term:

```bash
python manage_memories.py search "async"
```

This will show all memories that mention "async" in any field.

## Memory Format

Each memory entry is stored in markdown with the following structure:

```markdown
## Subject

**Category:** category_name
**Tags:** `tag1`, `tag2`, `tag3`
**Created:** YYYY-MM-DD HH:MM:SS

### Fact
The core fact or convention to remember

### Why This Matters
Explanation of why this is important for future work

### Source
Citations: file paths, line numbers, or references

---
```

## Integration with Development Workflow

### When to Add Memories

Add new memories when:

1. **Code Review**: You notice a pattern or convention that should be documented
2. **Bug Fixes**: You discover an important constraint or requirement
3. **New Features**: You establish a new pattern that should be followed
4. **Refactoring**: You document decisions about architecture or design
5. **Security**: You implement a security requirement that must be maintained

### What to Store

Store memories that are:

- **Actionable**: Can influence future coding decisions
- **Non-obvious**: Not easily inferred from limited code context
- **Persistent**: Unlikely to change over time
- **Important**: Have significant impact on code quality or correctness
- **Non-sensitive**: Contain no secrets or confidential information

### What NOT to Store

Don't store:

- Implementation details that are self-documenting
- Temporary decisions or workarounds
- Secrets, tokens, or sensitive data
- Obvious conventions that are universal to Python/language
- Information that quickly becomes outdated

## Programmatic Usage

You can also use the memory service programmatically in your code:

```python
from services.agent_memory_service import get_memory_service, MemoryCategory

# Get the memory service
service = get_memory_service()

# Store a memory
service.store_memory(
    subject="Custom Memory",
    fact="Important fact about the code",
    category=MemoryCategory.CODING_STYLE,
    citations="file.py:42",
    reason="This helps future development",
    tags=["important", "pattern"]
)

# Retrieve memories
coding_memories = service.get_all_memories(category=MemoryCategory.CODING_STYLE)
all_memories = service.get_all_memories()

# Search memories
results = service.search_memories("async")

# List categories
categories = service.list_categories()
```

## Testing

The memory system includes comprehensive tests:

```bash
# Run memory service tests
python -m pytest tests/test_agent_memory_service.py -v

# Run with coverage
python -m pytest tests/test_agent_memory_service.py --cov=services.agent_memory_service
```

Test coverage includes:
- Memory storage and retrieval
- Search functionality
- Category management
- Markdown formatting
- Edge cases and error handling

## Best Practices

1. **Be Specific**: Write clear, concise facts (< 500 characters recommended)
2. **Cite Sources**: Always include file paths or line numbers
3. **Explain Why**: The "reason" is crucial for understanding importance
4. **Use Tags**: Add relevant tags for better searchability
5. **Update Regularly**: Keep memories current as the codebase evolves
6. **Review Periodically**: Check if memories are still relevant
7. **Avoid Duplication**: Search before adding to prevent duplicate entries

## Example Memories

### Good Memory Example ✅

```
Subject: HTML Escape
Fact: Always use html.escape() for user input in Telegram messages with parse_mode='HTML'
Category: security
Citations: services/ticket_service.py:4, handlers/telegram.py
Reason: Prevents HTML injection attacks. Users can send malicious HTML code.
Tags: security, xss, html, telegram
```

### Poor Memory Example ❌

```
Subject: Code
Fact: Write good code
Category: general
Citations: N/A
Reason: Good code is important
Tags: code
```

**Why it's poor:**
- Too vague and not actionable
- No specific convention or pattern
- No sources cited
- Doesn't provide value for future decisions

## Future Enhancements

Potential improvements to the memory system:

1. **Web UI**: Build a web interface for browsing and managing memories
2. **Version Control**: Track changes to memories over time
3. **Memory Validation**: Automatically check if memories are still relevant
4. **Smart Suggestions**: Suggest memories based on code being written
5. **Team Collaboration**: Allow multiple team members to contribute memories
6. **Integration**: Integrate with IDE plugins for inline memory suggestions

## Related Documentation

- [GitHub Copilot Instructions](.github/copilot-instructions.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [Architecture Documentation](../ARCHITECTURAL_IMPROVEMENTS.md)

## Support

For issues or questions about the memory system:

1. Check existing memories: `python manage_memories.py list`
2. Search for related memories: `python manage_memories.py search <term>`
3. Review this documentation
4. Contact the development team

---

**Remember**: The goal of this system is to help agents (and humans!) understand the codebase better. Good memories lead to better code suggestions and faster development! 🚀
