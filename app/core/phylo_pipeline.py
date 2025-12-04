"""
Phylogenetic pipeline for BioLab Workbench.
Based on blast-phylo_pipeline_gui.py
"""
import os
import subprocess
import json
import shlex
import re
import statistics
from datetime import datetime
import config
from app.utils.logger import get_tools_logger
from app.utils.file_utils import create_result_dir, save_params, read_fasta_file, write_fasta_file
from app.core.sequence_utils import clean_fasta_headers

logger = get_tools_logger()


def sanitize_path(path):
    """Sanitize file path to prevent command injection."""
    if not path:
        return path
    # Only allow alphanumeric, underscore, hyphen, dot, forward slash
    if not re.match(r'^[\w\-./]+$', path):
        raise ValueError(f"Invalid characters in path: {path}")
    # Prevent directory traversal
    if '..' in path:
        raise ValueError(f"Directory traversal not allowed: {path}")
    return path


def run_conda_command(command, timeout=7200):
    """Run a command in the conda environment."""
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


def step1_clean_fasta(input_file, output_dir):
    """
    Step 1: Clean FASTA headers - keep only first space-separated ID.
    """
    output_file = os.path.join(output_dir, 'step1_cleaned.fasta')
    log_file = os.path.join(output_dir, 'step1.log')

    try:
        sequences = read_fasta_file(input_file)
        cleaned = []
        for header, seq in sequences:
            clean_id = header.split()[0]
            cleaned.append((clean_id, seq))

        write_fasta_file(output_file, cleaned)

        with open(log_file, 'w') as f:
            f.write(f"Cleaned {len(sequences)} sequences\n")
            f.write(f"Input: {input_file}\n")
            f.write(f"Output: {output_file}\n")

        logger.info(f"Step 1: Cleaned {len(sequences)} sequences")
        return True, output_file, f"Cleaned {len(sequences)} sequences"

    except Exception as e:
        logger.error(f"Step 1 failed: {str(e)}")
        return False, None, str(e)


def step2_hmmsearch(input_file, hmm_file, output_dir, cut_ga=True):
    """
    Step 2: Run HMMer search (hmmsearch).
    Returns (success, output, message, command).
    """
    try:
        input_file = sanitize_path(input_file)
        hmm_file = sanitize_path(hmm_file)
        output_dir = sanitize_path(output_dir)
    except ValueError as e:
        return False, None, str(e), None

    output_file = os.path.join(output_dir, 'step2_hmmsearch.out')
    tblout_file = os.path.join(output_dir, 'step2_hmmsearch.tbl')
    domtblout_file = os.path.join(output_dir, 'step2_hmmsearch.domtbl')

    cut_ga_opt = '--cut_ga' if cut_ga else ''

    command = (
        f'hmmsearch {cut_ga_opt} '
        f'--tblout {shlex.quote(tblout_file)} '
        f'--domtblout {shlex.quote(domtblout_file)} '
        f'-o {shlex.quote(output_file)} '
        f'{shlex.quote(hmm_file)} {shlex.quote(input_file)}'
    )

    # Full command for display
    full_command = f"conda run -n {config.CONDA_ENV} {command}"

    success, stdout, stderr = run_conda_command(command)

    if success:
        # Parse hits from tblout
        hits = parse_hmmsearch_tblout(tblout_file)
        logger.info(f"Step 2: Found {len(hits)} HMM hits")
        return True, tblout_file, f"Found {len(hits)} HMM hits", full_command
    else:
        logger.error(f"Step 2 failed: {stderr}")
        return False, None, stderr, full_command


def parse_hmmsearch_tblout(tblout_file):
    """Parse hmmsearch tblout file to get hit IDs."""
    hits = []
    with open(tblout_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.split()
            if parts:
                hits.append(parts[0])
    return hits


def step2_5_blast_filter(input_file, gold_list_file, output_dir,
                         pident_threshold=30, qcovs_threshold=50):
    """
    Step 2.5: Filter sequences using BLAST against gold standard list.
    """
    output_file = os.path.join(output_dir, 'step2_5_filtered.fasta')

    # Read gold standard IDs
    gold_ids = set()
    with open(gold_list_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                gold_ids.add(line.split()[0])

    # Read input sequences
    sequences = read_fasta_file(input_file)

    # Filter sequences present in gold list
    filtered = []
    for header, seq in sequences:
        seq_id = header.split()[0]
        if seq_id in gold_ids:
            filtered.append((header, seq))

    write_fasta_file(output_file, filtered)

    logger.info(f"Step 2.5: Filtered to {len(filtered)} sequences")
    return True, output_file, f"Filtered to {len(filtered)} sequences (from {len(sequences)})"


def step2_7_length_stats(input_file, output_dir):
    """
    Step 2.7: Calculate sequence length statistics.
    """
    stats_file = os.path.join(output_dir, 'step2_7_length_stats.json')

    sequences = read_fasta_file(input_file)
    lengths = [len(seq) for _, seq in sequences]

    if not lengths:
        return False, None, "No sequences found"

    stats = {
        'count': len(lengths),
        'mean': statistics.mean(lengths),
        'median': statistics.median(lengths),
        'stdev': statistics.stdev(lengths) if len(lengths) > 1 else 0,
        'min': min(lengths),
        'max': max(lengths),
    }

    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)

    logger.info(f"Step 2.7: Calculated stats for {len(lengths)} sequences")
    return True, stats_file, stats


def step2_8_length_filter(input_file, output_dir, min_length=50):
    """
    Step 2.8: Filter out sequences shorter than min_length.
    """
    output_file = os.path.join(output_dir, 'step2_8_length_filtered.fasta')

    sequences = read_fasta_file(input_file)
    filtered = [(h, s) for h, s in sequences if len(s) >= min_length]

    write_fasta_file(output_file, filtered)

    removed = len(sequences) - len(filtered)
    logger.info(f"Step 2.8: Removed {removed} short sequences")
    return True, output_file, f"Kept {len(filtered)} sequences (removed {removed} shorter than {min_length})"


def step3_mafft(input_file, output_dir, maxiterate=1000):
    """
    Step 3: Run MAFFT multiple sequence alignment.
    Returns (success, output, message, command).
    """
    try:
        input_file = sanitize_path(input_file)
        output_dir = sanitize_path(output_dir)
        maxiterate = int(maxiterate)
    except (ValueError, TypeError) as e:
        return False, None, str(e), None

    output_file = os.path.join(output_dir, 'step3_alignment.fasta')
    log_file = os.path.join(output_dir, 'step3_mafft.log')

    # Use shlex.quote for safe command construction
    command = f'mafft --maxiterate {maxiterate} {shlex.quote(input_file)}'

    # Full command for display
    display_command = f"conda run -n {config.CONDA_ENV} {command} > {output_file} 2> {log_file}"

    full_command = f"conda run -n {shlex.quote(config.CONDA_ENV)} {command} > {shlex.quote(output_file)} 2> {shlex.quote(log_file)}"

    try:
        result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=7200)
        success = result.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 0
    except Exception as e:
        logger.error(f"Step 3 failed: {str(e)}")
        return False, None, str(e), display_command

    if success:
        logger.info(f"Step 3: MAFFT alignment completed")
        return True, output_file, "MAFFT alignment completed", display_command
    else:
        return False, None, "MAFFT alignment failed", display_command


def step4_clipkit(input_file, output_dir, mode='kpic-gappy'):
    """
    Step 4: Trim alignment with ClipKIT.
    mode: kpic-gappy, gappy, kpic
    Returns (success, output, message, command).
    """
    try:
        input_file = sanitize_path(input_file)
        output_dir = sanitize_path(output_dir)
    except ValueError as e:
        return False, None, str(e), None

    # Validate mode
    valid_modes = ['kpic-gappy', 'gappy', 'kpic']
    if mode not in valid_modes:
        return False, None, f"Invalid mode: {mode}", None

    output_file = os.path.join(output_dir, 'step4_trimmed.fasta')
    log_file = os.path.join(output_dir, 'step4_clipkit.log')

    command = f'clipkit {shlex.quote(input_file)} -o {shlex.quote(output_file)} -m {mode} -l'

    # Full command for display
    display_command = f"conda run -n {config.CONDA_ENV} {command}"

    full_command = f"conda run -n {shlex.quote(config.CONDA_ENV)} {command} 2> {shlex.quote(log_file)}"

    try:
        result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=3600)
        success = result.returncode == 0 and os.path.exists(output_file)
    except Exception as e:
        logger.error(f"Step 4 failed: {str(e)}")
        return False, None, str(e), display_command

    if success:
        logger.info(f"Step 4: ClipKIT trimming completed")
        return True, output_file, "ClipKIT trimming completed", display_command
    else:
        return False, None, "ClipKIT trimming failed", display_command


def step4_5_check_sites(clipkit_log_file):
    """
    Step 4.5: Check ClipKIT log for trimmed sites information.
    """
    if not os.path.exists(clipkit_log_file):
        return False, None, "ClipKIT log file not found"

    try:
        with open(clipkit_log_file, 'r') as f:
            content = f.read()

        # Parse log for site information
        info = {
            'log_content': content,
            'sites_kept': None,
            'sites_trimmed': None
        }

        # Extract statistics if available
        for line in content.split('\n'):
            if 'kept' in line.lower():
                info['sites_kept'] = line
            if 'trimmed' in line.lower():
                info['sites_trimmed'] = line

        return True, info, "ClipKIT log parsed"

    except Exception as e:
        return False, None, str(e)


def step5_iqtree(input_file, output_dir, model='MFP', bootstrap=1000, threads=None, bnni=True):
    """
    Step 5: Build phylogenetic tree with IQ-Tree.
    Returns (success, output, message, command).
    """
    try:
        input_file = sanitize_path(input_file)
        output_dir = sanitize_path(output_dir)
        bootstrap = int(bootstrap)
        if threads is not None:
            threads = int(threads)
    except (ValueError, TypeError) as e:
        return False, None, str(e), None

    # Validate model - only allow alphanumeric and common model chars
    if not re.match(r'^[A-Za-z0-9+\-*]+$', model):
        return False, None, f"Invalid model: {model}", None

    prefix = os.path.join(output_dir, 'step5_tree')
    treefile = prefix + '.treefile'

    if threads is None:
        threads = config.DEFAULT_THREADS

    bnni_opt = '-bnni' if bnni else ''

    command = f'iqtree -s {shlex.quote(input_file)} -pre {shlex.quote(prefix)} -m {model} -B {bootstrap} -T {threads} {bnni_opt}'

    # Full command for display
    full_command = f"conda run -n {config.CONDA_ENV} {command}"

    success, stdout, stderr = run_conda_command(command, timeout=14400)

    if success and os.path.exists(treefile):
        logger.info(f"Step 5: IQ-Tree completed")
        return True, treefile, "IQ-Tree completed", full_command
    else:
        logger.error(f"Step 5 failed: {stderr}")
        return False, None, stderr or "IQ-Tree failed", full_command


def run_full_pipeline(input_file, hmm_file=None, gold_list_file=None, options=None):
    """
    Run the complete phylogenetic pipeline.
    """
    if options is None:
        options = {}

    result_dir = create_result_dir('phylo', 'pipeline')

    # Save parameters
    params = {
        'input_file': input_file,
        'hmm_file': hmm_file,
        'gold_list_file': gold_list_file,
        'options': options,
        'timestamp': datetime.now().isoformat()
    }
    save_params(result_dir, params)

    results = {
        'result_dir': result_dir,
        'steps': {},
        'commands': []
    }

    current_file = input_file

    # Step 1: Clean FASTA
    success, output, message = step1_clean_fasta(current_file, result_dir)
    results['steps']['step1'] = {'success': success, 'output': output, 'message': message}
    if not success:
        return False, results
    current_file = output

    # Step 2: HMMer (optional)
    if hmm_file and os.path.exists(hmm_file):
        success, output, message, command = step2_hmmsearch(
            current_file, hmm_file, result_dir,
            cut_ga=options.get('cut_ga', True)
        )
        results['steps']['step2'] = {'success': success, 'output': output, 'message': message, 'command': command}
        if command:
            results['commands'].append({'step': 'step2', 'name': 'HMMer Search', 'command': command})
        if not success:
            return False, results

    # Step 2.5: BLAST filter (optional)
    if gold_list_file and os.path.exists(gold_list_file):
        success, output, message = step2_5_blast_filter(
            current_file, gold_list_file, result_dir,
            pident_threshold=options.get('pident', 30),
            qcovs_threshold=options.get('qcovs', 50)
        )
        results['steps']['step2_5'] = {'success': success, 'output': output, 'message': message}
        if success:
            current_file = output

    # Step 2.7: Length stats
    success, output, message = step2_7_length_stats(current_file, result_dir)
    results['steps']['step2_7'] = {'success': success, 'output': output, 'message': message}

    # Step 2.8: Length filter
    min_length = options.get('min_length', 50)
    success, output, message = step2_8_length_filter(current_file, result_dir, min_length)
    results['steps']['step2_8'] = {'success': success, 'output': output, 'message': message}
    if success:
        current_file = output

    # Step 3: MAFFT
    success, output, message, command = step3_mafft(
        current_file, result_dir,
        maxiterate=options.get('maxiterate', 1000)
    )
    results['steps']['step3'] = {'success': success, 'output': output, 'message': message, 'command': command}
    if command:
        results['commands'].append({'step': 'step3', 'name': 'MAFFT Alignment', 'command': command})
    if not success:
        return False, results
    current_file = output

    # Step 4: ClipKIT
    success, output, message, command = step4_clipkit(
        current_file, result_dir,
        mode=options.get('clipkit_mode', 'kpic-gappy')
    )
    results['steps']['step4'] = {'success': success, 'output': output, 'message': message, 'command': command}
    if command:
        results['commands'].append({'step': 'step4', 'name': 'ClipKIT Trim', 'command': command})
    if not success:
        return False, results
    current_file = output

    # Step 5: IQ-Tree
    success, output, message, command = step5_iqtree(
        current_file, result_dir,
        model=options.get('model', 'MFP'),
        bootstrap=options.get('bootstrap', 1000),
        threads=options.get('threads', config.DEFAULT_THREADS),
        bnni=options.get('bnni', True)
    )
    results['steps']['step5'] = {'success': success, 'output': output, 'message': message, 'command': command}
    if command:
        results['commands'].append({'step': 'step5', 'name': 'IQ-Tree', 'command': command})

    return success, results
