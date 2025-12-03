#!/usr/bin/env python
"""
BioLab Workbench - Main Entry Point
Run this script to start the web application.
"""
import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Debug mode should only be enabled in development
    # Set BIOLAB_DEBUG=false in production
    debug_mode = os.environ.get('BIOLAB_DEBUG', 'false').lower() == 'true'
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
