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
    Returns (success, message).
    """
    try:
        input_file = sanitize_path(input_file)
        output_file = sanitize_path(output_file)
    except ValueError as e:
        return False, str(e)

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

    full_command = f"conda run -n {shlex.quote(config.CONDA_ENV)} {command} > {shlex.quote(output_file)}"

    try:
        result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=3600)
        if result.returncode == 0 and os.path.exists(output_file):
            return True, "MAFFT alignment completed"
        else:
            return False, result.stderr or "MAFFT failed"
    except Exception as e:
        return False, str(e)


def run_clustalw(input_file, output_file, options=None):
    """
    Run ClustalW alignment.
    Returns (success, message).
    """
    try:
        input_file = sanitize_path(input_file)
        output_file = sanitize_path(output_file)
    except ValueError as e:
        return False, str(e)

    command = f'clustalw -INFILE={shlex.quote(input_file)} -OUTFILE={shlex.quote(output_file)} -OUTPUT=FASTA'

    success, stdout, stderr = run_conda_command(command)

    if success:
        return True, "ClustalW alignment completed"
    else:
        return False, stderr or "ClustalW failed"


def run_muscle(input_file, output_file, options=None):
    """
    Run MUSCLE alignment.
    Returns (success, message).
    """
    try:
        input_file = sanitize_path(input_file)
        output_file = sanitize_path(output_file)
    except ValueError as e:
        return False, str(e)

    command = f'muscle -in {shlex.quote(input_file)} -out {shlex.quote(output_file)}'

    success, stdout, stderr = run_conda_command(command)

    if success:
        return True, "MUSCLE alignment completed"
    else:
        return False, stderr or "MUSCLE failed"


def run_alignment(input_file, tool='mafft', options=None):
    """
    Run sequence alignment with the specified tool.
    Returns (success, result_dir, output_file).
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
    if tool == 'mafft':
        success, message = run_mafft(input_file, output_file, options)
    elif tool == 'clustalw':
        success, message = run_clustalw(input_file, output_file, options)
    elif tool == 'muscle':
        success, message = run_muscle(input_file, output_file, options)
    else:
        return False, f"Unknown alignment tool: {tool}", None

    if success:
        logger.info(f"Alignment completed with {tool}")
        return True, result_dir, output_file
    else:
        logger.error(f"Alignment failed: {message}")
        return False, message, None


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


def generate_alignment_html(sequences, conservation=None):
    """
    Generate HTML visualization of alignment with conservation coloring.
    """
    if conservation is None:
        conservation = calculate_conservation(sequences)

    # Color scheme for conservation
    def get_color(score):
        if score >= 0.9:
            return '#ff0000'  # Red - highly conserved
        elif score >= 0.7:
            return '#ff6600'  # Orange
        elif score >= 0.5:
            return '#ffcc00'  # Yellow
        else:
            return '#ffffff'  # White - not conserved

    html = ['<div class="alignment-viewer">']
    html.append('<style>')
    html.append('.alignment-viewer { font-family: monospace; white-space: pre; }')
    html.append('.seq-id { display: inline-block; width: 200px; overflow: hidden; text-overflow: ellipsis; }')
    html.append('.seq-row { margin: 2px 0; }')
    html.append('</style>')

    for seq_id, sequence in sequences:
        html.append(f'<div class="seq-row"><span class="seq-id">{seq_id}</span>')
        for i, residue in enumerate(sequence):
            if i < len(conservation):
                color = get_color(conservation[i])
            else:
                color = '#ffffff'
            html.append(f'<span style="background-color:{color}">{residue}</span>')
        html.append('</div>')

    html.append('</div>')
    return '\n'.join(html)
