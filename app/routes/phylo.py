"""
Phylogenetic pipeline routes for BioLab Workbench.
"""
import os
from flask import Blueprint, render_template, request, jsonify, send_file
import config
from app.core.phylo_pipeline import (
    step1_clean_fasta, step2_hmmsearch, step2_hmmsearch_multiple, step2_5_blast_filter,
    step2_7_length_stats, step2_8_length_filter, step3_mafft,
    step4_clipkit, step4_5_check_sites, step5_iqtree,
    run_full_pipeline
)
from app.core.hmm_wrapper import run_hmmsearch, run_hmmsearch_multi, get_hmm_info
from app.core.clipkit_wrapper import run_clipkit, suggest_clipkit_mode, compare_before_after_trimming
from app.core.iqtree_wrapper import run_iqtree, run_iqtree_modelfinder, summarize_bootstrap_support
from app.utils.file_utils import save_uploaded_file, list_files_in_dir
from app.utils.logger import get_app_logger

phylo_bp = Blueprint('phylo', __name__)
logger = get_app_logger()


@phylo_bp.route('/')
def phylo_page():
    """Render the phylogenetic pipeline page (now uses pipeline.html)."""
    # List available HMM profiles
    hmm_files = list_files_in_dir(config.HMM_PROFILES_DIR, ['.hmm'])

    # List available gold lists
    gold_files = list_files_in_dir(config.GOLD_LISTS_DIR, ['.txt'])

    # Use the new unified pipeline.html template
    return render_template('pipeline.html',
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

        # Get optional HMM files (support multiple)
        hmm_files = []
        hmm_files_raw = request.form.getlist('hmm_files[]')
        if not hmm_files_raw:
            # Fallback for single file (backward compatibility)
            hmm_file_single = request.form.get('hmm_file')
            if hmm_file_single:
                hmm_files_raw = [hmm_file_single]
        
        for hmm_filename in hmm_files_raw:
            if hmm_filename:
                hmm_path = os.path.join(config.HMM_PROFILES_DIR, hmm_filename)
                if os.path.exists(hmm_path):
                    hmm_files.append(hmm_path)

        # Get optional gold list file
        gold_list_file = None
        if request.form.get('gold_list_file'):
            gold_list_file = os.path.join(config.GOLD_LISTS_DIR, request.form.get('gold_list_file'))

        # Get options
        options = {
            'cut_ga': request.form.get('cut_ga', 'true').lower() == 'true',
            'pident': float(request.form.get('pident', 30)),
            'qcovs': float(request.form.get('qcovs', 50)),
            'blast_db_path': (request.form.get('blast_db_path') or '').strip(),
            'blast_evalue': float(request.form.get('blast_evalue') or 1e-5),
            'blast_max_target_seqs': int(request.form.get('blast_max_target_seqs') or 5),
            'blast_threads': int(request.form.get('blast_threads') or config.DEFAULT_THREADS),
            'min_length': int(request.form.get('min_length', 50)),
            'maxiterate': int(request.form.get('maxiterate', 1000)),
            'clipkit_mode': request.form.get('clipkit_mode', 'kpic-gappy'),
            'model': request.form.get('model', 'MFP'),
            'bootstrap': int(request.form.get('bootstrap', 1000)),
            'threads': int(request.form.get('threads', config.DEFAULT_THREADS)),
            'bnni': request.form.get('bnni', 'true').lower() == 'true',
        }

        if gold_list_file and not options['blast_db_path']:
            return jsonify({'success': False, 'error': 'BLAST database path is required when using a gold standard list'})

        success, results = run_full_pipeline(input_file, hmm_files, gold_list_file, options)

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
        commands = None
        output = None
        message = None
        stats = None

        if step == 'step1':
            success, output, message = step1_clean_fasta(input_file, output_dir)

        elif step == 'step2':
            # Support multiple HMM files
            hmm_files = []
            hmm_files_raw = request.form.getlist('hmm_files[]')
            if not hmm_files_raw:
                # Fallback for single file
                hmm_file_single = request.form.get('hmm_file')
                if hmm_file_single:
                    hmm_files_raw = [hmm_file_single]
            
            for hmm_filename in hmm_files_raw:
                if hmm_filename:
                    hmm_path = os.path.join(config.HMM_PROFILES_DIR, hmm_filename)
                    if os.path.exists(hmm_path):
                        hmm_files.append(hmm_path)
            
            if not hmm_files:
                return jsonify({'success': False, 'error': 'At least one HMM profile is required for step 2'})
            
            cut_ga = request.form.get('cut_ga', 'true').lower() == 'true'
            success, output, message, commands = step2_hmmsearch_multiple(input_file, hmm_files, output_dir, cut_ga)

        elif step == 'step2_5':
            gold_name = request.form.get('gold_list_file') or request.form.get('gold_list')
            if gold_name:
                gold_file = os.path.join(config.GOLD_LISTS_DIR, gold_name)
            else:
                return jsonify({'success': False, 'error': 'Gold standard list is required for step 2.5'})

            blast_db_path = request.form.get('blast_db_path') or request.form.get('blast_db')
            if not blast_db_path:
                return jsonify({'success': False, 'error': 'BLAST database path is required for step 2.5'})

            pident = float(request.form.get('pident') or 30)
            qcovs = float(request.form.get('qcovs') or 50)
            blast_evalue = float(request.form.get('blast_evalue') or 1e-5)
            max_target = int(request.form.get('blast_max_target_seqs') or 5)
            blast_threads = int(request.form.get('blast_threads') or config.DEFAULT_THREADS)

            success, output, message, stats, command = step2_5_blast_filter(
                input_file,
                gold_file,
                output_dir,
                pident_threshold=pident,
                qcovs_threshold=qcovs,
                blast_db_path=blast_db_path,
                evalue=blast_evalue,
                max_target_seqs=max_target,
                threads=blast_threads
            )

        elif step == 'step2_7':
            success, output, message = step2_7_length_stats(input_file, output_dir)
            # For stats, return the stats object in a friendly format
            if success and isinstance(message, dict):
                stats = message
                message = (f"Sequences: {stats['count']}, "
                          f"Mean: {stats['mean']:.1f}, "
                          f"Median: {stats['median']:.1f}, "
                          f"Min: {stats['min']}, Max: {stats['max']}")

        elif step == 'step2_8':
            min_length = int(request.form.get('min_length', 50))
            result = step2_8_length_filter(input_file, output_dir, min_length)
            if len(result) == 4:
                success, output, message, stats = result
            else:
                success, output, message = result
                stats = None

        elif step == 'step3':
            maxiterate = int(request.form.get('maxiterate', 1000))
            success, output, message, command = step3_mafft(input_file, output_dir, maxiterate)

        elif step == 'step4':
            mode = request.form.get('clipkit_mode', 'kpic-gappy')
            success, output, message, command = step4_clipkit(input_file, output_dir, mode)

        elif step == 'step4_5':
            # Check ClipKIT trimming status
            success, output, message = step4_5_check_sites(input_file)
            if success and isinstance(output, dict):
                # Format the output nicely
                info = output
                message = info.get('log_content', 'Log parsed successfully')[:500]
                if len(info.get('log_content', '')) > 500:
                    message += '...'
                output = None  # No file to download

        elif step == 'step5':
            model = request.form.get('model', 'MFP')
            bootstrap = int(request.form.get('bootstrap', 1000))
            threads = int(request.form.get('threads', config.DEFAULT_THREADS))
            bnni = request.form.get('bnni', 'true').lower() == 'true'
            success, output, message, command = step5_iqtree(input_file, output_dir, model, bootstrap, threads, bnni)

        else:
            return jsonify({'success': False, 'error': f'Unknown step: {step}'})

        # Build response - handle both single command and multiple commands
        response_data = {
            'success': success,
            'output': output,
            'message': message,
            'result_dir': output_dir,
            'stats': stats
        }
        
        if stats:
            if stats.get('raw_output_file'):
                response_data['raw_output'] = stats['raw_output_file']
            if stats.get('log_file'):
                response_data['log_file'] = stats['log_file']
        
        if commands:
            response_data['commands'] = commands
        elif command:
            response_data['command'] = command
        
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Step {step} error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/download')
def download():
    """Download a result file."""
    try:
        from urllib.parse import unquote
        
        # Get filepath from query parameter
        filepath = request.args.get('path', '')
        if not filepath:
            return jsonify({'success': False, 'error': 'No path provided'}), 400
        
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
            # Determine MIME type based on file extension
            filename = os.path.basename(abs_path)
            mimetype = None
            if filename.endswith('.fasta') or filename.endswith('.fa') or filename.endswith('.fna') or filename.endswith('.faa'):
                mimetype = 'text/plain'
            elif filename.endswith('.treefile') or filename.endswith('.nwk'):
                mimetype = 'text/plain'
            elif filename.endswith('.tsv') or filename.endswith('.txt') or filename.endswith('.log'):
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


# New enhanced endpoints

@phylo_bp.route('/hmm-search', methods=['POST'])
def hmm_search():
    """Run HMM search with one or more profiles."""
    try:
        sequence_file = None
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            sequence_file = save_uploaded_file(file)
        else:
            sequence_file = request.form.get('file_path')
            if not sequence_file or not os.path.exists(sequence_file):
                return jsonify({'success': False, 'error': 'No sequence file uploaded or path invalid'})
        
        # Get HMM profiles
        hmm_files = request.form.getlist('hmm_files[]')
        if not hmm_files:
            return jsonify({'success': False, 'error': 'No HMM profiles selected'})
        
        hmm_paths = [os.path.join(config.HMM_PROFILES_DIR, hmm) for hmm in hmm_files]
        
        # Parameters
        evalue = float(request.form.get('evalue', 1e-5))
        cut_ga = request.form.get('cut_ga', 'false').lower() == 'true'
        
        # Run search
        if len(hmm_paths) == 1:
            success, result_dir, output_files, hits = run_hmmsearch(
                hmm_paths[0], sequence_file, evalue=evalue, cut_ga=cut_ga
            )
        else:
            success, result_dir, output_files, hits = run_hmmsearch_multi(
                hmm_paths, sequence_file, evalue=evalue, cut_ga=cut_ga
            )
        
        if success:
            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'output_files': output_files,
                'hit_count': len(hits),
                'hits': hits[:100]  # Return first 100 for display
            })
        else:
            return jsonify({'success': False, 'error': str(hits)})
    
    except Exception as e:
        logger.error(f"HMM search error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/clipkit-trim', methods=['POST'])
def clipkit_trim():
    """Run ClipKIT to trim alignment."""
    try:
        alignment_file = None
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            alignment_file = save_uploaded_file(file)
        else:
            alignment_file = request.form.get('file_path')
            if not alignment_file or not os.path.exists(alignment_file):
                return jsonify({'success': False, 'error': 'No alignment file uploaded or path invalid'})
        
        # Parameters
        mode = request.form.get('mode', 'kpic-gappy')
        gaps = float(request.form.get('gaps', 0.9))
        
        # Run ClipKIT
        success, result_dir, output_file, stats = run_clipkit(
            alignment_file, mode=mode, gaps=gaps
        )
        
        if success:
            # Get before/after comparison
            comparison = compare_before_after_trimming(alignment_file, output_file)
            
            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'output_file': output_file,
                'stats': stats,
                'comparison': comparison
            })
        else:
            return jsonify({'success': False, 'error': str(stats)})
    
    except Exception as e:
        logger.error(f"ClipKIT error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/suggest-clipkit-mode', methods=['POST'])
def suggest_mode():
    """Analyze alignment and suggest ClipKIT mode."""
    try:
        alignment_file = None
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            alignment_file = save_uploaded_file(file)
        else:
            alignment_file = request.form.get('file_path')
            if not alignment_file or not os.path.exists(alignment_file):
                return jsonify({'success': False, 'error': 'No alignment file uploaded or path invalid'})
        
        mode, reason = suggest_clipkit_mode(alignment_file)
        
        return jsonify({
            'success': True,
            'suggested_mode': mode,
            'reason': reason
        })
    
    except Exception as e:
        logger.error(f"Mode suggestion error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/iqtree-infer', methods=['POST'])
def iqtree_infer():
    """Run IQ-TREE phylogenetic inference."""
    try:
        alignment_file = None
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            alignment_file = save_uploaded_file(file)
        else:
            alignment_file = request.form.get('file_path')
            if not alignment_file or not os.path.exists(alignment_file):
                return jsonify({'success': False, 'error': 'No alignment file uploaded or path invalid'})
        
        # Parameters
        model = request.form.get('model', 'MFP')
        bootstrap = int(request.form.get('bootstrap', 1000))
        bootstrap_type = request.form.get('bootstrap_type', 'ufboot')
        alrt = request.form.get('alrt', 'false').lower() == 'true'
        bnni = request.form.get('bnni', 'true').lower() == 'true'
        threads = request.form.get('threads', 'AUTO')
        
        # Run IQ-TREE
        success, result_dir, output_files, log_info = run_iqtree(
            alignment_file,
            model=model,
            bootstrap=bootstrap,
            bootstrap_type=bootstrap_type,
            alrt=alrt,
            bnni=bnni,
            threads=threads
        )
        
        if success:
            # Get bootstrap support summary
            if 'treefile' in output_files:
                support_stats = summarize_bootstrap_support(output_files['treefile'])
            else:
                support_stats = {}
            
            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'output_files': output_files,
                'log_info': log_info,
                'support_stats': support_stats
            })
        else:
            return jsonify({'success': False, 'error': str(log_info)})
    
    except Exception as e:
        logger.error(f"IQ-TREE error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/modelfinder', methods=['POST'])
def modelfinder():
    """Run ModelFinder to select best substitution model."""
    try:
        alignment_file = None
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            alignment_file = save_uploaded_file(file)
        else:
            alignment_file = request.form.get('file_path')
            if not alignment_file or not os.path.exists(alignment_file):
                return jsonify({'success': False, 'error': 'No alignment file uploaded or path invalid'})
        
        # Run ModelFinder
        success, result_dir, best_model, log_info = run_iqtree_modelfinder(alignment_file)
        
        if success:
            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'best_model': best_model,
                'log_info': log_info
            })
        else:
            return jsonify({'success': False, 'error': str(log_info)})
    
    except Exception as e:
        logger.error(f"ModelFinder error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/hmm-info/<filename>', methods=['GET'])
def hmm_info(filename):
    """Get information about an HMM profile."""
    try:
        hmm_path = os.path.join(config.HMM_PROFILES_DIR, filename)
        
        if not os.path.exists(hmm_path):
            return jsonify({'success': False, 'error': 'HMM file not found'})
        
        info = get_hmm_info(hmm_path)
        
        if info:
            return jsonify({'success': True, 'info': info})
        else:
            return jsonify({'success': False, 'error': 'Failed to parse HMM file'})
    
    except Exception as e:
        logger.error(f"HMM info error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
