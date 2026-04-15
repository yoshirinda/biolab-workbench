"""
BLAST routes for BioLab Workbench.
"""
import os
import re
import csv
import uuid
from html import escape
from flask import Blueprint, render_template, request, jsonify, send_file
from werkzeug.exceptions import HTTPException
import config
from app.core.blast_wrapper import (
    list_blast_databases, create_blast_database, run_blast,
    extract_sequences, parse_blast_tsv, delete_blast_database,
    generate_identity_summary
)
from app.utils.file_utils import save_uploaded_file, resolve_input_file, write_result_manifest
from app.utils.logger import get_app_logger

blast_bp = Blueprint('blast', __name__)
logger = get_app_logger()


def _write_identity_summary_tsv(hits, out_path):
    """
    Write a compact summary table with identity bins.
    """
    headers = ['qseqid', 'sseqid', 'pident', 'qcovs', 'length', 'evalue', 'bitscore', 'identity_level']
    with open(out_path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(headers)
        for hit in hits:
            writer.writerow([
                hit.get('qseqid', ''),
                hit.get('sseqid', ''),
                hit.get('pident', ''),
                hit.get('qcovs', ''),
                hit.get('length', ''),
                hit.get('evalue', ''),
                hit.get('bitscore', ''),
                hit.get('identity_level', '')
            ])


def _write_simple_report_html(hits, out_path, context):
    """
    Write a compact standalone HTML report for BLAST table outputs.
    """
    max_rows = 5000
    display_hits = hits[:max_rows]
    truncated = len(hits) > max_rows
    rows_html = []
    for idx, hit in enumerate(display_hits, start=1):
        rows_html.append(
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{escape(str(hit.get('qseqid', '')))}</td>"
            f"<td>{escape(str(hit.get('sseqid', '')))}</td>"
            f"<td>{escape(str(hit.get('pident', '')))}</td>"
            f"<td>{escape(str(hit.get('qcovs', '')))}</td>"
            f"<td>{escape(str(hit.get('length', '')))}</td>"
            f"<td>{escape(str(hit.get('evalue', '')))}</td>"
            f"<td>{escape(str(hit.get('bitscore', '')))}</td>"
            f"<td>{escape(str(hit.get('identity_level', '')))}</td>"
            "</tr>"
        )

    filters_text = []
    if context.get('min_identity') is not None:
        filters_text.append(f"identity >= {context['min_identity']}%")
    if context.get('min_qcovs') is not None:
        filters_text.append(f"qcovs >= {context['min_qcovs']}%")
    if not filters_text:
        filters_text = ['no post-filter']

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BLAST Report</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 24px;
      color: #0f172a;
      background: #f8fafc;
    }}
    h1 {{ margin: 0 0 8px 0; }}
    .meta {{
      background: #e2e8f0;
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 16px;
      line-height: 1.45;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #ffffff;
    }}
    th, td {{
      border: 1px solid #cbd5e1;
      padding: 6px 8px;
      font-size: 13px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #e2e8f0;
      position: sticky;
      top: 0;
    }}
    .wrap {{
      max-height: 72vh;
      overflow: auto;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
    }}
  </style>
</head>
<body>
  <h1>BLAST Report</h1>
  <div class="meta">
    <div><strong>Program:</strong> {escape(str(context.get('program') or 'auto'))}</div>
    <div><strong>Query Type:</strong> {escape(str(context.get('query_type') or 'n/a'))}</div>
    <div><strong>DB Type:</strong> {escape(str(context.get('db_type') or 'n/a'))}</div>
    <div><strong>E-value:</strong> {escape(str(context.get('evalue')))}</div>
    <div><strong>Filters:</strong> {escape(' | '.join(filters_text))}</div>
    <div><strong>Total Hits:</strong> {len(hits)}</div>
    {f'<div><strong>Rows Shown:</strong> first {max_rows} (report truncated for size)</div>' if truncated else ''}
  </div>
  <div class="wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Query</th>
          <th>Subject</th>
          <th>%Identity</th>
          <th>Q-Covs</th>
          <th>Length</th>
          <th>E-value</th>
          <th>BitScore</th>
          <th>Identity Level</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows_html) if rows_html else '<tr><td colspan="9">No hits</td></tr>'}
      </tbody>
    </table>
  </div>
</body>
</html>
"""
    with open(out_path, 'w', encoding='utf-8') as handle:
        handle.write(html)


@blast_bp.errorhandler(Exception)
def blast_error_handler(err):
    """Return JSON for all blast errors to avoid HTML payloads breaking fetch()."""
    status = 500
    if isinstance(err, HTTPException):
        status = err.code or 500
    logger.error(f"BLAST error: {err}")
    return jsonify({'success': False, 'error': str(err)}), status


@blast_bp.route('/')
def blast_page():
    """Render the BLAST page."""
    databases = list_blast_databases()
    return render_template('blast.html', databases=databases)


@blast_bp.route('/databases')
def get_databases():
    """Get list of available BLAST databases."""
    try:
        databases = list_blast_databases()
        return jsonify({'success': True, 'databases': databases})
    except Exception as e:
        logger.error(f"Database listing error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@blast_bp.route('/create-database', methods=['POST'])
def create_database():
    """Create a new BLAST database."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        db_name = request.form.get('db_name', file.filename.rsplit('.', 1)[0])
        db_type = request.form.get('db_type', 'auto')

        # Save uploaded file
        filepath = save_uploaded_file(file)

        success, message, db_path = create_blast_database(filepath, db_name, db_type)

        return jsonify({
            'success': success,
            'message': message,
            'db_path': db_path
        })

    except Exception as e:
        logger.error(f"Database creation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@blast_bp.route('/delete-database', methods=['POST'])
def delete_database():
    """Delete a BLAST database by base path or name."""
    try:
        data = request.get_json() or request.form
        db_path = data.get('db_path') or data.get('database')
        if not db_path:
            return jsonify({'success': False, 'error': 'No database specified'})

        success, message = delete_blast_database(db_path)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        logger.error(f"Database deletion error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@blast_bp.route('/search', methods=['POST'])
def search():
    """Run BLAST search."""
    try:
        def _parse_bool(name, default=None):
            raw = request.form.get(name)
            if raw in (None, ''):
                return default
            return str(raw).strip().lower() in {'1', 'true', 'yes', 'on'}

        def _parse_float(name, default=None, min_val=None, max_val=None):
            raw = request.form.get(name)
            if raw in (None, ''):
                return default
            try:
                value = float(raw)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid {name}: must be a number")
            if min_val is not None and value < min_val:
                raise ValueError(f"Invalid {name}: must be >= {min_val}")
            if max_val is not None and value > max_val:
                raise ValueError(f"Invalid {name}: must be <= {max_val}")
            return value

        def _parse_evalue(name='evalue', default=1e-5):
            raw = request.form.get(name)
            if raw in (None, ''):
                return default
            raw = str(raw).strip()
            # Accept decimal or scientific notation, e.g. 0.001, 1e-5, 2E-20.
            if not re.match(r'^(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?$', raw):
                raise ValueError(f"Invalid {name}: use decimal or scientific notation like 1e-5")
            try:
                value = float(raw)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid {name}: must be a number")
            if value <= 0:
                raise ValueError(f"Invalid {name}: must be > 0")
            if value < 1e-300:
                raise ValueError(f"Invalid {name}: too small (minimum 1e-300)")
            return value

        def _parse_int(name, default=None, min_val=None, max_val=None):
            raw = request.form.get(name)
            if raw in (None, ''):
                return default
            try:
                value = int(raw)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid {name}: must be an integer")
            if min_val is not None and value < min_val:
                raise ValueError(f"Invalid {name}: must be >= {min_val}")
            if max_val is not None and value > max_val:
                raise ValueError(f"Invalid {name}: must be <= {max_val}")
            return value

        # Handle file path chaining, upload, or raw query text
        query_file = None

        # Prefer path/upload resolution when provided
        if request.form.get('file_path') or request.form.get('input_path') or (
            'file' in request.files and request.files['file'].filename
        ):
            try:
                query_file = resolve_input_file(request)
            except ValueError as e:
                return jsonify({'success': False, 'error': str(e)})

        # Fallback to raw query text
        if query_file is None:
            if request.form.get('query_text'):
                import tempfile
                query_text = request.form.get('query_text')
                with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta',
                                                delete=False, dir=config.UPLOADS_DIR) as f:
                    f.write(query_text)
                    query_file = f.name
            else:
                return jsonify({'success': False, 'error': 'No query provided'})

        database = request.form.get('database')
        if not database:
            return jsonify({'success': False, 'error': 'No database selected'})
        db_type_hint = (request.form.get('db_type_hint') or '').strip().lower() or None
        if db_type_hint not in {None, 'nucleotide', 'protein'}:
            db_type_hint = None

        output_format = request.form.get('output_format', 'tsv')
        if output_format not in {'tsv', 'txt', 'html', 'detailed'}:
            return jsonify({'success': False, 'error': 'Invalid output_format'}), 400

        try:
            evalue = _parse_evalue('evalue', default=1e-5)
            max_hits = _parse_int('max_hits', default=500, min_val=1, max_val=1000000)
            min_identity = _parse_float('min_identity', default=None, min_val=0, max_val=100)
            min_qcovs = _parse_float('min_qcovs', default=None, min_val=0, max_val=100)
            word_size = _parse_int('word_size', default=None, min_val=2, max_val=128)
            max_hsps = _parse_int('max_hsps', default=None, min_val=1, max_val=1000000)
            culling_limit = _parse_int('culling_limit', default=None, min_val=0, max_val=1000000)
            comp_based_stats = _parse_int('comp_based_stats', default=None, min_val=0, max_val=3)
            reward = _parse_int('reward', default=None, min_val=1, max_val=100)
            penalty = _parse_int('penalty', default=None, max_val=-1, min_val=-100)
            gapopen = _parse_int('gapopen', default=None, min_val=0, max_val=100)
            gapextend = _parse_int('gapextend', default=None, min_val=0, max_val=100)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        task = (request.form.get('task') or '').strip() or None
        dust = (request.form.get('dust') or '').strip().lower() or None
        seg = (request.form.get('seg') or '').strip().lower() or None
        soft_masking = _parse_bool('soft_masking', default=None)
        if dust not in {None, 'yes', 'no'}:
            return jsonify({'success': False, 'error': "Invalid dust: must be yes/no"}), 400
        if seg not in {None, 'yes', 'no'}:
            return jsonify({'success': False, 'error': "Invalid seg: must be yes/no"}), 400

        # Treat empty/auto as None so backend auto-detect kicks in
        program_raw = request.form.get('program')
        program = (program_raw or '').strip() or None

        success, result_dir, output_files, command = run_blast(
            query_file=query_file,
            database=database,
            output_format=output_format,
            evalue=evalue,
            max_hits=max_hits,
            program=program,
            min_identity=min_identity,
            min_query_coverage=min_qcovs,
            task=task,
            word_size=word_size,
            dust=dust,
            seg=seg,
            soft_masking=soft_masking,
            max_hsps=max_hsps,
            culling_limit=culling_limit,
            comp_based_stats=comp_based_stats,
            reward=reward,
            penalty=penalty,
            gapopen=gapopen,
            gapextend=gapextend,
            db_type_override=db_type_hint
        )

        if success:
            # Parse results for display
            hits = []
            identity_summary = None
            run_warnings = (output_files.get('meta') or {}).get('run_warnings') or []
            raw_preview = None

            result_path = output_files.get('main')
            raw_result_size = 0
            if result_path and os.path.exists(result_path):
                raw_result_size = os.path.getsize(result_path)

            if output_format in ['tsv', 'detailed'] and result_path:
                format_type = 'detailed' if output_format == 'detailed' else 'standard'
                hits = parse_blast_tsv(result_path, format_type)
                if min_identity is not None:
                    hits = [h for h in hits if float(h.get('pident', 0) or 0) >= min_identity]
                if min_qcovs is not None:
                    hits = [h for h in hits if float(h.get('qcovs', 0) or 0) >= min_qcovs]
                identity_summary = generate_identity_summary(hits)
                summary_tsv = os.path.join(result_dir, 'summary.tsv')
                try:
                    _write_identity_summary_tsv(hits, summary_tsv)
                    output_files['summary'] = summary_tsv
                except Exception as summary_error:
                    logger.warning(f"Failed to write BLAST summary.tsv: {summary_error}")
                report_html = os.path.join(result_dir, 'report.html')
                try:
                    _write_simple_report_html(
                        hits,
                        report_html,
                        {
                            'program': output_files.get('program'),
                            'query_type': output_files.get('query_type'),
                            'db_type': output_files.get('db_type'),
                            'evalue': evalue,
                            'min_identity': min_identity,
                            'min_qcovs': min_qcovs
                        }
                    )
                    output_files['report_html'] = report_html
                except Exception as report_error:
                    logger.warning(f"Failed to write BLAST report.html: {report_error}")
                if raw_result_size > 0 and not hits:
                    run_warnings.append(
                        "Result file is not empty but no tabular rows were parsed. "
                        "Try switching Output Format to TSV."
                    )
            elif output_format == 'txt' and result_path and os.path.exists(result_path):
                # Provide in-page preview for pairwise output while keeping full file downloadable.
                max_preview_chars = 20000
                with open(result_path, 'r', encoding='utf-8', errors='replace') as f:
                    raw_preview = f.read(max_preview_chars + 1)
                if len(raw_preview) > max_preview_chars:
                    raw_preview = raw_preview[:max_preview_chars] + "\n\n...[preview truncated, download full result for complete output]"

            try:
                write_result_manifest(
                    result_dir=result_dir,
                    domain='blast',
                    action='search',
                    input_files={
                        'query_file': query_file,
                        'database': database
                    },
                    output_files=output_files,
                    params={
                        'output_format': output_format,
                        'evalue': evalue,
                        'max_hits': max_hits,
                        'min_identity': min_identity,
                        'min_qcovs': min_qcovs,
                        'program': output_files.get('program') or program,
                        'task': task,
                        'word_size': word_size,
                        'dust': dust,
                        'seg': seg,
                        'soft_masking': soft_masking,
                        'max_hsps': max_hsps,
                        'culling_limit': culling_limit,
                        'comp_based_stats': comp_based_stats,
                        'reward': reward,
                        'penalty': penalty,
                        'gapopen': gapopen,
                        'gapextend': gapextend,
                        'db_type_hint': db_type_hint
                    },
                    commands=[command] if command else [],
                    tools=[output_files.get('program') or program]
                )
            except Exception as manifest_error:
                logger.warning(f"Failed to write BLAST manifest: {manifest_error}")

            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'output_files': output_files,
                'hits': hits[:100],  # First 100 for display
                'total_hits': len(hits),
                'result_mode': 'table' if output_format in ['tsv', 'detailed'] else 'raw',
                'output_format': output_format,
                'raw_result_size': raw_result_size,
                'raw_preview': raw_preview,
                'run_warnings': run_warnings,
                'identity_summary': identity_summary,
                'applied_filters': {
                    'min_identity': min_identity,
                    'min_qcovs': min_qcovs
                },
                'applied_options': {
                    'task': task,
                    'word_size': word_size,
                    'dust': dust,
                    'seg': seg,
                    'soft_masking': soft_masking,
                    'max_hsps': max_hsps,
                    'culling_limit': culling_limit,
                    'comp_based_stats': comp_based_stats,
                    'reward': reward,
                    'penalty': penalty,
                    'gapopen': gapopen,
                    'gapextend': gapextend
                },
                'query_type': output_files.get('query_type'),
                'db_type': output_files.get('db_type'),
                'query_length': output_files.get('query_length'),
                'program': output_files.get('program'),
                'command': command
            })
        else:
            return jsonify({'success': False, 'error': result_dir, 'command': command})

    except Exception as e:
        logger.error(f"BLAST search error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@blast_bp.route('/extract', methods=['POST'])
def extract():
    """Extract sequences from BLAST hits."""
    try:
        data = request.get_json()
        database = data.get('database')
        hit_ids = data.get('hit_ids', [])
        result_dir = data.get('result_dir')

        if not database or not hit_ids:
            return jsonify({'success': False, 'error': 'Missing database or hit IDs'})

        if not result_dir:
            result_dir = os.path.join(config.RESULTS_DIR, f'blast_extract_{uuid.uuid4().hex[:10]}')
        os.makedirs(result_dir, exist_ok=True)
        output_file = os.path.join(result_dir, 'extracted_sequences.fasta')

        success, message = extract_sequences(database, hit_ids, output_file)

        if success:
            return jsonify({
                'success': True,
                'message': message,
                'output_file': output_file
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            })

    except Exception as e:
        logger.error(f"Sequence extraction error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@blast_bp.route('/download')
def download():
    """Download a result file."""
    try:
        from urllib.parse import unquote
        
        # Get filepath from query parameter instead of path
        filepath = request.args.get('path', '')
        if not filepath:
            return jsonify({'success': False, 'error': 'No file path provided'}), 400
        
        # URL decode the filepath
        filepath = unquote(filepath)
        
        # Handle both absolute and relative paths
        if not os.path.isabs(filepath):
            abs_path = os.path.join(config.RESULTS_DIR, filepath)
        else:
            abs_path = filepath
        
        abs_path = os.path.abspath(abs_path)
        
        # Security: Ensure the file is within allowed directories
        results_dir = os.path.abspath(config.RESULTS_DIR)
        uploads_dir = os.path.abspath(config.UPLOADS_DIR)
        
        if not (abs_path.startswith(results_dir) or abs_path.startswith(uploads_dir)):
            logger.warning(f"Attempted path traversal: {filepath}")
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        if os.path.exists(abs_path):
            filename = os.path.basename(abs_path)
            return send_file(
                abs_path, 
                as_attachment=True,
                download_name=filename
            )
        else:
            logger.error(f"File not found: {abs_path}")
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
