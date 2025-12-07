"""
Alignment wrapper for multiple sequence alignment tools.
Supports MAFFT, ClustalW, and MUSCLE.
"""
import os
import subprocess
import tempfile
from datetime import datetime
from typing import Tuple, Dict, Optional, List
from app import config
from app.utils.fasta_utils import parse_fasta, write_fasta, get_fasta_stats
import logging

logger = logging.getLogger(__name__)


def run_alignment(
    input_file: str,
    tool: str = 'mafft',
    output_format: str = 'fasta',
    threads: int = 4,
    extra_params: Optional[Dict] = None
) -> Tuple[bool, str, str, Dict]:
    """
    Run sequence alignment with specified tool.
    
    Args:
        input_file: Path to input FASTA file
        tool: Alignment tool ('mafft', 'clustalw', 'muscle')
        output_format: Output format ('fasta', 'clustal', 'phylip')
        threads: Number of threads to use
        extra_params: Additional tool-specific parameters
        
    Returns:
        Tuple of (success, result_dir, output_file, stats)
    """
    try:
        # Create result directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_dir = os.path.join(config.RESULTS_DIR, f'alignment_{tool}_{timestamp}')
        os.makedirs(result_dir, exist_ok=True)
        
        # Determine output file path
        ext_map = {
            'fasta': '.fasta',
            'clustal': '.aln',
            'phylip': '.phy'
        }
        output_file = os.path.join(result_dir, f'aligned{ext_map.get(output_format, ".fasta")}')
        
        # Route to appropriate tool
        if tool.lower() == 'mafft':
            success, error_msg, command = _run_mafft(input_file, output_file, output_format, threads, extra_params)
        elif tool.lower() == 'clustalw':
            success, error_msg = _run_clustalw(input_file, output_file, output_format, threads, extra_params)
            command = ""  # TODO: implement command return for other tools
        elif tool.lower() == 'muscle':
            success, error_msg = _run_muscle(input_file, output_file, output_format, threads, extra_params)
            command = ""  # TODO
        else:
            return False, result_dir, '', {'error': f'Unknown alignment tool: {tool}'}
        
        if not success:
            return False, result_dir, '', {'error': error_msg}
        
        # Calculate statistics
        stats = _calculate_alignment_stats(output_file)
        stats['tool'] = tool
        stats['parameters'] = extra_params or {}
        stats['command'] = command
        
        return True, result_dir, output_file, stats
        
    except Exception as e:
        logger.error(f"Alignment error: {str(e)}")
        return False, result_dir if 'result_dir' in locals() else '', '', {'error': str(e)}


def _run_mafft(
    input_file: str,
    output_file: str,
    output_format: str,
    threads: int,
    extra_params: Optional[Dict]
) -> Tuple[bool, str, str]:
    """Run MAFFT alignment."""
    try:
        # Build MAFFT command
        cmd = [
            'mafft',
            '--thread', str(threads),
            '--auto'  # Auto select algorithm
        ]
        
        # Add extra parameters
        if extra_params:
            if extra_params.get('maxiterate') is not None:
                cmd.extend(['--maxiterate', str(extra_params['maxiterate'])])
            
            if extra_params.get('algorithm') == 'linsi':
                cmd = ['mafft', '--localpair', '--maxiterate', '1000', '--thread', str(threads)]
            elif extra_params.get('algorithm') == 'ginsi':
                cmd = ['mafft', '--globalpair', '--maxiterate', '1000', '--thread', str(threads)]
            elif extra_params.get('algorithm') == 'einsi':
                cmd = ['mafft', '--ep', '0', '--genafpair', '--maxiterate', '1000', '--thread', str(threads)]
            
            if extra_params.get('adjustdirection'):
                cmd.append('--adjustdirection')
        
        # Output format
        if output_format == 'clustal':
            cmd.append('--clustalout')
        elif output_format == 'phylip':
            cmd.append('--phylipout')
        
        cmd.append(input_file)
        
        command = ' '.join(cmd)
        
        # Run MAFFT
        logger.info(f"Running MAFFT: {command}")
        
        if config.USE_CONDA:
            full_command = f"conda run -n {config.CONDA_ENV} {command}"
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True
            )
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
        
        if result.returncode != 0:
            return False, f"MAFFT failed: {result.stderr}", command
        
        # Write output
        with open(output_file, 'w') as f:
            f.write(result.stdout)
        
        return True, "", command
        
    except Exception as e:
        return False, str(e), command if 'command' in locals() else ' '.join(cmd)


def _run_clustalw(
    input_file: str,
    output_file: str,
    output_format: str,
    threads: int,
    extra_params: Optional[Dict]
) -> Tuple[bool, str]:
    """Run ClustalW alignment."""
    try:
        # Build ClustalW command
        cmd = [
            'clustalw',
            f'-INFILE={input_file}',
            f'-OUTFILE={output_file}'
        ]
        
        # Output format
        if output_format == 'fasta':
            cmd.append('-OUTPUT=FASTA')
        elif output_format == 'phylip':
            cmd.append('-OUTPUT=PHYLIP')
        else:  # clustal
            cmd.append('-OUTPUT=CLUSTAL')
        
        # Add extra parameters
        if extra_params:
            if 'gapopen' in extra_params:
                cmd.append(f'-GAPOPEN={extra_params["gapopen"]}')
            if 'gapext' in extra_params:
                cmd.append(f'-GAPEXT={extra_params["gapext"]}')
            if 'matrix' in extra_params:
                cmd.append(f'-MATRIX={extra_params["matrix"]}')
        
        # Run ClustalW
        logger.info(f"Running ClustalW: {' '.join(cmd)}")
        
        if config.USE_CONDA:
            conda_cmd = f"conda run -n {config.CONDA_ENV} {' '.join(cmd)}"
            result = subprocess.run(
                conda_cmd,
                shell=True,
                capture_output=True,
                text=True
            )
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
        
        if result.returncode != 0:
            return False, f"ClustalW failed: {result.stderr}"
        
        return True, ""
        
    except Exception as e:
        return False, str(e)


def _run_muscle(
    input_file: str,
    output_file: str,
    output_format: str,
    threads: int,
    extra_params: Optional[Dict]
) -> Tuple[bool, str]:
    """Run MUSCLE alignment."""
    try:
        # Check MUSCLE version
        version_cmd = 'muscle -version' if not config.USE_CONDA else f'conda run -n {config.CONDA_ENV} muscle -version'
        version_result = subprocess.run(
            version_cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        
        is_muscle5 = 'MUSCLE v5' in version_result.stdout or 'MUSCLE v5' in version_result.stderr
        
        # Build MUSCLE command
        if is_muscle5:
            cmd = [
                'muscle',
                '-align', input_file,
                '-output', output_file,
                '-threads', str(threads)
            ]
            
            # MUSCLE5 output format
            if output_format == 'clustal':
                cmd.extend(['-clw'])
            elif output_format == 'phylip':
                cmd.extend(['-phylipi'])
        else:
            # MUSCLE v3
            cmd = [
                'muscle',
                '-in', input_file,
                '-out', output_file
            ]
            
            # MUSCLE3 output format
            if output_format == 'clustal':
                cmd.extend(['-clw'])
            elif output_format == 'phylip':
                cmd.extend(['-phyi'])
        
        # Add extra parameters
        if extra_params:
            if 'maxiters' in extra_params and not is_muscle5:
                cmd.extend(['-maxiters', str(extra_params['maxiters'])])
            if 'diags' in extra_params and not is_muscle5:
                cmd.append('-diags')
        
        # Run MUSCLE
        logger.info(f"Running MUSCLE: {' '.join(cmd)}")
        
        if config.USE_CONDA:
            conda_cmd = f"conda run -n {config.CONDA_ENV} {' '.join(cmd)}"
            result = subprocess.run(
                conda_cmd,
                shell=True,
                capture_output=True,
                text=True
            )
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
        
        if result.returncode != 0:
            return False, f"MUSCLE failed: {result.stderr}"
        
        return True, ""
        
    except Exception as e:
        return False, str(e)


def _calculate_alignment_stats(alignment_file: str) -> Dict:
    """Calculate statistics from alignment."""
    try:
        parsed = parse_fasta(alignment_file)
        sequences = {seq_id: seq for seq_id, _, seq in parsed}
        
        if not sequences:
            return {}
        
        # Get alignment length
        alignment_length = len(list(sequences.values())[0])
        
        # Count gaps per position
        gap_counts = [0] * alignment_length
        for seq in sequences.values():
            for i, char in enumerate(seq):
                if char in '-':
                    gap_counts[i] += 1
        
        # Calculate gap statistics
        num_seqs = len(sequences)
        gap_percentages = [(count / num_seqs) * 100 for count in gap_counts]
        
        conserved_positions = sum(1 for pct in gap_percentages if pct == 0)
        variable_positions = sum(1 for pct in gap_percentages if 0 < pct < 100)
        gap_only_positions = sum(1 for pct in gap_percentages if pct == 100)
        
        stats = {
            'num_sequences': num_seqs,
            'alignment_length': alignment_length,
            'conserved_positions': conserved_positions,
            'variable_positions': variable_positions,
            'gap_only_positions': gap_only_positions,
            'mean_gap_percentage': sum(gap_percentages) / len(gap_percentages),
            'max_gap_percentage': max(gap_percentages),
            'sequence_names': list(sequences.keys())
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Stats calculation error: {str(e)}")
        return {}


def select_sequences_interactive(
    input_file: str,
    selected_ids: List[str],
    output_file: str
) -> Tuple[bool, str]:
    """
    Select specific sequences from FASTA file.
    
    Args:
        input_file: Path to input FASTA file
        selected_ids: List of sequence IDs to keep
        output_file: Path to output FASTA file
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        sequences = parse_fasta(input_file)
        
        # Filter sequences
        selected = {seq_id: seq for seq_id, seq in sequences.items() if seq_id in selected_ids}
        
        if not selected:
            return False, "No sequences matched the selection"
        
        # Write output
        write_fasta(selected, output_file)
        
        return True, ""
        
    except Exception as e:
        return False, str(e)


def get_available_tools() -> List[str]:
    """Check which alignment tools are available."""
    tools = []
    
    for tool in ['mafft', 'clustalw', 'muscle']:
        try:
            if config.USE_CONDA:
                cmd = f"conda run -n {config.CONDA_ENV} which {tool}"
            else:
                cmd = f"which {tool}"
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                tools.append(tool)
        except:
            pass
    
    return tools
