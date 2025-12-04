"""
Phylogenetic pipeline routes for BioLab Workbench.
"""
import os
from flask import Blueprint, render_template, request, jsonify, send_file
import config
from app.core.phylo_pipeline import (
    step1_clean_fasta, step2_hmmsearch, step2_5_blast_filter,
    step2_7_length_stats, step2_8_length_filter, step3_mafft,
    step4_clipkit, step4_5_check_sites, step5_iqtree,
    run_full_pipeline
)
from app.utils.file_utils import save_uploaded_file, list_files_in_dir
from app.utils.logger import get_app_logger

phylo_bp = Blueprint('phylo', __name__)
logger = get_app_logger()


@phylo_bp.route('/')
def phylo_page():
    """Render the phylogenetic pipeline page."""
    # List available HMM profiles
    hmm_files = list_files_in_dir(config.HMM_PROFILES_DIR, ['.hmm'])

    # List available gold lists
    gold_files = list_files_in_dir(config.GOLD_LISTS_DIR, ['.txt'])

    return render_template('phylo.html',
                          hmm_files=hmm_files,
                          gold_files=gold_files)


@phylo_bp.route('/run-full', methods=['POST'])
def run_full():
    """Run the complete phylogenetic pipeline."""
    try:
        # Get input file
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        input_file = save_uploaded_file(file)

        # Get optional HMM file
        hmm_file = None
        if request.form.get('hmm_file'):
            hmm_file = os.path.join(config.HMM_PROFILES_DIR, request.form.get('hmm_file'))

        # Get optional gold list file
        gold_list_file = None
        if request.form.get('gold_list_file'):
            gold_list_file = os.path.join(config.GOLD_LISTS_DIR, request.form.get('gold_list_file'))

        # Get options
        options = {
            'cut_ga': request.form.get('cut_ga', 'true').lower() == 'true',
            'pident': float(request.form.get('pident', 30)),
            'qcovs': float(request.form.get('qcovs', 50)),
            'min_length': int(request.form.get('min_length', 50)),
            'maxiterate': int(request.form.get('maxiterate', 1000)),
            'clipkit_mode': request.form.get('clipkit_mode', 'kpic-gappy'),
            'model': request.form.get('model', 'MFP'),
            'bootstrap': int(request.form.get('bootstrap', 1000)),
            'threads': int(request.form.get('threads', config.DEFAULT_THREADS)),
            'bnni': request.form.get('bnni', 'true').lower() == 'true',
        }

        success, results = run_full_pipeline(input_file, hmm_file, gold_list_file, options)

        return jsonify({
            'success': success,
            'results': results
        })

    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/run-step/<step>', methods=['POST'])
def run_step(step):
    """Run a single pipeline step."""
    try:
        # Get input file
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})

        file = request.files['file']
        input_file = save_uploaded_file(file)

        # Create output directory
        from app.utils.file_utils import create_result_dir
        output_dir = create_result_dir('phylo', step)

        command = None

        if step == 'step1':
            success, output, message = step1_clean_fasta(input_file, output_dir)

        elif step == 'step2':
            hmm_file = request.form.get('hmm_file')
            if hmm_file:
                hmm_file = os.path.join(config.HMM_PROFILES_DIR, hmm_file)
            cut_ga = request.form.get('cut_ga', 'true').lower() == 'true'
            success, output, message, command = step2_hmmsearch(input_file, hmm_file, output_dir, cut_ga)

        elif step == 'step2_5':
            gold_file = request.form.get('gold_list_file')
            if gold_file:
                gold_file = os.path.join(config.GOLD_LISTS_DIR, gold_file)
            pident = float(request.form.get('pident', 30))
            qcovs = float(request.form.get('qcovs', 50))
            success, output, message = step2_5_blast_filter(input_file, gold_file, output_dir, pident, qcovs)

        elif step == 'step2_7':
            success, output, message = step2_7_length_stats(input_file, output_dir)

        elif step == 'step2_8':
            min_length = int(request.form.get('min_length', 50))
            success, output, message = step2_8_length_filter(input_file, output_dir, min_length)

        elif step == 'step3':
            maxiterate = int(request.form.get('maxiterate', 1000))
            success, output, message, command = step3_mafft(input_file, output_dir, maxiterate)

        elif step == 'step4':
            mode = request.form.get('clipkit_mode', 'kpic-gappy')
            success, output, message, command = step4_clipkit(input_file, output_dir, mode)

        elif step == 'step5':
            model = request.form.get('model', 'MFP')
            bootstrap = int(request.form.get('bootstrap', 1000))
            threads = int(request.form.get('threads', config.DEFAULT_THREADS))
            bnni = request.form.get('bnni', 'true').lower() == 'true'
            success, output, message, command = step5_iqtree(input_file, output_dir, model, bootstrap, threads, bnni)

        else:
            return jsonify({'success': False, 'error': f'Unknown step: {step}'})

        return jsonify({
            'success': success,
            'output': output,
            'message': message,
            'result_dir': output_dir,
            'command': command
        })

    except Exception as e:
        logger.error(f"Step {step} error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/download/<path:filepath>')
def download(filepath):
    """Download a result file."""
    try:
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
            return send_file(abs_path, as_attachment=True)
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
