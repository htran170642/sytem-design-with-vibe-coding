#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Set PYTHONPATH to include src directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Run the application
cd src
python -m app.main
