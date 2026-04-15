"""
General BLAST route for Arabidopsis thaliana (TAIR10) genome.
Supports multiple programs (blastn, blastp, blastx, tblastn).
"""
import os
import uuid
import json
from flask import Blueprint, render_template, request, jsonify, current_app, send_file
import config
from app.core.blast_wrapper import run_blast, parse_blast_tsv, generate_identity_summary
from app.utils.file_utils import resolve_input_file, write_result_manifest, read_fasta_file
from app.utils.logger import get_app_logger
from app.core.sequence_utils import normalize_gene_id, detect_sequence_type

ara_blast_bp = Blueprint('ara_blast', __name__)
logger = get_app_logger()

# Default paths for Arabidopsis
DEFAULT_ARA_PROTEIN_DB = os.environ.get(
    'BIOLAB_ARA_PROTEIN_DB',
    os.path.join(config.DATABASES_DIR, 'AT')
)

@ara_blast_bp.route('/')
def ara_blast_page():
    """Render the Arabidopsis General BLAST page."""
    # Check if the protein database exists
    protein_db_exists = any(os.path.exists(DEFAULT_ARA_PROTEIN_DB + ext) for ext in [".pin", ".phr", ".psq"])
    
    # Check if there are other Arabidopsis databases in the databases dir
    from app.core.blast_wrapper import list_blast_databases
    all_dbs = list_blast_databases()
    # Find all Arabidopsis-related databases
    ara_dbs = [db for db in all_dbs if 'athaliana' in db['name'].lower() or 'arabidopsis' in db['name'].lower() or 'at' == db['name'].lower()]
    
    # Ensure the default protein DB is in the list
    if protein_db_exists and not any(db['path'] == DEFAULT_ARA_PROTEIN_DB for db in ara_dbs):
        ara_dbs.insert(0, {
            'name': 'TAIR10 Protein (Existing)',
            'path': DEFAULT_ARA_PROTEIN_DB,
            'type': 'protein'
        })
    
    return render_template(
        'ara_blast.html', 
        ara_dbs=ara_dbs,
        default_db=DEFAULT_ARA_PROTEIN_DB
    )

@ara_blast_bp.route('/sample-query')
def download_sample():
    """Download a sample protein query file."""
    sample_path = os.path.join(current_app.root_path, 'data', 'examples', 'sample_proteins.fasta')
    if os.path.exists(sample_path):
        return send_file(sample_path, as_attachment=True, download_name='ara_query_sample.fasta')
    return jsonify({'success': False, 'error': 'Sample file not found'}), 404

@ara_blast_bp.route('/search', methods=['POST'])
def search():
    """Run general Arabidopsis BLAST search."""
    try:
        # 1. Resolve query file
        try:
            query_file = resolve_input_file(request)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)})

        if not query_file:
            return jsonify({'success': False, 'error': 'No query provided'})

        # 2. Resolve database
        database = request.form.get('database') or DEFAULT_ARA_PROTEIN_DB
        
        # 3. Parameters
        program = request.form.get('program') or 'auto'
        evalue = float(request.form.get('evalue', 1e-5))
        min_identity = float(request.form.get('min_identity', 0))
        min_qcovs = float(request.form.get('min_qcovs', 0))
        max_hits = int(request.form.get('max_hits', 500))
        
        # 4. Run BLAST (run_blast handles program auto-detection if program='auto')
        success, result_dir, output_files, command = run_blast(
            query_file=query_file,
            database=database,
            output_format='detailed',
            program=None if program == 'auto' else program,
            evalue=evalue,
            max_hits=max_hits,
            min_identity=min_identity,
            min_query_coverage=min_qcovs
        )

        if not success:
            return jsonify({'success': False, 'error': result_dir, 'command': command})

        # 5. Parse Results
        result_path = output_files.get('main')
        hits = parse_blast_tsv(result_path, 'detailed')
        
        # Group hits by Query ID for better readability
        grouped_hits = {}
        for hit in hits:
            qid = hit.get('qseqid', 'unknown')
            if qid not in grouped_hits:
                grouped_hits[qid] = []
            
            # Additional cleanups
            try:
                hit['pident'] = round(float(hit.get('pident', 0)), 1)
                hit['qcovs'] = round(float(hit.get('qcovs', 0)), 1)
                hit['bitscore'] = round(float(hit.get('bitscore', 0)), 0)
            except:
                pass
            
            grouped_hits[qid].append(hit)

        identity_summary = generate_identity_summary(hits)
        
        # 6. Write manifest
        try:
            write_result_manifest(
                result_dir=result_dir,
                domain='ara_blast',
                action='general_search',
                input_files={'query': query_file, 'database': database},
                output_files=output_files,
                params={
                    'program': output_files.get('program'),
                    'evalue': evalue,
                    'min_identity': min_identity,
                    'min_qcovs': min_qcovs
                },
                commands=[command]
            )
        except Exception as e:
            logger.warning(f"Failed to write manifest: {e}")

        return jsonify({
            'success': True,
            'result_dir': result_dir,
            'output_files': output_files,
            'grouped_hits': grouped_hits,
            'total_hits': len(hits),
            'query_count': len(grouped_hits),
            'identity_summary': identity_summary,
            'program': output_files.get('program'),
            'command': command
        })

    except Exception as e:
        logger.error(f"Ara-BLAST error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
