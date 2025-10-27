#!/bin/bash
# Code quality check script
# Runs all quality tools on the codebase

set -e  # Exit on error

echo "=========================================="
echo "Running Code Quality Checks"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall status
FAILED=0

# Function to run a check and track status
run_check() {
    local name=$1
    local command=$2

    echo -e "${YELLOW}Running $name...${NC}"
    if eval "$command"; then
        echo -e "${GREEN}✓ $name passed${NC}"
        echo ""
    else
        echo -e "${RED}✗ $name failed${NC}"
        echo ""
        FAILED=1
    fi
}

# 1. Black formatting check
run_check "Black (format check)" "uv run black --check backend/ main.py"

# 2. Ruff linting
run_check "Ruff (linting)" "uv run ruff check backend/ main.py"

# 3. Run tests
run_check "PyTest (tests)" "uv run pytest backend/tests/ -v"

# Note: MyPy type checking is available but optional
# Uncomment the line below to enable strict type checking:
# run_check "MyPy (type checking)" "uv run mypy backend/ main.py"

# Summary
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All checks passed! ✓${NC}"
    echo "=========================================="
    exit 0
else
    echo -e "${RED}Some checks failed ✗${NC}"
    echo "=========================================="
    exit 1
fi
