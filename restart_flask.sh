#!/bin/bash

echo "========================================"
echo "  Restarting BioLab Workbench Flask"
echo "========================================"

# Kill existing Flask process
echo "1. Stopping existing Flask process..."
pkill -f "python.*run.py" 2>/dev/null || true
sleep 2

# Clear Python cache
echo "2. Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# Start Flask
echo "3. Starting Flask with clean modules..."
echo ""
python3 run.py

