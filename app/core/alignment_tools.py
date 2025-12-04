"""
Alignment tools wrapper for BioLab Workbench.
"""
import os
import subprocess
import shlex
import re
from datetime import datetime
import config
from app.utils.logger import get_tools_logger
from app.utils.file_utils import create_result_dir, save_params

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


def run_conda_command(command, timeout=3600):
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
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, '', 'Command timed out'
    except Exception as e:
        return False, '', str(e)


def check_available_tools():
    """
    Check which alignment tools are available.
    Returns dict of tool -> available.
    """
    tools = {
        'mafft': False,
        'clustalw': False,
        'muscle': False
    }

    for tool in tools:
        try:
            success, _, _ = run_conda_command(f'{tool} --version')
            tools[tool] = success
        except Exception:
            pass

    return tools


def run_mafft(input_file, output_file, options=None):
    """
    Run MAFFT alignment.
    Returns (success, message, command).
    """
    try:
        input_file = sanitize_path(input_file)
        output_file = sanitize_path(output_file)
    except ValueError as e:
        return False, str(e), None

    if options is None:
        options = {}

    cmd_opts = []
    if options.get('maxiterate'):
        try:
            maxiterate = int(options['maxiterate'])
            cmd_opts.append(f"--maxiterate {maxiterate}")
        except (ValueError, TypeError):
            pass
    if options.get('auto'):
        cmd_opts.append('--auto')

    opts_str = ' '.join(cmd_opts)
    command = f'mafft {opts_str} {shlex.quote(input_file)}'

    # Full command for display
    full_command = f"conda run -n {config.CONDA_ENV} {command} > {shlex.quote(output_file)}"

    full_shell_command = f"conda run -n {shlex.quote(config.CONDA_ENV)} {command} > {shlex.quote(output_file)}"

    try:
        result = subprocess.run(full_shell_command, shell=True, capture_output=True, text=True, timeout=3600)
        if result.returncode == 0 and os.path.exists(output_file):
            return True, "MAFFT alignment completed", full_command
        else:
            return False, result.stderr or "MAFFT failed", full_command
    except Exception as e:
        return False, str(e), full_command


def run_clustalw(input_file, output_file, options=None):
    """
    Run ClustalW alignment.
    Returns (success, message, command).
    """
    try:
        input_file = sanitize_path(input_file)
        output_file = sanitize_path(output_file)
    except ValueError as e:
        return False, str(e), None

    command = f'clustalw -INFILE={shlex.quote(input_file)} -OUTFILE={shlex.quote(output_file)} -OUTPUT=FASTA'

    # Full command for display
    full_command = f"conda run -n {config.CONDA_ENV} {command}"

    success, stdout, stderr = run_conda_command(command)

    if success:
        return True, "ClustalW alignment completed", full_command
    else:
        return False, stderr or "ClustalW failed", full_command


def run_muscle(input_file, output_file, options=None):
    """
    Run MUSCLE alignment.
    Returns (success, message, command).
    """
    try:
        input_file = sanitize_path(input_file)
        output_file = sanitize_path(output_file)
    except ValueError as e:
        return False, str(e), None

    command = f'muscle -in {shlex.quote(input_file)} -out {shlex.quote(output_file)}'

    # Full command for display
    full_command = f"conda run -n {config.CONDA_ENV} {command}"

    success, stdout, stderr = run_conda_command(command)

    if success:
        return True, "MUSCLE alignment completed", full_command
    else:
        return False, stderr or "MUSCLE failed", full_command


def run_alignment(input_file, tool='mafft', options=None):
    """
    Run sequence alignment with the specified tool.
    Returns (success, result_dir, output_file, command).
    """
    if options is None:
        options = {}

    result_dir = create_result_dir('alignment', tool)
    output_file = os.path.join(result_dir, f'alignment.fasta')

    # Save parameters
    params = {
        'input_file': input_file,
        'tool': tool,
        'options': options,
        'timestamp': datetime.now().isoformat()
    }
    save_params(result_dir, params)

    # Run alignment
    command = None
    if tool == 'mafft':
        success, message, command = run_mafft(input_file, output_file, options)
    elif tool == 'clustalw':
        success, message, command = run_clustalw(input_file, output_file, options)
    elif tool == 'muscle':
        success, message, command = run_muscle(input_file, output_file, options)
    else:
        return False, f"Unknown alignment tool: {tool}", None, None

    if success:
        logger.info(f"Alignment completed with {tool}")
        return True, result_dir, output_file, command
    else:
        logger.error(f"Alignment failed: {message}")
        return False, message, None, command


def parse_alignment(filepath):
    """
    Parse alignment file and return sequences.
    Returns list of (id, sequence) tuples.
    """
    sequences = []
    current_id = None
    current_seq = []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if current_id is not None:
                    sequences.append((current_id, ''.join(current_seq)))
                current_id = line[1:].split()[0]
                current_seq = []
            elif line:
                current_seq.append(line)

        if current_id is not None:
            sequences.append((current_id, ''.join(current_seq)))

    return sequences


def calculate_conservation(sequences):
    """
    Calculate per-position conservation scores for an alignment.
    Returns list of conservation scores (0-1).
    """
    if not sequences:
        return []

    alignment_length = len(sequences[0][1])
    conservation = []

    for pos in range(alignment_length):
        residues = [seq[1][pos] if pos < len(seq[1]) else '-' for _, seq in sequences]

        # Remove gaps
        residues = [r for r in residues if r != '-']

        if not residues:
            conservation.append(0)
            continue

        # Calculate frequency of most common residue
        from collections import Counter
        counts = Counter(residues)
        most_common_count = counts.most_common(1)[0][1]
        score = most_common_count / len(residues)
        conservation.append(score)

    return conservation


def generate_alignment_html(sequences, conservation=None, color_mode='conservation'):
    """
    Generate HTML visualization of alignment with color coding.
    
    Args:
        sequences: List of (id, sequence) tuples
        conservation: Pre-calculated conservation scores (optional)
        color_mode: 'conservation', 'chemistry', or 'identity'
    
    Returns:
        HTML string with styled alignment
    """
    if not sequences:
        return '<div class="alert alert-warning">No sequences to display</div>'
    
    if conservation is None:
        conservation = calculate_conservation(sequences)

    alignment_length = len(sequences[0][1]) if sequences else 0
    
    # Amino acid chemistry color scheme (Clustal-like)
    aa_colors = {
        # Hydrophobic - Blue
        'A': '#80a0f0', 'I': '#80a0f0', 'L': '#80a0f0', 'M': '#80a0f0', 
        'F': '#80a0f0', 'W': '#80a0f0', 'V': '#80a0f0',
        # Positive charge - Red
        'K': '#f01505', 'R': '#f01505', 'H': '#f01505',
        # Negative charge - Magenta
        'D': '#c048c0', 'E': '#c048c0',
        # Polar - Green
        'S': '#15c015', 'T': '#15c015', 'N': '#15c015', 'Q': '#15c015',
        # Cysteine - Yellow
        'C': '#f0f000',
        # Glycine - Orange
        'G': '#f09048',
        # Proline - Yellow
        'P': '#c0c000',
        # Tyrosine - Cyan
        'Y': '#15a4a4',
        # Gaps
        '-': '#ffffff', '.': '#ffffff'
    }
    
    def get_conservation_color(score, residue):
        """Get color based on conservation score."""
        if residue in ['-', '.']:
            return '#ffffff'
        if score >= 1.0:
            return '#ff0000'  # 100% conserved - Red
        elif score >= 0.7:
            return '#ffb6c1'  # ≥70% similar - Pink
        elif score >= 0.5:
            return '#ffeb3b'  # ≥50% - Yellow
        else:
            return '#ffffff'  # White
    
    def get_residue_color(residue, conservation_score, mode):
        """Get color for a residue based on mode."""
        if mode == 'chemistry':
            return aa_colors.get(residue.upper(), '#ffffff')
        elif mode == 'conservation':
            return get_conservation_color(conservation_score, residue)
        else:  # identity
            return get_conservation_color(conservation_score, residue)
    
    # Build consensus sequence
    consensus = []
    for pos in range(alignment_length):
        residues = [seq[1][pos].upper() if pos < len(seq[1]) else '-' for _, seq in sequences]
        residues_no_gaps = [r for r in residues if r not in ['-', '.']]
        if residues_no_gaps:
            from collections import Counter
            counts = Counter(residues_no_gaps)
            most_common = counts.most_common(1)[0][0]
            freq = counts.most_common(1)[0][1] / len(residues_no_gaps)
            if freq >= 0.5:
                consensus.append(most_common if freq >= 0.7 else most_common.lower())
            else:
                consensus.append('.')
        else:
            consensus.append('-')
    
    # Generate HTML
    html = []
    html.append('<div class="alignment-container">')
    
    # Styles
    html.append('''<style>
.alignment-container { font-family: "Courier New", Consolas, monospace; font-size: 12px; overflow-x: auto; }
.alignment-block { margin-bottom: 20px; }
.seq-row { white-space: nowrap; line-height: 1.4; }
.seq-id { display: inline-block; width: 180px; overflow: hidden; text-overflow: ellipsis; font-weight: bold; color: #333; padding-right: 10px; }
.seq-data { letter-spacing: 1px; }
.seq-data span { display: inline-block; width: 12px; text-align: center; }
.ruler { color: #666; }
.ruler-tick { color: #999; }
.consensus-row { background: #f5f5f5; border-top: 1px solid #ddd; margin-top: 5px; padding-top: 5px; }
.legend { margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px; }
.legend-item { display: inline-block; margin-right: 15px; }
.legend-color { display: inline-block; width: 16px; height: 16px; margin-right: 5px; vertical-align: middle; border: 1px solid #ccc; }
</style>''')
    
    # Process in blocks of 60 characters for readability
    block_size = 60
    
    for block_start in range(0, alignment_length, block_size):
        block_end = min(block_start + block_size, alignment_length)
        
        html.append('<div class="alignment-block">')
        
        # Position ruler
        html.append('<div class="seq-row ruler">')
        html.append('<span class="seq-id"></span>')
        html.append('<span class="seq-data">')
        for pos in range(block_start, block_end):
            if (pos + 1) % 10 == 0:
                num_str = str(pos + 1)
                html.append(f'<span class="ruler-tick">{num_str[-1]}</span>')
            elif (pos + 1) % 5 == 0:
                html.append('<span class="ruler-tick">.</span>')
            else:
                html.append('<span> </span>')
        html.append('</span>')
        html.append('</div>')
        
        # Sequence rows
        for seq_id, sequence in sequences:
            html.append('<div class="seq-row">')
            html.append(f'<span class="seq-id" title="{seq_id}">{seq_id[:25]}</span>')
            html.append('<span class="seq-data">')
            
            for pos in range(block_start, block_end):
                if pos < len(sequence):
                    residue = sequence[pos]
                    cons_score = conservation[pos] if pos < len(conservation) else 0
                    color = get_residue_color(residue, cons_score, color_mode)
                    html.append(f'<span style="background-color:{color}">{residue}</span>')
                else:
                    html.append('<span>-</span>')
            
            html.append('</span>')
            html.append('</div>')
        
        # Consensus row
        html.append('<div class="seq-row consensus-row">')
        html.append('<span class="seq-id">Consensus</span>')
        html.append('<span class="seq-data">')
        for pos in range(block_start, block_end):
            if pos < len(consensus):
                html.append(f'<span>{consensus[pos]}</span>')
            else:
                html.append('<span>-</span>')
        html.append('</span>')
        html.append('</div>')
        
        html.append('</div>')
    
    # Legend
    html.append('<div class="legend">')
    html.append('<strong>Color Legend:</strong> ')
    if color_mode == 'conservation':
        html.append('<span class="legend-item"><span class="legend-color" style="background:#ff0000"></span>100% conserved</span>')
        html.append('<span class="legend-item"><span class="legend-color" style="background:#ffb6c1"></span>≥70% similar</span>')
        html.append('<span class="legend-item"><span class="legend-color" style="background:#ffeb3b"></span>≥50%</span>')
        html.append('<span class="legend-item"><span class="legend-color" style="background:#ffffff"></span>&lt;50%</span>')
    elif color_mode == 'chemistry':
        html.append('<span class="legend-item"><span class="legend-color" style="background:#80a0f0"></span>Hydrophobic</span>')
        html.append('<span class="legend-item"><span class="legend-color" style="background:#f01505"></span>Positive</span>')
        html.append('<span class="legend-item"><span class="legend-color" style="background:#c048c0"></span>Negative</span>')
        html.append('<span class="legend-item"><span class="legend-color" style="background:#15c015"></span>Polar</span>')
        html.append('<span class="legend-item"><span class="legend-color" style="background:#f0f000"></span>Cysteine</span>')
        html.append('<span class="legend-item"><span class="legend-color" style="background:#f09048"></span>Glycine</span>')
    html.append('</div>')
    
    html.append('</div>')
    
    return '\n'.join(html)


def export_alignment_html(sequences, output_file, conservation=None, color_mode='conservation'):
    """
    Export alignment visualization to an HTML file.
    
    Args:
        sequences: List of (id, sequence) tuples
        output_file: Path to output HTML file
        conservation: Pre-calculated conservation scores (optional)
        color_mode: 'conservation', 'chemistry', or 'identity'
    
    Returns:
        (success, message)
    """
    try:
        html_content = generate_alignment_html(sequences, conservation, color_mode)
        
        full_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Sequence Alignment</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .info {{ color: #666; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>Sequence Alignment Visualization</h1>
    <div class="info">
        <p>Sequences: {len(sequences)} | Alignment Length: {len(sequences[0][1]) if sequences else 0} positions</p>
        <p>Color Mode: {color_mode.capitalize()}</p>
    </div>
    {html_content}
</body>
</html>'''
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        return True, f"Alignment exported to {output_file}"
    except Exception as e:
        logger.error(f"Failed to export alignment HTML: {e}")
        return False, str(e)
