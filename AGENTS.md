# Agent Instructions for Roo

This document provides context and instructions for AI agents working on the tiny-cache-py project.

## Project Overview

### tiny-cache-py
A Python client library for the tiny-cache gRPC service, providing efficient distributed caching with connection pooling, error handling, and comprehensive API support. This is a client-side library that connects to the tiny-cache server to provide caching functionality for Python applications.

## Environment Setup

The project uses Python virtual environments. **IMPORTANT**: Before running any tests or Python commands, you must activate the virtual environment:

```bash
. ./venv/bin/activate
```

This is critical for:
- Running tests
- Installing dependencies
- Executing Python scripts
- Using project-specific tools

## Development Workflow

### For tiny-cache-py:
1. Activate virtual environment: `. ./venv/bin/activate`
2. Install dependencies: `pip install -r requirements.txt`
3. Install in development mode: `pip install -e .`
4. Generate protobuf files: `make proto`
5. Run tests: `python test_client.py`

### General Guidelines:
- Always activate the venv before running any Python-related commands
- Check for requirements.txt files in project directories
- Look for Makefile targets for common operations
- This is a client library, so tests require a running tiny-cache server

## Testing

When running tests for this project:
1. **MUST** activate virtual environment first: `. ./venv/bin/activate`
2. **MUST** start the tiny-cache server first: `cd ../tiny-cache && python server.py`
3. Then run the test client: `python test_client.py`
4. Common test runners: pytest, unittest, or custom test scripts

## Coding Standards

### Code Style Requirements
- **NO EMOTICONS**: Do not use any emoticons, emojis, or Unicode symbols in code, comments, documentation, or output messages
- Use clear, professional text instead of emoticons (e.g., "SUCCESS" instead of "✅", "ERROR" instead of "❌")
- Maintain clean, readable code without visual decorations
- Focus on technical accuracy and clarity over visual appeal

### Documentation Standards
- Write clear, concise documentation without emoticons
- Use standard markdown formatting
- Provide practical examples and usage instructions
- Keep documentation professional and technical

## Documentation Organization

### File Structure
- **README.md**: Main project documentation (MUST remain in root directory)
- **AGENTS.md**: AI agent instructions (MUST remain in root directory)
- **docs/**: All other documentation files (testing guides, architecture docs, etc.)

### Documentation Guidelines
- Only README.md and AGENTS.md should be in the root directory
- All other documentation files MUST be placed in the `docs/` directory
- This includes: testing documentation, architecture guides, API docs, tutorials, etc.
- When creating new documentation, always place it in `docs/` unless it's README.md or AGENTS.md
- Reference documentation in `docs/` from README.md when appropriate

### Reading Documentation
- Start with README.md for project overview and setup
- Check `docs/` directory for detailed documentation:
  - Testing guides and procedures
  - Architecture documentation
  - Technical specifications
  - Development guides

## Testing Requirements

### Mandatory Testing Protocol
- **ALL code changes REQUIRE corresponding tests**
- **ALL tests MUST pass before any change is considered complete**
- No exceptions to the testing requirement - every modification needs test coverage
- Use pytest framework for all Python testing

### Testing Workflow
1. Write or update tests for any code changes
2. Start tiny-cache server: `cd ../tiny-cache && python server.py`
3. Run client tests: `python test_client.py`
4. Ensure all tests pass before considering work complete
5. Update test documentation if new test patterns are introduced

### Test Categories
- Unit tests: Test individual client components in isolation
- Integration tests: Test client-server interactions
- Connection tests: Test connection pooling and error handling
- Performance tests: Validate client performance requirements

## Project-Specific Considerations

### Client Library Architecture
- **Async-First Design**: All client methods are async for high-performance applications
- **Connection Pooling**: Maintains persistent gRPC channels for efficiency
- **Error Handling**: Comprehensive exception hierarchy for different error conditions
- **Type Safety**: Full type hints and input validation
- **Retry Logic**: Exponential backoff for transient failures

### Dependencies
- **gRPC**: Core communication protocol with tiny-cache server
- **asyncio**: Async support for non-blocking operations
- **typing**: Type hints for better code quality
- **protobuf**: Message serialization

### Development Dependencies
- **pytest**: Testing framework
- **black**: Code formatting
- **mypy**: Type checking
- **setuptools**: Package building

## Notes for AI Agents

- The virtual environment activation is not optional - it's required for proper dependency management
- This project requires a running tiny-cache server for integration testing
- Check for project-specific documentation in README.md files
- Look for Makefile or setup.py scripts for automated workflows
- **CRITICAL**: Always follow the testing requirements - no code changes without tests and passing test suite
- **CRITICAL**: Never use emoticons or emojis in any project files or outputs
- **CRITICAL**: This is a client library - ensure server compatibility when making changes
- **CRITICAL**: Maintain async patterns and proper connection management in all code changes