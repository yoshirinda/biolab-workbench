#!/bin/bash
# BioLab Workbench - Arabidopsis Database Setup Script
# Downloads TAIR10 proteome and creates a BLAST database.

# Centralized data directory from config
DATA_DIR="biolab_data/databases"
DB_PATH="${DATA_DIR}/Athaliana_TAIR10_db"

mkdir -p "${DATA_DIR}"

echo "--- Arabidopsis TAIR10 Database Setup ---"

# Check if database already exists
if [ -f "${DB_PATH}.pin" ] || [ -f "${DB_PATH}.psq" ]; then
    echo "Arabidopsis database already exists at ${DB_PATH}."
    exit 0
fi

# Download TAIR10 proteome (Example from TAIR)
# NOTE: This is a public URL for TAIR10 proteins
# https://www.arabidopsis.org/download_files/Proteins/TAIR10_protein_lists/TAIR10_pep_20101214.gz
SOURCE_URL="https://www.arabidopsis.org/download_files/Proteins/TAIR10_protein_lists/TAIR10_pep_20101214.gz"
TMP_FILE="${DATA_DIR}/TAIR10_pep.gz"
TMP_FASTA="${DATA_DIR}/TAIR10_pep.fasta"

echo "Downloading TAIR10 proteome from TAIR..."
curl -L "${SOURCE_URL}" -o "${TMP_FILE}"

if [ ! -f "${TMP_FILE}" ]; then
    echo "Error: Download failed."
    exit 1
fi

echo "Extracting..."
gunzip -c "${TMP_FILE}" > "${TMP_FASTA}"

echo "Creating BLAST database..."
# Assuming 'makeblastdb' is in PATH or conda env 'bio' is active
if command -v makeblastdb >/dev/null 2>&1; then
    makeblastdb -in "${TMP_FASTA}" -dbtype prot -title "Arabidopsis thaliana TAIR10" -out "${DB_PATH}"
else
    echo "Warning: 'makeblastdb' not found in PATH."
    echo "Attempting to use conda env 'bio'..."
    conda run -n bio makeblastdb -in "${TMP_FASTA}" -dbtype prot -title "Arabidopsis thaliana TAIR10" -out "${DB_PATH}"
fi

if [ $? -eq 0 ]; then
    echo "--- Success! ---"
    echo "Arabidopsis database created at: ${DB_PATH}"
    # Cleanup
    rm "${TMP_FILE}" "${TMP_FASTA}"
else
    echo "Error: Database creation failed."
    exit 1
fi
