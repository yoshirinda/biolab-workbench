"""
UniProt API client for BioLab Workbench.
"""
import requests
from urllib.parse import urlencode
import time
from datetime import datetime
import os
import config
from app.utils.logger import get_tools_logger
from app.utils.file_utils import create_result_dir, save_params

logger = get_tools_logger()

# UniProt REST API base URL
UNIPROT_API_BASE = "https://rest.uniprot.org/uniprotkb"


def search_uniprot(query, taxonomy_id=None, database_type='all', limit=500):
    """
    Search UniProt for sequences.

    Args:
        query: Search keywords
        taxonomy_id: Taxonomy ID to filter by (e.g., 3702 for Arabidopsis)
        database_type: 'reviewed' (Swiss-Prot), 'unreviewed' (TrEMBL), or 'all'
        limit: Maximum number of results

    Returns:
        (success, results, message)
    """
    # Build query
    search_query = query

    if taxonomy_id:
        search_query += f" AND taxonomy_id:{taxonomy_id}"

    if database_type == 'reviewed':
        search_query += " AND reviewed:true"
    elif database_type == 'unreviewed':
        search_query += " AND reviewed:false"

    params = {
        'query': search_query,
        'format': 'json',
        'size': min(limit, 500),
        'fields': 'accession,id,protein_name,gene_names,organism_name,sequence'
    }

    url = f"{UNIPROT_API_BASE}/search?{urlencode(params)}"
    logger.info(f"Searching UniProt: {url}")

    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        data = response.json()
        results = data.get('results', [])

        logger.info(f"Found {len(results)} UniProt entries")
        return True, results, f"Found {len(results)} entries"

    except requests.exceptions.Timeout:
        logger.error("UniProt search timed out")
        return False, [], "Request timed out"
    except requests.exceptions.RequestException as e:
        logger.error(f"UniProt search failed: {str(e)}")
        return False, [], str(e)
    except Exception as e:
        logger.error(f"UniProt search error: {str(e)}")
        return False, [], str(e)


def format_header(entry, format_type='gene_species_id'):
    """
    Format FASTA header for a UniProt entry.
    format_type: 'gene_species_id' -> GeneSymbol_Species_UniProtID
    """
    accession = entry.get('primaryAccession', '')

    # Get gene name
    gene_names = entry.get('genes', [])
    if gene_names and gene_names[0].get('geneName'):
        gene = gene_names[0]['geneName'].get('value', '')
    else:
        gene = accession

    # Get species (simplified)
    organism = entry.get('organism', {}).get('scientificName', '')
    species = organism.replace(' ', '_')

    if format_type == 'gene_species_id':
        return f"{gene}_{species}_{accession}"
    else:
        return f"{accession}|{gene}|{organism}"


def get_sequence(entry):
    """Extract sequence from a UniProt entry."""
    seq_info = entry.get('sequence', {})
    return seq_info.get('value', '')


def download_sequences(query, taxonomy_id=None, database_type='all', limit=500,
                       header_format='gene_species_id'):
    """
    Search UniProt and download sequences as FASTA.

    Returns:
        (success, result_dir, fasta_file, count)
    """
    result_dir = create_result_dir('uniprot', 'search')

    # Save parameters
    params = {
        'query': query,
        'taxonomy_id': taxonomy_id,
        'database_type': database_type,
        'limit': limit,
        'header_format': header_format,
        'timestamp': datetime.now().isoformat()
    }
    save_params(result_dir, params)

    # Search UniProt
    success, results, message = search_uniprot(query, taxonomy_id, database_type, limit)

    if not success:
        return False, result_dir, None, message

    if not results:
        return True, result_dir, None, "No results found"

    # Write FASTA file
    fasta_file = os.path.join(result_dir, 'sequences.fasta')

    with open(fasta_file, 'w') as f:
        for entry in results:
            header = format_header(entry, header_format)
            sequence = get_sequence(entry)
            if sequence:
                f.write(f">{header}\n")
                # Write sequence in lines of 60 characters
                for i in range(0, len(sequence), 60):
                    f.write(sequence[i:i+60] + '\n')

    logger.info(f"Downloaded {len(results)} sequences to {fasta_file}")
    return True, result_dir, fasta_file, len(results)


def get_entry(accession):
    """
    Get a single UniProt entry by accession.
    """
    url = f"{UNIPROT_API_BASE}/{accession}.json"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 404:
            return False, None, "Entry not found"
        response.raise_for_status()
        return True, response.json(), "Success"
    except Exception as e:
        return False, None, str(e)


def batch_retrieve(accessions):
    """
    Retrieve multiple UniProt entries by accession.
    """
    results = []
    for acc in accessions:
        success, entry, _ = get_entry(acc)
        if success:
            results.append(entry)
        time.sleep(0.1)  # Rate limiting
    return results
