"""
BLAST command wrapper for BioLab Workbench.
"""
import os
import subprocess
import json
import shlex
import re
from datetime import datetime
import config
from app.utils.logger import get_tools_logger
from app.utils.file_utils import create_result_dir, save_params
from app.core.sequence_utils import detect_sequence_type, normalize_gene_id

logger = get_tools_logger()


def sanitize_path(path):
    """Sanitize file path to prevent command injection."""
    if not path:
        return path
    # Remove any shell metacharacters
    # Only allow alphanumeric, underscore, hyphen, dot, forward slash
    if not re.match(r'^[\w\-./]+$', path):
        raise ValueError(f"Invalid characters in path: {path}")
    # Prevent directory traversal
    if '..' in path:
        raise ValueError(f"Directory traversal not allowed: {path}")
    return path


def run_conda_command(command, timeout=3600):
    """
    Run a command in the conda environment.
    Returns (success, stdout, stderr).
    """
    full_command = f"conda run -n {shlex.quote(config.CONDA_ENV)} {command}"
    logger.info(f"Running command: {full_command}")

    try:
        result = subprocess.run(
            full_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        logger.info(f"Command completed with return code: {result.returncode}")
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout} seconds")
        return False, '', 'Command timed out'
    except Exception as e:
        logger.error(f"Command failed: {str(e)}")
        return False, '', str(e)


def list_blast_databases(db_dir=None):
    """
    List available BLAST databases in the specified directory.
    Returns list of database info dicts.
    """
    if db_dir is None:
        db_dir = config.DATABASES_DIR

    databases = []

    if not os.path.exists(db_dir):
        return databases

    # Walk through directories looking for BLAST database files
    for root, dirs, files in os.walk(db_dir):
        # Look for .nin (nucleotide) or .pin (protein) files
        for f in files:
            if f.endswith('.nin') or f.endswith('.pin'):
                db_name = f.rsplit('.', 2)[0]
                db_path = os.path.join(root, db_name)
                db_type = 'nucleotide' if f.endswith('.nin') else 'protein'

                # Get relative path from databases dir
                rel_path = os.path.relpath(root, db_dir)
                if rel_path == '.':
                    display_name = db_name
                else:
                    display_name = os.path.join(rel_path, db_name)

                databases.append({
                    'name': display_name,
                    'path': db_path,
                    'type': db_type
                })

    return databases


def save_database_metadata(db_path, source_fasta, db_type, title):
    """
    Save metadata for a BLAST database including the source FASTA path.
    This allows fallback extraction from the source file when blastdbcmd fails.
    """
    metadata_file = db_path + '.meta.json'
    metadata = {
        'source_fasta': source_fasta,
        'db_type': db_type,
        'title': title,
        'created': datetime.now().isoformat()
    }
    try:
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved database metadata: {metadata_file}")
    except Exception as e:
        logger.warning(f"Failed to save database metadata: {e}")


def get_source_fasta(database):
    """
    Get the source FASTA file path from database metadata.
    Returns the source FASTA path if available and exists, None otherwise.
    """
    metadata_file = database + '.meta.json'
    if not os.path.exists(metadata_file):
        return None
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        source_fasta = metadata.get('source_fasta')
        if source_fasta and os.path.exists(source_fasta):
            return source_fasta
    except Exception as e:
        logger.warning(f"Failed to read database metadata: {e}")
    
    return None


def build_fuzzy_id_index(hit_ids):
    """
    Build an index for fuzzy gene ID matching.
    
    Returns:
        dict: Maps normalized IDs to original IDs
    """
    index = {}
    for hit_id in hit_ids:
        normalized, original = normalize_gene_id(hit_id)
        if normalized:
            # Store original ID, preferring exact matches
            if normalized not in index:
                index[normalized] = original
    return index


def fuzzy_match_id(seq_id, hit_ids_set, fuzzy_index):
    """
    Check if a sequence ID matches any hit ID using fuzzy matching.
    
    Priority:
    1. Exact match
    2. Case-insensitive match with version suffix handling
    
    Returns:
        bool: True if matched
    """
    # Exact match
    if seq_id in hit_ids_set:
        return True
    
    # Fuzzy match using normalized ID
    normalized, _ = normalize_gene_id(seq_id)
    if normalized in fuzzy_index:
        return True
    
    return False


def extract_from_fasta(source_fasta, hit_ids, output_file, fuzzy_match=True):
    """
    Extract sequences from a FASTA file by IDs.
    This is a fallback when blastdbcmd fails.
    
    Args:
        source_fasta: Path to source FASTA file
        hit_ids: List of sequence IDs to extract
        output_file: Path to output FASTA file
        fuzzy_match: Enable fuzzy matching (case-insensitive, version-agnostic)
    
    Returns:
        (success, extracted_count)
    """
    try:
        hit_ids_set = set(hit_ids)
        fuzzy_index = build_fuzzy_id_index(hit_ids) if fuzzy_match else {}
        extracted = []
        
        with open(source_fasta, 'r', encoding='utf-8') as f:
            current_header = None
            current_seq = []
            
            for line in f:
                line = line.strip()
                if line.startswith('>'):
                    # Save previous sequence if it matches
                    if current_header is not None:
                        seq_id = current_header.split()[0]
                        if fuzzy_match_id(seq_id, hit_ids_set, fuzzy_index):
                            extracted.append((current_header, ''.join(current_seq)))
                    current_header = line[1:]
                    current_seq = []
                elif line:
                    current_seq.append(line)
            
            # Handle last sequence
            if current_header is not None:
                seq_id = current_header.split()[0]
                if fuzzy_match_id(seq_id, hit_ids_set, fuzzy_index):
                    extracted.append((current_header, ''.join(current_seq)))
        
        # Write extracted sequences
        with open(output_file, 'w', encoding='utf-8') as f:
            for header, seq in extracted:
                f.write(f">{header}\n")
                # Write sequence in lines of 60 characters
                for i in range(0, len(seq), 60):
                    f.write(seq[i:i+60] + '\n')
        
        return True, len(extracted)
    except Exception as e:
        logger.error(f"Failed to extract from FASTA: {e}")
        return False, 0


def create_blast_database(input_file, db_name, db_type='auto', title=None):
    """
    Create a BLAST database using makeblastdb.
    db_type: 'nucl', 'prot', or 'auto' (detect from sequence)
    Returns (success, message, db_path).
    """
    try:
        input_file = sanitize_path(input_file)
        db_name = sanitize_path(db_name)
    except ValueError as e:
        return False, str(e), None

    if not os.path.exists(input_file):
        return False, f"Input file not found: {input_file}", None

    # Auto-detect database type
    if db_type == 'auto':
        with open(input_file, 'r') as f:
            content = f.read(10000)
            # Skip headers and get sequence
            lines = content.split('\n')
            seq_lines = [l for l in lines if not l.startswith('>')]
            sample_seq = ''.join(seq_lines)[:500]
            seq_type = detect_sequence_type(sample_seq)
            db_type = 'nucl' if seq_type == 'nucleotide' else 'prot'

    if title is None:
        title = db_name

    # Sanitize title
    title = re.sub(r'[^\w\s\-]', '', title)

    # Create database in config.DATABASES_DIR instead of input file directory
    # This ensures the database is found by list_blast_databases()
    db_path = os.path.join(config.DATABASES_DIR, db_name)

    command = f'makeblastdb -in {shlex.quote(input_file)} -dbtype {shlex.quote(db_type)} -out {shlex.quote(db_path)} -title {shlex.quote(title)}'

    success, stdout, stderr = run_conda_command(command)

    if success:
        logger.info(f"Created BLAST database: {db_path}")
        # Save metadata with source FASTA path for fallback extraction
        save_database_metadata(db_path, input_file, db_type, title)
        return True, "Database created successfully", db_path
    else:
        logger.error(f"Failed to create database: {stderr}")
        return False, stderr, None


def select_blast_program(query_type, db_type):
    """
    Select appropriate BLAST program based on query and database types.
    Returns program name.
    """
    if query_type == 'nucleotide' and db_type == 'nucleotide':
        return 'blastn'
    elif query_type == 'protein' and db_type == 'protein':
        return 'blastp'
    elif query_type == 'nucleotide' and db_type == 'protein':
        return 'blastx'
    elif query_type == 'protein' and db_type == 'nucleotide':
        return 'tblastn'
    else:
        return 'blastn'  # Default


def add_tsv_header(filepath, output_format):
    """
    Add a header row to TSV BLAST output files.
    Uses a temporary file approach to handle large files efficiently.
    """
    if output_format not in ['tsv', 'detailed']:
        return  # Only add headers to TSV format files
    
    if not os.path.exists(filepath):
        return
    
    # Define headers based on format
    if output_format == 'tsv':
        header = "qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen\tqstart\tqend\tsstart\tsend\tevalue\tbitscore\n"
    elif output_format == 'detailed':
        header = "qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen\tqstart\tqend\tsstart\tsend\tevalue\tbitscore\tqlen\tslen\tqcovs\tstitle\n"
    else:
        return
    
    temp_file = filepath + '.tmp'
    try:
        # Write header to temp file, then append original content (stream approach)
        with open(temp_file, 'w', encoding='utf-8') as out_f:
            out_f.write(header)
            with open(filepath, 'r', encoding='utf-8') as in_f:
                for line in in_f:
                    out_f.write(line)
        
        # Replace original file with temp file
        os.replace(temp_file, filepath)
        
        logger.info(f"Added TSV header to {filepath}")
    except Exception as e:
        logger.warning(f"Failed to add TSV header: {e}")
        # Clean up temp file if it exists
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass


def run_blast(query_file, database, output_format='tsv', evalue=1e-5,
              num_threads=None, max_hits=500, program=None, outfmt=None):
    """
    Run BLAST search.
    output_format: 'tsv', 'txt', 'html', 'detailed'
    Returns (success, result_dir, output_files, command).
    """
    try:
        query_file = sanitize_path(query_file)
        database = sanitize_path(database)
    except ValueError as e:
        return False, str(e), None, None

    if not os.path.exists(query_file):
        return False, f"Query file not found: {query_file}", None, None

    # Auto-detect query type
    with open(query_file, 'r') as f:
        content = f.read(10000)
        lines = content.split('\n')
        seq_lines = [l for l in lines if not l.startswith('>')]
        sample_seq = ''.join(seq_lines)[:500]
        query_type = detect_sequence_type(sample_seq)

    # Determine database type from files
    if os.path.exists(f"{database}.nin"):
        db_type = 'nucleotide'
    elif os.path.exists(f"{database}.pin"):
        db_type = 'protein'
    else:
        # Try to find db files with extensions
        db_type = 'nucleotide'  # Default

    # Select BLAST program
    if program is None:
        program = select_blast_program(query_type, db_type)

    # Validate program
    valid_programs = ['blastn', 'blastp', 'blastx', 'tblastn', 'tblastx']
    if program not in valid_programs:
        return False, f"Invalid BLAST program: {program}", None, None

    # Create result directory
    result_dir = create_result_dir('blast', 'search')

    # Output format codes
    if outfmt is None:
        format_codes = {
            'tsv': '6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore',
            'txt': '0',  # Pairwise
            'html': '5',  # XML (for conversion)
            'detailed': '6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore qlen slen qcovs stitle',
        }
        outfmt = format_codes.get(output_format, format_codes['tsv'])

    output_file = os.path.join(result_dir, f'blast_result.{output_format}')

    if num_threads is None:
        num_threads = config.DEFAULT_THREADS

    # Validate numeric parameters
    try:
        evalue = float(evalue)
        num_threads = int(num_threads)
        max_hits = int(max_hits)
    except (ValueError, TypeError):
        return False, "Invalid numeric parameter", None, None

    command = (
        f'{program} -query {shlex.quote(query_file)} -db {shlex.quote(database)} '
        f'-out {shlex.quote(output_file)} -outfmt {shlex.quote(outfmt)} '
        f'-evalue {evalue} -num_threads {num_threads} -max_target_seqs {max_hits}'
    )

    # Full command for display (with conda wrapper)
    full_command = f"conda run -n {config.CONDA_ENV} {command}"

    # Save parameters
    params = {
        'query_file': query_file,
        'database': database,
        'program': program,
        'evalue': evalue,
        'num_threads': num_threads,
        'max_hits': max_hits,
        'output_format': output_format,
        'timestamp': datetime.now().isoformat()
    }
    save_params(result_dir, params)

    success, stdout, stderr = run_conda_command(command)

    if success:
        # Add header to TSV output files
        add_tsv_header(output_file, output_format)
        logger.info(f"BLAST search completed: {output_file}")
        return True, result_dir, {'main': output_file}, full_command
    else:
        logger.error(f"BLAST search failed: {stderr}")
        return False, stderr, None, full_command


def extract_sequences(database, hit_ids, output_file):
    """
    Extract sequences from BLAST database using blastdbcmd.
    Falls back to extracting from source FASTA if blastdbcmd fails.
    
    hit_ids: list of sequence IDs to extract
    Returns (success, message).
    """
    if not hit_ids:
        return False, "No hit IDs provided"

    try:
        database = sanitize_path(database)
        output_file = sanitize_path(output_file)
    except ValueError as e:
        return False, str(e)

    # Sanitize hit IDs - only allow alphanumeric, underscore, hyphen, dot, pipe
    sanitized_ids = []
    for hit_id in hit_ids:
        if re.match(r'^[\w\-.|]+$', hit_id):
            sanitized_ids.append(hit_id)
        else:
            logger.warning(f"Skipping invalid hit ID: {hit_id}")

    if not sanitized_ids:
        return False, "No valid hit IDs after sanitization"

    # First try blastdbcmd
    id_file = output_file + '.ids'
    stderr = ''
    try:
        with open(id_file, 'w') as f:
            f.write('\n'.join(sanitized_ids))

        command = f'blastdbcmd -db {shlex.quote(database)} -entry_batch {shlex.quote(id_file)} -out {shlex.quote(output_file)}'

        success, stdout, stderr = run_conda_command(command)
    finally:
        # Clean up temp file
        if os.path.exists(id_file):
            try:
                os.remove(id_file)
            except Exception:
                pass

    # Check if blastdbcmd succeeded and output file has content
    blastdbcmd_success = success and os.path.exists(output_file) and os.path.getsize(output_file) > 0

    if blastdbcmd_success:
        logger.info(f"Extracted {len(sanitized_ids)} sequences to {output_file}")
        return True, f"Extracted {len(sanitized_ids)} sequences"
    
    # Fallback: try to extract from source FASTA
    logger.info(f"blastdbcmd failed, attempting fallback extraction from source FASTA")
    source_fasta = get_source_fasta(database)
    
    if source_fasta:
        logger.info(f"Found source FASTA: {source_fasta}")
        fallback_success, extracted_count = extract_from_fasta(source_fasta, sanitized_ids, output_file)
        
        if fallback_success and extracted_count > 0:
            logger.info(f"Fallback extraction succeeded: {extracted_count} sequences")
            return True, f"Extracted {extracted_count} sequences (from source FASTA)"
        else:
            logger.error(f"Fallback extraction failed")
            return False, f"blastdbcmd failed and fallback extraction found no matching sequences"
    else:
        logger.error(f"No source FASTA available for fallback extraction")
        return False, f"Sequence extraction failed: {stderr}. No source FASTA available for fallback."


def parse_blast_tsv(filepath):
    """
    Parse BLAST TSV output file.
    Returns list of hit dicts.
    """
    hits = []
    headers = ['qseqid', 'sseqid', 'pident', 'length', 'mismatch', 'gapopen',
               'qstart', 'qend', 'sstart', 'send', 'evalue', 'bitscore']
    
    # Set of expected header field names for robust detection
    header_fields = set(headers)

    if not os.path.exists(filepath):
        return hits

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('\t')
            
            # Skip header row if present - check if all fields match expected headers
            # This handles both standard and detailed format headers
            if parts and parts[0] in header_fields:
                # Check if this looks like a header row (first few fields match headers)
                first_fields = set(parts[:min(len(parts), 6)])
                if first_fields <= header_fields.union({'qlen', 'slen', 'qcovs', 'stitle'}):
                    continue

            hit = {}
            for i, header in enumerate(headers):
                if i < len(parts):
                    hit[header] = parts[i]
            hits.append(hit)

    return hits
