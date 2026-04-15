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

IUPAC_NUC_SET = set('ACGTUNRYSWKMBDHV')
AA_ONLY_HINT_SET = set('EFILPQZX*')
SUPPORTED_BLASTN_REWARD_PENALTY_PAIRS = {
    (1, -5),
    (1, -4),
    (1, -3),
    (1, -2),
    (1, -1),
    (2, -7),
    (2, -5),
    (2, -3),
    (2, -2),
}
PROTEIN_WORD_SIZE_LIMITS = {
    'blastp': (2, 7),
    'blastx': (2, 7),
    'tblastn': (2, 7),
    'tblastx': (2, 3),
}
TASK_WORD_SIZE_DEFAULTS = {
    'blastn': 11,
    'blastn-short': 7,
    'dc-megablast': 11,
    'megablast': 28,
    'blastp': 6,
    'blastx': 3,
    'tblastn': 3,
    'tblastx': 3,
}


def sanitize_path(path):
    """Sanitize file path to prevent command injection."""
    if not path:
        return path
    # Remove any shell metacharacters
    # Allow common safe path chars including spaces.
    if not re.match(r'^[\w\-./ ]+$', path):
        raise ValueError(f"Invalid characters in path: {path}")
    # Prevent directory traversal
    if '..' in path:
        raise ValueError(f"Directory traversal not allowed: {path}")
    return path


def get_supported_blastn_reward_penalty_pairs():
    """Return supported blastn reward/penalty pairs as a stable sorted list."""
    return sorted(SUPPORTED_BLASTN_REWARD_PENALTY_PAIRS, key=lambda pair: (pair[0], pair[1]))


def get_blast_word_size_limits(program, task=None):
    """
    Return program-specific word_size bounds when BLAST documents them clearly.

    For blastp / blastx / tblastn / tblastx the supported ranges are explicit.
    For blastn tasks we keep the broader CLI validation because task-specific
    defaults are better suited for guidance than hard rejection here.
    """
    if program in PROTEIN_WORD_SIZE_LIMITS:
        return PROTEIN_WORD_SIZE_LIMITS[program]
    return (2, 128)


def get_blast_word_size_default(program, task=None):
    """Return a task-aware default word_size suggestion for UI / auto-tuning."""
    if program == 'blastn':
        return TASK_WORD_SIZE_DEFAULTS.get(task or 'blastn')
    return TASK_WORD_SIZE_DEFAULTS.get(program)


def normalize_blast_scoring_options(program, task=None, word_size=None, reward=None, penalty=None):
    """
    Validate and normalize scientific BLAST options that depend on program/task.

    Returns (success, message, normalized_dict, warnings).
    """
    warnings = []
    normalized = {
        'word_size': word_size,
        'reward': reward,
        'penalty': penalty,
    }

    if (reward is None) ^ (penalty is None):
        return False, "reward and penalty must be provided together for blastn scoring", None, warnings

    if program == 'blastn' and reward is not None and penalty is not None:
        if (reward, penalty) not in SUPPORTED_BLASTN_REWARD_PENALTY_PAIRS:
            pair_text = ', '.join(f'{r}/{p}' for r, p in get_supported_blastn_reward_penalty_pairs())
            return (
                False,
                f"Unsupported blastn reward/penalty pair {reward}/{penalty}. Supported pairs: {pair_text}",
                None,
                warnings,
            )

    limits = get_blast_word_size_limits(program, task=task)
    if normalized['word_size'] is not None and limits is not None:
        min_word_size, max_word_size = limits
        if not (min_word_size <= normalized['word_size'] <= max_word_size):
            return (
                False,
                f"word_size must be between {min_word_size} and {max_word_size} for {program}",
                None,
                warnings,
            )

    if program == 'blastn' and task == 'blastn-short' and normalized['word_size'] is None:
        normalized['word_size'] = TASK_WORD_SIZE_DEFAULTS['blastn-short']
        warnings.append("task=blastn-short: auto-set word_size=7 for short nucleotide queries.")

    return True, "", normalized, warnings


def run_conda_command(command, timeout=3600):
    """
    Run a command in the conda environment.
    Returns (success, stdout, stderr).
    """
    if config.USE_CONDA and config.CONDA_ENV:
        full_command = f"conda run -n {shlex.quote(config.CONDA_ENV)} {command}"
    else:
        full_command = command
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

    # Collect candidate db paths and types
    db_candidates = {}
    nucleotide_exts = {'.nin', '.nhr', '.nsq'}
    protein_exts = {'.pin', '.phr', '.psq'}

    for root, dirs, files in os.walk(db_dir):
        for f in files:
            base, ext = os.path.splitext(f)
            db_path = os.path.join(root, base)

            db_type = None
            if ext in nucleotide_exts:
                db_type = 'nucleotide'
            elif ext in protein_exts:
                db_type = 'protein'

            if db_type:
                # Prefer an already detected type if exists
                if db_path not in db_candidates:
                    db_candidates[db_path] = db_type

    for db_path, db_type in db_candidates.items():
        # Prefer metadata-informed type when available
        db_type = get_db_type(db_path)
        rel_path = os.path.relpath(os.path.dirname(db_path), db_dir)
        db_name = os.path.basename(db_path)
        display_name = db_name if rel_path == '.' else os.path.join(rel_path, db_name)

        databases.append({
            'name': display_name,
            'path': db_path,
            'type': db_type
        })

    return databases


def delete_blast_database(db_path: str):
    """Delete a BLAST database (all index files and metadata)."""
    try:
        base = db_path
        if not os.path.isabs(base):
            base = os.path.join(config.DATABASES_DIR, db_path)
        base = os.path.abspath(base)

        # Safety: only allow deletion inside DATABASES_DIR
        allowed_root = os.path.abspath(config.DATABASES_DIR)
        if not base.startswith(allowed_root):
            return False, 'Access denied: outside database directory'

        exts = ['.nin', '.nhr', '.nsq', '.pin', '.phr', '.psq', '.pog', '.pog.idx', '.ndb', '.not', '.nto', '.ntf', '.nal', '.pal', '.meta.json']
        removed = []
        for ext in exts:
            candidate = base + ext
            if os.path.exists(candidate):
                os.remove(candidate)
                removed.append(os.path.basename(candidate))

        # Also remove mask files if present
        mask_file = base + '.msk'
        if os.path.exists(mask_file):
            os.remove(mask_file)
            removed.append(os.path.basename(mask_file))

        # Remove base file if plain fasta copy exists
        if os.path.exists(base):
            os.remove(base)
            removed.append(os.path.basename(base))

        if removed:
            return True, f"Removed: {', '.join(removed)}"
        return True, 'Database files not found (nothing to delete)'
    except Exception as e:
        logger.error(f"Failed to delete database {db_path}: {e}")
        return False, str(e)


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


def get_db_type(database):
    """
    Determine database type using metadata or file extensions.
    Returns 'nucleotide' or 'protein' (default nucleotide if unknown).
    """
    # Try metadata first
    metadata_file = database + '.meta.json'
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            db_type = meta.get('db_type')
            if db_type == 'nucl':
                return 'nucleotide'
            if db_type == 'prot':
                return 'protein'
            if db_type in ['nucleotide', 'protein']:
                return db_type
        except Exception as e:
            logger.warning(f"Failed to read db metadata for type: {e}")

    # Fallback to file extension detection
    nucleotide_exts = ['.nin', '.nhr', '.nsq']
    protein_exts = ['.pin', '.phr', '.psq']
    for ext in nucleotide_exts:
        if os.path.exists(f"{database}{ext}"):
            return 'nucleotide'
    for ext in protein_exts:
        if os.path.exists(f"{database}{ext}"):
            return 'protein'

    return 'nucleotide'


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

    # Use -parse_seqids so blastdbcmd can reliably extract records by subject IDs.
    command = (
        f'makeblastdb -in {shlex.quote(input_file)} '
        f'-dbtype {shlex.quote(db_type)} '
        f'-out {shlex.quote(db_path)} '
        f'-title {shlex.quote(title)} '
        f'-parse_seqids'
    )

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


def infer_sequence_type_robust(sequence: str) -> str:
    """
    Robust sequence type inference for BLAST dispatch.
    """
    if not sequence:
        return 'nucleotide'

    seq = re.sub(r'[^A-Za-z*]', '', sequence.upper())
    if not seq:
        return 'nucleotide'

    if any(ch in AA_ONLY_HINT_SET for ch in seq):
        return 'protein'

    nuc_ratio = sum(1 for ch in seq if ch in IUPAC_NUC_SET) / len(seq)
    return 'nucleotide' if nuc_ratio >= 0.9 else 'protein'


def infer_first_query_length(query_file: str) -> int:
    """
    Infer the length of the first query sequence in a FASTA file.
    Returns 0 when it cannot be inferred.
    """
    try:
        first_seq = []
        in_first = False
        with open(query_file, 'r', encoding='utf-8', errors='ignore') as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith('>'):
                    if in_first:
                        break
                    in_first = True
                    continue
                if in_first:
                    first_seq.append(re.sub(r'[^A-Za-z*]', '', line))
        if first_seq:
            return len(''.join(first_seq))
    except Exception:
        pass
    return 0


def is_program_compatible(program, query_type, db_type):
    """Check whether selected BLAST program matches query/database molecule types."""
    compat = {
        ('nucleotide', 'nucleotide'): {'blastn', 'tblastx'},
        ('protein', 'protein'): {'blastp'},
        ('nucleotide', 'protein'): {'blastx'},
        ('protein', 'nucleotide'): {'tblastn'},
    }
    return program in compat.get((query_type, db_type), {'blastn'})


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
        header = "qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen\tqstart\tqend\tsstart\tsend\tevalue\tbitscore\tqcovs\n"
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
              num_threads=None, max_hits=500, program=None, outfmt=None,
              min_identity=None, min_query_coverage=None,
              task=None, word_size=None, dust=None, seg=None,
              soft_masking=None, max_hsps=None, culling_limit=None,
              comp_based_stats=None, reward=None, penalty=None,
              gapopen=None, gapextend=None, db_type_override=None):
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

    # Auto-detect query type (robust heuristic to avoid protein->DNA misclassification)
    with open(query_file, 'r') as f:
        content = f.read(10000)
        lines = content.split('\n')
        seq_lines = [l for l in lines if not l.startswith('>')]
        sample_seq = ''.join(seq_lines)[:500]
        query_type = infer_sequence_type_robust(sample_seq)

    # Determine database type from metadata/extensions, optionally overridden by UI hint.
    db_type = get_db_type(database)
    if db_type_override in {'nucleotide', 'protein'}:
        db_type = db_type_override

    run_warnings = []

    # Normalize and select BLAST program
    program = program or None
    if program is None:
        program = select_blast_program(query_type, db_type)

    query_length = infer_first_query_length(query_file)

    # Validate program
    valid_programs = ['blastn', 'blastp', 'blastx', 'tblastn', 'tblastx']
    if program not in valid_programs:
        return False, f"Invalid BLAST program: {program}", None, None
    if not is_program_compatible(program, query_type, db_type):
        suggested_program = select_blast_program(query_type, db_type)
        msg = (
            f"Incompatible program '{program}' for query={query_type} vs db={db_type}. "
            f"Auto-switched to '{suggested_program}'."
        )
        logger.warning(msg)
        run_warnings.append(msg)
        program = suggested_program

    # Create result directory
    result_dir = create_result_dir('blast', 'search')

    # Output format codes
    if outfmt is None:
        format_codes = {
            'tsv': '6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore qcovs',
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
        min_identity = None if min_identity in [None, ''] else float(min_identity)
        min_query_coverage = None if min_query_coverage in [None, ''] else float(min_query_coverage)
        word_size = None if word_size in [None, ''] else int(word_size)
        max_hsps = None if max_hsps in [None, ''] else int(max_hsps)
        culling_limit = None if culling_limit in [None, ''] else int(culling_limit)
        comp_based_stats = None if comp_based_stats in [None, ''] else int(comp_based_stats)
        reward = None if reward in [None, ''] else int(reward)
        penalty = None if penalty in [None, ''] else int(penalty)
        gapopen = None if gapopen in [None, ''] else int(gapopen)
        gapextend = None if gapextend in [None, ''] else int(gapextend)
    except (ValueError, TypeError):
        return False, "Invalid numeric parameter", None, None
    if evalue <= 0:
        return False, "E-value must be > 0", None, None
    if num_threads < 1:
        return False, "num_threads must be >= 1", None, None
    if max_hits < 1:
        return False, "max_hits must be >= 1", None, None
    if min_identity is not None and not (0 <= min_identity <= 100):
        return False, "min_identity must be between 0 and 100", None, None
    if min_query_coverage is not None and not (0 <= min_query_coverage <= 100):
        return False, "min_query_coverage must be between 0 and 100", None, None
    if max_hsps is not None and max_hsps < 1:
        return False, "max_hsps must be >= 1", None, None
    if culling_limit is not None and culling_limit < 0:
        return False, "culling_limit must be >= 0", None, None
    if comp_based_stats is not None and comp_based_stats not in {0, 1, 2, 3}:
        return False, "comp_based_stats must be one of 0, 1, 2, 3", None, None
    if reward is not None and not (1 <= reward <= 100):
        return False, "reward must be between 1 and 100", None, None
    if penalty is not None and not (-100 <= penalty <= -1):
        return False, "penalty must be between -100 and -1", None, None
    if gapopen is not None and not (0 <= gapopen <= 100):
        return False, "gapopen must be between 0 and 100", None, None
    if gapextend is not None and not (0 <= gapextend <= 100):
        return False, "gapextend must be between 0 and 100", None, None

    if task:
        task = str(task).strip()
    if dust is not None:
        dust = str(dust).strip().lower()
        if dust not in {'yes', 'no'}:
            return False, "dust must be 'yes' or 'no'", None, None
    if seg is not None:
        seg = str(seg).strip().lower()
        if seg not in {'yes', 'no'}:
            return False, "seg must be 'yes' or 'no'", None, None
    if soft_masking is not None:
        if isinstance(soft_masking, str):
            soft_masking = soft_masking.strip().lower() in {'1', 'true', 'yes', 'on'}
        else:
            soft_masking = bool(soft_masking)

    blastn_tasks = {'blastn', 'blastn-short', 'dc-megablast', 'megablast'}
    if task:
        if program == 'blastn':
            if task not in blastn_tasks:
                return False, f"Invalid blastn task: {task}", None, None
        else:
            msg = f"Ignoring task={task} for program={program}"
            logger.warning(msg)
            run_warnings.append(msg)
            task = None
    elif program == 'blastn' and query_length and query_length <= 50:
        # For short nucleotide queries, blastn-short is generally more appropriate.
        task = 'blastn-short'
        run_warnings.append(
            f"Detected short nucleotide query ({query_length} bp); auto-set task=blastn-short."
        )

    nucleotide_programs = {'blastn', 'tblastx'}
    protein_programs = {'blastp', 'blastx', 'tblastn'}
    if dust is not None and program not in nucleotide_programs:
        msg = f"Ignoring dust={dust} for program={program}"
        logger.warning(msg)
        run_warnings.append(msg)
        dust = None
    if seg is not None and program not in protein_programs:
        msg = f"Ignoring seg={seg} for program={program}"
        logger.warning(msg)
        run_warnings.append(msg)
        seg = None
    if comp_based_stats is not None and program not in protein_programs:
        msg = f"Ignoring comp_based_stats={comp_based_stats} for program={program}"
        logger.warning(msg)
        run_warnings.append(msg)
        comp_based_stats = None
    if (reward is not None or penalty is not None) and program != 'blastn':
        msg = f"Ignoring reward/penalty for program={program}"
        logger.warning(msg)
        run_warnings.append(msg)
        reward = None
        penalty = None
    if (gapopen is not None or gapextend is not None) and program == 'tblastx':
        msg = "Ignoring gapopen/gapextend for program=tblastx because tblastx is ungapped."
        logger.warning(msg)
        run_warnings.append(msg)
        gapopen = None
        gapextend = None

    scoring_ok, scoring_message, normalized_scoring, scoring_warnings = normalize_blast_scoring_options(
        program=program,
        task=task,
        word_size=word_size,
        reward=reward,
        penalty=penalty,
    )
    if not scoring_ok:
        return False, scoring_message, None, None
    if scoring_warnings:
        run_warnings.extend(scoring_warnings)
    word_size = normalized_scoring['word_size']
    reward = normalized_scoring['reward']
    penalty = normalized_scoring['penalty']

    command = (
        f'{program} -query {shlex.quote(query_file)} -db {shlex.quote(database)} '
        f'-out {shlex.quote(output_file)} -outfmt {shlex.quote(outfmt)} '
        f'-evalue {evalue} -num_threads {num_threads} -max_target_seqs {max_hits}'
    )
    if task:
        command += f' -task {shlex.quote(task)}'
    if word_size is not None:
        command += f' -word_size {word_size}'
    if dust is not None:
        command += f' -dust {dust}'
    if seg is not None:
        command += f' -seg {seg}'
    if soft_masking is not None:
        command += f' -soft_masking {"true" if soft_masking else "false"}'
    if max_hsps is not None:
        command += f' -max_hsps {max_hsps}'
    if culling_limit is not None:
        command += f' -culling_limit {culling_limit}'
    if comp_based_stats is not None:
        command += f' -comp_based_stats {comp_based_stats}'
    if reward is not None:
        command += f' -reward {reward}'
    if penalty is not None:
        command += f' -penalty {penalty}'
    if gapopen is not None:
        command += f' -gapopen {gapopen}'
    if gapextend is not None:
        command += f' -gapextend {gapextend}'

    # Full command for display
    if config.USE_CONDA and config.CONDA_ENV:
        full_command = f"conda run -n {config.CONDA_ENV} {command}"
    else:
        full_command = command

    # Save parameters
    params = {
        'query_file': query_file,
        'database': database,
        'query_type': query_type,
        'db_type': db_type,
        'program': program,
        'evalue': evalue,
        'num_threads': num_threads,
        'max_hits': max_hits,
        'min_identity': min_identity,
        'min_query_coverage': min_query_coverage,
        'output_format': output_format,
        'query_length': query_length,
        'task': task,
        'word_size': word_size,
        'dust': dust,
        'seg': seg,
        'soft_masking': soft_masking,
        'max_hsps': max_hsps,
        'culling_limit': culling_limit,
        'comp_based_stats': comp_based_stats,
        'reward': reward,
        'penalty': penalty,
        'gapopen': gapopen,
        'gapextend': gapextend,
        'run_warnings': run_warnings,
        'timestamp': datetime.now().isoformat()
    }
    save_params(result_dir, params)

    success, stdout, stderr = run_conda_command(command)

    if success:
        # Add header to TSV output files
        add_tsv_header(output_file, output_format)
        logger.info(f"BLAST search completed: {output_file}")
        return True, result_dir, {
            'main': output_file,
            'query_type': query_type,
            'query_length': query_length,
            'db_type': db_type,
            'program': program,
            'meta': {
                'run_warnings': run_warnings
            }
        }, full_command
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

    # Sanitize hit IDs - allow common accession delimiters while still blocking whitespace/shell chars.
    sanitized_ids = []
    seen_ids = set()
    for hit_id in hit_ids:
        if re.match(r'^[A-Za-z0-9._|:-]+$', str(hit_id or '')):
            normalized_id = str(hit_id).strip()
            if normalized_id and normalized_id not in seen_ids:
                seen_ids.add(normalized_id)
                sanitized_ids.append(normalized_id)
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
    
    # Fallback 1: try to extract from source FASTA
    logger.info("blastdbcmd failed, attempting fallback extraction from source FASTA")
    source_fasta = get_source_fasta(database)
    
    if source_fasta:
        logger.info(f"Found source FASTA: {source_fasta}")
        fallback_success, extracted_count = extract_from_fasta(source_fasta, sanitized_ids, output_file)
        
        if fallback_success and extracted_count > 0:
            logger.info(f"Fallback extraction succeeded: {extracted_count} sequences")
            return True, f"Extracted {extracted_count} sequences (from source FASTA)"

        logger.error("Fallback extraction failed")
        return False, "blastdbcmd failed and fallback extraction found no matching sequences"

    # Fallback 2: dump DB entries then fuzzy-extract from dumped FASTA.
    # This supports legacy DBs created without -parse_seqids metadata.
    logger.info("No source FASTA metadata found; attempting blastdbcmd -entry all fallback")
    dump_file = output_file + '.dbdump.fa'
    try:
        dump_command = (
            f'blastdbcmd -db {shlex.quote(database)} '
            f'-entry all -out {shlex.quote(dump_file)}'
        )
        dump_success, _, dump_stderr = run_conda_command(dump_command)
        if dump_success and os.path.exists(dump_file) and os.path.getsize(dump_file) > 0:
            fallback_success, extracted_count = extract_from_fasta(dump_file, sanitized_ids, output_file)
            if fallback_success and extracted_count > 0:
                logger.info(f"Fallback extraction from DB dump succeeded: {extracted_count} sequences")
                return True, f"Extracted {extracted_count} sequences (from DB dump fallback)"
            return False, "No matching sequences found in DB dump fallback"

        logger.error(f"DB dump fallback failed: {dump_stderr}")
        return False, (
            f"Sequence extraction failed: {stderr}. "
            f"DB has no accession index; recreate database with -parse_seqids for reliable ID extraction."
        )
    finally:
        if os.path.exists(dump_file):
            try:
                os.remove(dump_file)
            except Exception:
                pass


def parse_blast_tsv(filepath, format_type='standard'):
    """
    Parse BLAST TSV output file.
    Returns list of hit dicts with identity classification.
    
    Args:
        filepath: Path to TSV file
        format_type: 'standard' or 'detailed'
    """
    hits = []
    
    # Define headers based on format
    if format_type == 'detailed':
        headers = ['qseqid', 'sseqid', 'pident', 'length', 'mismatch', 'gapopen',
                   'qstart', 'qend', 'sstart', 'send', 'evalue', 'bitscore',
                   'qlen', 'slen', 'qcovs', 'stitle']
    else:
        headers = ['qseqid', 'sseqid', 'pident', 'length', 'mismatch', 'gapopen',
                   'qstart', 'qend', 'sstart', 'send', 'evalue', 'bitscore', 'qcovs']
    
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
            
            # Skip header row if present
            if parts and parts[0] in header_fields:
                first_fields = set(parts[:min(len(parts), 6)])
                if first_fields <= header_fields.union({'qlen', 'slen', 'qcovs', 'stitle'}):
                    continue

            hit = {}
            for i, header in enumerate(headers):
                if i < len(parts):
                    hit[header] = parts[i]
            
            # Add identity classification
            try:
                pident = float(hit.get('pident', 0))
                if pident >= 90:
                    hit['identity_level'] = 'HIGH_ID'
                    hit['identity_class'] = 'high'
                elif pident >= 70:
                    hit['identity_level'] = 'MEDIUM_ID'
                    hit['identity_class'] = 'medium'
                else:
                    hit['identity_level'] = 'LOW_ID'
                    hit['identity_class'] = 'low'
            except (ValueError, TypeError):
                hit['identity_level'] = 'UNKNOWN'
                hit['identity_class'] = 'unknown'
            
            hits.append(hit)

    return hits


def generate_identity_summary(hits):
    """
    Generate identity level summary from BLAST hits.
    Returns dict with counts and percentages.
    """
    if not hits:
        return {
            'total': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'high_pct': 0,
            'medium_pct': 0,
            'low_pct': 0
        }
    
    total = len(hits)
    high = sum(1 for h in hits if h.get('identity_class') == 'high')
    medium = sum(1 for h in hits if h.get('identity_class') == 'medium')
    low = sum(1 for h in hits if h.get('identity_class') == 'low')
    
    return {
        'total': total,
        'high': high,
        'medium': medium,
        'low': low,
        'high_pct': round(high / total * 100, 1) if total > 0 else 0,
        'medium_pct': round(medium / total * 100, 1) if total > 0 else 0,
        'low_pct': round(low / total * 100, 1) if total > 0 else 0
    }
