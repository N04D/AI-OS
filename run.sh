#!/bin/bash
set -e

# Setup venv if available
if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
fi

# Run the main orchestrator loop
echo "Starting orchestrator..."
python3 -m orchestrator.main_loop
