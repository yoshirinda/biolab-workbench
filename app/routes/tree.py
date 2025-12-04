"""
Tree visualization routes for BioLab Workbench.
"""
import os
from flask import Blueprint, render_template, request, jsonify, send_file
import config
from app.core.tree_visualizer import (
    visualize_tree, get_tree_info, get_species_from_tree,
    read_newick, get_default_colors, DEFAULT_COLORS
)
from app.utils.file_utils import save_uploaded_file
from app.utils.logger import get_app_logger

tree_bp = Blueprint('tree', __name__)
logger = get_app_logger()


@tree_bp.route('/')
def tree_page():
    """Render the tree visualization page."""
    return render_template('tree.html', default_colors=DEFAULT_COLORS)


@tree_bp.route('/upload', methods=['POST'])
def upload():
    """Upload a tree file and get species information."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        filepath = save_uploaded_file(file)

        # Get tree information
        info = get_tree_info(filepath)

        if info:
            # Assign default colors
            colors = get_default_colors(info.get('species', []))

            return jsonify({
                'success': True,
                'filepath': filepath,
                'info': info,
                'default_colors': colors
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to parse tree file'})

    except Exception as e:
        logger.error(f"Tree upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@tree_bp.route('/visualize', methods=['POST'])
def visualize():
    """Visualize a phylogenetic tree."""
    try:
        data = request.get_json() or request.form

        tree_file = data.get('tree_file')
        if not tree_file or not os.path.exists(tree_file):
            return jsonify({'success': False, 'error': 'Tree file not found'})

        layout = data.get('layout', 'rectangular')
        show_bootstrap = data.get('show_bootstrap', True)
        if isinstance(show_bootstrap, str):
            show_bootstrap = show_bootstrap.lower() == 'true'

        font_size = int(data.get('font_size', 10))
        v_scale = float(data.get('v_scale', 1.0))

        # Parse colored species
        colored_species = {}
        if data.get('colored_species'):
            if isinstance(data.get('colored_species'), dict):
                colored_species = data.get('colored_species')
            else:
                import json
                colored_species = json.loads(data.get('colored_species'))

        # Parse highlighted genes
        highlighted_genes = []
        if data.get('highlighted_genes'):
            if isinstance(data.get('highlighted_genes'), list):
                highlighted_genes = data.get('highlighted_genes')
            else:
                highlighted_genes = [g.strip() for g in data.get('highlighted_genes').split(',') if g.strip()]

        success, result_dir, output_file, message = visualize_tree(
            tree_file=tree_file,
            layout=layout,
            colored_species=colored_species,
            highlighted_genes=highlighted_genes,
            show_bootstrap=show_bootstrap,
            font_size=font_size,
            v_scale=v_scale
        )

        if success:
            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'output_file': output_file,
                'message': message
            })
        else:
            return jsonify({'success': False, 'error': message})

    except Exception as e:
        logger.error(f"Tree visualization error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@tree_bp.route('/download/<path:filepath>')
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
            if filename.endswith('.svg'):
                mimetype = 'image/svg+xml'
            elif filename.endswith('.png'):
                mimetype = 'image/png'
            elif filename.endswith('.pdf'):
                mimetype = 'application/pdf'
            elif filename.endswith('.nwk') or filename.endswith('.treefile'):
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


@tree_bp.route('/view/<path:filepath>')
def view(filepath):
    """View a SVG file."""
    try:
        from urllib.parse import unquote
        
        # URL decode the filepath for port-forwarding scenarios
        filepath = unquote(filepath)
        
        # Security: Ensure the file is within allowed directories
        abs_path = os.path.abspath(filepath)
        results_dir = os.path.abspath(config.RESULTS_DIR)
        uploads_dir = os.path.abspath(config.UPLOADS_DIR)
        
        # Only allow viewing from results or uploads directories
        if not (abs_path.startswith(results_dir + os.sep) or 
                abs_path.startswith(uploads_dir + os.sep)):
            logger.warning(f"Attempted path traversal: {filepath}")
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        if os.path.exists(abs_path) and abs_path.endswith('.svg'):
            return send_file(abs_path, mimetype='image/svg+xml')
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"View error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
