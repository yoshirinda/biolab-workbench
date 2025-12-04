#!/usr/bin/env python
"""
BioLab Workbench Setup Wizard
First-run configuration for new installations.
"""
import os
import sys


def create_directory_structure(base_dir):
    """Create the required directory structure."""
    directories = [
        base_dir,
        os.path.join(base_dir, 'databases'),
        os.path.join(base_dir, 'references'),
        os.path.join(base_dir, 'references', 'gold_lists'),
        os.path.join(base_dir, 'references', 'hmm_profiles'),
        os.path.join(base_dir, 'projects'),
        os.path.join(base_dir, 'uploads'),
        os.path.join(base_dir, 'results'),
        os.path.join(base_dir, 'logs'),
    ]
    
    for dir_path in directories:
        os.makedirs(dir_path, exist_ok=True)
        print(f"  Created: {dir_path}")


def save_config(base_dir):
    """Save the configuration to user config file."""
    config_dir = os.path.expanduser('~/.biolab')
    os.makedirs(config_dir, exist_ok=True)
    
    config_file = os.path.join(config_dir, 'config')
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(base_dir)
    
    print(f"  Config saved to: {config_file}")


def copy_example_data(base_dir):
    """Copy example data to the data directory if available."""
    import shutil
    
    project_dir = os.path.dirname(os.path.abspath(__file__))
    examples_src = os.path.join(project_dir, 'data', 'examples')
    gold_lists_src = os.path.join(project_dir, 'data', 'references', 'gold_lists')
    
    # Copy example FASTA files
    if os.path.exists(examples_src):
        examples_dst = os.path.join(base_dir, 'examples')
        os.makedirs(examples_dst, exist_ok=True)
        for filename in os.listdir(examples_src):
            src_file = os.path.join(examples_src, filename)
            dst_file = os.path.join(examples_dst, filename)
            if os.path.isfile(src_file) and not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)
                print(f"  Copied example: {filename}")
    
    # Copy gold lists
    if os.path.exists(gold_lists_src):
        gold_lists_dst = os.path.join(base_dir, 'references', 'gold_lists')
        os.makedirs(gold_lists_dst, exist_ok=True)
        for filename in os.listdir(gold_lists_src):
            src_file = os.path.join(gold_lists_src, filename)
            dst_file = os.path.join(gold_lists_dst, filename)
            if os.path.isfile(src_file) and not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)
                print(f"  Copied gold list: {filename}")


def run_setup_wizard():
    """Run the first-time setup wizard."""
    print("=" * 50)
    print("    Welcome to BioLab Workbench Setup!")
    print("=" * 50)
    print()
    print("This wizard will help you configure BioLab Workbench")
    print("for first-time use on this computer.")
    print()
    
    # Suggest default directory
    default_dir = os.path.expanduser("~/biolab_data")
    
    # Ask for data directory
    print("Where would you like to store BioLab data?")
    print(f"(Press Enter to use default: {default_dir})")
    print()
    
    try:
        user_input = input("Data directory: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled.")
        return False
    
    base_dir = user_input if user_input else default_dir
    
    # Expand user path
    base_dir = os.path.expanduser(base_dir)
    base_dir = os.path.abspath(base_dir)
    
    print()
    print(f"Setting up BioLab Workbench with data directory:")
    print(f"  {base_dir}")
    print()
    
    # Create directory structure
    print("Creating directory structure...")
    try:
        create_directory_structure(base_dir)
    except PermissionError as e:
        print(f"Error: Permission denied creating directories: {e}")
        return False
    except Exception as e:
        print(f"Error creating directories: {e}")
        return False
    
    print()
    
    # Save configuration
    print("Saving configuration...")
    try:
        save_config(base_dir)
    except Exception as e:
        print(f"Error saving configuration: {e}")
        return False
    
    print()
    
    # Copy example data
    print("Copying example data...")
    try:
        copy_example_data(base_dir)
    except Exception as e:
        print(f"Warning: Could not copy example data: {e}")
    
    print()
    print("=" * 50)
    print("    Setup Complete!")
    print("=" * 50)
    print()
    print("You can now start BioLab Workbench:")
    print("  python run.py")
    print()
    print("Access the web interface at:")
    print("  http://localhost:5000")
    print()
    
    return True


def main():
    """Main entry point."""
    success = run_setup_wizard()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
