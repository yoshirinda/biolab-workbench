"""
BLAST routes for BioLab Workbench.
"""
import os
from flask import Blueprint, render_template, request, jsonify, send_file
import config
from app.core.blast_wrapper import (
    list_blast_databases, create_blast_database, run_blast,
    extract_sequences, parse_blast_tsv
)
from app.utils.file_utils import save_uploaded_file
from app.utils.logger import get_app_logger

blast_bp = Blueprint('blast', __name__)
logger = get_app_logger()


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


@blast_bp.route('/search', methods=['POST'])
def search():
    """Run BLAST search."""
    try:
        # Handle file or text input
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            query_file = save_uploaded_file(file)
        elif request.form.get('query_text'):
            # Save query text to temp file
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

        output_format = request.form.get('output_format', 'tsv')
        evalue = float(request.form.get('evalue', 1e-5))
        max_hits = int(request.form.get('max_hits', 500))
        program = request.form.get('program')  # None for auto-detect

        success, result_dir, output_files, command = run_blast(
            query_file=query_file,
            database=database,
            output_format=output_format,
            evalue=evalue,
            max_hits=max_hits,
            program=program
        )

        if success:
            # Parse results for display
            hits = []
            if output_format == 'tsv' and output_files.get('main'):
                hits = parse_blast_tsv(output_files['main'])

            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'output_files': output_files,
                'hits': hits[:100],  # First 100 for display
                'total_hits': len(hits),
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

        output_file = os.path.join(result_dir, 'extracted_sequences.fasta')

        success, message = extract_sequences(database, hit_ids, output_file)

        return jsonify({
            'success': success,
            'message': message,
            'output_file': output_file
        })

    except Exception as e:
        logger.error(f"Sequence extraction error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@blast_bp.route('/download/<path:filepath>')
def download(filepath):
    """Download a result file."""
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
            # Determine MIME type based on file extension
            filename = os.path.basename(abs_path)
            mimetype = None
            if filename.endswith('.fasta') or filename.endswith('.fa') or filename.endswith('.fna') or filename.endswith('.faa'):
                mimetype = 'text/plain'
            elif filename.endswith('.tsv') or filename.endswith('.txt'):
                mimetype = 'text/tab-separated-values'
            elif filename.endswith('.json'):
                mimetype = 'application/json'
            elif filename.endswith('.xml'):
                mimetype = 'application/xml'
            
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
