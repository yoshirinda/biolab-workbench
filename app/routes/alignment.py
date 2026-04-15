"""
Alignment routes for BioLab Workbench.
"""
import os
from flask import Blueprint, render_template, request, jsonify, send_file
import config
from app.core.alignment_tools import (
    check_available_tools, run_alignment, parse_alignment,
    calculate_conservation, generate_alignment_html, export_alignment_html,
    check_pymsaviz_available, export_alignment_visualization
)
from app.core.alignment_wrapper import (
    run_alignment as run_multi_tool_alignment,
    select_sequences_interactive,
    get_available_tools
)
from app.core.msaviz_wrapper import (
    check_pymsaviz_available as check_pymsaviz,
    visualize_alignment_pymsaviz,
    get_available_color_schemes,
    create_custom_visualization,
    visualize_alignment_region
)
from app.utils.file_utils import save_uploaded_file, write_result_manifest
from app.utils.fasta_utils import parse_fasta as parse_fasta_records
from app.core.sequence_utils import detect_sequence_type
from app.utils.logger import get_app_logger

alignment_bp = Blueprint('alignment', __name__)
logger = get_app_logger()

VALID_ALIGNMENT_TOOLS = {'mafft', 'clustalw', 'muscle'}
VALID_ALIGNMENT_FORMATS = {'fasta', 'clustal', 'phylip'}
VALID_ALIGNMENT_COLOR_MODES = {'conservation', 'chemistry', 'identity'}
MAFFT_HIGH_ACCURACY_ALGORITHMS = {'linsi', 'ginsi', 'einsi'}
CLUSTALW_PROTEIN_MATRICES = {'BLOSUM', 'PAM', 'GONNET', 'ID'}
CLUSTALW_DNA_MATRICES = {'IUB', 'CLUSTALW'}


def _parse_int(raw, field_name, minimum=None, maximum=None, default=None):
    if raw in (None, ''):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {field_name}: must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"Invalid {field_name}: must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"Invalid {field_name}: must be <= {maximum}")
    return value


def _parse_float(raw, field_name, minimum=None, maximum=None, default=None):
    if raw in (None, ''):
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {field_name}: must be a number")
    if minimum is not None and value < minimum:
        raise ValueError(f"Invalid {field_name}: must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"Invalid {field_name}: must be <= {maximum}")
    return value


def _collect_alignment_input_stats(input_file):
    sequences = parse_fasta_records(input_file)
    lengths = [len(seq or '') for _, _, seq in sequences]
    type_counts = {'nucleotide': 0, 'protein': 0}
    for _, _, seq in sequences:
        clean_seq = str(seq or '').replace('-', '').strip()
        if not clean_seq:
            continue
        seq_type = detect_sequence_type(clean_seq)
        if seq_type in type_counts:
            type_counts[seq_type] += 1

    non_zero_types = [seq_type for seq_type, count in type_counts.items() if count > 0]
    if len(non_zero_types) == 1:
        sequence_type = non_zero_types[0]
    elif len(non_zero_types) > 1:
        sequence_type = 'mixed'
    else:
        sequence_type = 'unknown'
    return {
        'sequence_count': len(sequences),
        'max_length': max(lengths) if lengths else 0,
        'mean_length': (sum(lengths) / len(lengths)) if lengths else 0.0,
        'sequence_type': sequence_type,
        'type_counts': type_counts,
    }


def _validate_alignment_input_compatibility(tool, input_stats, extra_params):
    sequence_type = str((input_stats or {}).get('sequence_type') or 'unknown').lower()
    if sequence_type == 'mixed':
        raise ValueError(
            'Detected a mixture of nucleotide and protein sequences in one alignment job. '
            'Split DNA and protein inputs before alignment.'
        )

    if tool != 'clustalw':
        return sequence_type

    matrix = str((extra_params or {}).get('matrix') or '').upper().strip()
    if not matrix:
        return sequence_type

    if sequence_type == 'nucleotide' and matrix not in CLUSTALW_DNA_MATRICES:
        raise ValueError(
            f'ClustalW DNA alignments must use DNA matrices ({", ".join(sorted(CLUSTALW_DNA_MATRICES))}), '
            f'not {matrix}.'
        )

    if sequence_type == 'protein' and matrix not in CLUSTALW_PROTEIN_MATRICES:
        raise ValueError(
            f'ClustalW protein alignments must use protein matrices ({", ".join(sorted(CLUSTALW_PROTEIN_MATRICES))}), '
            f'not {matrix}.'
        )

    return sequence_type


def _default_clustalw_matrix(sequence_type):
    return 'IUB' if str(sequence_type or '').lower() == 'nucleotide' else 'BLOSUM'


def _normalize_alignment_color_mode(sequence_type, color_mode):
    normalized_mode = str(color_mode or 'conservation').strip().lower() or 'conservation'
    if normalized_mode not in VALID_ALIGNMENT_COLOR_MODES:
        raise ValueError(f"Invalid color_mode: {normalized_mode}")

    warnings = []
    effective_mode = normalized_mode
    if str(sequence_type or '').lower() == 'nucleotide' and normalized_mode == 'chemistry':
        effective_mode = 'conservation'
        warnings.append(
            'Chemistry color mode is amino-acid oriented. Nucleotide alignments were rendered in conservation mode instead.'
        )

    return effective_mode, warnings


def _build_alignment_warnings(tool, extra_params, input_stats):
    warnings = []
    if (input_stats or {}).get('sequence_count', 0) < 2:
        return warnings

    sequence_type = str((input_stats or {}).get('sequence_type') or 'unknown').lower()
    if tool == 'mafft':
        algorithm = str((extra_params or {}).get('algorithm') or 'auto').lower()
        seq_count = input_stats.get('sequence_count', 0)
        max_length = input_stats.get('max_length', 0)
        if algorithm in MAFFT_HIGH_ACCURACY_ALGORITHMS and (seq_count > 200 or max_length > 2000):
            warnings.append(
                f'MAFFT {algorithm} is intended for high-accuracy runs on roughly <=200 sequences and <=2000 residues; '
                'consider Auto for larger datasets.'
            )
    elif tool == 'clustalw':
        if (input_stats or {}).get('sequence_count', 0) > 500:
            warnings.append('ClustalW can become slow on large datasets; MAFFT Auto is usually a better default for large alignments.')
        matrix = str((extra_params or {}).get('matrix') or '').upper().strip()
        if sequence_type == 'nucleotide' and matrix:
            warnings.append(f'ClustalW will treat this dataset as DNA and use -DNAMATRIX={matrix}.')
        elif sequence_type == 'protein' and matrix:
            warnings.append(f'ClustalW will treat this dataset as protein and use -MATRIX={matrix}.')

    return warnings


@alignment_bp.route('/')
def alignment_page():
    """Render the alignment page."""
    force_refresh = request.args.get('refresh') == '1'
    tools = check_available_tools(force=force_refresh)
    return render_template('alignment.html', available_tools=tools, has_any_tool=any(tools.values()))


@alignment_bp.route('/tools')
def get_tools():
    """Get list of available alignment tools."""
    try:
        force_refresh = request.args.get('refresh') == '1'
        tools = check_available_tools(force=force_refresh)
        return jsonify({'success': True, 'tools': tools})
    except Exception as e:
        logger.error(f"Tool check error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@alignment_bp.route('/run', methods=['POST'])
def run():
    """Run sequence alignment."""
    try:
        # Get input sequences
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            input_file = save_uploaded_file(file)
        elif request.form.get('sequences'):
            # Save sequences to temp file
            import tempfile
            sequences = request.form.get('sequences')
            with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta',
                                            delete=False, dir=config.UPLOADS_DIR) as f:
                f.write(sequences)
                input_file = f.name
        else:
            return jsonify({'success': False, 'error': 'No sequences provided'})

        input_stats = _collect_alignment_input_stats(input_file)
        if input_stats['sequence_count'] < 2:
            return jsonify({'success': False, 'error': 'At least two FASTA sequences are required for multiple sequence alignment.'}), 400

        tool = request.form.get('tool', 'mafft')
        requested_color_mode = request.form.get('color_mode', 'conservation')
        tool = (tool or 'mafft').lower()
        if tool not in VALID_ALIGNMENT_TOOLS:
            return jsonify({'success': False, 'error': f'Invalid tool: {tool}'}), 400
        available_tools = check_available_tools()
        if not available_tools.get(tool):
            return jsonify({
                'success': False,
                'error': (
                    f'{tool} is not available in the current runtime. '
                    'Install/activate the tool and open /alignment/?refresh=1 to re-check.'
                )
            }), 400

        # Get tool options
        options = {}
        try:
            if request.form.get('maxiterate'):
                options['maxiterate'] = _parse_int(
                    request.form.get('maxiterate'),
                    'maxiterate',
                    minimum=1,
                    maximum=100000
                )
            if request.form.get('auto'):
                options['auto'] = True
            if request.form.get('algorithm'):
                algorithm = request.form.get('algorithm')
                if algorithm not in {'auto', 'linsi', 'ginsi', 'einsi'}:
                    return jsonify({'success': False, 'error': 'Invalid algorithm'}), 400
                options['algorithm'] = algorithm
            if request.form.get('matrix'):
                matrix = request.form.get('matrix')
                if matrix not in CLUSTALW_PROTEIN_MATRICES.union(CLUSTALW_DNA_MATRICES):
                    return jsonify({'success': False, 'error': 'Invalid matrix'}), 400
                options['matrix'] = matrix
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        try:
            options['sequence_type'] = _validate_alignment_input_compatibility(tool, input_stats, options)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        warnings = _build_alignment_warnings(tool, options, input_stats)
        try:
            effective_color_mode, color_mode_warnings = _normalize_alignment_color_mode(
                input_stats.get('sequence_type'),
                requested_color_mode
            )
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        warnings.extend(color_mode_warnings)

        success, result_dir, output_file, stats = run_alignment(input_file, tool, options)

        if success:
            # Parse alignment for visualization
            sequences = parse_alignment(output_file)
            conservation = calculate_conservation(sequences)
            html_view = generate_alignment_html(sequences, conservation, effective_color_mode)
            
            # Also export HTML visualization file
            html_output = os.path.join(result_dir, 'alignment_visualization.html')
            export_alignment_html(sequences, html_output, conservation, effective_color_mode)

            try:
                write_result_manifest(
                    result_dir=result_dir,
                    domain='alignment',
                    action='run',
                    input_files={'input_file': input_file},
                    output_files={
                        'alignment_file': output_file,
                        'html_visualization': html_output
                    },
                    params={
                        'tool': tool,
                        'color_mode': effective_color_mode,
                        'requested_color_mode': requested_color_mode,
                        'options': options
                    },
                    commands=[stats.get('command', '')] if stats.get('command') else [],
                    tools=[tool]
                )
            except Exception as manifest_error:
                logger.warning(f"Failed to write alignment manifest: {manifest_error}")

            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'output_file': output_file,
                'html_file': html_output,
                'alignment_html': html_view,
                'sequence_count': len(sequences),
                'alignment_length': len(sequences[0][1]) if sequences else 0,
                'tool': tool,
                'command': stats.get('command', ''),
                'stats': stats,
                'warnings': warnings,
                'input_stats': input_stats,
                'requested_color_mode': requested_color_mode,
                'effective_color_mode': effective_color_mode
            })
        else:
            return jsonify({'success': False, 'error': result_dir, 'command': stats.get('command', '')})

    except Exception as e:
        logger.error(f"Alignment error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@alignment_bp.route('/download')
def download():
    """Download a result file."""
    try:
        from urllib.parse import unquote
        
        # Get filepath from query parameter instead of path
        filepath = request.args.get('path', '')
        if not filepath:
            logger.warning("Download attempt without path parameter")
            return jsonify({'success': False, 'error': 'No file path provided'}), 400
        
        # URL decode the filepath
        filepath = unquote(filepath)
        
        # Handle both absolute and relative paths
        if not os.path.isabs(filepath):
            abs_path = os.path.join(config.RESULTS_DIR, filepath)
        else:
            abs_path = filepath
        
        abs_path = os.path.abspath(abs_path)
        results_dir = os.path.abspath(config.RESULTS_DIR)
        uploads_dir = os.path.abspath(config.UPLOADS_DIR)
        
        # Security: Ensure the file is within allowed directories
        if not (abs_path.startswith(results_dir) or abs_path.startswith(uploads_dir)):
            logger.warning(f"Attempted path traversal: {filepath}")
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        if os.path.exists(abs_path):
            # Determine MIME type and whether to force download
            filename = os.path.basename(abs_path)
            mimetype = None
            force_download = True
            if filename.endswith(('.fasta', '.fa', '.aln', '.txt', '.log')):
                mimetype = 'text/plain'
            elif filename.endswith('.json'):
                mimetype = 'application/json'
            elif filename.endswith('.html'):
                mimetype = 'text/html'
                force_download = False  # allow inline render for iframe

            logger.info(f"Downloading file: {abs_path} (as_attachment={force_download})")
            return send_file(
                abs_path,
                as_attachment=force_download,
                download_name=filename,
                mimetype=mimetype
            )
        else:
            logger.error(f"File not found: {abs_path}")
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@alignment_bp.route('/download/<path:filepath>')
def download_legacy(filepath):
    """Legacy download route - redirects to query parameter version."""
    try:
        from urllib.parse import unquote
        
        # URL decode the filepath for port-forwarding scenarios
        filepath = unquote(filepath)
        
        # Handle both absolute and relative paths
        # If relative, join with RESULTS_DIR
        if not os.path.isabs(filepath):
            abs_path = os.path.join(config.RESULTS_DIR, filepath)
        else:
            abs_path = filepath
        
        abs_path = os.path.abspath(abs_path)
        results_dir = os.path.abspath(config.RESULTS_DIR)
        uploads_dir = os.path.abspath(config.UPLOADS_DIR)
        
        # Security: Ensure the file is within allowed directories
        # Only allow downloads from results or uploads directories
        if not (abs_path.startswith(results_dir + os.sep) or 
                abs_path.startswith(uploads_dir + os.sep)):
            logger.warning(f"Attempted path traversal: {filepath}")
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        if os.path.exists(abs_path):
            # Determine MIME type and whether to force download
            filename = os.path.basename(abs_path)
            mimetype = None
            force_download = True
            if filename.endswith(('.fasta', '.fa', '.aln', '.txt', '.log')):
                mimetype = 'text/plain'
            elif filename.endswith('.json'):
                mimetype = 'application/json'
            elif filename.endswith('.html'):
                mimetype = 'text/html'
                force_download = False
            
            return send_file(
                abs_path, 
                as_attachment=force_download,
                download_name=filename,
                mimetype=mimetype
            )
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@alignment_bp.route('/check-pymsaviz')
def check_pymsaviz():
    """Check if pymsaviz is available."""
    try:
        available = check_pymsaviz_available()
        return jsonify({
            'success': True,
            'available': available
        })
    except Exception as e:
        logger.error(f"pymsaviz check error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@alignment_bp.route('/visualize', methods=['POST'])
def visualize():
    """
    Generate alignment visualization.
    
    Supports PDF, PNG, SVG, and HTML output formats.
    Uses pymsaviz for PDF/PNG/SVG when available, falls back to HTML.
    """
    try:
        # Get input - either from file or result directory
        result_dir = request.form.get('result_dir')
        output_format = request.form.get('format', 'pdf')
        color_mode = request.form.get('color_mode', 'conservation')
        
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            input_file = save_uploaded_file(file)
        elif result_dir:
            # Look for alignment file in result directory
            alignment_file = os.path.join(result_dir, 'alignment.fasta')
            if not os.path.exists(alignment_file):
                return jsonify({'success': False, 'error': 'Alignment file not found'})
            input_file = alignment_file
        else:
            return jsonify({'success': False, 'error': 'No alignment file provided'})
        
        # Parse alignment
        sequences = parse_alignment(input_file)
        if not sequences:
            return jsonify({'success': False, 'error': 'No sequences found in alignment file'})

        sequence_types = set()
        for _, seq in sequences:
            clean_seq = str(seq or '').replace('-', '').replace('.', '').strip()
            if not clean_seq:
                continue
            sequence_types.add(detect_sequence_type(clean_seq))
        sequence_type = 'mixed' if len(sequence_types) > 1 else (next(iter(sequence_types)) if sequence_types else 'unknown')
        try:
            effective_color_mode, color_mode_warnings = _normalize_alignment_color_mode(sequence_type, color_mode)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        
        # Generate visualization
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_dir = os.path.dirname(input_file) or config.RESULTS_DIR
        
        success, output_file, message = export_alignment_visualization(
            sequences, output_dir, f"{base_name}_viz", 
            output_format=output_format, color_mode=effective_color_mode
        )
        
        if success:
            return jsonify({
                'success': True,
                'output_file': output_file,
                'format': output_format,
                'message': message,
                'pymsaviz_used': check_pymsaviz_available() and output_format != 'html',
                'requested_color_mode': color_mode,
                'effective_color_mode': effective_color_mode,
                'warnings': color_mode_warnings
            })
        else:
            return jsonify({'success': False, 'error': message})
    
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


# New enhanced endpoints

@alignment_bp.route('/align-multi', methods=['POST'])
def align_multi():
    """Run alignment with ClustalW/MUSCLE/MAFFT support."""
    try:
        file_path = request.form.get('file_path') or request.form.get('input_path')

        if file_path and os.path.exists(file_path):
            input_file = file_path
        elif 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            input_file = save_uploaded_file(file)
        else:
            return jsonify({'success': False, 'error': 'No file uploaded or path provided'})

        input_stats = _collect_alignment_input_stats(input_file)
        if input_stats['sequence_count'] < 2:
            return jsonify({'success': False, 'error': 'At least two FASTA sequences are required for multiple sequence alignment.'}), 400
        
        # Parameters
        try:
            tool = request.form.get('tool', 'mafft').lower()
            output_format = request.form.get('output_format', 'fasta').lower()
            if tool not in VALID_ALIGNMENT_TOOLS:
                return jsonify({'success': False, 'error': f'Invalid tool: {tool}'}), 400
            if output_format not in VALID_ALIGNMENT_FORMATS:
                return jsonify({'success': False, 'error': f'Invalid output_format: {output_format}'}), 400

            threads = _parse_int(request.form.get('threads', 4), 'threads', minimum=1, maximum=128, default=4)

            # Tool-specific parameters
            extra_params = {}
            if tool == 'mafft':
                algorithm = request.form.get('mafft_algorithm', 'auto')
                if algorithm not in {'auto', 'linsi', 'ginsi', 'einsi'}:
                    return jsonify({'success': False, 'error': 'Invalid mafft_algorithm'}), 400
                extra_params['algorithm'] = algorithm
                extra_params['adjustdirection'] = request.form.get('adjustdirection', 'false') == 'true'
                extra_params['maxiterate'] = _parse_int(
                    request.form.get('maxiterate', 1000),
                    'maxiterate',
                    minimum=1,
                    maximum=100000,
                    default=1000
                )
            elif tool == 'clustalw':
                default_matrix = _default_clustalw_matrix(input_stats.get('sequence_type'))
                extra_params['gapopen'] = _parse_float(
                    request.form.get('gapopen', 10.0),
                    'gapopen',
                    minimum=0,
                    maximum=1000,
                    default=10.0
                )
                extra_params['gapext'] = _parse_float(
                    request.form.get('gapext', 0.2),
                    'gapext',
                    minimum=0,
                    maximum=1000,
                    default=0.2
                )
                matrix = request.form.get('matrix', default_matrix)
                if matrix not in CLUSTALW_PROTEIN_MATRICES.union(CLUSTALW_DNA_MATRICES):
                    return jsonify({'success': False, 'error': 'Invalid matrix'}), 400
                extra_params['matrix'] = matrix
            elif tool == 'muscle':
                extra_params['maxiters'] = _parse_int(
                    request.form.get('maxiters', 16),
                    'maxiters',
                    minimum=1,
                    maximum=100000,
                    default=16
                )
                extra_params['diags'] = request.form.get('diags', 'false') == 'true'
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        try:
            extra_params['sequence_type'] = _validate_alignment_input_compatibility(tool, input_stats, extra_params)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        warnings = _build_alignment_warnings(tool, extra_params, input_stats)

        # Run alignment
        success, result_dir, output_file, stats = run_multi_tool_alignment(
            input_file, tool, output_format, threads, extra_params
        )
        
        if success:
            try:
                write_result_manifest(
                    result_dir=result_dir,
                    domain='alignment',
                    action='align-multi',
                    input_files={'input_file': input_file},
                    output_files={'alignment_file': output_file},
                    params={
                        'tool': tool,
                        'output_format': output_format,
                        'threads': threads,
                        'extra_params': extra_params
                    },
                    commands=[stats.get('command', '')] if stats.get('command') else [],
                    tools=[tool]
                )
            except Exception as manifest_error:
                logger.warning(f"Failed to write alignment manifest: {manifest_error}")

            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'output_file': output_file,
                'stats': stats,
                'command': stats.get('command', ''),
                'warnings': warnings,
                'input_stats': input_stats
            })
        else:
            return jsonify({'success': False, 'error': stats.get('error', 'Unknown error')})
    
    except Exception as e:
        logger.error(f"Multi-tool alignment error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@alignment_bp.route('/select-sequences', methods=['POST'])
def select_sequences():
    """Select specific sequences from FASTA file."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['file']
        input_file = save_uploaded_file(file)
        
        # Get selected IDs
        selected_ids = request.form.getlist('selected_ids[]')
        if not selected_ids:
            return jsonify({'success': False, 'error': 'No sequences selected'})
        
        # Create output file
        output_file = os.path.join(
            os.path.dirname(input_file),
            'selected_' + os.path.basename(input_file)
        )
        
        success, error_msg = select_sequences_interactive(input_file, selected_ids, output_file)
        
        if success:
            return jsonify({
                'success': True,
                'output_file': output_file,
                'num_selected': len(selected_ids)
            })
        else:
            return jsonify({'success': False, 'error': error_msg})
    
    except Exception as e:
        logger.error(f"Sequence selection error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@alignment_bp.route('/tools-check', methods=['GET'])
def tools_check():
    """Check which alignment tools are available."""
    try:
        available = get_available_tools()
        return jsonify({
            'success': True,
            'available_tools': available
        })
    except Exception as e:
        logger.error(f"Tools check error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@alignment_bp.route('/visualize-pymsaviz', methods=['POST'])
def visualize_pymsaviz():
    """Visualize alignment using pyMSAviz."""
    try:
        if not check_pymsaviz():
            return jsonify({
                'success': False, 
                'error': 'pyMSAviz is not available. Install it with: pip install pymsaviz'
            })
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['file']
        input_file = save_uploaded_file(file)
        
        # Parameters
        output_format = request.form.get('output_format', 'png')
        show_count = request.form.get('show_count', 'true') == 'true'
        show_consensus = request.form.get('show_consensus', 'true') == 'true'
        color_scheme = request.form.get('color_scheme', 'Zappo')
        wrap_length = request.form.get('wrap_length')
        if wrap_length:
            wrap_length = int(wrap_length)
        dpi = int(request.form.get('dpi', 300))
        
        # Generate visualization
        success, output_file, error_msg = visualize_alignment_pymsaviz(
            input_file, output_format, show_count, show_consensus,
            color_scheme, wrap_length, dpi
        )
        
        if success:
            return jsonify({
                'success': True,
                'output_file': output_file,
                'format': output_format
            })
        else:
            return jsonify({'success': False, 'error': error_msg})
    
    except Exception as e:
        logger.error(f"pyMSAviz visualization error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@alignment_bp.route('/pymsaviz-color-schemes', methods=['GET'])
def pymsaviz_color_schemes():
    """Get available pyMSAviz color schemes."""
    try:
        schemes = get_available_color_schemes()
        return jsonify({
            'success': True,
            'color_schemes': schemes
        })
    except Exception as e:
        logger.error(f"Color schemes error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@alignment_bp.route('/visualize-custom', methods=['POST'])
def visualize_custom():
    """Create custom alignment visualization."""
    try:
        if not check_pymsaviz():
            return jsonify({
                'success': False, 
                'error': 'pyMSAviz is not available'
            })
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['file']
        input_file = save_uploaded_file(file)
        
        # Get custom config
        config_dict = {
            'color_scheme': request.form.get('color_scheme', 'Zappo'),
            'show_count': request.form.get('show_count', 'true') == 'true',
            'show_consensus': request.form.get('show_consensus', 'true') == 'true',
            'show_grid': request.form.get('show_grid', 'true') == 'true',
            'show_seq_char': request.form.get('show_seq_char', 'true') == 'true',
            'wrap_length': None,
            'consensus_threshold': float(request.form.get('consensus_threshold', 0.7)),
            'dpi': int(request.form.get('dpi', 300))
        }
        
        if request.form.get('wrap_length'):
            config_dict['wrap_length'] = int(request.form.get('wrap_length'))
        
        # Output file
        output_format = request.form.get('output_format', 'png')
        output_file = os.path.join(
            os.path.dirname(input_file),
            f'custom_viz.{output_format}'
        )
        
        success, error_msg = create_custom_visualization(
            input_file, output_file, config_dict
        )
        
        if success:
            return jsonify({
                'success': True,
                'output_file': output_file
            })
        else:
            return jsonify({'success': False, 'error': error_msg})
    
    except Exception as e:
        logger.error(f"Custom visualization error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@alignment_bp.route('/visualize-region', methods=['POST'])
def visualize_region():
    """Visualize specific region of alignment."""
    try:
        if not check_pymsaviz():
            return jsonify({
                'success': False, 
                'error': 'pyMSAviz is not available'
            })
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['file']
        input_file = save_uploaded_file(file)
        
        # Get region parameters
        start_pos = int(request.form.get('start_pos', 1))
        end_pos = int(request.form.get('end_pos', 100))
        color_scheme = request.form.get('color_scheme', 'Zappo')
        
        # Selected sequences (optional)
        selected_seqs = request.form.getlist('selected_seqs[]')
        if not selected_seqs:
            selected_seqs = None
        
        # Output file
        output_format = request.form.get('output_format', 'png')
        output_file = os.path.join(
            os.path.dirname(input_file),
            f'region_{start_pos}-{end_pos}.{output_format}'
        )
        
        success, error_msg = visualize_alignment_region(
            input_file, output_file, start_pos, end_pos,
            selected_seqs, color_scheme
        )
        
        if success:
            return jsonify({
                'success': True,
                'output_file': output_file,
                'region': f'{start_pos}-{end_pos}'
            })
        else:
            return jsonify({'success': False, 'error': error_msg})
            
    except Exception as e:
        logger.error(f"Region visualization error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
