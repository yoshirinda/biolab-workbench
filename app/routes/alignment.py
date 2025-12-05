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
from app.utils.file_utils import save_uploaded_file
from app.utils.logger import get_app_logger

alignment_bp = Blueprint('alignment', __name__)
logger = get_app_logger()


@alignment_bp.route('/')
def alignment_page():
    """Render the alignment page."""
    force_refresh = request.args.get('refresh') == '1'
    tools = check_available_tools(force=force_refresh)
    return render_template('alignment.html', available_tools=tools)


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

        tool = request.form.get('tool', 'mafft')
        color_mode = request.form.get('color_mode', 'conservation')

        # Get tool options
        options = {}
        if request.form.get('maxiterate'):
            options['maxiterate'] = int(request.form.get('maxiterate'))
        if request.form.get('auto'):
            options['auto'] = True
        if request.form.get('algorithm'):
            options['algorithm'] = request.form.get('algorithm')
        if request.form.get('matrix'):
            options['matrix'] = request.form.get('matrix')

        success, result_dir, output_file, command = run_alignment(input_file, tool, options)

        if success:
            # Parse alignment for visualization
            sequences = parse_alignment(output_file)
            conservation = calculate_conservation(sequences)
            html_view = generate_alignment_html(sequences, conservation, color_mode)
            
            # Also export HTML visualization file
            html_output = os.path.join(result_dir, 'alignment_visualization.html')
            export_alignment_html(sequences, html_output, conservation, color_mode)

            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'output_file': output_file,
                'html_file': html_output,
                'alignment_html': html_view,
                'sequence_count': len(sequences),
                'alignment_length': len(sequences[0][1]) if sequences else 0,
                'tool': tool,
                'command': command
            })
        else:
            return jsonify({'success': False, 'error': result_dir, 'command': command})

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
        
        # Generate visualization
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_dir = os.path.dirname(input_file) or config.RESULTS_DIR
        
        success, output_file, message = export_alignment_visualization(
            sequences, output_dir, f"{base_name}_viz", 
            output_format=output_format, color_mode=color_mode
        )
        
        if success:
            return jsonify({
                'success': True,
                'output_file': output_file,
                'format': output_format,
                'message': message,
                'pymsaviz_used': check_pymsaviz_available() and output_format != 'html'
            })
        else:
            return jsonify({'success': False, 'error': message})
            
    except Exception as e:
        logger.error(f"Visualization error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
