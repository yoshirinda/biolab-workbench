"""
HMM Search wrapper for BioLab Workbench.
Integrates hmmsearch from HMMER package.
"""
import os
import subprocess
import shlex
import re
from datetime import datetime
import config
from app.utils.logger import get_tools_logger
from app.utils.file_utils import create_result_dir, save_params
from app.utils.fasta_utils import parse_fasta, write_fasta, deduplicate_sequences

logger = get_tools_logger()


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


def parse_hmmsearch_domtblout(domtblout_file):
    """
    Parse hmmsearch --domtblout output.
    
    Returns:
        List of dicts with hit information
    """
    hits = []
    
    try:
        with open(domtblout_file, 'r') as f:
            for line in f:
                if line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) < 23:
                    continue
                
                hit = {
                    'target_name': parts[0],
                    'target_accession': parts[1],
                    'query_name': parts[3],
                    'query_accession': parts[4],
                    'full_evalue': float(parts[6]),
                    'full_score': float(parts[7]),
                    'full_bias': float(parts[8]),
                    'domain_num': int(parts[9]),
                    'domain_total': int(parts[10]),
                    'domain_c_evalue': float(parts[11]),
                    'domain_i_evalue': float(parts[12]),
                    'domain_score': float(parts[13]),
                    'domain_bias': float(parts[14]),
                    'hmm_from': int(parts[15]),
                    'hmm_to': int(parts[16]),
                    'ali_from': int(parts[17]),
                    'ali_to': int(parts[18]),
                    'env_from': int(parts[19]),
                    'env_to': int(parts[20]),
                }
                hits.append(hit)
    except Exception as e:
        logger.error(f"Failed to parse domtblout: {e}")
        return []
    
    return hits


def run_hmmsearch(hmm_profile, sequence_file, output_format='domtblout', 
                  evalue=1e-5, cut_ga=False, cpu=None):
    """
    Run hmmsearch to find protein domains.
    
    Args:
        hmm_profile: Path to HMM profile file
        sequence_file: Path to protein FASTA file
        output_format: 'domtblout' or 'tblout'
        evalue: E-value threshold (ignored if cut_ga=True)
        cut_ga: Use gathering thresholds from HMM file
        cpu: Number of CPU threads (default: config.DEFAULT_THREADS)
        
    Returns:
        (success, result_dir, output_files, hits)
    """
    if not os.path.exists(hmm_profile):
        return False, None, None, f"HMM profile not found: {hmm_profile}"
    
    if not os.path.exists(sequence_file):
        return False, None, None, f"Sequence file not found: {sequence_file}"
    
    result_dir = create_result_dir('hmm', 'search')
    
    hmm_name = os.path.basename(hmm_profile).rsplit('.', 1)[0]
    output_file = os.path.join(result_dir, f'{hmm_name}_hits.domtblout')
    stdout_file = os.path.join(result_dir, f'{hmm_name}_search.out')
    
    if cpu is None:
        cpu = config.DEFAULT_THREADS
    
    # Build command
    command = f'hmmsearch --domtblout {shlex.quote(output_file)} --cpu {cpu}'
    
    if cut_ga:
        command += ' --cut_ga'
    else:
        command += f' -E {evalue}'
    
    command += f' {shlex.quote(hmm_profile)} {shlex.quote(sequence_file)}'
    command += f' > {shlex.quote(stdout_file)}'
    
    # Save parameters
    params = {
        'hmm_profile': hmm_profile,
        'sequence_file': sequence_file,
        'evalue': evalue if not cut_ga else 'GA threshold',
        'cut_ga': cut_ga,
        'cpu': cpu,
        'timestamp': datetime.now().isoformat()
    }
    save_params(result_dir, params)
    
    # Execute
    success, stdout, stderr = run_conda_command(command)
    
    if not success:
        logger.error(f"hmmsearch failed: {stderr}")
        return False, result_dir, None, stderr
    
    # Parse hits
    hits = parse_hmmsearch_domtblout(output_file)
    
    logger.info(f"hmmsearch completed: {len(hits)} domain hits found")
    
    output_files = {
        'domtblout': output_file,
        'stdout': stdout_file
    }
    
    return True, result_dir, output_files, hits


def extract_hit_sequences(hits, source_fasta, output_fasta, evalue_cutoff=None):
    """
    Extract sequences for HMM hits from source FASTA.
    
    Args:
        hits: List of hit dicts from parse_hmmsearch_domtblout
        source_fasta: Path to original protein FASTA file
        output_fasta: Path to write extracted sequences
        evalue_cutoff: Optional additional E-value filter
        
    Returns:
        (success, extracted_count)
    """
    # Get hit IDs
    hit_ids = set()
    for hit in hits:
        if evalue_cutoff and hit['full_evalue'] > evalue_cutoff:
            continue
        hit_ids.add(hit['target_name'])
    
    if not hit_ids:
        logger.warning("No hits to extract")
        return False, 0
    
    # Parse source FASTA
    sequences = parse_fasta(source_fasta)
    
    # Extract matching sequences
    extracted = []
    for seq_id, desc, seq in sequences:
        if seq_id in hit_ids:
            extracted.append((seq_id, desc, seq))
    
    if not extracted:
        logger.warning(f"No sequences found matching {len(hit_ids)} hit IDs")
        return False, 0
    
    # Remove duplicates
    extracted, duplicates = deduplicate_sequences(extracted, by_id=True)
    if duplicates:
        logger.info(f"Removed {len(duplicates)} duplicate sequences")
    
    # Write output
    success = write_fasta(extracted, output_fasta)
    
    if success:
        logger.info(f"Extracted {len(extracted)} sequences to {output_fasta}")
        return True, len(extracted)
    else:
        return False, 0


def run_hmmsearch_multi(hmm_profiles, sequence_file, evalue=1e-5, cut_ga=False, 
                       merge_output=True, cpu=None):
    """
    Run hmmsearch with multiple HMM profiles.
    
    Args:
        hmm_profiles: List of HMM profile file paths
        sequence_file: Path to protein FASTA file
        evalue: E-value threshold
        cut_ga: Use gathering thresholds
        merge_output: Merge results from all profiles
        cpu: CPU threads
        
    Returns:
        (success, result_dir, output_files, all_hits)
    """
    if not hmm_profiles:
        return False, None, None, "No HMM profiles provided"
    
    result_dir = create_result_dir('hmm', 'multi_search')
    all_hits = []
    all_output_files = {}
    
    for hmm_profile in hmm_profiles:
        logger.info(f"Running hmmsearch with {os.path.basename(hmm_profile)}")
        
        success, sub_dir, output_files, hits = run_hmmsearch(
            hmm_profile, sequence_file, evalue=evalue, cut_ga=cut_ga, cpu=cpu
        )
        
        if not success:
            logger.error(f"hmmsearch failed for {hmm_profile}")
            continue
        
        all_hits.extend(hits)
        profile_name = os.path.basename(hmm_profile).rsplit('.', 1)[0]
        all_output_files[profile_name] = output_files
    
    if not all_hits:
        return False, result_dir, all_output_files, "No hits found"
    
    # Merge and deduplicate
    if merge_output:
        merged_file = os.path.join(result_dir, 'merged_hits.fasta')
        
        # Get unique hit IDs
        hit_ids = set(hit['target_name'] for hit in all_hits)
        logger.info(f"Total unique hits: {len(hit_ids)}")
        
        # Extract sequences
        success, count = extract_hit_sequences(all_hits, sequence_file, merged_file)
        
        if success:
            all_output_files['merged'] = merged_file
    
    logger.info(f"Multi-profile hmmsearch completed: {len(all_hits)} total hits")
    
    return True, result_dir, all_output_files, all_hits


def get_hmm_info(hmm_file):
    """
    Extract information from HMM profile file.
    
    Returns:
        Dict with NAME, ACC, DESC, LENG, etc.
    """
    info = {}
    
    try:
        with open(hmm_file, 'r') as f:
            for line in f:
                if line.startswith('NAME'):
                    info['name'] = line.split(None, 1)[1].strip()
                elif line.startswith('ACC'):
                    info['accession'] = line.split(None, 1)[1].strip()
                elif line.startswith('DESC'):
                    info['description'] = line.split(None, 1)[1].strip()
                elif line.startswith('LENG'):
                    info['length'] = int(line.split()[1])
                elif line.startswith('GA'):
                    parts = line.split()
                    if len(parts) >= 3:
                        info['ga_threshold'] = {
                            'sequence': float(parts[1].rstrip(';')),
                            'domain': float(parts[2].rstrip(';'))
                        }
                elif line.startswith('//'):
                    break
    except Exception as e:
        logger.error(f"Failed to parse HMM file: {e}")
        return None
    
    return info
