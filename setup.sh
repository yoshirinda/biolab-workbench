#!/bin/bash
#
# BioLab Workbench - One-Click Installation Script
# This script sets up the complete BioLab Workbench environment.
#

set -e

echo "=============================================="
echo "    BioLab Workbench Installation Script"
echo "=============================================="
echo ""

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "Error: conda not found."
    echo ""
    echo "Please install Miniconda or Anaconda first:"
    echo "  https://docs.conda.io/en/latest/miniconda.html"
    echo ""
    exit 1
fi

echo "Found conda: $(conda --version)"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Working directory: $SCRIPT_DIR"
echo ""

# Check if environment.yml exists
if [ ! -f "environment.yml" ]; then
    echo "Error: environment.yml not found in $SCRIPT_DIR"
    exit 1
fi

# Create or update conda environment
echo "Setting up conda environment 'bio'..."
echo ""

if conda env list | grep -q "^bio "; then
    echo "Updating existing 'bio' environment..."
    conda env update -f environment.yml --prune
else
    echo "Creating new 'bio' environment..."
    conda env create -f environment.yml
fi

echo ""
echo "Conda environment setup complete!"
echo ""

# Activate environment and install additional dependencies
echo "Installing additional Python dependencies..."
echo ""

# Source conda for shell
CONDA_BASE=$(conda info --base)
source "$CONDA_BASE/etc/profile.d/conda.sh"
conda activate bio

# Install requirements
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

echo ""
echo "Python dependencies installed!"
echo ""

# Run setup wizard
echo "Running setup wizard..."
echo ""
python setup_wizard.py

echo ""
echo "=============================================="
echo "    Installation Complete!"
echo "=============================================="
echo ""
echo "To start BioLab Workbench:"
echo ""
echo "  1. Activate the conda environment:"
echo "     conda activate bio"
echo ""
echo "  2. Run the application:"
echo "     python run.py"
echo ""
echo "  3. Open your browser to:"
echo "     http://localhost:5000"
echo ""
