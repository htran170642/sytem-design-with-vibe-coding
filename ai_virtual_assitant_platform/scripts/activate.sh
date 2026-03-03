#!/bin/bash

# AIVA Virtual Environment Activation Script
# Usage: source scripts/activate.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
    echo "✓ Virtual environment activated"
    echo "Python: $(which python)"
    echo "Version: $(python --version)"
else
    echo "✗ Virtual environment not found!"
    echo "Please run: python3 -m venv venv"
    exit 1
fi