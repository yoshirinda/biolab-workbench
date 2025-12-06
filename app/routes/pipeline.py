"""
Phylogenetic pipeline routes for complete workflow integration.
"""
import os
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
import config
from app.utils.logger import get_app_logger
from app.utils.file_utils import save_uploaded_file, resolve_input_file
from app.utils.fasta_utils import parse_fasta, write_fasta, clean_headers, filter_by_length

pipeline_bp = Blueprint('pipeline', __name__, url_prefix='/pipeline')
logger = get_app_logger()


@pipeline_bp.route('/')
def pipeline_page():
    """Render the phylogenetic pipeline page."""
    from app.utils.file_utils import list_files_in_dir
    from app.core.blast_wrapper import list_blast_databases
    hmm_files = list_files_in_dir(config.HMM_PROFILES_DIR, ['.hmm'])
    gold_files = list_files_in_dir(config.GOLD_LISTS_DIR, ['.txt'])
    blast_databases = list_blast_databases()
    return render_template('pipeline.html', hmm_files=hmm_files, gold_files=gold_files, blast_databases=blast_databases)


@pipeline_bp.route('/status/<job_id>')
def get_status(job_id):
    """Get status of a pipeline job."""
    # TODO: Implement job tracking
    return jsonify({
        'success': True,
        'status': 'running',
        'current_step': 'alignment',
        'progress': 60
    })


@pipeline_bp.route('/clean-headers', methods=['POST'])
def clean_headers_route():
    """Clean FASTA headers (whitespace/special chars) and return sanitized file."""
    try:
        try:
            fasta_path = resolve_input_file(request)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)})

        sequences = parse_fasta(fasta_path)
        cleaned, id_map = clean_headers(sequences)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_dir = os.path.join(config.RESULTS_DIR, f'clean_headers_{timestamp}')
        os.makedirs(result_dir, exist_ok=True)
        output_file = os.path.join(result_dir, 'cleaned.fasta')
        write_fasta(cleaned, output_file)

        return jsonify({
            'success': True,
            'output_file': output_file,
            'result_dir': result_dir,
            'count': len(cleaned),
            'id_map': id_map
        })
    except Exception as e:
        logger.error(f"Clean headers error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@pipeline_bp.route('/filter-length', methods=['POST'])
def filter_length():
    """Filter sequences by length and return new FASTA with detailed statistics."""
    try:
        try:
            fasta_path = resolve_input_file(request)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)})

        min_len = int(request.form.get('min_length', 0))
        max_len = int(request.form.get('max_length', 10000000))

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_dir = os.path.join(config.RESULTS_DIR, f'filter_len_{timestamp}')
        os.makedirs(result_dir, exist_ok=True)

        # Use the enhanced phylo_pipeline function for detailed statistics
        from app.core.phylo_pipeline import step2_8_length_filter
        success, output_file, message, stats = step2_8_length_filter(
            fasta_path, result_dir, min_len
        )

        if not success:
            return jsonify({'success': False, 'error': message})

        return jsonify({
            'success': True,
            'output_file': output_file,
            'result_dir': result_dir,
            'kept': stats['kept'],
            'removed': stats['deleted'],
            'stats': stats,
            'message': message
        })
    except Exception as e:
        logger.error(f"Filter length error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@pipeline_bp.route('/run-full', methods=['POST'])
def run_full_pipeline():
    """
    Run the complete phylogenetic pipeline.
    
    Steps:
    1. HMM search (optional)
    2. BLAST search
    3. Length filtering
    4. Multiple sequence alignment
    5. ClipKIT trimming
    6. IQ-TREE inference
    7. Tree visualization
    """
    try:
        data = request.get_json() or request.form
        
        # Get configuration for each step
        config = {
            'hmm': {
                'enabled': data.get('hmm_enabled', False),
                'profiles': data.getlist('hmm_profiles[]') if hasattr(data, 'getlist') else data.get('hmm_profiles', []),
                'evalue': float(data.get('hmm_evalue', 1e-5)),
                'cut_ga': data.get('hmm_cut_ga', False)
            },
            'blast': {
                'evalue': float(data.get('blast_evalue', 1e-3)),
                'max_targets': int(data.get('blast_max_targets', 100))
            },
            'filter': {
                'min_length': int(data.get('min_length', 200)),
                'max_length': int(data.get('max_length', 1000))
            },
            'alignment': {
                'tool': data.get('align_tool', 'mafft'),
                'algorithm': data.get('mafft_algorithm', 'auto')
            },
            'clipkit': {
                'mode': data.get('clipkit_mode', 'kpic-gappy'),
                'gaps': float(data.get('clipkit_gaps', 0.9))
            },
            'iqtree': {
                'model': data.get('iqtree_model', 'MFP'),
                'bootstrap': int(data.get('iqtree_bootstrap', 1000)),
                'bootstrap_type': data.get('iqtree_bootstrap_type', 'ufboot')
            }
        }
        
        # TODO: Implement full pipeline execution with job queue
        # For now, return configuration
        
        return jsonify({
            'success': True,
            'job_id': 'job_12345',
            'message': 'Pipeline started',
            'config': config
        })
        
    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@pipeline_bp.route('/templates')
def list_templates():
    """List available pipeline templates."""
    templates = [
        {
            'name': 'ACO Analysis',
            'description': 'Standard pipeline for ACO protein family analysis',
            'steps': ['hmm', 'blast', 'filter', 'align', 'clipkit', 'iqtree']
        },
        {
            'name': 'Quick Alignment',
            'description': 'Fast alignment and tree building',
            'steps': ['align', 'iqtree']
        },
        {
            'name': 'Full Analysis',
            'description': 'Complete phylogenetic analysis workflow',
            'steps': ['hmm', 'blast', 'filter', 'align', 'clipkit', 'iqtree', 'visualize']
        }
    ]
    
    return jsonify({
        'success': True,
        'templates': templates
    })
