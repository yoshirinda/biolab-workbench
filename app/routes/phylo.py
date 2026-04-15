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
from app.core.iqtree_wrapper import (
    run_iqtree, run_iqtree_modelfinder, summarize_bootstrap_support, parse_iqtree_log
)
from app.core.sequence_utils import detect_sequence_type
from app.utils.file_utils import (
    save_uploaded_file, list_files_in_dir, resolve_input_file, create_result_dir, write_result_manifest
)
from app.utils.path_utils import safe_filename
from app.utils.fasta_utils import parse_fasta
from app.utils.logger import get_app_logger

phylo_bp = Blueprint('phylo', __name__, url_prefix='/phylo')
logger = get_app_logger()

# Global dict to track running processes
running_processes = {}
VALID_CLIPKIT_MODES = {'kpic', 'kpic-gappy', 'kpi', 'gappy', 'smart-gap'}
IQTREE_AUTO_MODEL_PREFIXES = ('MFP', 'MF', 'TESTONLY', 'TEST')
IQTREE_PROTEIN_MODEL_TOKENS = {
    'LG', 'POISSON', 'CPREV', 'MTREV', 'DAYHOFF', 'MTMAM', 'JTT', 'WAG', 'MTART',
    'MTZOA', 'VT', 'RTREV', 'DCMUT', 'PMB', 'HIVB', 'HIVW', 'JTTDCMUT', 'FLU',
    'BLOSUM62', 'GTR20', 'MTMET', 'MTVER', 'MTINV', 'FLAVI',
    'C10', 'C20', 'C30', 'C40', 'C50', 'C60', 'EX2', 'EX3', 'EHO', 'UL2', 'UL3',
    'EX_EHO', 'LG4M', 'LG4X'
}
IQTREE_NUCLEOTIDE_MODEL_TOKENS = {
    'HKY', 'JC', 'F81', 'K2P', 'K3P', 'K81UF', 'TN', 'TRN', 'TNEF',
    'TIM', 'TIMEF', 'TVM', 'TVMEF', 'SYM', 'GTR', 'STRSYM', 'NONREV', 'UNREST'
}
IQTREE_CODON_MODEL_TOKENS = {
    'KOSI07', 'SCHN05', 'GY', 'MG', 'MGK', 'GY0K', 'GY1KTS', 'GY1KTV',
    'GY2K', 'MG1KTS', 'MG1KTV', 'MG2K'
}
IQTREE_BINARY_MODEL_TOKENS = {'JC2', 'GTR2'}
IQTREE_MORPHOLOGY_MODEL_TOKENS = {'MK', 'ORDERED'}


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


def _parse_threads(value, default='AUTO'):
    if value in (None, ''):
        return default
    val = str(value).strip()
    if val.upper() == 'AUTO':
        return 'AUTO'
    return _parse_int(val, 'threads', minimum=1, maximum=256)


def _normalize_iqtree_support_settings(bootstrap, bootstrap_type, alrt_enabled, alrt_replicates, bnni):
    """
    Enforce IQ-TREE support settings that have clear methodological constraints.

    - Ultrafast bootstrap (-bb) is documented for >= 1000 replicates.
    - SH-aLRT is documented for >= 1000 replicates.
    - -bnni is only meaningful when UFBoot is enabled.
    """
    warnings = []

    if bootstrap > 0 and bootstrap_type in {'ufboot', 'both'} and bootstrap < 1000:
        raise ValueError(
            'Ultrafast bootstrap requires >= 1000 replicates. '
            'Use 1000+ for ufboot/both, or switch to standard bootstrap for quick previews.'
        )

    if alrt_enabled and (alrt_replicates is None or alrt_replicates < 1000):
        raise ValueError('SH-aLRT requires >= 1000 replicates for stable support estimation.')

    bnni_effective = bool(bnni and bootstrap > 0 and bootstrap_type in {'ufboot', 'both'})
    if bnni and not bnni_effective:
        warnings.append('Disabled -bnni because it only applies when ultrafast bootstrap is enabled.')

    return bnni_effective, warnings


def _normalize_hmm_threshold_settings(cut_ga, evalue, dom_evalue):
    """Normalize HMMER threshold options based on official hmmsearch semantics."""
    warnings = []
    effective_settings = {
        'mode': 'cut_ga' if cut_ga else 'custom',
        'cut_ga': bool(cut_ga),
        'sequence_evalue': None,
        'domain_evalue': None
    }
    if cut_ga and dom_evalue is not None:
        warnings.append('Ignored Domain E-value because --cut_ga sets all HMMER thresholding.')
        dom_evalue = None
    if cut_ga:
        return None, None, warnings, effective_settings

    if dom_evalue is None:
        dom_evalue = evalue
        warnings.append('Domain E-value was not provided, so the app used the same threshold as sequence E-value for consistent custom HMMER reporting.')
    elif evalue is not None and dom_evalue > evalue:
        warnings.append('Domain E-value is looser than sequence E-value, so domain-level output may include weaker domains than the sequence-level filter suggests.')
    elif evalue is not None and dom_evalue < evalue:
        warnings.append('Domain E-value is stricter than sequence E-value, so some reported sequence hits may still contain fewer accepted domains.')

    effective_settings['sequence_evalue'] = evalue
    effective_settings['domain_evalue'] = dom_evalue
    return evalue, dom_evalue, warnings, effective_settings


def _normalize_clipkit_gap_settings(mode, gaps):
    """Normalize ClipKIT gap threshold usage based on mode semantics."""
    warnings = []
    gap_threshold_modes = {'gappy', 'kpic-gappy'}
    if gaps is not None and mode not in gap_threshold_modes:
        warnings.append(f'Ignored gap threshold because ClipKIT mode "{mode}" does not use -g.')
        gaps = None
    return gaps, warnings


def _guess_alignment_formats(input_file):
    extension = os.path.splitext(str(input_file or ''))[1].lower()
    preferred = {
        '.fa': ['fasta'],
        '.faa': ['fasta'],
        '.fasta': ['fasta'],
        '.fna': ['fasta'],
        '.fas': ['fasta'],
        '.aln': ['clustal'],
        '.phy': ['phylip-relaxed', 'phylip'],
        '.phylip': ['phylip-relaxed', 'phylip'],
        '.nex': ['nexus'],
        '.nexus': ['nexus'],
        '.msf': ['msf'],
        '.sto': ['stockholm'],
    }.get(extension, [])
    fallback_order = ['fasta', 'phylip-relaxed', 'phylip', 'clustal', 'nexus', 'msf', 'stockholm']
    seen = set()
    ordered = []
    for fmt in preferred + fallback_order:
        if fmt not in seen:
            seen.add(fmt)
            ordered.append(fmt)
    return ordered


def _inspect_alignment_input(input_file):
    """Parse an alignment-like file and summarize whether it is suitable for tree/trimming steps."""
    sequences = []
    parsed_format = None
    parse_error = None

    try:
        from Bio import AlignIO
    except Exception as exc:
        AlignIO = None
        parse_error = exc

    if AlignIO is not None:
        for fmt in _guess_alignment_formats(input_file):
            try:
                alignment = AlignIO.read(input_file, fmt)
                sequences = [str(record.seq) for record in alignment]
                parsed_format = fmt
                break
            except Exception as exc:
                parse_error = exc

    if not sequences:
        parsed = parse_fasta(input_file)
        if parsed:
            sequences = [seq for _, _, seq in parsed]
            parsed_format = parsed_format or 'fasta'

    if not sequences:
        detail = f' ({parse_error})' if parse_error else ''
        raise ValueError(
            'Could not parse this alignment file. Provide a FASTA/PHYLIP/NEXUS/CLUSTAL/MSF alignment.' + detail
        )

    raw_lengths = [len(str(seq or '')) for seq in sequences]
    aligned = len(set(raw_lengths)) <= 1
    type_counts = {'nucleotide': 0, 'protein': 0}
    ungapped_lengths = []
    for seq in sequences:
        clean_seq = str(seq or '').replace('-', '').replace('.', '').replace('?', '').strip()
        ungapped_lengths.append(len(clean_seq))
        if clean_seq:
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

    codon_like = (
        sequence_type == 'nucleotide'
        and bool(ungapped_lengths)
        and all(length == 0 or length % 3 == 0 for length in ungapped_lengths)
    )

    return {
        'format': parsed_format or 'unknown',
        'sequence_count': len(sequences),
        'alignment_length': raw_lengths[0] if aligned and raw_lengths else max(raw_lengths or [0]),
        'min_length': min(raw_lengths) if raw_lengths else 0,
        'max_length': max(raw_lengths) if raw_lengths else 0,
        'aligned': aligned,
        'sequence_type': sequence_type,
        'type_counts': type_counts,
        'contains_gaps': any('-' in str(seq or '') or '.' in str(seq or '') for seq in sequences),
        'codon_like': codon_like,
    }


def _validate_alignment_input_for_phylo(input_stats, tool_name):
    if not input_stats:
        raise ValueError(f'{tool_name} requires a readable alignment input.')

    sequence_count = int((input_stats or {}).get('sequence_count') or 0)
    if sequence_count < 2:
        raise ValueError(f'{tool_name} requires at least two sequences.')

    sequence_type = str((input_stats or {}).get('sequence_type') or 'unknown').lower()
    if sequence_type == 'mixed':
        raise ValueError(
            f'{tool_name} does not support mixed nucleotide/protein inputs. '
            'Split DNA and protein alignments before this step.'
        )

    if not (input_stats or {}).get('aligned'):
        min_length = input_stats.get('min_length', 0)
        max_length = input_stats.get('max_length', 0)
        raise ValueError(
            f'{tool_name} requires an aligned multiple sequence alignment with equal-length sequences. '
            f'Current sequence lengths range from {min_length} to {max_length}. '
            'Run an MSA step first or provide an already aligned file.'
        )

    return input_stats


def _extract_iqtree_model_token(model):
    normalized = str(model or '').strip().upper()
    if not normalized:
        return ''
    for separator in ('+', '*', ' ', '\t'):
        if separator in normalized:
            normalized = normalized.split(separator, 1)[0]
    return normalized


def _classify_iqtree_model(model):
    token = _extract_iqtree_model_token(model)
    if not token:
        return 'unknown', token
    if token.startswith(IQTREE_AUTO_MODEL_PREFIXES):
        return 'auto', token
    if token.startswith('Q.') or token in IQTREE_PROTEIN_MODEL_TOKENS:
        return 'protein', token
    if token.startswith('NQ.') or token in IQTREE_NUCLEOTIDE_MODEL_TOKENS:
        return 'nucleotide', token
    if token in IQTREE_CODON_MODEL_TOKENS:
        return 'codon', token
    if token in IQTREE_BINARY_MODEL_TOKENS:
        return 'binary', token
    if token in IQTREE_MORPHOLOGY_MODEL_TOKENS:
        return 'morphology', token
    if '_' in token:
        left, right = token.split('_', 1)
        if left in IQTREE_CODON_MODEL_TOKENS or right in IQTREE_CODON_MODEL_TOKENS:
            return 'codon', token
    if token.isdigit() and len(token) == 6:
        return 'nucleotide', token
    if token.count('.') == 1 and token.replace('.', '').replace('A', '').replace('B', '').replace('C', '').isdigit():
        return 'nucleotide', token
    return 'unknown', token


def _normalize_iqtree_model_context(input_stats, model):
    sequence_type = str((input_stats or {}).get('sequence_type') or 'unknown').lower()
    model_class, model_token = _classify_iqtree_model(model)
    warnings = []

    if sequence_type == 'nucleotide' and model_class == 'protein':
        raise ValueError(
            f'Detected a nucleotide alignment, but IQ-TREE model "{model}" is protein-oriented. '
            'Use MFP/ModelFinder or a nucleotide/codon model such as GTR+G4.'
        )
    if sequence_type == 'protein' and model_class == 'nucleotide':
        raise ValueError(
            f'Detected a protein alignment, but IQ-TREE model "{model}" is nucleotide-oriented. '
            'Use MFP/ModelFinder or a protein model such as LG+G4.'
        )
    if sequence_type == 'protein' and model_class == 'codon':
        raise ValueError(
            f'Codon model "{model}" requires an in-frame nucleotide codon alignment, not amino-acid sequences.'
        )
    if sequence_type in {'nucleotide', 'protein'} and model_class in {'binary', 'morphology'}:
        raise ValueError(
            f'Model "{model}" is not appropriate for a {sequence_type} sequence alignment in this workflow.'
        )
    if sequence_type == 'nucleotide' and model_class == 'codon' and not (input_stats or {}).get('codon_like'):
        warnings.append(
            'A codon model was requested on nucleotide data. Make sure this alignment is codon-aware and in-frame, '
            'not a generic nucleotide MSA.'
        )
    if model_class == 'unknown' and model_token:
        warnings.append(
            f'The app could not confidently classify IQ-TREE model "{model}". '
            'Review model/data compatibility manually before trusting the result.'
        )

    return {
        'requested_model': model,
        'model_token': model_token,
        'model_class': model_class,
        'selection_mode': 'auto' if model_class == 'auto' else 'manual',
        'input_sequence_type': sequence_type,
        'codon_like_input': bool((input_stats or {}).get('codon_like'))
    }, warnings


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
    manifest_params = {'step': step}
    manifest_tools = []

    if step in {'step0', 'step1'}:
        success, output, message = step0_clean_headers(input_file, output_dir)
        manifest_params['canonical_step'] = 'step0'
        manifest_tools = ['python']
    elif step == 'step2':
        hmm_files = request.form.getlist('hmm_files[]')
        try:
            cut_ga = _as_bool(request.form.get('cut_ga', ''), default=False)
            evalue = _parse_float(request.form.get('evalue', 1e-5), 'evalue', minimum=1e-300, default=1e-5)
            dom_evalue = _parse_float(request.form.get('dom_evalue'), 'dom_evalue', minimum=1e-300, default=None)
            threads = _parse_int(request.form.get('threads'), 'threads', minimum=1, maximum=256, default=None)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        evalue, dom_evalue, step_warnings, hmm_threshold_settings = _normalize_hmm_threshold_settings(cut_ga, evalue, dom_evalue)

        if not hmm_files:
            return jsonify({'success': False, 'error': 'At least one HMM profile is required.'}), 400
        hmm_paths = []
        for hf in hmm_files:
            if os.path.isabs(hf):
                fname = hf
            else:
                fname = hf if hf.endswith('.hmm') else f"{hf}.hmm"
                fname = os.path.join(config.HMM_PROFILES_DIR, fname)
            if not os.path.exists(fname):
                return jsonify({'success': False, 'error': f'HMM profile not found: {hf}'}), 400
            hmm_paths.append(fname)
        success, output, message, commands = step2_hmmsearch_multiple(
            input_file, hmm_paths, output_dir, cut_ga, evalue, dom_evalue, threads
        )
        manifest_params.update({
            'hmm_files': hmm_paths,
            'cut_ga': cut_ga,
            'evalue': evalue,
            'dom_evalue': dom_evalue,
            'threads': threads,
            'effective_thresholds': hmm_threshold_settings
        })
        manifest_tools = ['hmmsearch']
    elif step == 'step2_5':
        gold_name = request.form.get('gold_list_file')
        blast_db_path = request.form.get('blast_db_path')
        blast_program = (request.form.get('blast_program') or '').strip() or None
        strict_gold_match = _as_bool(request.form.get('strict_gold_match', 'true'), default=True)
        try:
            pident = _parse_float(request.form.get('pident', 30), 'pident', minimum=0, maximum=100, default=30)
            qcovs = _parse_float(request.form.get('qcovs', 50), 'qcovs', minimum=0, maximum=100, default=50)
            blast_evalue = _parse_float(request.form.get('blast_evalue'), 'blast_evalue', minimum=1e-300, default=None)
            blast_max_target = _parse_int(
                request.form.get('blast_max_target_seqs', 5),
                'blast_max_target_seqs',
                minimum=1,
                maximum=1000000,
                default=5
            )
            blast_threads = _parse_int(
                request.form.get('blast_threads', config.DEFAULT_THREADS),
                'blast_threads',
                minimum=1,
                maximum=256,
                default=config.DEFAULT_THREADS
            )
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        if not blast_db_path:
            return jsonify({'success': False, 'error': 'BLAST database path is required'}), 400
        if not gold_name:
            return jsonify({'success': False, 'error': 'Gold list file is required'}), 400
        logger.info(
            f"[step2_5] params: pident={pident}, qcovs={qcovs}, evalue={blast_evalue}, "
            f"max_target={blast_max_target}, threads={blast_threads}, gold={gold_name}, "
            f"db={blast_db_path}, program={blast_program}, strict_gold_match={strict_gold_match}"
        )
        gold_file = os.path.join(config.GOLD_LISTS_DIR, gold_name) if gold_name else None
        if gold_file and not os.path.exists(gold_file):
            return jsonify({'success': False, 'error': f'Gold list not found: {gold_name}'}), 400
        success, output, message, stats, command = step2_5_blast_filter(
            input_file, gold_file, output_dir, pident, qcovs, blast_db_path,
            evalue=blast_evalue, max_target_seqs=blast_max_target,
            threads=blast_threads, program=blast_program,
            strict_gold_match=strict_gold_match
        )
        manifest_params.update({
            'pident': pident,
            'qcovs': qcovs,
            'blast_evalue': blast_evalue,
            'blast_max_target_seqs': blast_max_target,
            'blast_threads': blast_threads,
            'gold_list_file': gold_name,
            'blast_db_path': blast_db_path,
            'blast_program': blast_program,
            'strict_gold_match': strict_gold_match
        })
        manifest_tools = ['blastp', 'blastx', 'blastn', 'tblastn', 'tblastx']
    elif step == 'step2_7':
        success, output, stats = step2_7_length_stats(input_file, output_dir)
        if success:
            message = "Length statistics calculated."
        manifest_tools = ['python']
    elif step == 'step2_8':
        try:
            min_length = _parse_int(request.form.get('min_length', 0), 'min_length', minimum=0, maximum=10000000, default=0)
            max_length = _parse_int(request.form.get('max_length'), 'max_length', minimum=1, maximum=10000000, default=None)
            if max_length is not None and max_length < min_length:
                return jsonify({'success': False, 'error': 'max_length must be >= min_length'}), 400
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        success, output, message, stats = step2_8_length_filter(input_file, output_dir, min_length, max_length=max_length)
        manifest_params.update({'min_length': min_length, 'max_length': max_length})
        manifest_tools = ['python']
    elif step == 'step3':
        success, output, message, command = step3_mafft(input_file, output_dir)
        manifest_tools = ['mafft']
    elif step == 'step4':
        mode = request.form.get('clipkit_mode', 'kpic-gappy')
        if mode not in VALID_CLIPKIT_MODES:
            return jsonify({'success': False, 'error': f'Invalid clipkit_mode: {mode}'}), 400
        step_gaps_raw = request.form.get('gaps', '')
        try:
            step_gaps = _parse_float(step_gaps_raw, 'gaps', minimum=0, maximum=1, default=None)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        step_gaps, step_warnings = _normalize_clipkit_gap_settings(mode, step_gaps)
        try:
            input_stats = _inspect_alignment_input(input_file)
            _validate_alignment_input_for_phylo(input_stats, 'ClipKIT')
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        success, output, message, command = step4_clipkit(input_file, output_dir, mode, gaps=step_gaps)
        manifest_params.update({'clipkit_mode': mode})
        manifest_tools = ['clipkit']
    elif step == 'step4_5':
        clipkit_log = request.form.get('clipkit_log', '').strip()
        if clipkit_log:
            if not os.path.isabs(clipkit_log):
                clipkit_log = os.path.abspath(clipkit_log)
            results_dir = os.path.abspath(config.RESULTS_DIR)
            uploads_dir = os.path.abspath(config.UPLOADS_DIR)
            if not (clipkit_log.startswith(results_dir + os.sep) or clipkit_log.startswith(uploads_dir + os.sep)):
                return jsonify({'success': False, 'error': 'Invalid ClipKIT log path'}), 400
            if not os.path.exists(clipkit_log) or not os.path.isfile(clipkit_log):
                return jsonify({'success': False, 'error': 'ClipKIT log file not found'}), 400
        elif 'clipkit_log' in request.files:
            log_upload = request.files['clipkit_log']
            if not log_upload or not log_upload.filename:
                return jsonify({'success': False, 'error': 'ClipKIT log file not provided'}), 400
            safe_log_name = f"clipkit_{safe_filename(log_upload.filename)}"
            clipkit_log = save_uploaded_file(log_upload, filename=safe_log_name)
        else:
            clipkit_log = input_file

        success, stats, message = step4_5_check_sites(clipkit_log)
        output = clipkit_log if success else None
        manifest_params.update({'canonical_step': 'step4_5', 'clipkit_log': clipkit_log})
        manifest_tools = ['python']
    elif step == 'step5':
        try:
            input_stats = _inspect_alignment_input(input_file)
            _validate_alignment_input_for_phylo(input_stats, 'IQ-TREE')
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        success, output, message, command = step5_iqtree(input_file, output_dir)
        manifest_tools = ['iqtree']
    else:
        return jsonify({'success': False, 'error': f'Unknown step: {step}'})

    if success:
        try:
            all_commands = [command] if command else []
            if commands:
                all_commands.extend([cmd for cmd in commands if isinstance(cmd, str) and cmd])
            write_result_manifest(
                result_dir=output_dir,
                domain='phylo',
                action=f'run-step:{step}',
                input_files={'input_file': input_file},
                output_files={'output': output},
                params=manifest_params,
                commands=all_commands,
                tools=manifest_tools
            )
        except Exception as manifest_error:
            logger.warning(f"Failed to write phylo manifest for {step}: {manifest_error}")

    response_data = {
        'success': success,
        'output': output,
        'message': message,
        'stats': stats,
        'command': command or (commands[0] if commands else None),
        'warnings': step_warnings if 'step_warnings' in locals() else []
    }
    if 'hmm_threshold_settings' in locals():
        response_data['threshold_settings'] = hmm_threshold_settings
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
            if not os.path.exists(fname):
                return jsonify({'success': False, 'error': f'HMM profile not found: {hf}'}), 400
            hmm_paths.append(fname)

        try:
            cut_ga = _as_bool(request.form.get('cut_ga', ''), default=False)
            evalue = _parse_float(request.form.get('evalue', 1e-5), 'evalue', minimum=1e-300, default=1e-5)
            dom_evalue = _parse_float(request.form.get('dom_evalue'), 'dom_evalue', minimum=1e-300, default=None)
            threads = _parse_int(request.form.get('threads'), 'threads', minimum=1, maximum=256, default=None)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        evalue, dom_evalue, hmm_warnings, hmm_threshold_settings = _normalize_hmm_threshold_settings(cut_ga, evalue, dom_evalue)
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

        if success:
            try:
                write_result_manifest(
                    result_dir=output_dir,
                    domain='phylo',
                    action='hmm-search',
                    input_files={'input_file': input_file, 'hmm_files': hmm_paths},
                    output_files=output_files,
                    params={
                        'cut_ga': cut_ga,
                        'evalue': evalue,
                        'dom_evalue': dom_evalue,
                        'threads': threads,
                        'effective_thresholds': hmm_threshold_settings
                    },
                    commands=commands,
                    tools=['hmmsearch']
                )
            except Exception as manifest_error:
                logger.warning(f"Failed to write HMM manifest: {manifest_error}")

        return jsonify({
            'success': success,
            'output_files': output_files,
            'message': message,
            'error': None if success else message,
            'hit_count': hit_count,
            'commands': commands,
            'warnings': hmm_warnings,
            'threshold_settings': hmm_threshold_settings,
            'profile_count': len(hmm_paths)
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
        if mode not in VALID_CLIPKIT_MODES:
            return jsonify({'success': False, 'error': f'Invalid mode: {mode}'}), 400
        try:
            gaps = _parse_float(request.form.get('gaps', ''), 'gaps', minimum=0, maximum=1, default=None)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        gaps, clipkit_warnings = _normalize_clipkit_gap_settings(mode, gaps)
        try:
            input_stats = _inspect_alignment_input(input_file)
            _validate_alignment_input_for_phylo(input_stats, 'ClipKIT')
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

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

        try:
            write_result_manifest(
                result_dir=result_dir,
                domain='phylo',
                action='clipkit-trim',
                input_files={'input_file': input_file},
                output_files={'trimmed_alignment': output_file, 'log_file': log_file},
                params={'mode': mode, 'gaps': gaps, 'stats': stats},
                commands=[],
                tools=['clipkit']
            )
        except Exception as manifest_error:
            logger.warning(f"Failed to write ClipKIT manifest: {manifest_error}")

        return jsonify({
            'success': True,
            'output_file': output_file,
            'result_dir': result_dir,
            'log_file': log_file,
            'stats': stats,
            'warnings': clipkit_warnings
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
        try:
            input_stats = _inspect_alignment_input(input_file)
            _validate_alignment_input_for_phylo(input_stats, 'ClipKIT mode suggestion')
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

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
        try:
            input_stats = _inspect_alignment_input(input_file)
            _validate_alignment_input_for_phylo(input_stats, 'ModelFinder')
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        test_models = request.form.get('test_models', 'all')
        try:
            threads = _parse_threads(request.form.get('threads', 'AUTO'), default='AUTO')
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        success, result_dir, best_model, log_info = run_iqtree_modelfinder(
            input_file, test_models=test_models, threads=threads
        )

        if not success:
            return jsonify({'success': False, 'error': log_info})

        try:
            write_result_manifest(
                result_dir=result_dir,
                domain='phylo',
                action='modelfinder',
                input_files={'input_file': input_file},
                output_files={},
                params={'test_models': test_models, 'threads': threads, 'best_model': best_model},
                commands=[],
                tools=['iqtree']
            )
        except Exception as manifest_error:
            logger.warning(f"Failed to write ModelFinder manifest: {manifest_error}")

        return jsonify({
            'success': True,
            'best_model': best_model,
            'result_dir': result_dir,
            'log_info': log_info,
            'input_stats': input_stats
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

        model = (request.form.get('model', 'MFP') or 'MFP').strip()
        if not model:
            return jsonify({'success': False, 'error': 'model is required'}), 400
        if len(model) > 120:
            return jsonify({'success': False, 'error': 'model is too long'}), 400
        try:
            input_stats = _inspect_alignment_input(input_file)
            _validate_alignment_input_for_phylo(input_stats, 'IQ-TREE')
            model_context, model_warnings = _normalize_iqtree_model_context(input_stats, model)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        try:
            bootstrap = _parse_int(request.form.get('bootstrap', 1000), 'bootstrap', minimum=0, maximum=100000, default=1000)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        bootstrap_type = (request.form.get('bootstrap_type', 'ufboot') or 'ufboot').strip().lower()
        if bootstrap_type not in {'ufboot', 'boot', 'both'}:
            return jsonify({'success': False, 'error': f'Invalid bootstrap_type: {bootstrap_type}'}), 400
        try:
            alrt_enabled = _as_bool(request.form.get('alrt'), default=False)
            alrt_replicates = _parse_int(
                request.form.get('alrt_replicates', 1000 if alrt_enabled else None),
                'alrt_replicates',
                minimum=1000,
                maximum=100000,
                default=1000
            ) if alrt_enabled else False
            bnni = _as_bool(request.form.get('bnni'), default=True)
            threads = _parse_threads(request.form.get('threads', 'AUTO'), default='AUTO')
            seed = _parse_int(request.form.get('seed'), 'seed', minimum=1, maximum=2147483647, default=None)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        redo = _as_bool(request.form.get('redo'), default=False)
        try:
            bnni, iqtree_warnings = _normalize_iqtree_support_settings(
                bootstrap=bootstrap,
                bootstrap_type=bootstrap_type,
                alrt_enabled=alrt_enabled,
                alrt_replicates=alrt_replicates if alrt_enabled else None,
                bnni=bnni,
            )
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        iqtree_warnings.extend(model_warnings)

        # Build command for display
        command = f'iqtree -s {input_file} -m {model} -nt {threads}'
        if bootstrap > 0:
            if bootstrap_type == 'ufboot':
                command += f' -bb {bootstrap}'
            elif bootstrap_type == 'boot':
                command += f' -b {bootstrap}'
            elif bootstrap_type == 'both':
                command += f' -bb {bootstrap} -b {bootstrap}'
        if bnni:
            command += ' -bnni'
        if alrt_enabled:
            command += f' -alrt {alrt_replicates}'
        if seed is not None:
            command += f' -seed {seed}'
        if redo:
            command += ' -redo'

        popen, result_dir, output_files, output_prefix = run_iqtree(
            alignment_file=input_file,
            model=model,
            bootstrap=bootstrap,
            bootstrap_type=bootstrap_type,
            alrt=alrt_replicates,
            bnni=bnni,
            threads=threads,
            seed=seed,
            redo=redo
        )

        # Store process info
        running_processes[output_prefix] = {
            'popen': popen,
            'result_dir': result_dir,
            'output_files': output_files,
            'start_time': os.path.getctime(output_files['log']) if os.path.exists(output_files['log']) else None,
            'input_stats': input_stats,
            'model_context': model_context,
            'bootstrap_type': bootstrap_type
        }

        try:
            write_result_manifest(
                result_dir=result_dir,
                domain='phylo',
                action='iqtree-infer',
                input_files={'alignment_file': input_file},
                output_files=output_files,
                params={
                    'model': model,
                    'bootstrap': bootstrap,
                    'bootstrap_type': bootstrap_type,
                    'alrt': alrt_replicates,
                    'bnni': bnni,
                    'threads': threads,
                    'seed': seed,
                    'redo': redo
                },
                commands=[command],
                tools=['iqtree']
            )
        except Exception as manifest_error:
            logger.warning(f"Failed to write IQ-TREE manifest: {manifest_error}")

        return jsonify({
            'success': True,
            'result_dir': result_dir,
            'output_files': output_files,
            'output_prefix': output_prefix,
            'command': command,
            'warnings': iqtree_warnings,
            'input_stats': input_stats,
            'model_context': model_context
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
        log_file = proc_info['output_files'].get('log')
        analysis_info = parse_iqtree_log(log_file) if log_file and os.path.exists(log_file) else {}
        return jsonify({
            'status': 'completed',
            'output_files': proc_info['output_files'],
            'result_dir': proc_info['result_dir'],
            'support_stats': support_stats,
            'input_stats': proc_info.get('input_stats'),
            'model_context': proc_info.get('model_context'),
            'bootstrap_type': proc_info.get('bootstrap_type'),
            'analysis_info': analysis_info
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


@phylo_bp.route('/clipkit-check', methods=['POST'])
def clipkit_check_legacy():
    """
    Legacy endpoint kept for backward compatibility with old frontend scripts.
    Uses ClipKIT log only and does not require alignment mapping.
    """
    try:
        data = request.get_json() or request.form
        ref_id = (data.get('id') or '').strip()
        sites = (data.get('sites') or '').strip()
        log_file = (data.get('log_file') or '').strip()
        if not ref_id or not sites or not log_file:
            return jsonify({'success': False, 'error': 'id, sites, and log_file are required'}), 400

        success, info, msg = step4_5_check_sites(log_file)
        if not success:
            return jsonify({'success': False, 'error': msg})

        site_list = []
        for part in sites.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                try:
                    start, end = map(int, part.split('-', 1))
                except ValueError:
                    return jsonify({'success': False, 'error': f'Invalid range: {part}'}), 400
                if start > end:
                    return jsonify({'success': False, 'error': f'Invalid range: {part}'}), 400
                site_list.extend(list(range(start, end + 1)))
            elif part.isdigit():
                site_list.append(int(part))
            else:
                return jsonify({'success': False, 'error': f'Invalid site token: {part}'}), 400

        kept_line = info.get('sites_kept') or ''
        trimmed_line = info.get('sites_trimmed') or ''
        report = [f"Reference ID: {ref_id}", f"Sites: {site_list}", ""]
        for site in site_list:
            status = 'UNKNOWN'
            if kept_line and str(site) in kept_line:
                status = 'KEPT'
            elif trimmed_line and str(site) in trimmed_line:
                status = 'TRIMMED'
            report.append(f"Site {site}: {status}")

        return jsonify({'success': True, 'report': '\n'.join(report)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


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
                try:
                    start, end = map(int, part.split('-'))
                except ValueError:
                    return jsonify({'success': False, 'error': f'Invalid range: {part}'}), 400
                if start > end:
                    return jsonify({'success': False, 'error': f'Invalid range: {part}'}), 400
                key_sites_set.update(range(start, end + 1))
            else:
                try:
                    key_sites_set.add(int(part))
                except ValueError:
                    return jsonify({'success': False, 'error': f'Invalid site: {part}'}), 400

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
