#!/usr/bin/env python
"""
BioLab Workbench - Main Entry Point
Run this script to start the web application.
"""
import os
import sys


def check_first_run():
    """Check if this is the first run and offer setup wizard."""
    # Import config to check if first run
    import config
    
    if config.is_first_run():
        print("=" * 50)
        print("    BioLab Workbench - First Run Detected")
        print("=" * 50)
        print()
        print("It looks like this is your first time running BioLab Workbench.")
        print("Would you like to run the setup wizard? (Y/n)")
        print()
        
        try:
            response = input("Run setup wizard? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nStarting with default configuration...")
            return
        
        if response in ('', 'y', 'yes'):
            # Run setup wizard
            from setup_wizard import run_setup_wizard
            if run_setup_wizard():
                # Reload config after setup
                import importlib
                importlib.reload(config)
            else:
                print("Setup wizard was not completed.")
                print("Starting with default configuration...")
        else:
            print("Skipping setup wizard.")
            print("Starting with default configuration...")
            print()


def main():
    """Main entry point."""
    # Check for first run
    check_first_run()
    
    # Import app after potential config changes
    from app import create_app
    
    app = create_app()
    
    # Debug mode should only be enabled in development
    # Set BIOLAB_DEBUG=true in development
    debug_mode = os.environ.get('BIOLAB_DEBUG', 'false').lower() == 'true'
    
    print()
    print("=" * 50)
    print("    BioLab Workbench is starting...")
    print("=" * 50)
    print()
    print("  Web interface: http://localhost:5000")
    print("  Press Ctrl+C to stop the server")
    print()
    
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)


if __name__ == "__main__":
    main()
