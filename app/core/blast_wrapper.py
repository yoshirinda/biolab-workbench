"""
BLAST command wrapper for BioLab Workbench.
"""
import os
import subprocess
import json
from datetime import datetime
import config
from app.utils.logger import get_tools_logger
from app.utils.file_utils import create_result_dir, save_params
from app.core.sequence_utils import detect_sequence_type

logger = get_tools_logger()


def run_conda_command(command, timeout=3600):
    """
    Run a command in the conda environment.
    Returns (success, stdout, stderr).
    """
    full_command = f"conda run -n {config.CONDA_ENV} {command}"
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


def create_blast_database(input_file, db_name, db_type='auto', title=None):
    """
    Create a BLAST database using makeblastdb.
    db_type: 'nucl', 'prot', or 'auto' (detect from sequence)
    Returns (success, message, db_path).
    """
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

    db_dir = os.path.dirname(input_file)
    db_path = os.path.join(db_dir, db_name)

    command = f'makeblastdb -in "{input_file}" -dbtype {db_type} -out "{db_path}" -title "{title}"'

    success, stdout, stderr = run_conda_command(command)

    if success:
        logger.info(f"Created BLAST database: {db_path}")
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


def run_blast(query_file, database, output_format='tsv', evalue=1e-5,
              num_threads=None, max_hits=500, program=None, outfmt=None):
    """
    Run BLAST search.
    output_format: 'tsv', 'txt', 'html', 'detailed'
    Returns (success, result_dir, output_files).
    """
    if not os.path.exists(query_file):
        return False, f"Query file not found: {query_file}", None

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

    command = (
        f'{program} -query "{query_file}" -db "{database}" '
        f'-out "{output_file}" -outfmt "{outfmt}" '
        f'-evalue {evalue} -num_threads {num_threads} -max_target_seqs {max_hits}'
    )

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
        logger.info(f"BLAST search completed: {output_file}")
        return True, result_dir, {'main': output_file}
    else:
        logger.error(f"BLAST search failed: {stderr}")
        return False, stderr, None


def extract_sequences(database, hit_ids, output_file):
    """
    Extract sequences from BLAST database using blastdbcmd.
    hit_ids: list of sequence IDs to extract
    Returns (success, message).
    """
    if not hit_ids:
        return False, "No hit IDs provided"

    # Write IDs to temp file
    id_file = output_file + '.ids'
    with open(id_file, 'w') as f:
        f.write('\n'.join(hit_ids))

    command = f'blastdbcmd -db "{database}" -entry_batch "{id_file}" -out "{output_file}"'

    success, stdout, stderr = run_conda_command(command)

    # Clean up temp file
    if os.path.exists(id_file):
        os.remove(id_file)

    if success:
        logger.info(f"Extracted {len(hit_ids)} sequences to {output_file}")
        return True, f"Extracted {len(hit_ids)} sequences"
    else:
        logger.error(f"Sequence extraction failed: {stderr}")
        return False, stderr


def parse_blast_tsv(filepath):
    """
    Parse BLAST TSV output file.
    Returns list of hit dicts.
    """
    hits = []
    headers = ['qseqid', 'sseqid', 'pident', 'length', 'mismatch', 'gapopen',
               'qstart', 'qend', 'sstart', 'send', 'evalue', 'bitscore']

    if not os.path.exists(filepath):
        return hits

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('\t')
            hit = {}
            for i, header in enumerate(headers):
                if i < len(parts):
                    hit[header] = parts[i]
            hits.append(hit)

    return hits
