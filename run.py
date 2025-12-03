#!/usr/bin/env python
"""
BioLab Workbench - Main Entry Point
Run this script to start the web application.
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
