#!/usr/bin/env bash
# Run code quality checks for the backend.
# Usage:
#   ./check.sh          # check formatting (no changes written)
#   ./check.sh --fix    # auto-format in place

set -e

if [ "$1" = "--fix" ]; then
    echo "Formatting backend with Black..."
    uv run black backend/
    echo "Done."
else
    echo "Checking backend formatting with Black..."
    uv run black --check backend/
    echo "All files are correctly formatted."
fi
