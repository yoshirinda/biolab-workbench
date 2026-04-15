"""
Tree visualization routes for BioLab Workbench.
"""
import os
import re
from flask import Blueprint, render_template, request, jsonify, send_file
import config
from app.core.tree_visualizer import (
    visualize_tree, get_tree_info, get_species_from_tree,
    read_newick, get_default_colors, DEFAULT_COLORS, extract_clade
)
from app.utils.multiprocess_utils import run_in_process
from app.utils.file_utils import save_uploaded_file, write_result_manifest
from app.utils.logger import get_app_logger

tree_bp = Blueprint('tree', __name__)
logger = get_app_logger()


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _parse_int(value, field_name, minimum=None, maximum=None, default=None):
    if value in (None, ''):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {field_name}: must be an integer")
    if minimum is not None and parsed < minimum:
        raise ValueError(f"Invalid {field_name}: must be >= {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"Invalid {field_name}: must be <= {maximum}")
    return parsed


def _parse_float(value, field_name, minimum=None, maximum=None, default=None):
    if value in (None, ''):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {field_name}: must be a number")
    if minimum is not None and parsed < minimum:
        raise ValueError(f"Invalid {field_name}: must be >= {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"Invalid {field_name}: must be <= {maximum}")
    return parsed


def _parse_hex_color(value, field_name, default='#d62828'):
    if value in (None, ''):
        return default
    color = str(value).strip()
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError(f"Invalid {field_name}: must be a hex color like #d62828")
    return color


def _parse_support_metric(value, default='trailing'):
    metric = (value or default or 'trailing').strip().lower()
    if metric not in {'leading', 'trailing'}:
        raise ValueError('Invalid support_metric: must be "leading" or "trailing"')
    return metric


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
        info, error = get_tree_info(filepath)

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
            return jsonify({'success': False, 'error': error or 'Failed to parse tree file'})

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
        if layout not in {'rectangular', 'circular'}:
            return jsonify({'success': False, 'error': f'Invalid layout: {layout}'}), 400
        show_bootstrap = _as_bool(data.get('show_bootstrap', True), default=True)

        try:
            font_size = _parse_int(data.get('font_size', 10), 'font_size', minimum=6, maximum=72, default=10)
            v_scale = _parse_float(data.get('v_scale', 1.0), 'v_scale', minimum=0.1, maximum=20.0, default=1.0)
            support_metric = _parse_support_metric(data.get('support_metric', 'trailing'))
            radius_edges = _parse_int(data.get('radius_edges', 3), 'radius_edges', minimum=1, maximum=1000, default=3)
            low_bootstrap_threshold = _parse_float(
                data.get('low_bootstrap_threshold'),
                'low_bootstrap_threshold',
                minimum=0,
                maximum=100,
                default=None
            )
            low_bootstrap_color = _parse_hex_color(
                data.get('low_bootstrap_color'),
                'low_bootstrap_color',
                default='#d62828'
            )
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        center_gene = (data.get('center_gene') or '').strip() or None

        # Parse colored species
        colored_species = {}
        if data.get('colored_species'):
            if isinstance(data.get('colored_species'), dict):
                colored_species = data.get('colored_species')
            else:
                import json
                try:
                    colored_species = json.loads(data.get('colored_species'))
                except json.JSONDecodeError:
                    return jsonify({'success': False, 'error': 'Invalid colored_species JSON'}), 400

        # Parse highlighted genes
        highlighted_genes = []
        if data.get('highlighted_genes'):
            if isinstance(data.get('highlighted_genes'), list):
                highlighted_genes = data.get('highlighted_genes')
            else:
                highlighted_genes = [g.strip() for g in data.get('highlighted_genes').split(',') if g.strip()]

        # Parse highlight species
        highlight_species = []
        if data.get('highlight_species'):
            if isinstance(data.get('highlight_species'), list):
                highlight_species = data.get('highlight_species')
            else:
                highlight_species = [s.strip() for s in data.get('highlight_species').split(',') if s.strip()]

        fixed_branch_length = _as_bool(data.get('fixed_branch_length', False), default=False)

        success, result_dir, output_file, message, support_stats = run_in_process(
            visualize_tree,
            tree_file=tree_file,
            layout=layout,
            colored_species=colored_species,
            highlighted_genes=highlighted_genes,
            show_bootstrap=show_bootstrap,
            font_size=font_size,
            v_scale=v_scale,
            center_gene=center_gene,
            radius_edges=radius_edges,
            highlight_species=highlight_species,
            fixed_branch_length=fixed_branch_length,
            low_bootstrap_threshold=low_bootstrap_threshold,
            support_metric=support_metric,
            low_bootstrap_color=low_bootstrap_color
        )

        if success:
            manifest_output_file = output_file
            if manifest_output_file and not os.path.isabs(manifest_output_file):
                manifest_output_file = os.path.join(config.RESULTS_DIR, manifest_output_file)
            try:
                write_result_manifest(
                    result_dir=result_dir,
                    domain='tree',
                    action='visualize',
                    input_files={'tree_file': tree_file},
                    output_files={'visualization': manifest_output_file},
                    params={
                        'layout': layout,
                        'show_bootstrap': show_bootstrap,
                        'font_size': font_size,
                        'v_scale': v_scale,
                        'center_gene': center_gene,
                        'radius_edges': radius_edges,
                        'fixed_branch_length': fixed_branch_length,
                        'low_bootstrap_threshold': low_bootstrap_threshold,
                        'support_metric': support_metric,
                        'low_bootstrap_color': low_bootstrap_color,
                        'highlight_species': highlight_species,
                        'highlighted_genes': highlighted_genes
                    },
                    commands=[],
                    tools=['ete3']
                )
            except Exception as manifest_error:
                logger.warning(f"Failed to write tree visualize manifest: {manifest_error}")

            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'output_file': output_file,
                'message': message,
                'support_stats': support_stats
            })
        else:
            return jsonify({'success': False, 'error': message})

    except Exception as e:
        logger.error(f"Tree visualization error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@tree_bp.route('/extract-clade', methods=['POST'])
def extract_clade_route():
    """Extract and visualize a clade around a target gene."""
    try:
        data = request.get_json() or request.form

        tree_file = data.get('tree_file')
        if not tree_file or not os.path.exists(tree_file):
            return jsonify({'success': False, 'error': 'Tree file not found'})

        target_gene = data.get('target_gene', '').strip()
        if not target_gene:
            return jsonify({'success': False, 'error': 'Target gene required'})

        try:
            levels_up = _parse_int(data.get('levels_up', 2), 'levels_up', minimum=0, maximum=1000, default=2)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        layout = data.get('layout', 'rectangular')
        if layout not in {'rectangular', 'circular'}:
            return jsonify({'success': False, 'error': f'Invalid layout: {layout}'}), 400
        show_bootstrap = _as_bool(data.get('show_bootstrap', True), default=True)
        try:
            font_size = _parse_int(data.get('font_size', 10), 'font_size', minimum=6, maximum=72, default=10)
            v_scale = _parse_float(data.get('v_scale', 1.0), 'v_scale', minimum=0.1, maximum=20.0, default=1.0)
            support_metric = _parse_support_metric(data.get('support_metric', 'trailing'))
            low_bootstrap_threshold = _parse_float(
                data.get('low_bootstrap_threshold'),
                'low_bootstrap_threshold',
                minimum=0,
                maximum=100,
                default=None
            )
            low_bootstrap_color = _parse_hex_color(
                data.get('low_bootstrap_color'),
                'low_bootstrap_color',
                default='#d62828'
            )
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        fixed_branch = data.get('fixed_branch_length', False)
        fixed_branch = _as_bool(fixed_branch, default=False)

        colored_species = {}
        if data.get('colored_species'):
            import json
            if isinstance(data.get('colored_species'), dict):
                colored_species = data.get('colored_species')
            else:
                try:
                    colored_species = json.loads(data.get('colored_species'))
                except json.JSONDecodeError:
                    return jsonify({'success': False, 'error': 'Invalid colored_species JSON'}), 400

        # Parse highlight species
        highlight_species = []
        if data.get('highlight_species'):
            if isinstance(data.get('highlight_species'), list):
                highlight_species = data.get('highlight_species')
            else:
                highlight_species = [s.strip() for s in data.get('highlight_species').split(',') if s.strip()]

        success, result_dir, output_file, message, clade_info = run_in_process(
            extract_clade,
            tree_file=tree_file,
            target_gene=target_gene,
            levels_up=levels_up,
            layout=layout,
            colored_species=colored_species,
            show_bootstrap=show_bootstrap,
            font_size=font_size,
            v_scale=v_scale,
            fixed_branch_length=fixed_branch,
            highlight_species=highlight_species,
            low_bootstrap_threshold=low_bootstrap_threshold,
            support_metric=support_metric,
            low_bootstrap_color=low_bootstrap_color
        )

        if success:
            manifest_output_file = output_file
            if manifest_output_file and not os.path.isabs(manifest_output_file):
                manifest_output_file = os.path.join(config.RESULTS_DIR, manifest_output_file)
            try:
                write_result_manifest(
                    result_dir=result_dir,
                    domain='tree',
                    action='extract-clade',
                    input_files={'tree_file': tree_file},
                    output_files={'clade_visualization': manifest_output_file},
                    params={
                        'target_gene': target_gene,
                        'levels_up': levels_up,
                        'layout': layout,
                        'show_bootstrap': show_bootstrap,
                        'font_size': font_size,
                        'v_scale': v_scale,
                        'fixed_branch_length': fixed_branch,
                        'low_bootstrap_threshold': low_bootstrap_threshold,
                        'support_metric': support_metric,
                        'low_bootstrap_color': low_bootstrap_color,
                        'highlight_species': highlight_species
                    },
                    commands=[],
                    tools=['ete3']
                )
            except Exception as manifest_error:
                logger.warning(f"Failed to write tree clade manifest: {manifest_error}")

            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'output_file': output_file,
                'message': message,
                'clade_info': clade_info,
                'support_stats': (clade_info or {}).get('support_stats')
            })
        else:
            return jsonify({'success': False, 'error': message})

    except Exception as e:
        logger.error(f"Clade extraction error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@tree_bp.route('/download/<path:filepath>')
def download(filepath):
    """Download a result file."""
    try:
        from urllib.parse import unquote
        
        # URL decode the filepath
        filepath = unquote(filepath)
        
        # Security: Ensure the file is within allowed directories
        abs_path = os.path.abspath(os.path.join(config.RESULTS_DIR, filepath))
        results_dir = os.path.abspath(config.RESULTS_DIR)
        
        # Only allow downloads from results directory
        if not abs_path.startswith(results_dir + os.sep):
            logger.warning(f"Attempted path traversal: {filepath}")
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        if os.path.exists(abs_path):
            filename = os.path.basename(abs_path)
            mimetype = None
            if filename.endswith('.svg'):
                mimetype = 'image/svg+xml'
            elif filename.endswith('.png'):
                mimetype = 'image/png'
            elif filename.endswith('.pdf'):
                mimetype = 'application/pdf'
            
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
        
        # URL decode the filepath
        filepath = unquote(filepath)
        
        # Security: Ensure the file is within allowed directories
        abs_path = os.path.abspath(os.path.join(config.RESULTS_DIR, filepath))
        results_dir = os.path.abspath(config.RESULTS_DIR)
        
        # Only allow viewing from results directory
        if not abs_path.startswith(results_dir + os.sep):
            logger.warning(f"Attempted path traversal: {filepath}")
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        if os.path.exists(abs_path) and abs_path.endswith('.svg'):
            return send_file(abs_path, mimetype='image/svg+xml')
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"View error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
