#!/bin/bash
# Gifty Documentation Helper

# Set PYTHONPATH to the current directory to allow mkdocstrings to find the 'app' module
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Ensure dependencies are installed
echo "Checking/Installing documentation dependencies..."
pip install -r requirements-docs.txt

COMMAND=$1
if [ -z "$COMMAND" ]; then
    COMMAND="serve"
fi

if [ "$COMMAND" == "serve" ]; then
    echo "Starting documentation server on http://localhost:8001..."
    python3 -m mkdocs serve -a localhost:8001
elif [ "$COMMAND" == "build" ]; then
    echo "Building documentation site..."
    python3 -m mkdocs build
else
    echo "Usage: ./scripts/docs.sh [serve|build]"
    exit 1
fi
