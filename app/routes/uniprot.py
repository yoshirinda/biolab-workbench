"""
UniProt routes for BioLab Workbench.
"""
import os
from flask import Blueprint, render_template, request, jsonify, send_file
import config
from app.core.uniprot_client import search_uniprot, download_sequences, get_entry
from app.utils.logger import get_app_logger

uniprot_bp = Blueprint('uniprot', __name__)
logger = get_app_logger()


@uniprot_bp.route('/')
def uniprot_page():
    """Render the UniProt search page."""
    return render_template('uniprot.html', taxonomy_options=config.TAXONOMY_OPTIONS)


@uniprot_bp.route('/search', methods=['POST'])
def search():
    """Search UniProt."""
    try:
        data = request.get_json() or request.form

        query = data.get('query')
        if not query:
            return jsonify({'success': False, 'error': 'No query provided'})

        taxonomy_id = data.get('taxonomy_id')
        if taxonomy_id:
            taxonomy_id = int(taxonomy_id)

        database_type = data.get('database_type', 'all')
        limit = int(data.get('limit', 500))

        success, results, message = search_uniprot(query, taxonomy_id, database_type, limit)

        if success:
            # Format results for display
            formatted_results = []
            for entry in results:
                formatted_results.append({
                    'accession': entry.get('primaryAccession', ''),
                    'entry_name': entry.get('uniProtkbId', ''),
                    'protein_name': entry.get('proteinDescription', {}).get('recommendedName', {}).get('fullName', {}).get('value', ''),
                    'gene_names': ', '.join([g.get('geneName', {}).get('value', '') for g in entry.get('genes', []) if g.get('geneName')]),
                    'organism': entry.get('organism', {}).get('scientificName', ''),
                    'sequence_length': entry.get('sequence', {}).get('length', 0)
                })

            return jsonify({
                'success': True,
                'results': formatted_results,
                'count': len(formatted_results),
                'message': message
            })
        else:
            return jsonify({'success': False, 'error': message})

    except Exception as e:
        logger.error(f"UniProt search error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@uniprot_bp.route('/download', methods=['POST'])
def download():
    """Download sequences from UniProt."""
    try:
        data = request.get_json() or request.form

        query = data.get('query')
        if not query:
            return jsonify({'success': False, 'error': 'No query provided'})

        taxonomy_id = data.get('taxonomy_id')
        if taxonomy_id:
            taxonomy_id = int(taxonomy_id)

        database_type = data.get('database_type', 'all')
        limit = int(data.get('limit', 500))
        header_format = data.get('header_format', 'gene_species_id')

        success, result_dir, fasta_file, count = download_sequences(
            query, taxonomy_id, database_type, limit, header_format
        )

        if success and fasta_file:
            return jsonify({
                'success': True,
                'result_dir': result_dir,
                'fasta_file': fasta_file,
                'count': count
            })
        else:
            return jsonify({
                'success': False,
                'error': count if isinstance(count, str) else 'No sequences found'
            })

    except Exception as e:
        logger.error(f"UniProt download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@uniprot_bp.route('/entry/<accession>')
def entry(accession):
    """Get a single UniProt entry."""
    try:
        success, entry_data, message = get_entry(accession)

        if success:
            return jsonify({
                'success': True,
                'entry': entry_data
            })
        else:
            return jsonify({'success': False, 'error': message})

    except Exception as e:
        logger.error(f"UniProt entry error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@uniprot_bp.route('/download-file/<path:filepath>')
def download_file(filepath):
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
            if filename.endswith('.fasta') or filename.endswith('.fa') or filename.endswith('.fna') or filename.endswith('.faa'):
                mimetype = 'text/plain'
            elif filename.endswith('.tsv') or filename.endswith('.txt'):
                mimetype = 'text/tab-separated-values'
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
