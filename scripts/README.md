# Development Scripts

This directory contains helper scripts for development workflow.

## Available Scripts

### `format.sh`
Automatically formats the codebase using Black and Ruff.

```bash
./scripts/format.sh
```

**What it does:**
- Runs Black formatter on all Python files
- Applies Ruff auto-fixes for common issues
- Fixes import ordering (isort)
- Applies code style improvements

**When to use:**
- Before committing code
- After writing new features
- When you see formatting errors in CI/CD

### `quality_check.sh`
Runs all quality checks without modifying files.

```bash
./scripts/quality_check.sh
```

**What it does:**
1. Black format check (verifies formatting)
2. Ruff linting (checks for code issues)
3. MyPy type checking (verifies type hints)
4. PyTest (runs test suite)

**When to use:**
- Before pushing to remote
- To verify your changes pass CI/CD
- As part of local development workflow

**Exit codes:**
- `0`: All checks passed
- `1`: One or more checks failed

## Integration with Pre-commit

Pre-commit hooks automatically run quality checks on changed files before each commit.

```bash
# Install hooks (one-time setup)
uv run pre-commit install

# Run manually on all files
uv run pre-commit run --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

## Tips

1. **Fast feedback loop**: Run `format.sh` frequently while developing
2. **Before commits**: Always run `quality_check.sh` before pushing
3. **CI/CD alignment**: These scripts mirror what runs in CI/CD pipelines
4. **Windows users**: Use Git Bash to run these scripts
