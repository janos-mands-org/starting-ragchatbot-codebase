#!/bin/bash
# Code formatting script
# Automatically formats code with black and fixes ruff issues

set -e  # Exit on error

echo "=========================================="
echo "Formatting Code"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Run black formatter
echo -e "${YELLOW}Running Black formatter...${NC}"
uv run black backend/ main.py
echo -e "${GREEN}✓ Black formatting complete${NC}"
echo ""

# 2. Run ruff with auto-fix
echo -e "${YELLOW}Running Ruff auto-fix...${NC}"
uv run ruff check backend/ main.py --fix
echo -e "${GREEN}✓ Ruff fixes applied${NC}"
echo ""

echo "=========================================="
echo -e "${GREEN}Code formatting complete! ✓${NC}"
echo "=========================================="
