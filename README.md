# Course Materials RAG System

A Retrieval-Augmented Generation (RAG) system designed to answer questions about course materials using semantic search and AI-powered responses.

## Overview

This application is a full-stack web application that enables users to query course materials and receive intelligent, context-aware responses. It uses ChromaDB for vector storage, Anthropic's Claude for AI generation, and provides a web interface for interaction.


## Prerequisites

- Python 3.13 or higher
- uv (Python package manager)
- An Anthropic API key (for Claude AI)
- **For Windows**: Use Git Bash to run the application commands - [Download Git for Windows](https://git-scm.com/downloads/win)

## Installation

1. **Install uv** (if not already installed)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install Python dependencies**
   ```bash
   uv sync
   ```

3. **Set up environment variables**

   Create a `.env` file in the root directory:
   ```bash
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```

## Running the Application

### Quick Start

Use the provided shell script:
```bash
chmod +x run.sh
./run.sh
```

### Manual Start

```bash
cd backend
uv run uvicorn app:app --reload --port 8000
```

The application will be available at:
- Web Interface: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`

## Development

### Code Quality Tools

This project uses several tools to maintain code quality:

**Quick Commands:**
```bash
# Format code automatically
./scripts/format.sh

# Run all quality checks (format, lint, type check, tests)
./scripts/quality_check.sh
```

**Individual Tools:**
```bash
# Black - code formatting
uv run black backend/ main.py

# Ruff - linting and code quality
uv run ruff check backend/ main.py --fix

# MyPy - type checking
uv run mypy backend/ main.py

# PyTest - run tests
uv run pytest backend/tests/ -v
```

**Pre-commit Hooks:**

Pre-commit hooks automatically run quality checks on changed files before each commit:

```bash
# Install hooks (one-time setup, already done if you cloned this repo)
uv run pre-commit install

# Run manually on all files
uv run pre-commit run --all-files
```

**Configuration:**
- All tool configurations are in `pyproject.toml`
- Pre-commit hook settings are in `.pre-commit-config.yaml`
- See `scripts/README.md` for detailed script documentation
