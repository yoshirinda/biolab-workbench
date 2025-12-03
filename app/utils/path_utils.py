"""
Path utilities for BioLab Workbench.
Handles Windows/WSL path conversions.
"""
import os
import re


def windows_to_wsl(windows_path):
    """
    Convert Windows path to WSL path.
    Example: C:\\Users\\name -> /mnt/c/Users/name
    Example: E:\\Kun\\wsl -> /mnt/e/Kun/wsl
    """
    if not windows_path:
        return windows_path

    # Check if already a WSL path
    if windows_path.startswith('/'):
        return windows_path

    # Match Windows drive letter
    match = re.match(r'^([A-Za-z]):\\(.*)$', windows_path)
    if match:
        drive = match.group(1).lower()
        path = match.group(2).replace('\\', '/')
        return f'/mnt/{drive}/{path}'

    # Handle paths without drive letter
    return windows_path.replace('\\', '/')


def wsl_to_windows(wsl_path):
    """
    Convert WSL path to Windows path.
    Example: /mnt/c/Users/name -> C:\\Users\\name
    Example: /mnt/e/Kun/wsl -> E:\\Kun\\wsl
    """
    if not wsl_path:
        return wsl_path

    # Match WSL mount point
    match = re.match(r'^/mnt/([a-z])/(.*)$', wsl_path)
    if match:
        drive = match.group(1).upper()
        path = match.group(2).replace('/', '\\')
        return f'{drive}:\\{path}'

    return wsl_path


def normalize_path(path):
    """
    Normalize a path to WSL format.
    Removes trailing slashes and normalizes separators.
    """
    if not path:
        return path

    # Convert to WSL if Windows path
    path = windows_to_wsl(path)

    # Normalize the path
    path = os.path.normpath(path)

    return path


def ensure_dir(path):
    """
    Ensure a directory exists, creating it if necessary.
    """
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path


def safe_filename(filename):
    """
    Create a safe filename by removing/replacing problematic characters.
    """
    # Remove leading/trailing whitespace
    filename = filename.strip()

    # Replace problematic characters
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        filename = filename.replace(char, '_')

    # Remove multiple consecutive underscores
    while '__' in filename:
        filename = filename.replace('__', '_')

    return filename
