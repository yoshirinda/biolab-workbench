# Phylogenetic pipeline for BioLab Workbench.
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
from app.utils.path_utils import windows_to_wsl
from app.core.sequence_utils import clean_fasta_headers

logger = get_tools_logger()

def sanitize_path(path):
    if not path:
        return path
    # 放宽校验，允许括号和空格等常见字符
    if not re.match(r'^[\w\-./"\' :\\()]+$', path):
        raise ValueError(f"Invalid characters in path: {path}")
    if '..' in path.replace('\\', '/'):
        raise ValueError(f"Directory traversal not allowed: {path}")
    return path

def step0_clean_headers(input_file, output_dir):
    """
    Step 0: Clean FASTA headers using app.core.sequence_utils.clean_fasta_headers.
    """
    output_file = os.path.join(output_dir, 'step0_cleaned.fasta')
    try:
        sequences = read_fasta_file(input_file)
        cleaned_sequences, _ = clean_fasta_headers(sequences)
        write_fasta_file(output_file, cleaned_sequences)
        message = f"Cleaned {len(cleaned_sequences)} sequences."
        logger.info(f"Step 0: {message}")
        return True, output_file, message
    except Exception as e:
        logger.error(f"Step 0 failed: {str(e)}")
        return False, None, str(e)


BLAST_DB_EXTENSIONS = (".pin", ".psq", ".phr", ".nin", ".nsq", ".nhr")


def _resolve_blast_db_path(blast_db_path):
    """Validate and resolve a BLAST database base path, supporting Windows/WSL inputs."""
    if not blast_db_path or not str(blast_db_path).strip():
        raise ValueError("BLAST database path is required")

    normalized = windows_to_wsl(str(blast_db_path).strip())
    normalized = os.path.expanduser(normalized)
    normalized = os.path.normpath(normalized)

    base, ext = os.path.splitext(normalized)
    if ext in BLAST_DB_EXTENSIONS:
        normalized = base

    candidates = []
    if os.path.isabs(normalized):
        candidates.append(normalized)
    else:
        candidates.append(os.path.abspath(normalized))
        candidates.append(os.path.abspath(os.path.join(config.DATABASES_DIR, normalized)))

    seen = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.append(candidate)
        if any(os.path.exists(candidate + ext) for ext in BLAST_DB_EXTENSIONS):
            return candidate

    raise FileNotFoundError(f"BLAST database not found at: {blast_db_path}")


def run_conda_command(command, timeout=7200):
    """Run a command in the conda environment."""
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

def step2_hmmsearch_multiple(input_file, hmm_files, output_dir,
                             cut_ga=False, evalue=1e-5,
                             dom_evalue=None, threads=None):
    """
    Step 2: Run HMMer search with multiple HMM files.
    Merge results and deduplicate.
    
    Args:
        input_file: Input FASTA file path
        hmm_files: List of HMM profile file paths
        output_dir: Output directory path
        cut_ga: Use --cut_ga threshold flag
        evalue: E-value threshold
    
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

    # Verify HMM files exist before running
    missing = [hf for hf in hmm_files if not os.path.exists(hf)]
    if missing:
        return False, None, f"HMM file not found: {missing[0]}", []
    
    all_tbl_files = []
    all_commands = []
    
    logger.info(f"[STEP2] Processing {len(hmm_files)} HMM file(s)")
    
    # Run hmmsearch for each HMM file
    last_error = ''
    for i, hmm_file in enumerate(hmm_files):
        hmm_basename = os.path.basename(hmm_file)
        logger.info(f"[STEP2] Processing HMM file {i+1}/{len(hmm_files)}: {hmm_basename}")
        
        tblout_file = os.path.join(output_dir, f'step2_hmmsearch_{i}_{hmm_basename}.tbl')
        output_file = os.path.join(output_dir, f'step2_hmmsearch_{i}_{hmm_basename}.out')
        domtblout_file = os.path.join(output_dir, f'step2_hmmsearch_{i}_{hmm_basename}.domtbl')
        
        cut_ga_opt = '--cut_ga' if cut_ga else ''
        dom_opt = f'--domE {dom_evalue}' if dom_evalue not in (None, '') else ''
        cpu_opt = ''
        try:
            cpu_val = int(threads) if threads not in (None, '', False) else int(config.DEFAULT_THREADS)
            cpu_val = max(1, cpu_val)
            cpu_opt = f'--cpu {cpu_val}'
        except Exception:
            cpu_opt = ''
        
        evalue_opt = '' if cut_ga else f'-E {evalue}'

        command = (
            f'hmmsearch {cut_ga_opt} {dom_opt} {cpu_opt} {evalue_opt} ' 
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
            logger.info(f"[STEP2] HMM {hmm_basename}: Found {len(hits)} hits")
        else:
            logger.warning(f"[STEP2] HMM {hmm_basename} failed: {stderr}")
            last_error = stderr or 'hmmsearch failed'
    
    if not all_tbl_files:
        return False, None, f"All HMM searches failed, or no hits found. Last error: {last_error}", all_commands
    
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
    
    logger.info(f"[STEP2] Found {total_hits} total hits, {unique_count} unique after deduplication")
    logger.info(f"[STEP2] Removed {duplicate_count} duplicate hits")
    
    # Extract sequences with unique IDs
    output_fasta = os.path.join(output_dir, 'step2_hmm_hits.fasta')
    extracted_count = extract_sequences_by_ids(input_file, unique_ids, output_fasta)
    
    logger.info(f"[STEP2] Extracted {extracted_count} sequences to {output_fasta}")
    
    message = f"Found {unique_count} unique hits from {len(hmm_files)} HMM file(s) (removed {duplicate_count} duplicates)"
    
    return True, output_fasta, message, all_commands

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

def step2_5_blast_filter(input_file, gold_list_file, output_dir,
                         pident_threshold=30, qcovs_threshold=50,
                         blast_db_path=None, evalue=1e-5, max_target_seqs=5,
                         threads=None, progress_callback=None):
    """
    Step 2.5: Filter sequences using BLAST against a gold standard database.
    Runs blastp, writes raw TSV output and a verbose filter log, and returns stats.
    """
    output_file = os.path.join(output_dir, 'step2_5_filtered.fasta')
    raw_output_file = os.path.join(output_dir, 'step2_5_blast_raw.tsv')
    log_file = os.path.join(output_dir, 'step2_5_blast_filter.log')

    try:
        input_file = sanitize_path(input_file)
        gold_list_file = sanitize_path(gold_list_file)
        output_dir = sanitize_path(output_dir)
    except ValueError as e:
        return False, None, str(e), None, None

    if not os.path.exists(input_file):
        return False, None, f"Input file not found: {input_file}", None, None
    if not os.path.exists(gold_list_file):
        return False, None, f"Gold list file not found: {gold_list_file}", None, None
    os.makedirs(output_dir, exist_ok=True)

    if blast_db_path is None or str(blast_db_path).strip() == '':
        return False, None, "BLAST database path is required for step 2.5", None, None

    # Normalize numeric inputs with safe defaults
    def _float_default(val, default):
        if val is None:
            return default
        try:
            sval = str(val).strip()
            if sval == '':
                return default
            return float(sval)
        except Exception:
            return default

    def _int_default(val, default):
        if val is None:
            return default
        try:
            sval = str(val).strip()
            if sval == '':
                return default
            return int(sval)
        except Exception:
            return default

    # evalue 允许为空以关闭 e-value 过滤
    if evalue in (None, ''):
        evalue = None
    else:
        evalue = _float_default(evalue, 1e-5)
    pident_threshold = _float_default(pident_threshold, 30)
    qcovs_threshold = _float_default(qcovs_threshold, 50)
    max_target_seqs = max(1, _int_default(max_target_seqs, 5))

    if threads is None or str(threads).strip() == '':
        threads = config.DEFAULT_THREADS
    try:
        threads = max(1, int(threads))
    except (ValueError, TypeError):
        threads = config.DEFAULT_THREADS

    try:
        resolved_db_path = _resolve_blast_db_path(blast_db_path)
    except (ValueError, FileNotFoundError) as e:
        return False, None, str(e), None, None

    msg = "[STEP2.5] Loading gold standard list..."
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')

    gold_ids = set()
    with open(gold_list_file, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            clean_id = line.split()[0]
            clean_id = clean_id.split('.')[0].upper()
            gold_ids.add(clean_id)

    if not gold_ids:
        logger.warning(f"Gold list {gold_list_file} contains no IDs")

    msg = f"[STEP2.5] Loaded {len(gold_ids)} gold standard IDs"
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')

    outfmt = shlex.quote('6 qseqid sseqid pident qcovs')
    blast_command = (
        f"blastp -query {shlex.quote(input_file)} "
        f"-db {shlex.quote(resolved_db_path)} "
        + (f"-evalue {evalue} " if evalue is not None else "")
        + f"-max_target_seqs {max_target_seqs} "
        + f"-outfmt {outfmt} "
        + f"-num_threads {threads}"
    )
    display_command = f"conda run -n {config.CONDA_ENV} {blast_command}"

    success, stdout, stderr = run_conda_command(blast_command, timeout=7200)
    if not success:
        logger.error(f"Step 2.5 BLAST failed: {stderr}")
        return False, None, stderr or stdout or "BLASTP failed", None, display_command

    stdout = stdout or ''
    with open(raw_output_file, 'w', encoding='utf-8') as raw_f:
        raw_f.write("qseqid\tsseqid\tpident\tqcovs\n")
        if stdout:
            raw_f.write(stdout if stdout.endswith('\n') else stdout + '\n')

    valid_query_ids = set()
    total_hits = 0
    parsed_queries = set()
    hit_details = {}
    failure_reasons = {}
    hit_seen = Counter()
    # 只用 max_target_seqs 控制 BLAST top hits
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) < 4:
            continue
        total_hits += 1
        qseqid = parts[0].strip()
        sseqid_clean = parts[1].split('.')[0].upper()
        try:
            pident = float(parts[2])
            qcovs = float(parts[3])
        except (ValueError, TypeError):
            continue

        hit_seen[qseqid] += 1
        # BLAST 已用 max_target_seqs 控制 top hits

        match_ok = False
        if sseqid_clean in gold_ids:
            match_ok = True
        else:
            for gid in gold_ids:
                if gid in sseqid_clean or sseqid_clean in gid:
                    match_ok = True
                    break

        # record parsed query
        parsed_queries.add(qseqid)
        hit_details.setdefault(qseqid, []).append((sseqid_clean, pident, qcovs, match_ok))

        # evaluate quality
        if match_ok and pident >= pident_threshold and qcovs >= qcovs_threshold:
            valid_query_ids.add(qseqid)
            failure_reasons[qseqid] = ['valid']
        else:
            reasons = failure_reasons.get(qseqid, [])
            if not match_ok:
                reasons.append('no_gold_match')
            if pident < pident_threshold:
                reasons.append('low_identity')
            if qcovs < qcovs_threshold:
                reasons.append('low_coverage')
            failure_reasons[qseqid] = list(set(reasons))

    msg = "[STEP2.5] Reading input sequences..."
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')

    sequences = read_fasta_file(input_file)
    filtered = []
    all_ids = []
    for header, seq in sequences:
        seq_id = header.split()[0]
        all_ids.append(seq_id)
        if seq_id in valid_query_ids:
            filtered.append((header, seq))

    deleted_ids = [seq_id for seq_id in all_ids if seq_id not in valid_query_ids]
    # Add reasons for sequences that were parsed but not valid
    deleted_with_reasons = []
    for seq_id in deleted_ids:
        q = seq_id
        reasons = []
        if q in failure_reasons:
            reasons = failure_reasons[q]
        else:
            # No BLAST hits recorded
            reasons = ['no_hits']
        deleted_with_reasons.append((seq_id, reasons))
    write_fasta_file(output_file, filtered)

    deleted_unique = sorted(set(deleted_ids))
    deleted_preview = deleted_unique[:50]

    log_lines = [
        "--- BLAST Filter Summary ---",
        f"Database: {resolved_db_path}",
        f"Gold list entries: {len(gold_ids)}",
           ("Filters: {0}Min P-Ident >= {1}% | Min Q-Covs >= {2}% | Max target seqs: {3}").format(
               (f"E-value <= {evalue} | " if evalue is not None else ""),
               pident_threshold, qcovs_threshold, max_target_seqs),
        f"Threads: {threads}",
        f"Total sequences in: {len(all_ids)}",
        f"Sequences Kept (passed all filters): {len(filtered)}",
        f"Sequences Deleted (failed filters): {len(all_ids) - len(filtered)}",
        f"BLAST hits parsed: {total_hits}",
    ]
    if not stdout.strip():
        log_lines.append("BLAST returned zero hits.")

    if deleted_unique:
        log_lines.append("\n--- Deleted Sequences (no gold match or failed quality) ---")
        for idx, deleted_id in enumerate(deleted_preview):
            log_lines.append(f"  {deleted_id}")
        if len(deleted_unique) > len(deleted_preview):
            log_lines.append(f"  ... and {len(deleted_unique) - len(deleted_preview)} more.")

    with open(log_file, 'w', encoding='utf-8') as log_f:
        for line in log_lines:
            log_f.write(line + '\n')

    kept_count = len(filtered)
    total_sequences = len(all_ids)
    message = f"BLAST filter kept {kept_count} of {total_sequences} sequences"
    if kept_count == 0:
        message = "No sequences passed BLAST filter"

    msg = f"Step 2.5: Filtered {kept_count} sequences (from {total_sequences})"
    logger.info(msg)
    if progress_callback:
        progress_callback(msg, 'info')


    # Prepare concise hit details for first 50 queries for debugging
    hit_details_preview = {k: v[:10] for k, v in list(hit_details.items())[:50]}

    stats = {
        'total_in': total_sequences,
        'kept': kept_count,
        'deleted': total_sequences - kept_count,
        'deleted_ids': deleted_preview,
        'deleted_with_reasons': deleted_with_reasons[:50] if deleted_with_reasons else [],
        'log_file': log_file,
        'raw_output_file': raw_output_file,
        'database': resolved_db_path,
        'pident_threshold': pident_threshold,
        'qcovs_threshold': qcovs_threshold,
        'evalue': evalue,
        'max_target_seqs': max_target_seqs,
        'threads': threads,
        'total_hits': total_hits,
        'hit_details_preview': hit_details_preview,
    }

    logger.info(f"Step 2.5: Filtered {kept_count} sequences (from {total_sequences})")
    return True, output_file, message, stats, display_command

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
    Returns detailed statistics like original script (lines 416-438).
    """
    output_file = os.path.join(output_dir, 'step2_8_length_filtered.fasta')
    log_file = os.path.join(output_dir, 'step2_8_length_filter.log')

    sequences = read_fasta_file(input_file)
    
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

    logger.info(f"Step 2.8: Removed {len(deleted_ids)} short sequences")
    
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

    # Full command for display and execution
    if config.USE_CONDA:
        display_command = f"conda run -n {config.CONDA_ENV} {command} > {output_file} 2> {log_file}"
        full_command = f"conda run -n {shlex.quote(config.CONDA_ENV)} {command} > {shlex.quote(output_file)} 2> {shlex.quote(log_file)}"
    else:
        display_command = f"{command} > {output_file} 2> {log_file}"
        full_command = f"{command} > {shlex.quote(output_file)} 2> {shlex.quote(log_file)}"

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

    # Full command for display and execution
    if config.USE_CONDA:
        display_command = f"conda run -n {config.CONDA_ENV} {command}"
        full_command = f"conda run -n {shlex.quote(config.CONDA_ENV)} {command} 2> {shlex.quote(log_file)}"
    else:
        display_command = command
        full_command = f"{command} 2> {shlex.quote(log_file)}"

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

def run_full_pipeline(input_file, hmm_files=None, gold_list_file=None, options=None):
    """
    Run the complete phylogenetic pipeline.
    """
    if options is None:
        options = {}

    result_dir = create_result_dir('phylo', 'pipeline')

    if isinstance(hmm_files, str):
        hmm_files_list = [hmm_files] if hmm_files else []
    else:
        hmm_files_list = [f for f in hmm_files if f]

    params = {'input_file': input_file,'hmm_files': hmm_files_list,'gold_list_file': gold_list_file,'options': options,'timestamp': datetime.now().isoformat()}
    save_params(result_dir, params)
    results = {'result_dir': result_dir,'steps': {},'commands': []}
    current_file = input_file

    success, output, message = step1_clean_fasta(current_file, result_dir)
    results['steps']['step1'] = {'success': success, 'output': output, 'message': message}
    if not success: return False, results
    current_file = output

    valid_hmm_files = [f for f in hmm_files_list if os.path.exists(f)]
    if valid_hmm_files:
        success, output, message, commands = step2_hmmsearch_multiple(current_file, valid_hmm_files, result_dir, cut_ga=options.get('cut_ga', True))
        results['steps']['step2'] = {'success': success, 'output': output, 'message': message}
        if commands:
            for i, cmd in enumerate(commands):
                results['commands'].append({'step': f'step2_{i+1}','name': f'HMMer Search ({i+1}/{len(commands)})','command': cmd})
        if success:
            current_file = output
        else:
            return False, results

    if gold_list_file and os.path.exists(gold_list_file):
        blast_db_path = (options.get('blast_db_path') or '').strip()
        if not blast_db_path:
            results['steps']['step2_5'] = {'success': False,'output': None,'message': 'BLAST database path is required for step 2.5','stats': None,'command': None,'raw_output': None,'log_file': None}
            return False, results
        success, output, message, stats, command = step2_5_blast_filter(current_file,gold_list_file,result_dir,pident_threshold=options.get('pident', 30),qcovs_threshold=options.get('qcovs', 50),blast_db_path=blast_db_path,evalue=options.get('blast_evalue', 1e-5),max_target_seqs=options.get('blast_max_target_seqs', 5),threads=options.get('blast_threads', config.DEFAULT_THREADS))
        results['steps']['step2_5'] = {'success': success,'output': output,'message': message,'stats': stats,'command': command,'raw_output': stats.get('raw_output_file') if stats else None,'log_file': stats.get('log_file') if stats else None}
        if command:
            results['commands'].append({'step': 'step2_5', 'name': 'BLAST Filter', 'command': command})
        if success:
            current_file = output
        else:
            return False, results

    success, output, message = step2_7_length_stats(current_file, result_dir)
    results['steps']['step2_7'] = {'success': success, 'output': output, 'message': message}
    min_length = options.get('min_length', 50)
    success, output, message = step2_8_length_filter(current_file, result_dir, min_length)
    results['steps']['step2_8'] = {'success': success, 'output': output, 'message': message}
    if success:
        current_file = output

    success, output, message, command = step3_mafft(current_file, result_dir,maxiterate=options.get('maxiterate', 1000))
    results['steps']['step3'] = {'success': success, 'output': output, 'message': message, 'command': command}
    if command:
        results['commands'].append({'step': 'step3', 'name': 'MAFFT Alignment', 'command': command})
    if not success: return False, results
    current_file = output

    success, output, message, command = step4_clipkit(current_file, result_dir,mode=options.get('clipkit_mode', 'kpic-gappy'))
    results['steps']['step4'] = {'success': success, 'output': output, 'message': message, 'command': command}
    if command:
        results['commands'].append({'step': 'step4', 'name': 'ClipKIT Trim', 'command': command})
    if not success: return False, results
    current_file = output

    success, output, message, command = step5_iqtree(current_file, result_dir,model=options.get('model', 'MFP'),bootstrap=options.get('bootstrap', 1000),threads=options.get('threads', config.DEFAULT_THREADS),bnni=options.get('bnni', True))
    results['steps']['step5'] = {'success': success, 'output': output, 'message': message, 'command': command}
    if command:
        results['commands'].append({'step': 'step5', 'name': 'IQ-Tree', 'command': command})

    return success, results
