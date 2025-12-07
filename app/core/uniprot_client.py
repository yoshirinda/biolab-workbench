"""
UniProt API client for BioLab Workbench.
"""
import re
import requests
from urllib.parse import urlencode
import time
from datetime import datetime
import os
import config
from app.utils.logger import get_tools_logger
from app.utils.file_utils import create_result_dir, save_params

logger = get_tools_logger()

# UniProt REST API base URLs
UNIPROT_API_BASE = "https://rest.uniprot.org"
UNIPROTKB_BASE = f"{UNIPROT_API_BASE}/uniprotkb"
TAXONOMY_BASE = f"{UNIPROT_API_BASE}/taxonomy"


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

    url = f"{UNIPROTKB_BASE}/search?{urlencode(params)}"
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


def search_taxonomy(query, limit=50):
    """
    Search the UniProt taxonomy database.
    """
    params = {
        'query': query,
        'format': 'json',
        'size': limit,
        'fields': 'id,scientific_name,common_name,lineage'
    }
    url = f"{TAXONOMY_BASE}/search?{urlencode(params)}"
    logger.info(f"Searching UniProt Taxonomy: {url}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        return True, data.get('results', []), "Success"
    except Exception as e:
        logger.error(f"Taxonomy search failed: {e}")
        return False, [], str(e)


def get_taxonomy_lineage(taxon_id):
    """
    Get the lineage for a given taxon ID.
    """
    url = f"{TAXONOMY_BASE}/lineage/{taxon_id}?format=json"
    logger.info(f"Fetching lineage for taxon: {taxon_id}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        return True, data.get('lineage', []), "Success"
    except Exception as e:
        logger.error(f"Taxonomy lineage fetch failed: {e}")
        return False, [], str(e)


def get_taxonomy_children(parent_id):
    """
    Get the direct children for a given taxon ID.
    """
    query = f"parent:{parent_id}"
    params = {
        'query': query,
        'format': 'json',
        'size': 500,  # Get a reasonable number of children
        'fields': 'id,scientific_name,common_name'
    }
    url = f"{TAXONOMY_BASE}/search?{urlencode(params)}"
    logger.info(f"Fetching children for taxon: {parent_id}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        return True, data.get('results', []), "Success"
    except Exception as e:
        logger.error(f"Taxonomy children fetch failed: {e}")
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
    
    relative_path = os.path.relpath(fasta_file, config.RESULTS_DIR)
    logger.info(f"Downloaded {len(results)} sequences to {fasta_file}")
    return True, result_dir, relative_path, len(results)


def get_entry(accession):
    """
    Get a single UniProt entry by accession.
    """
    url = f"{UNIPROTKB_BASE}/{accession}.json"

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


FASTA_SPECIES_PATTERN = re.compile(r'OS=([^=]+?)(?:\sOX=|\sGN=|\sPE=|\sSV=|$)')
FASTA_GENE_PATTERN = re.compile(r'GN=([^\s=]+)')
ACCESSION_PATTERN = re.compile(r'^[^|]+\|([^|]+)\|')


def _chunked(items, size):
    for idx in range(0, len(items), size):
        yield items[idx:idx + size]


def _iter_fasta_records(fasta_text):
    header = None
    sequence_lines = []
    for raw_line in fasta_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('>'):
            if header:
                yield header, ''.join(sequence_lines)
            header = line[1:].strip()
            sequence_lines = []
        else:
            sequence_lines.append(line)
    if header:
        yield header, ''.join(sequence_lines)


def _parse_fasta_header(header):
    accession_match = ACCESSION_PATTERN.match(header)
    if accession_match:
        accession = accession_match.group(1)
    else:
        accession = header.split(' ')[0]

    species_match = FASTA_SPECIES_PATTERN.search(header)
    species = species_match.group(1).strip() if species_match else None

    gene_match = FASTA_GENE_PATTERN.search(header)
    gene = gene_match.group(1).strip() if gene_match else None

    return {
        'accession': accession,
        'species': species,
        'gene': gene,
        'original_header': header
    }


def _clean_species_name(species):
    if not species:
        return 'Unknown'
    cleaned = species.split(' (')[0].strip()
    cleaned = cleaned.replace(' ', '_').replace('.', '')
    return cleaned or 'Unknown'


def _clean_gene_name(gene, accession):
    if not gene:
        return accession
    cleaned = gene.strip()
    if not cleaned or cleaned.lower() == 'unknown':
        return accession
    return cleaned


def _build_curated_header(metadata, header_format):
    if header_format == 'gene_species_id':
        accession = metadata.get('accession', '')
        gene = _clean_gene_name(metadata.get('gene'), accession)
        species = _clean_species_name(metadata.get('species'))
        return f"{gene}_{species}_{accession}"
    return metadata.get('original_header') or metadata.get('accession', '')


def fetch_curated_sequences(accessions, header_format='gene_species_id', batch_size=100):
    if not accessions:
        return []

    stream_url = f"{UNIPROTKB_BASE}/stream"
    order_map = {acc: idx for idx, acc in enumerate(accessions)}
    collected = {}

    for batch_index, batch in enumerate(_chunked(accessions, batch_size)):
        query = " OR ".join([f"accession:{acc}" for acc in batch])
        logger.info(f"Fetching curated batch {batch_index + 1}: {len(batch)} accessions")

        try:
            response = requests.get(
                stream_url,
                params={'query': query, 'format': 'fasta'},
                timeout=120
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error(f"Curated UniProt batch failed: {exc}")
            raise

        for header, sequence in _iter_fasta_records(response.text):
            if not sequence:
                continue
            metadata = _parse_fasta_header(header)
            accession = metadata.get('accession')
            if not accession or accession not in order_map or accession in collected:
                continue
            collected[accession] = {
                'accession': accession,
                'header': _build_curated_header(metadata, header_format),
                'sequence': sequence
            }

        if len(accessions) > batch_size:
            time.sleep(0.2)

    ordered_records = [collected[acc] for acc in accessions if acc in collected]
    return ordered_records


def download_selected_sequences(accessions, header_format='gene_species_id'):
    """Download curated sequences for a list of accessions."""
    if not accessions:
        return False, None, None, "No selected accessions provided"

    result_dir = create_result_dir('uniprot', 'curated')
    params = {
        'selected_ids': accessions,
        'count': len(accessions),
        'header_format': header_format,
        'timestamp': datetime.now().isoformat()
    }
    save_params(result_dir, params)

    try:
        curated_records = fetch_curated_sequences(accessions, header_format=header_format)
    except requests.RequestException as exc:
        return False, result_dir, None, str(exc)

    if not curated_records:
        return False, result_dir, None, "No sequences retrieved for selected accessions"

    fasta_file = os.path.join(result_dir, 'curated_sequences.fasta')
    with open(fasta_file, 'w') as handle:
        for record in curated_records:
            sequence = record.get('sequence', '')
            if not sequence:
                continue
            handle.write(f">{record['header']}\n")
            for i in range(0, len(sequence), 60):
                handle.write(sequence[i:i+60] + '\n')
    
    relative_path = os.path.relpath(fasta_file, config.RESULTS_DIR)
    logger.info(f"Downloaded {len(curated_records)} curated sequences to {fasta_file}")
    return True, result_dir, relative_path, len(curated_records)
