"""
Phylogenetic pipeline routes for BioLab Workbench.
"""
import os
import uuid
from flask import Blueprint, render_template, request, jsonify, send_file
from urllib.parse import unquote
from werkzeug.exceptions import HTTPException
import config
from app.utils.stream_runner import run_pipeline_step_with_stream
from app.core.phylo_pipeline import (
    step0_clean_headers, step1_clean_fasta, step2_hmmsearch_multiple, step2_5_blast_filter,
    step2_7_length_stats, step2_8_length_filter, step3_mafft,
    step4_clipkit, step4_5_check_sites, step5_iqtree,
    run_full_pipeline
)
from app.core.hmm_wrapper import run_hmmsearch, run_hmmsearch_multi, get_hmm_info
from app.core.clipkit_wrapper import run_clipkit, suggest_clipkit_mode, compare_before_after_trimming
from app.core.iqtree_wrapper import run_iqtree, run_iqtree_modelfinder, summarize_bootstrap_support
from app.utils.file_utils import save_uploaded_file, list_files_in_dir, resolve_input_file, create_result_dir
from app.utils.logger import get_app_logger

phylo_bp = Blueprint('phylo', __name__, url_prefix='/phylo')
logger = get_app_logger()

# Global dict to track running processes
running_processes = {}

@phylo_bp.route('/clipkit-check', methods=['POST'])
def clipkit_check():
    """Check ClipKIT trimming sites (Step 4.5)"""
    try:
        data = request.get_json()
        ref_id = data.get('id', '').strip()
        sites = data.get('sites', '').strip()
        log_file = data.get('log_file', '').strip()
        if not ref_id or not sites or not log_file:
            return jsonify({'success': False, 'error': '参数缺失'})
        # 调用 step4_5_check_sites
        success, info, msg = step4_5_check_sites(log_file)
        if not success:
            return jsonify({'success': False, 'error': msg})
        # 解析 sites 支持逗号和区间
        site_list = []
        for part in sites.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                site_list.extend(list(range(int(start), int(end)+1)))
            elif part.isdigit():
                site_list.append(int(part))
        # 构造报告（这里只做简单示例，实际可结合 log 内容更详细）
        report = f"参考ID: {ref_id}\n检查位点: {site_list}\n\n"
        # 假设 log_content 里有保留位点信息
        kept_line = info.get('sites_kept') or ''
        trimmed_line = info.get('sites_trimmed') or ''
        for site in site_list:
            status = '未知'
            if kept_line and str(site) in kept_line:
                status = '✅ 保留'
            elif trimmed_line and str(site) in trimmed_line:
                status = '❌ Trimmed'
            report += f"位点 {site}: {status}\n"
        return jsonify({'success': True, 'report': report})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
"""
Phylogenetic pipeline routes for BioLab Workbench.
"""
import os
import uuid
from flask import Blueprint, render_template, request, jsonify, send_file
from urllib.parse import unquote
from werkzeug.exceptions import HTTPException
import config
from app.utils.stream_runner import run_pipeline_step_with_stream
from app.core.phylo_pipeline import (
    step0_clean_headers, step1_clean_fasta, step2_hmmsearch_multiple, step2_5_blast_filter,
    step2_7_length_stats, step2_8_length_filter, step3_mafft,
    step4_clipkit, step4_5_check_sites, step5_iqtree,
    run_full_pipeline
)
from app.core.hmm_wrapper import run_hmmsearch, run_hmmsearch_multi, get_hmm_info
from app.core.clipkit_wrapper import run_clipkit, suggest_clipkit_mode, compare_before_after_trimming
from app.core.iqtree_wrapper import run_iqtree, run_iqtree_modelfinder, summarize_bootstrap_support
from app.utils.file_utils import save_uploaded_file, list_files_in_dir, resolve_input_file, create_result_dir
from app.utils.logger import get_app_logger

phylo_bp = Blueprint('phylo', __name__, url_prefix='/phylo')
logger = get_app_logger()


@phylo_bp.errorhandler(Exception)
def phylo_error_handler(err):
    """Return JSON for all phylo errors to avoid HTML payloads breaking fetch()."""
    status = 500
    if isinstance(err, HTTPException):
        status = err.code or 500
    logger.error(f"Phylo error: {err}")
    return jsonify({'success': False, 'error': str(err)}), status

@phylo_bp.route('/')
def phylo_page():
    """Render the phylogenetic pipeline page."""
    from app.core.blast_wrapper import list_blast_databases
    hmm_files = list_files_in_dir(config.HMM_PROFILES_DIR, ['.hmm'])
    gold_files = list_files_in_dir(config.GOLD_LISTS_DIR, ['.txt'])
    blast_databases = list_blast_databases()
    return render_template('pipeline.html',
                           hmm_files=hmm_files,
                           gold_files=gold_files,
                           blast_databases=blast_databases)

@phylo_bp.route('/run-step/<step>', methods=['POST'])
def run_step(step):
    """Run a single pipeline step."""
    try:
        input_file = resolve_input_file(request)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)})

    output_dir = create_result_dir('phylo', step)
    
    success, output, message, stats, command, commands = False, None, "Unknown error", None, None, None

    if step == 'step0':
        success, output, message = step0_clean_headers(input_file, output_dir)
    elif step == 'step2':
        hmm_files = request.form.getlist('hmm_files[]')
        cut_ga = str(request.form.get('cut_ga', '')).lower() in ('true', '1', 'on', 'yes')
        evalue_raw = request.form.get('evalue', 1e-5)
        try:
            evalue = float(evalue_raw if evalue_raw not in (None, '') else 1e-5)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Invalid e-value'}), 400
        dom_evalue = request.form.get('dom_evalue')
        threads = request.form.get('threads')
        if not hmm_files:
            return jsonify({'success': False, 'error': 'At least one HMM profile is required.'})
        hmm_paths = []
        for hf in hmm_files:
            if os.path.isabs(hf):
                fname = hf
            else:
                fname = hf if hf.endswith('.hmm') else f"{hf}.hmm"
                fname = os.path.join(config.HMM_PROFILES_DIR, fname)
            hmm_paths.append(fname)
        success, output, message, commands = step2_hmmsearch_multiple(
            input_file, hmm_paths, output_dir, cut_ga, evalue, dom_evalue, threads
        )
    elif step == 'step2_5':
        gold_name = request.form.get('gold_list_file')
        blast_db_path = request.form.get('blast_db_path')

        def _float_or_default(val, default):
            if val is None:
                return default
            val = str(val).strip()
            if val == '':
                return default
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        def _int_or_default(val, default):
            if val is None:
                return default
            val = str(val).strip()
            if val == '':
                return default
            try:
                return int(val)
            except (TypeError, ValueError):
                return default

        pident = _float_or_default(request.form.get('pident'), 30)
        qcovs = _float_or_default(request.form.get('qcovs'), 50)
        blast_evalue_raw = request.form.get('blast_evalue')
        blast_evalue = _float_or_default(blast_evalue_raw, None) if blast_evalue_raw not in (None, '') else None
        blast_max_target = _int_or_default(request.form.get('blast_max_target_seqs'), 5)
        blast_threads = _int_or_default(request.form.get('blast_threads'), config.DEFAULT_THREADS)
        logger.info(f"[step2_5] params: pident={pident}, qcovs={qcovs}, evalue={blast_evalue}, max_target={blast_max_target}, threads={blast_threads}, gold={gold_name}, db={blast_db_path}")
        gold_file = os.path.join(config.GOLD_LISTS_DIR, gold_name) if gold_name else None
        success, output, message, stats, command = step2_5_blast_filter(
            input_file, gold_file, output_dir, pident, qcovs, blast_db_path,
            evalue=blast_evalue, max_target_seqs=blast_max_target,
            threads=blast_threads
        )
    elif step == 'step2_7':
        success, output, stats = step2_7_length_stats(input_file, output_dir)
        if success: message = "Length statistics calculated."
    elif step == 'step2_8':
        min_length = int(request.form.get('min_length', 0))
        success, output, message, stats = step2_8_length_filter(input_file, output_dir, min_length)
    elif step == 'step3':
        success, output, message, command = step3_mafft(input_file, output_dir)
    elif step == 'step4':
        mode = request.form.get('clipkit_mode', 'kpic-gappy')
        success, output, message, command = step4_clipkit(input_file, output_dir, mode)
    elif step == 'step5':
        success, output, message, command = step5_iqtree(input_file, output_dir)
    else:
        return jsonify({'success': False, 'error': f'Unknown step: {step}'})

    response_data = {
        'success': success,
        'output': output,
        'message': message,
        'stats': stats,
        'command': command or (commands[0] if commands else None)
    }
    # Always include the result directory used for this step so clients can find other artifacts
    response_data['result_dir'] = output_dir
    return jsonify(response_data)


@phylo_bp.route('/download')
def download():
    """Download a result file for phylo pipeline."""
    try:
        filepath = request.args.get('path', '')
        if not filepath:
            logger.warning("Download attempt without path parameter")
            return jsonify({'success': False, 'error': 'No file path provided'}), 400

        filepath = unquote(filepath)

        if not os.path.isabs(filepath):
            abs_path = os.path.join(config.RESULTS_DIR, filepath)
        else:
            abs_path = filepath

        abs_path = os.path.abspath(abs_path)
        results_dir = os.path.abspath(config.RESULTS_DIR)
        uploads_dir = os.path.abspath(config.UPLOADS_DIR)

        if not (abs_path.startswith(results_dir) or abs_path.startswith(uploads_dir)):
            logger.warning(f"Attempted path traversal: {filepath}")
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        if os.path.exists(abs_path):
            filename = os.path.basename(abs_path)
            force_download = True
            mimetype = None
            if filename.endswith(('.fasta', '.fa', '.aln', '.txt', '.log')):
                mimetype = 'text/plain'
            elif filename.endswith('.json'):
                mimetype = 'application/json'
            elif filename.endswith('.html'):
                mimetype = 'text/html'
                force_download = False

            logger.info(f"Downloading file: {abs_path} (as_attachment={force_download})")
            return send_file(
                abs_path,
                as_attachment=force_download,
                download_name=filename,
                mimetype=mimetype
            )

        logger.error(f"File not found: {abs_path}")
        return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@phylo_bp.route('/hmm-search', methods=['POST'])
def hmm_search():
    """Run HMM search with support for chained file_path input."""
    try:
        try:
            input_file = resolve_input_file(request)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)})

        hmm_files = request.form.getlist('hmm_files[]') or request.form.getlist('hmm_files')
        if not hmm_files:
            return jsonify({'success': False, 'error': 'At least one HMM profile is required.'})

        hmm_paths = []
        for hf in hmm_files:
            if os.path.isabs(hf):
                fname = hf
            else:
                fname = hf if hf.endswith('.hmm') else f"{hf}.hmm"
                fname = os.path.join(config.HMM_PROFILES_DIR, fname)
            hmm_paths.append(fname)

        cut_ga = str(request.form.get('cut_ga', '')).lower() in ('true', '1', 'on', 'yes')
        evalue_raw = request.form.get('evalue', 1e-5)
        try:
            evalue = float(evalue_raw if evalue_raw not in (None, '') else 1e-5)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Invalid e-value'}), 400
        dom_evalue = request.form.get('dom_evalue')
        threads = request.form.get('threads')
        output_dir = create_result_dir('phylo', 'hmm')

        success, output, message, commands = step2_hmmsearch_multiple(
            input_file, hmm_paths, output_dir, cut_ga, evalue, dom_evalue, threads
        )

        hit_count = 0
        if output and os.path.exists(output):
            try:
                with open(output, 'r', encoding='utf-8') as f:
                    hit_count = sum(1 for line in f if line.startswith('>'))
            except Exception:
                hit_count = 0

        output_files = {}
        if output:
            output_files = {
                'hits': output,
                'hits_fasta': output,
                'fasta': output,
                'main': output
            }

        return jsonify({
            'success': success,
            'output_files': output_files,
            'message': message,
            'error': None if success else message,
            'hit_count': hit_count,
            'commands': commands
        })
    except Exception as e:
        logger.error(f"HMM search error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/clipkit-trim', methods=['POST'])
def clipkit_trim():
    """Run ClipKIT trimming with chained input support."""
    try:
        try:
            input_file = resolve_input_file(request)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)})

        mode = request.form.get('mode', 'kpic-gappy')
        gaps_raw = request.form.get('gaps', '')
        gaps = float(gaps_raw) if gaps_raw not in (None, '') else None

        success, result_dir, output_file, log_file, stats_raw = run_clipkit(
            input_file, mode=mode, gaps=gaps
        )

        if not success:
            return jsonify({'success': False, 'error': stats_raw})

        stats = {
            'kept_sites': stats_raw.get('output_length'),
            'total_sites': stats_raw.get('input_length'),
            'percentage_kept': stats_raw.get('percent_kept'),
            'input_seq_count': stats_raw.get('input_seq_count'),
            'output_seq_count': stats_raw.get('output_seq_count')
        }

        return jsonify({
            'success': True,
            'output_file': output_file,
            'result_dir': result_dir,
            'log_file': log_file,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"ClipKIT trim error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/suggest-clipkit-mode', methods=['POST'])
def suggest_clipkit():
    """Suggest ClipKIT mode using alignment conservation."""
    try:
        try:
            input_file = resolve_input_file(request)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)})

        suggested_mode, reason = suggest_clipkit_mode(input_file)
        return jsonify({'success': True, 'suggested_mode': suggested_mode, 'reason': reason})
    except Exception as e:
        logger.error(f"Suggest ClipKIT mode error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/modelfinder', methods=['POST'])
def modelfinder():
    """Run IQ-TREE ModelFinder only."""
    try:
        try:
            input_file = resolve_input_file(request)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)})

        test_models = request.form.get('test_models', 'all')
        threads = request.form.get('threads', 'AUTO')

        success, result_dir, best_model, log_info = run_iqtree_modelfinder(
            input_file, test_models=test_models, threads=threads
        )

        if not success:
            return jsonify({'success': False, 'error': log_info})

        return jsonify({
            'success': True,
            'best_model': best_model,
            'result_dir': result_dir,
            'log_info': log_info
        })
    except Exception as e:
        logger.error(f"ModelFinder error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/iqtree-infer', methods=['POST'])
def iqtree_infer():
    """Run IQ-TREE inference with chained input support."""
    try:
        try:
            input_file = resolve_input_file(request)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)})

        model = request.form.get('model', 'MFP')
        bootstrap = int(request.form.get('bootstrap', 1000))
        bootstrap_type = request.form.get('bootstrap_type', 'ufboot')
        alrt = request.form.get('alrt') == 'true'
        bnni = request.form.get('bnni') == 'true'
        threads = request.form.get('threads', 'AUTO')

        # Build command for display
        command = f'iqtree -s {input_file} -m {model} -bb {bootstrap} -nt {threads}'
        if bnni:
            command += ' -bnni'
        if alrt:
            command += ' -alrt 1000'

        popen, result_dir, output_files, output_prefix = run_iqtree(
            alignment_file=input_file,
            model=model,
            bootstrap=bootstrap,
            bootstrap_type=bootstrap_type,
            alrt=alrt,
            bnni=bnni,
            threads=threads
        )

        # Store process info
        running_processes[output_prefix] = {
            'popen': popen,
            'result_dir': result_dir,
            'output_files': output_files,
            'start_time': os.path.getctime(output_files['log']) if os.path.exists(output_files['log']) else None
        }

        return jsonify({
            'success': True,
            'result_dir': result_dir,
            'output_files': output_files,
            'output_prefix': output_prefix,
            'command': command
        })
    except Exception as e:
        logger.error(f"IQ-TREE inference error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@phylo_bp.route('/iqtree-log')
def iqtree_log():
    """Get IQ-TREE log content."""
    prefix = request.args.get('prefix')
    if not prefix:
        return jsonify({'error': 'No prefix provided'}), 400
    
    log_file = prefix + '.log'
    if not os.path.exists(log_file):
        return jsonify({'content': 'Log file not found yet...'})
    
    try:
        with open(log_file, 'r') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@phylo_bp.route('/iqtree-status')
def iqtree_status():
    """Check IQ-TREE process status."""
    prefix = request.args.get('prefix')
    if prefix not in running_processes:
        return jsonify({'status': 'not_found'})

    proc_info = running_processes[prefix]
    popen = proc_info['popen']

    if popen.poll() is None:
        return jsonify({'status': 'running'})

    # Completed
    del running_processes[prefix]

    # Check if successful
    treefile = proc_info['output_files'].get('treefile')
    if treefile and os.path.exists(treefile):
        support_stats = summarize_bootstrap_support(treefile)
        return jsonify({
            'status': 'completed',
            'output_files': proc_info['output_files'],
            'result_dir': proc_info['result_dir'],
            'support_stats': support_stats
        })
    else:
        # Try to get error from log
        log_file = proc_info['output_files'].get('log')
        error_msg = 'Tree file not found'
        if log_file and os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        error_msg = ''.join(lines[-10:])  # Last 10 lines
            except:
                pass
        return jsonify({'status': 'failed', 'error': error_msg})


@phylo_bp.route('/check-sites', methods=['POST'])
def check_sites():
    """Check trimming status of specific sites in alignment."""
    try:
        alignment_file = resolve_input_file(request)
        clipkit_log = request.form.get('clipkit_log')
        ref_id = request.form.get('ref_id', '').strip()
        sites_str = request.form.get('sites', '').strip()

        if not alignment_file or not os.path.exists(alignment_file):
            return jsonify({'success': False, 'error': 'Alignment file not found'})

        if not clipkit_log or not os.path.exists(clipkit_log):
            return jsonify({'success': False, 'error': 'ClipKIT log file not found'})

        if not ref_id:
            return jsonify({'success': False, 'error': 'Reference ID is required'})

        if not sites_str:
            return jsonify({'success': False, 'error': 'Sites list is required'})

        # Parse sites
        key_sites_set = set()
        for part in sites_str.split(','):
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                key_sites_set.update(range(start, end + 1))
            else:
                key_sites_set.add(int(part))

        # Load trimmed sites
        trimmed_sites_set = set()
        with open(clipkit_log, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1].lower() == 'trim':
                    try:
                        trimmed_sites_set.add(int(parts[0]))
                    except ValueError:
                        continue

        # Find reference sequence
        from app.utils.fasta_utils import parse_fasta
        parsed = parse_fasta(alignment_file)
        ref_seq = None
        for seq_id, _, seq in parsed:
            if seq_id == ref_id:
                ref_seq = seq
                break

        if not ref_seq:
            return jsonify({'success': False, 'error': f'Reference ID {ref_id} not found in alignment'})

        # Map positions
        mapping = []
        pos = 1
        for i, aa in enumerate(ref_seq):
            if aa != '-':
                mapping.append((i + 1, pos))  # (align_col, orig_pos)
                pos += 1

        # Generate report
        report = []
        found_count = 0
        for align_col, orig_pos in mapping:
            if orig_pos in key_sites_set:
                found_count += 1
                aa = ref_seq[align_col - 1]
                is_trimmed = align_col in trimmed_sites_set
                status = "TRIMMED" if is_trimmed else "KEPT"
                report.append({
                    'site': orig_pos,
                    'aa': aa,
                    'align_col': align_col,
                    'status': status
                })

        return jsonify({
            'success': True,
            'report': report,
            'found_count': found_count,
            'total_sites': len(key_sites_set)
        })

    except Exception as e:
        logger.error(f"Site check error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
