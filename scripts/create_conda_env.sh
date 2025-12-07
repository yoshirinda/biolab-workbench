#!/usr/bin/env bash
# Create conda environment for BioLab Workbench
ENV_NAME=${1:-biolab-workbench}
echo "Creating conda environment: $ENV_NAME"
conda env create -f environment.yml -n "$ENV_NAME"
echo "To activate: conda activate $ENV_NAME"
