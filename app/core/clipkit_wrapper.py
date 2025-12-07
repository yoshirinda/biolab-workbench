"""
ClipKIT wrapper for BioLab Workbench.
Trims poorly aligned positions from multiple sequence alignments.
"""
import os
import subprocess
import shlex
from datetime import datetime
import config
from app.utils.logger import get_tools_logger
from app.utils.file_utils import create_result_dir, save_params
from app.utils.fasta_utils import parse_fasta, get_fasta_stats

logger = get_tools_logger()


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


def parse_clipkit_log(log_file):
    """
    Parse ClipKIT log file to extract trimming statistics.
    
    Returns:
        Dict with alignment stats
    """
    stats = {
        'input_length': None,
        'output_length': None,
        'trimmed_sites': None,
        'percent_kept': None
    }
    
    try:
        with open(log_file, 'r') as f:
            content = f.read()
            
            # Parse log content
            for line in content.split('\n'):
                if 'alignment length:' in line.lower():
                    # Extract numbers from line
                    import re
                    numbers = re.findall(r'\d+', line)
                    if len(numbers) >= 2:
                        stats['input_length'] = int(numbers[0])
                        stats['output_length'] = int(numbers[1])
                        if stats['input_length'] > 0:
                            stats['trimmed_sites'] = stats['input_length'] - stats['output_length']
                            stats['percent_kept'] = (stats['output_length'] / stats['input_length']) * 100
                elif 'Alignment has' in line and 'sequences with' in line and 'columns' in line:
                    # Fallback: parse from IQ-TREE style line
                    import re
                    match = re.search(r'Alignment has (\d+) sequences with (\d+) columns', line)
                    if match:
                        stats['input_length'] = int(match.group(2))
                        stats['output_length'] = int(match.group(2))  # Assume no trim info, set same
                        stats['percent_kept'] = 100.0
    except Exception as e:
        logger.warning(f"Failed to parse ClipKIT log: {e}")
    
    return stats


def run_clipkit(input_alignment, output_file=None, mode='kpic-gappy', 
                gaps=0.9, complement=False, log_file=None):
    """
    Run ClipKIT to trim alignment.
    
    Args:
        input_alignment: Path to input alignment file (FASTA format)
        output_file: Path for output trimmed alignment (optional)
        mode: Trimming mode
            - 'kpic' (default): keeps parsimoniously informative and constant sites
            - 'kpic-gappy': kpic but retains gaps
            - 'kpi': keeps only parsimoniously informative sites
            - 'gappy': trim sites with gaps
            - 'smart-gap': dynamic gap threshold
        gaps: Gap threshold (0-1, default 0.9)
        complement: Keep trimmed sites instead of keeping informative sites
        log_file: Path for log file (optional)
        
    Returns:
        (success, result_dir, output_file, stats)
    """
    if not os.path.exists(input_alignment):
        return False, None, None, f"Input alignment not found: {input_alignment}"
    
    # Create result directory
    result_dir = create_result_dir('clipkit', 'trim')
    
    if output_file is None:
        basename = os.path.basename(input_alignment).rsplit('.', 1)[0]
        output_file = os.path.join(result_dir, f'{basename}_trimmed.fasta')
    
    if log_file is None:
        log_file = output_file + '.log'
    
    # Build command
    command = f'clipkit {shlex.quote(input_alignment)}'
    command += f' -o {shlex.quote(output_file)}'
    command += f' -m {shlex.quote(mode)}'
    
    if gaps is not None:
        command += f' -g {gaps}'
    
    if complement:
        command += ' --complement'
    
    command += f' -l'
    
    # Save parameters
    params = {
        'input_alignment': input_alignment,
        'output_file': output_file,
        'mode': mode,
        'gaps': gaps,
        'complement': complement,
        'timestamp': datetime.now().isoformat()
    }
    save_params(result_dir, params)
    
    # Execute
    success, stdout, stderr = run_conda_command(command)
    
    if not success:
        logger.error(f"ClipKIT failed: {stderr}")
        return False, result_dir, None, stderr
    
    # Write log
    with open(log_file, 'w') as f:
        f.write(stdout)
    
    # Parse log
    stats = parse_clipkit_log(log_file)
    
    # Get sequence counts and lengths
    input_seqs = parse_fasta(input_alignment)
    output_seqs = parse_fasta(output_file)
    
    input_length = len(input_seqs[0][2]) if input_seqs else 0
    output_length = len(output_seqs[0][2]) if output_seqs else 0
    
    stats['input_length'] = input_length
    stats['output_length'] = output_length
    stats['percent_kept'] = (output_length / input_length) * 100 if input_length > 0 else 0
    stats['input_seq_count'] = len(input_seqs)
    stats['output_seq_count'] = len(output_seqs)
    
    logger.info(f"ClipKIT completed: {stats['output_length']} sites kept from {stats['input_length']}")
    
    return True, result_dir, output_file, log_file, stats


def analyze_alignment_conservation(alignment_file, window_size=10):
    """
    Analyze conservation patterns in alignment.
    
    Args:
        alignment_file: Path to alignment FASTA file
        window_size: Window size for sliding conservation analysis
        
    Returns:
        Dict with conservation statistics
    """
    sequences = parse_fasta(alignment_file)
    
    if not sequences:
        return None
    
    # Get alignment length
    aln_length = len(sequences[0][2])
    
    # Calculate per-site conservation
    conservation_scores = []
    
    for pos in range(aln_length):
        # Get all residues at this position
        residues = [seq[2][pos] for seq_id, desc, seq in sequences if pos < len(seq)]
        
        # Calculate conservation score (proportion of most common residue)
        if residues:
            from collections import Counter
            counts = Counter(residues)
            # Ignore gaps for conservation calculation
            non_gap_residues = [r for r in residues if r != '-']
            if non_gap_residues:
                most_common_count = Counter(non_gap_residues).most_common(1)[0][1]
                conservation = most_common_count / len(non_gap_residues)
            else:
                conservation = 0
            
            conservation_scores.append(conservation)
    
    # Calculate statistics
    if conservation_scores:
        avg_conservation = sum(conservation_scores) / len(conservation_scores)
        high_conservation_sites = sum(1 for s in conservation_scores if s >= 0.8)
        low_conservation_sites = sum(1 for s in conservation_scores if s < 0.5)
    else:
        avg_conservation = 0
        high_conservation_sites = 0
        low_conservation_sites = 0
    
    return {
        'alignment_length': aln_length,
        'sequence_count': len(sequences),
        'avg_conservation': avg_conservation,
        'high_conservation_sites': high_conservation_sites,
        'low_conservation_sites': low_conservation_sites,
        'conservation_scores': conservation_scores
    }


def suggest_clipkit_mode(alignment_file):
    """
    Analyze alignment and suggest appropriate ClipKIT mode.
    
    Returns:
        (suggested_mode, reason)
    """
    stats = analyze_alignment_conservation(alignment_file)
    
    if not stats:
        return 'kpic-gappy', "Default mode (unable to analyze alignment)"
    
    # Decision logic
    avg_cons = stats['avg_conservation']
    
    if avg_cons < 0.3:
        return 'kpic', "Low conservation - use strict trimming"
    elif avg_cons < 0.5:
        return 'kpic-gappy', "Medium conservation - balance between retention and trimming"
    elif avg_cons < 0.7:
        return 'gappy', "Good conservation - mainly remove gappy regions"
    else:
        return 'smart-gap', "High conservation - use adaptive gap trimming"


def compare_before_after_trimming(input_file, output_file):
    """
    Compare alignment before and after ClipKIT trimming.
    
    Returns:
        Dict with comparison statistics
    """
    input_seqs = parse_fasta(input_file)
    output_seqs = parse_fasta(output_file)
    
    input_stats = get_fasta_stats(input_seqs)
    output_stats = get_fasta_stats(output_seqs)
    
    # Calculate gaps
    def count_gaps(sequences):
        total_gaps = 0
        total_length = 0
        for _, _, seq in sequences:
            total_gaps += seq.count('-')
            total_length += len(seq)
        return total_gaps, total_length
    
    input_gaps, input_length = count_gaps(input_seqs)
    output_gaps, output_length = count_gaps(output_seqs)
    
    comparison = {
        'input': {
            'sequences': input_stats['count'],
            'length': input_stats['max_length'],
            'gaps': input_gaps,
            'gap_percent': (input_gaps / input_length * 100) if input_length > 0 else 0
        },
        'output': {
            'sequences': output_stats['count'],
            'length': output_stats['max_length'],
            'gaps': output_gaps,
            'gap_percent': (output_gaps / output_length * 100) if output_length > 0 else 0
        },
        'change': {
            'sites_removed': input_stats['max_length'] - output_stats['max_length'],
            'percent_kept': (output_stats['max_length'] / input_stats['max_length'] * 100) if input_stats['max_length'] > 0 else 0,
            'gap_reduction': input_gaps - output_gaps
        }
    }
    
    return comparison
