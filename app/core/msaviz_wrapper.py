"""
pyMSAviz wrapper for alignment visualization.
Based on the original seq_aligner.py pyMSAviz functionality.
"""
import os
import subprocess
import tempfile
from datetime import datetime
from typing import Tuple, Dict, Optional, List
from app import config
from app.utils.fasta_utils import parse_fasta
import logging

logger = logging.getLogger(__name__)


def check_pymsaviz_available() -> bool:
    """Check if pyMSAviz is available."""
    try:
        if config.USE_CONDA:
            cmd = f"conda run -n {config.CONDA_ENV} python -c 'import pymsaviz'"
        else:
            cmd = "python -c 'import pymsaviz'"
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        
        return result.returncode == 0
    except:
        return False


def visualize_alignment_pymsaviz(
    alignment_file: str,
    output_format: str = 'png',
    show_count: bool = True,
    show_consensus: bool = True,
    color_scheme: str = 'Zappo',
    wrap_length: Optional[int] = None,
    dpi: int = 300
) -> Tuple[bool, str, str]:
    """
    Visualize alignment using pyMSAviz.
    
    Args:
        alignment_file: Path to alignment file (FASTA/ClustalW/PHYLIP)
        output_format: Output format ('png', 'svg', 'jpg', 'pdf')
        show_count: Show sequence count
        show_consensus: Show consensus sequence
        color_scheme: Color scheme (Zappo, Taylor, Hydrophobicity, etc.)
        wrap_length: Wrap alignment at this length (None = no wrap)
        dpi: DPI for raster outputs
        
    Returns:
        Tuple of (success, output_file, error_message)
    """
    try:
        # Create result directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_dir = os.path.join(config.RESULTS_DIR, f'msaviz_{timestamp}')
        os.makedirs(result_dir, exist_ok=True)
        
        # Output file
        base_name = os.path.splitext(os.path.basename(alignment_file))[0]
        output_file = os.path.join(result_dir, f'{base_name}_viz.{output_format}')
        
        # Generate Python script for visualization
        viz_script = _generate_viz_script(
            alignment_file, output_file, show_count, show_consensus,
            color_scheme, wrap_length, dpi
        )
        
        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(viz_script)
            script_path = f.name
        
        try:
            # Run visualization script
            if config.USE_CONDA:
                cmd = f"conda run -n {config.CONDA_ENV} python {script_path}"
            else:
                cmd = f"python {script_path}"
            
            logger.info(f"Running pyMSAviz: {cmd}")
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=result_dir
            )
            
            if result.returncode != 0:
                return False, '', f"Visualization failed: {result.stderr}"
            
            if not os.path.exists(output_file):
                return False, '', "Output file was not created"
            
            return True, output_file, ""
            
        finally:
            # Clean up temp script
            if os.path.exists(script_path):
                os.remove(script_path)
        
    except Exception as e:
        logger.error(f"pyMSAviz error: {str(e)}")
        return False, '', str(e)


def _generate_viz_script(
    alignment_file: str,
    output_file: str,
    show_count: bool,
    show_consensus: bool,
    color_scheme: str,
    wrap_length: Optional[int],
    dpi: int
) -> str:
    """Generate Python script for pyMSAviz visualization."""
    script = f"""
import sys
from pymsaviz import MsaViz

try:
    # Create visualization
    mv = MsaViz(
        '{alignment_file}',
        color_scheme='{color_scheme}',
        show_count={show_count},
        show_consensus={show_consensus}
    )
    
    # Set wrap length if specified
    {"mv.set_wrap_length(" + str(wrap_length) + ")" if wrap_length else "# No wrap"}
    
    # Save figure
    mv.savefig('{output_file}', dpi={dpi})
    
    print("Visualization created successfully")
    sys.exit(0)
    
except Exception as e:
    print(f"Error: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
"""
    return script


def get_available_color_schemes() -> List[str]:
    """Get list of available pyMSAviz color schemes."""
    return [
        'Zappo',           # Default, by physicochemical properties
        'Taylor',          # Classic Taylor color scheme
        'Hydrophobicity',  # By hydrophobicity
        'Buried_Index',    # By buried index
        'Identity',        # Single color for all
        'Clustal',         # ClustalX color scheme
        'Nucleotide',      # For DNA/RNA
    ]


def create_custom_visualization(
    alignment_file: str,
    output_file: str,
    config_dict: Dict
) -> Tuple[bool, str]:
    """
    Create custom visualization with advanced options.
    
    Args:
        alignment_file: Path to alignment file
        output_file: Path to output file
        config_dict: Dictionary with visualization config
            - color_scheme: str
            - show_count: bool
            - show_consensus: bool
            - wrap_length: int or None
            - show_grid: bool
            - show_seq_char: bool
            - consensus_threshold: float (0.0-1.0)
            
    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Generate advanced script
        script = f"""
import sys
from pymsaviz import MsaViz

try:
    mv = MsaViz(
        '{alignment_file}',
        color_scheme='{config_dict.get("color_scheme", "Zappo")}',
        show_count={config_dict.get("show_count", True)},
        show_consensus={config_dict.get("show_consensus", True)},
        show_grid={config_dict.get("show_grid", True)},
        show_seq_char={config_dict.get("show_seq_char", True)}
    )
    
    # Advanced settings
    if {config_dict.get("wrap_length")} is not None:
        mv.set_wrap_length({config_dict.get("wrap_length")})
    
    # Consensus threshold
    mv.set_consensus_threshold({config_dict.get("consensus_threshold", 0.7)})
    
    # Save
    mv.savefig('{output_file}', dpi={config_dict.get("dpi", 300)})
    
    print("Custom visualization created")
    sys.exit(0)
    
except Exception as e:
    print(f"Error: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
"""
        
        # Write and run script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script)
            script_path = f.name
        
        try:
            if config.USE_CONDA:
                cmd = f"conda run -n {config.CONDA_ENV} python {script_path}"
            else:
                cmd = f"python {script_path}"
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return False, f"Visualization failed: {result.stderr}"
            
            return True, ""
            
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)
        
    except Exception as e:
        return False, str(e)


def visualize_alignment_region(
    alignment_file: str,
    output_file: str,
    start_pos: int,
    end_pos: int,
    selected_seqs: Optional[List[str]] = None,
    color_scheme: str = 'Zappo'
) -> Tuple[bool, str]:
    """
    Visualize a specific region of alignment.
    
    Args:
        alignment_file: Path to alignment file
        output_file: Path to output file
        start_pos: Start position (1-indexed)
        end_pos: End position (1-indexed)
        selected_seqs: List of sequence IDs to include (None = all)
        color_scheme: Color scheme
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Create temporary subset alignment
        from Bio import AlignIO
        
        alignment = AlignIO.read(alignment_file, 'fasta')
        
        # Filter sequences if specified
        if selected_seqs:
            alignment = [rec for rec in alignment if rec.id in selected_seqs]
        
        # Extract region (convert to 0-indexed)
        region_alignment = alignment[:, start_pos-1:end_pos]
        
        # Write temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
            AlignIO.write(region_alignment, f, 'fasta')
            temp_file = f.name
        
        try:
            # Visualize
            success, viz_file, error = visualize_alignment_pymsaviz(
                temp_file, 
                output_format=output_file.split('.')[-1],
                color_scheme=color_scheme
            )
            
            if success:
                # Move to desired output path
                import shutil
                shutil.move(viz_file, output_file)
                return True, ""
            else:
                return False, error
                
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        
    except Exception as e:
        return False, str(e)
