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


# Display configuration constants
MAX_SEQ_ID_DISPLAY_LENGTH = 25  # Maximum length for sequence ID display
BLOCK_SIZE = 60  # Number of residues per alignment block
SEQ_NAME_TRUNCATE_LENGTH = 22  # Maximum length for sequence name in exported HTML

# Amino acid color scheme for visualization
# Based on residue chemical properties as specified in original seq_aligner.py
AA_COLORS = {
    # Hydrophobic (A,V,L,I,M,F,W,P) - Yellow
    'A': '#f0c000', 'V': '#f0c000', 'L': '#f0c000', 'I': '#f0c000', 
    'M': '#f0c000', 'F': '#f0c000', 'W': '#f0c000', 'P': '#f0c000',
    # Polar (S,T,N,Q) - Green
    'S': '#00c000', 'T': '#00c000', 'N': '#00c000', 'Q': '#00c000',
    # Negatively charged (D,E) - Red
    'D': '#c00000', 'E': '#c00000',
    # Positively charged (K,R) - Blue
    'K': '#0000c0', 'R': '#0000c0',
    # Histidine - Light blue
    'H': '#0080c0',
    # C, G, Y - Cyan
    'C': '#00c0c0', 'G': '#00c0c0', 'Y': '#00c0c0',
    # Gap - Gray
    '-': '#e5e5e5',
}


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
        residues = [sequence[pos].upper() if pos < len(sequence) else '-' for _, sequence in sequences]
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
            display_id = seq_id[:MAX_SEQ_ID_DISPLAY_LENGTH] if len(seq_id) > MAX_SEQ_ID_DISPLAY_LENGTH else seq_id
            html.append(f'<span class="seq-id" title="{seq_id}">{display_id}</span>')
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
    Generates a complete, standalone HTML file with embedded styling.
    Based on the original seq_aligner.py export_html_visualization implementation.
    
    Args:
        sequences: List of (id, sequence) tuples
        output_file: Path to output HTML file
        conservation: Pre-calculated conservation scores (optional)
        color_mode: 'conservation', 'chemistry', or 'identity'
    
    Returns:
        (success, message)
    """
    try:
        if not sequences:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('<html><body><p>No sequences to display</p></body></html>')
            return True, "Empty alignment exported"
        
        # Convert sequences to dictionary format for processing
        sequences_dict = {name: seq for name, seq in sequences}
        names = list(sequences_dict.keys())
        seqs = list(sequences_dict.values())
        seq_len = len(seqs[0]) if seqs else 0
        
        # Use module-level amino acid colors constant
        colors = AA_COLORS
        
        def get_conservation(pos):
            """Calculate conservation at a position."""
            bases = [s[pos].upper() for s in seqs if pos < len(s)]
            if not bases:
                return 0, '-'
            most_common = max(set(bases), key=bases.count)
            ratio = bases.count(most_common) / len(bases)
            return ratio, most_common
        
        # Build HTML
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Alignment Visualization</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: Consolas, Monaco, 'Courier New', monospace;
            background: #f5f5f5; 
            padding: 20px;
            font-size: 13px;
        }}
        .header {{
            background: linear-gradient(135deg, #1e3a5f, #2d5a87);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
        .stats {{ display: flex; gap: 20px; margin-top: 15px; }}
        .stat {{ background: rgba(255,255,255,0.1); padding: 8px 15px; border-radius: 4px; }}
        .alignment-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            overflow-x: auto;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .block {{ margin-bottom: 30px; }}
        .seq-row {{
            display: flex;
            align-items: center;
            height: 22px;
            white-space: nowrap;
        }}
        .seq-name {{
            display: inline-block;
            width: 200px;
            min-width: 200px;
            max-width: 200px;
            padding-right: 15px;
            text-align: right;
            font-weight: bold;
            color: #333;
            overflow: hidden;
            text-overflow: ellipsis;
            border-right: 2px solid #ccc;
            margin-right: 10px;
        }}
        .seq-data {{
            display: flex;
        }}
        .base {{
            display: inline-block;
            width: 14px;
            height: 18px;
            text-align: center;
            line-height: 18px;
            margin: 0;
            font-size: 12px;
        }}
        .conserved {{
            background: #c00000 !important;
            color: white !important;
            font-weight: bold;
        }}
        .similar {{
            background: #ffcccc !important;
            color: #800000 !important;
        }}
        .position-row {{
            color: #888;
            font-size: 11px;
            border-bottom: 1px solid #ddd;
            margin-bottom: 5px;
            padding-bottom: 3px;
        }}
        .consensus-row {{
            border-top: 1px solid #eee;
            margin-top: 5px;
            padding-top: 5px;
        }}
        .consensus-name {{
            color: #888;
            font-style: italic;
            font-weight: normal;
        }}
        .legend {{
            margin-top: 20px;
            padding: 15px;
            background: #fafafa;
            border-radius: 8px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .legend-title {{ width: 100%; font-weight: bold; margin-bottom: 5px; }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; padding: 3px 8px; background: white; border-radius: 4px; }}
        .legend-color {{ width: 20px; height: 20px; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧬 Sequence Alignment Visualization</h1>
        <div class="stats">
            <div class="stat">📊 Sequences: {len(names)}</div>
            <div class="stat">📏 Length: {seq_len}</div>
            <div class="stat">🎨 Color Mode: {color_mode.capitalize()}</div>
        </div>
    </div>
    <div class="alignment-container">
'''
        
        for start in range(0, seq_len, BLOCK_SIZE):
            end = min(start + BLOCK_SIZE, seq_len)
            
            # Position ruler
            ruler_html = '<div class="seq-row position-row"><span class="seq-name"></span><span class="seq-data">'
            for i in range(start, end):
                if (i + 1) % 10 == 0:
                    ruler_html += f'<span class="base" style="font-weight:bold">{i+1}</span>'
                else:
                    ruler_html += '<span class="base">·</span>'
            ruler_html += '</span></div>'
            
            html += f'<div class="block">\n{ruler_html}\n'
            
            # Sequence rows
            for name, seq in zip(names, seqs):
                segment = seq[start:end] if start < len(seq) else ''
                display_name = name[:SEQ_NAME_TRUNCATE_LENGTH] if len(name) > SEQ_NAME_TRUNCATE_LENGTH else name
                
                html += f'<div class="seq-row"><span class="seq-name" title="{name}">{display_name}</span><span class="seq-data">'
                
                for i, base in enumerate(segment):
                    pos = start + i
                    cons_ratio, most_common = get_conservation(pos)
                    base_upper = base.upper()
                    
                    if cons_ratio == 1.0 and base != '-':
                        css_class = "base conserved"
                        style = ""
                    elif cons_ratio >= 0.7 and base_upper == most_common:
                        css_class = "base similar"
                        style = ""
                    else:
                        css_class = "base"
                        color = colors.get(base_upper, '#fff')
                        style = f'style="background:{color}"'
                    
                    html += f'<span class="{css_class}" {style}>{base}</span>'
                
                html += '</span></div>\n'
            
            # Consensus row
            html += '<div class="seq-row consensus-row"><span class="seq-name consensus-name">consensus</span><span class="seq-data">'
            for i in range(start, end):
                if i < seq_len:
                    cons_ratio, most_common = get_conservation(i)
                    if cons_ratio == 1.0 and most_common != '-':
                        html += '<span class="base" style="color:#c00000;font-weight:bold">*</span>'
                    elif cons_ratio >= 0.7:
                        html += '<span class="base" style="color:#888">:</span>'
                    elif cons_ratio >= 0.5:
                        html += '<span class="base" style="color:#ccc">.</span>'
                    else:
                        html += '<span class="base"> </span>'
            html += '</span></div>\n</div>\n'
        
        html += '''
    </div>
    <div class="legend">
        <div class="legend-title">📖 Legend</div>
        <div class="legend-item"><div class="legend-color" style="background:#c00000"></div> 100% conserved</div>
        <div class="legend-item"><div class="legend-color" style="background:#ffcccc"></div> ≥70% similar</div>
        <div class="legend-item"><div class="legend-color" style="background:#f0c000"></div> Hydrophobic</div>
        <div class="legend-item"><div class="legend-color" style="background:#00c000"></div> Polar</div>
        <div class="legend-item"><div class="legend-color" style="background:#0000c0"></div> Positive</div>
        <div class="legend-item"><div class="legend-color" style="background:#c00000;opacity:0.7"></div> Negative</div>
    </div>
</body>
</html>'''
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return True, f"Alignment exported to {output_file}"
    except Exception as e:
        logger.error(f"Failed to export alignment HTML: {e}")
        return False, str(e)


def check_pymsaviz_available():
    """
    Check if pymsaviz is available for import.
    
    Returns:
        bool: True if pymsaviz is available
    """
    try:
        from pymsaviz import MsaViz
        return True
    except ImportError:
        return False


def visualize_alignment_pymsaviz(fasta_path, output_path, output_format='pdf', 
                                  wrap_length=80, show_count=True, dpi=150):
    """
    Generate alignment visualization using pymsaviz.
    
    This produces high-quality, publication-ready alignment figures with
    conservancy coloring similar to standard alignment viewers.
    
    Args:
        fasta_path: Path to aligned FASTA file
        output_path: Output file path (without extension)
        output_format: 'pdf', 'png', or 'svg'
        wrap_length: Number of residues per line (default: 80)
        show_count: Show position count (default: True)
        dpi: Resolution for PNG output (default: 150)
    
    Returns:
        (success, output_file_path, message)
    """
    if not check_pymsaviz_available():
        logger.warning("pymsaviz not available, falling back to HTML visualization")
        return False, None, "pymsaviz not installed. Install with: pip install pymsaviz"
    
    try:
        from pymsaviz import MsaViz
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Generate output filename with extension
        if not output_path.endswith(f'.{output_format}'):
            output_file = f"{output_path}.{output_format}"
        else:
            output_file = output_path
        
        logger.info(f"Generating pymsaviz visualization: {output_file}")
        
        # Create visualization
        mv = MsaViz(fasta_path, wrap_length=wrap_length, show_count=show_count)
        mv.savefig(output_file, dpi=dpi)
        
        logger.info(f"Visualization saved: {output_file}")
        return True, output_file, f"Visualization saved to {output_file}"
        
    except Exception as e:
        logger.error(f"pymsaviz visualization failed: {e}")
        return False, None, f"Visualization failed: {str(e)}"


def export_alignment_visualization(sequences, output_dir, base_name, 
                                   output_format='pdf', color_mode='conservation'):
    """
    Export alignment visualization to file.
    
    Attempts to use pymsaviz for PDF/PNG output, falls back to HTML.
    
    Args:
        sequences: List of (id, sequence) tuples
        output_dir: Directory to save output
        base_name: Base filename (without extension)
        output_format: 'pdf', 'png', 'svg', or 'html'
        color_mode: 'conservation', 'chemistry', or 'identity'
    
    Returns:
        (success, output_file, message)
    """
    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # For HTML output, use native HTML export
    if output_format == 'html':
        output_file = os.path.join(output_dir, f"{base_name}.html")
        success, message = export_alignment_html(sequences, output_file, color_mode=color_mode)
        return success, output_file if success else None, message
    
    # For PDF/PNG/SVG, try pymsaviz first
    if output_format in ['pdf', 'png', 'svg']:
        # First, write sequences to temporary FASTA file
        temp_fasta = os.path.join(output_dir, f"{base_name}_temp.fasta")
        try:
            with open(temp_fasta, 'w', encoding='utf-8') as f:
                for seq_id, seq in sequences:
                    f.write(f">{seq_id}\n")
                    for i in range(0, len(seq), 60):
                        f.write(seq[i:i+60] + '\n')
            
            output_file = os.path.join(output_dir, f"{base_name}.{output_format}")
            success, result_file, message = visualize_alignment_pymsaviz(
                temp_fasta, output_file, output_format
            )
            
            # Clean up temp file
            try:
                os.remove(temp_fasta)
            except OSError:
                pass
            
            if success:
                return True, result_file, message
            else:
                # Fall back to HTML
                logger.info("Falling back to HTML visualization")
                html_file = os.path.join(output_dir, f"{base_name}.html")
                html_success, html_message = export_alignment_html(sequences, html_file, color_mode=color_mode)
                return html_success, html_file if html_success else None, html_message
                
        except Exception as e:
            # Clean up on error
            try:
                os.remove(temp_fasta)
            except OSError:
                pass
            logger.error(f"Visualization export failed: {e}")
            return False, None, str(e)
    
    return False, None, f"Unsupported output format: {output_format}"
