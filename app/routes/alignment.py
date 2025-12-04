"""
Alignment routes for BioLab Workbench.
"""
import os
from flask import Blueprint, render_template, request, jsonify, send_file
import config
from app.core.alignment_tools import (
    check_available_tools, run_alignment, parse_alignment,
    calculate_conservation, generate_alignment_html, export_alignment_html
)
from app.utils.file_utils import save_uploaded_file
from app.utils.logger import get_app_logger

alignment_bp = Blueprint('alignment', __name__)
logger = get_app_logger()


@alignment_bp.route('/')
def alignment_page():
    """Render the alignment page."""
    tools = check_available_tools()
    return render_template('alignment.html', available_tools=tools)


@alignment_bp.route('/tools')
def get_tools():
    """Get list of available alignment tools."""
    try:
        tools = check_available_tools()
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


@alignment_bp.route('/download/<path:filepath>')
def download(filepath):
    """Download a result file."""
    try:
        from urllib.parse import unquote
        
        # URL decode the filepath for port-forwarding scenarios
        filepath = unquote(filepath)
        
        # Security: Ensure the file is within allowed directories
        abs_path = os.path.abspath(filepath)
        results_dir = os.path.abspath(config.RESULTS_DIR)
        uploads_dir = os.path.abspath(config.UPLOADS_DIR)
        
        # Only allow downloads from results or uploads directories
        if not (abs_path.startswith(results_dir + os.sep) or 
                abs_path.startswith(uploads_dir + os.sep)):
            logger.warning(f"Attempted path traversal: {filepath}")
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        if os.path.exists(abs_path):
            # Determine MIME type based on file extension
            filename = os.path.basename(abs_path)
            mimetype = None
            if filename.endswith('.fasta') or filename.endswith('.fa') or filename.endswith('.aln'):
                mimetype = 'text/plain'
            elif filename.endswith('.txt') or filename.endswith('.log'):
                mimetype = 'text/plain'
            elif filename.endswith('.json'):
                mimetype = 'application/json'
            
            return send_file(
                abs_path, 
                as_attachment=True,
                download_name=filename,
                mimetype=mimetype
            )
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
