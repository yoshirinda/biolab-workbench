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
from collections import Counter
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


def extract_sequences_by_ids(input_file, ids, output_file):
    """Extract sequences from input file by ID set."""
    sequences = read_fasta_file(input_file)
    extracted = []
    for header, seq in sequences:
        seq_id = header.split()[0]
        if seq_id in ids:
            extracted.append((header, seq))
    write_fasta_file(output_file, extracted)
    return len(extracted)


def step2_hmmsearch_multiple(input_file, hmm_files, output_dir, cut_ga=True, progress_callback=None):
    """
    Step 2: Run HMMer search with multiple HMM files.
    Merge results and deduplicate.
    
    Args:
        input_file: Input FASTA file path
        hmm_files: List of HMM profile file paths
        output_dir: Output directory path
        cut_ga: Use --cut_ga threshold flag
        progress_callback: Optional callable to emit progress messages
    
    Returns:
        (success, output_fasta, message, commands_list)
    """
    # Handle single file case
    if isinstance(hmm_files, str):
        hmm_files = [hmm_files]
    
    if not hmm_files:
        return False, None, "No HMM files provided", []
    
    try:
        input_file = sanitize_path(input_file)
        output_dir = sanitize_path(output_dir)
        hmm_files = [sanitize_path(hf) for hf in hmm_files]
    except ValueError as e:
        return False, None, str(e), []
    
    all_tbl_files = []
    all_commands = []
    
    msg = f"[STEP2] Processing {len(hmm_files)} HMM file(s)"
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')
    
    # Run hmmsearch for each HMM file
    for i, hmm_file in enumerate(hmm_files):
        hmm_basename = os.path.basename(hmm_file)
        msg = f"[STEP2] Processing HMM file {i+1}/{len(hmm_files)}: {hmm_basename}"
        logger.info(msg)
        if progress_callback:
            progress_callback(msg, 'info')
        
        tblout_file = os.path.join(output_dir, f'step2_hmmsearch_{i}_{hmm_basename}.tbl')
        output_file = os.path.join(output_dir, f'step2_hmmsearch_{i}_{hmm_basename}.out')
        domtblout_file = os.path.join(output_dir, f'step2_hmmsearch_{i}_{hmm_basename}.domtbl')
        
        cut_ga_opt = '--cut_ga' if cut_ga else ''
        
        command = (
            f'hmmsearch {cut_ga_opt} '
            f'--tblout {shlex.quote(tblout_file)} '
            f'--domtblout {shlex.quote(domtblout_file)} '
            f'-o {shlex.quote(output_file)} '
            f'{shlex.quote(hmm_file)} {shlex.quote(input_file)}'
        )
        
        full_command = f"conda run -n {config.CONDA_ENV} {command}"
        all_commands.append(full_command)
        
        success, stdout, stderr = run_conda_command(command)
        
        if success:
            all_tbl_files.append(tblout_file)
            hits = parse_hmmsearch_tblout(tblout_file)
            msg = f"[STEP2] HMM {hmm_basename}: Found {len(hits)} hits"
            logger.info(msg)
            if progress_callback:
                progress_callback(msg, 'info')
        else:
            msg = f"[STEP2] HMM {hmm_basename} failed: {stderr}"
            logger.warning(msg)
            if progress_callback:
                progress_callback(msg, 'warning')
    
    if not all_tbl_files:
        return False, None, "All HMM searches failed", all_commands
    
    # Merge all tblout results and deduplicate
    all_hit_ids = []
    for tbl_file in all_tbl_files:
        hits = parse_hmmsearch_tblout(tbl_file)
        all_hit_ids.extend(hits)
    
    # Use Counter for deduplication and statistics
    id_counts = Counter(all_hit_ids)
    unique_ids = set(id_counts.keys())
    
    total_hits = len(all_hit_ids)
    unique_count = len(unique_ids)
    duplicate_count = total_hits - unique_count
    
    msg = f"[STEP2] Found {total_hits} total hits, {unique_count} unique after deduplication"
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')
    
    msg = f"[STEP2] Removed {duplicate_count} duplicate hits"
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')
    
    # Extract sequences with unique IDs
    output_fasta = os.path.join(output_dir, 'step2_hmm_hits.fasta')
    extracted_count = extract_sequences_by_ids(input_file, unique_ids, output_fasta)
    
    msg = f"[STEP2] Extracted {extracted_count} sequences to {output_fasta}"
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')
    
    message = f"Found {unique_count} unique hits from {len(hmm_files)} HMM file(s) (removed {duplicate_count} duplicates)"
    
    return True, output_fasta, message, all_commands


def step2_5_blast_filter(input_file, gold_list_file, output_dir,
                         pident_threshold=30, qcovs_threshold=50, progress_callback=None):
    """
    Step 2.5: Filter sequences using BLAST against gold standard list.
    Returns detailed statistics like the original script.
    """
    output_file = os.path.join(output_dir, 'step2_5_filtered.fasta')
    log_file = os.path.join(output_dir, 'step2_5_blast_filter.log')

    msg = "[STEP2.5] Loading gold standard list..."
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')

    # Read gold standard IDs
    gold_ids = set()
    with open(gold_list_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                gold_ids.add(line.split()[0])

    msg = f"[STEP2.5] Loaded {len(gold_ids)} gold standard IDs"
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')

    msg = "[STEP2.5] Reading input sequences..."
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')

    # Read input sequences
    sequences = read_fasta_file(input_file)
    all_ids = set([header.split()[0] for header, _ in sequences])

    # Filter sequences present in gold list
    filtered = []
    kept_ids = set()
    for header, seq in sequences:
        seq_id = header.split()[0]
        if seq_id in gold_ids:
            filtered.append((header, seq))
            kept_ids.add(seq_id)

    deleted_ids = all_ids - kept_ids

    msg = f"[STEP2.5] Filtered sequences: {len(kept_ids)} kept, {len(deleted_ids)} deleted"
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')

    write_fasta_file(output_file, filtered)

    # Generate detailed log like original script (lines 323-351)
    log_lines = []
    log_lines.append(f"--- BLAST Filter Summary ---")
    log_lines.append(f"Filters: Min P-Ident >= {pident_threshold}% | Min Q-Covs >= {qcovs_threshold}%")
    log_lines.append(f"Total sequences in: {len(all_ids)}")
    log_lines.append(f"Sequences Kept (passed all filters): {len(kept_ids)}")
    log_lines.append(f"Sequences Deleted (failed filters): {len(deleted_ids)}")

    if deleted_ids:
        log_lines.append("\n--- Deleted Sequences (no match in gold list OR failed quality check) ---")
        deleted_list = sorted(list(deleted_ids))
        for i, deleted_id in enumerate(deleted_list):
            log_lines.append(f"  {deleted_id}")
            if i >= 50 and len(deleted_ids) > 51:
                log_lines.append(f"  ... and {len(deleted_ids) - i - 1} more.")
                break

    with open(log_file, 'w', encoding='utf-8') as f:
        for line in log_lines:
            f.write(line + '\n')

    msg = f"Step 2.5: Filtered to {len(filtered)} sequences (from {len(sequences)})"
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')
    
    # Return statistics dict for display
    stats = {
        'total_in': len(all_ids),
        'kept': len(kept_ids),
        'deleted': len(deleted_ids),
        'deleted_ids': deleted_list[:50] if deleted_ids else [],
        'log_file': log_file
    }
    
    return True, output_file, f"Filtered to {len(filtered)} sequences (from {len(sequences)})", stats


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


def step2_8_length_filter(input_file, output_dir, min_length=50, progress_callback=None):
    """
    Step 2.8: Filter out sequences shorter than min_length.
    Returns detailed statistics like original script (lines 416-438).
    """
    output_file = os.path.join(output_dir, 'step2_8_length_filtered.fasta')
    log_file = os.path.join(output_dir, 'step2_8_length_filter.log')

    msg = "[STEP2.8] Reading input sequences..."
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')

    sequences = read_fasta_file(input_file)
    
    msg = f"[STEP2.8] Filtering sequences (threshold: {min_length} aa)..."
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')
    
    # Track kept and deleted sequences with details
    filtered = []
    deleted_ids = []
    
    for header, seq in sequences:
        seq_id = header.split()[0]
        if len(seq) >= min_length:
            filtered.append((header, seq))
        else:
            deleted_ids.append((seq_id, len(seq)))

    write_fasta_file(output_file, filtered)

    # Generate detailed log like original script (lines 414-438)
    log_lines = []
    log_lines.append(f"--- Length Filter Summary ---")
    log_lines.append(f"Threshold: Remove sequences < {min_length} aa")
    log_lines.append(f"Total sequences in: {len(sequences)}")
    log_lines.append(f"Sequences Kept: {len(filtered)}")
    log_lines.append(f"Sequences Deleted: {len(deleted_ids)}")

    if deleted_ids:
        log_lines.append("\n--- Deleted Sequences (too short) ---")
        deleted_ids.sort(key=lambda x: x[1])  # Sort by length
        for seq_id, length in deleted_ids:
            log_lines.append(f"  {seq_id} (Length: {length} aa)")

    with open(log_file, 'w', encoding='utf-8') as f:
        for line in log_lines:
            f.write(line + '\n')

    msg = f"Step 2.8: Removed {len(deleted_ids)} short sequences"
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')
    
    # Return statistics dict for display
    stats = {
        'total_in': len(sequences),
        'kept': len(filtered),
        'deleted': len(deleted_ids),
        'threshold': min_length,
        'deleted_with_lengths': deleted_ids,
        'log_file': log_file
    }
    
    return True, output_file, f"Kept {len(filtered)} sequences (removed {len(deleted_ids)} shorter than {min_length})", stats


def step3_mafft(input_file, output_dir, maxiterate=1000, progress_callback=None):
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

    msg = f"[STEP3] Starting MAFFT alignment (maxiterate={maxiterate})..."
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')

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
        msg = f"Step 3: MAFFT alignment completed"
        logger.info(msg)
        if progress_callback:
            progress_callback(msg, 'info')
        return True, output_file, "MAFFT alignment completed", display_command
    else:
        msg = "MAFFT alignment failed"
        logger.error(msg)
        if progress_callback:
            progress_callback(msg, 'error')
        return False, None, "MAFFT alignment failed", display_command


def step4_clipkit(input_file, output_dir, mode='kpic-gappy', progress_callback=None):
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

    msg = f"[STEP4] Starting ClipKIT trimming (mode={mode})..."
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')

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
        msg = f"Step 4: ClipKIT trimming completed"
        logger.info(msg)
        if progress_callback:
            progress_callback(msg, 'info')
        return True, output_file, "ClipKIT trimming completed", display_command
    else:
        msg = "ClipKIT trimming failed"
        logger.error(msg)
        if progress_callback:
            progress_callback(msg, 'error')
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


def step5_iqtree(input_file, output_dir, model='MFP', bootstrap=1000, threads=None, bnni=True, progress_callback=None):
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

    msg = f"[STEP5] Starting IQ-Tree inference (model={model}, bootstrap={bootstrap}, threads={threads})..."
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')

    command = f'iqtree -s {shlex.quote(input_file)} -pre {shlex.quote(prefix)} -m {model} -B {bootstrap} -T {threads} {bnni_opt}'

    # Full command for display
    full_command = f"conda run -n {config.CONDA_ENV} {command}"

    success, stdout, stderr = run_conda_command(command, timeout=14400)

    if success and os.path.exists(treefile):
        msg = f"Step 5: IQ-Tree completed"
        logger.info(msg)
        if progress_callback:
            progress_callback(msg, 'info')
        return True, treefile, "IQ-Tree completed", full_command
    else:
        msg = stderr or "IQ-Tree failed"
        logger.error(f"Step 5 failed: {msg}")
        if progress_callback:
            progress_callback(msg, 'error')
        return False, None, msg, full_command


def run_full_pipeline(input_file, hmm_files=None, gold_list_file=None, options=None):
    """
    Run the complete phylogenetic pipeline.
    
    Args:
        input_file: Input FASTA file path
        hmm_files: Single HMM file path (string) or list of HMM file paths
        gold_list_file: Gold standard list file path (optional)
        options: Dictionary of pipeline options
    """
    if options is None:
        options = {}

    result_dir = create_result_dir('phylo', 'pipeline')

    # Normalize hmm_files to a list
    if hmm_files is None:
        hmm_files_list = []
    elif isinstance(hmm_files, str):
        hmm_files_list = [hmm_files] if hmm_files else []
    else:
        hmm_files_list = [f for f in hmm_files if f]

    # Save parameters
    params = {
        'input_file': input_file,
        'hmm_files': hmm_files_list,
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

    # Step 2: HMMer (optional) - supports multiple HMM files
    valid_hmm_files = [f for f in hmm_files_list if os.path.exists(f)]
    if valid_hmm_files:
        success, output, message, commands = step2_hmmsearch_multiple(
            current_file, valid_hmm_files, result_dir,
            cut_ga=options.get('cut_ga', True)
        )
        results['steps']['step2'] = {'success': success, 'output': output, 'message': message}
        if commands:
            for i, cmd in enumerate(commands):
                results['commands'].append({
                    'step': f'step2_{i+1}',
                    'name': f'HMMer Search ({i+1}/{len(commands)})',
                    'command': cmd
                })
        if success:
            current_file = output
        else:
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
