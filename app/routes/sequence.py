"""
Sequence management routes for BioLab Workbench.
"""
import os
import json
import sys
from uuid import uuid4
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session
from app.core.sequence_utils import (
    parse_fasta, format_fasta, detect_sequence_type,
    translate_dna, reverse_complement, find_orfs,
    calculate_sequence_stats, validate_sequence,
    parse_gene_ids_from_text, extract_sequences_fuzzy
)
from app.core.project_manager import (
    list_projects, create_project, get_project, update_project, delete_project, create_folder,
    add_sequences_to_project, remove_sequence_from_project, update_sequence_in_project,
    update_sequence_annotation, export_project_sequences,
    save_collection, load_collection,
    add_sequence_feature, update_sequence_feature, delete_sequence_feature,
    get_feature_types
)
from app.utils.file_utils import save_uploaded_file, read_fasta_file
from app.utils.logger import get_app_logger
import config

sequence_bp = Blueprint('sequence', __name__)
logger = get_app_logger()

# Session key for storing source FASTA path
SOURCE_FASTA_KEY = 'source_fasta_path'
SOURCE_FASTA_ID_KEY = 'source_fasta_id'
SOURCE_FASTA_LIBRARY_FILE = os.path.join(config.UPLOADS_DIR, 'source_fasta_library.json')


def _load_source_fasta_library():
    if os.path.exists(SOURCE_FASTA_LIBRARY_FILE):
        try:
            with open(SOURCE_FASTA_LIBRARY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_source_fasta_library(entries):
    os.makedirs(os.path.dirname(SOURCE_FASTA_LIBRARY_FILE), exist_ok=True)
    with open(SOURCE_FASTA_LIBRARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


@sequence_bp.route('/')
def sequence_page():
    """Render the sequence management page."""
    return render_template('sequence_v2.html')


@sequence_bp.route('/import', methods=['POST'])
def import_sequences():
    """
    Import sequences from file or text and add them to a project.
    """
    try:
        project_path = request.form.get('project_path')
        print(f"!!! DEBUG: Received import request for project_path: '{project_path}'", file=sys.stderr)

        source = request.form.get('source', 'text')
        sequences_to_parse = []

        if source == 'file':
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file part in the request'}), 400
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400
            
            text_content = file.read().decode('utf-8')
            sequences_to_parse = parse_fasta(text_content)

        else: # source == 'text'
            text = request.form.get('text', '')
            if not text.strip():
                return jsonify({'success': False, 'error': 'No sequence text provided'}), 400
            sequences_to_parse = parse_fasta(text)

        if not sequences_to_parse:
            return jsonify({'success': False, 'error': 'No valid FASTA sequences found in the input.'}), 400

        formatted_sequences = []
        for seq_id, desc, seq in sequences_to_parse:
            seq_type = detect_sequence_type(seq)
            formatted_sequences.append({
                'id': seq_id,
                'description': desc,
                'sequence': seq,
                'type': seq_type
            })

        updated_project = None
        message = 'Sequences parsed successfully'
        if project_path:
            success, updated_project, message = add_sequences_to_project(project_path, formatted_sequences)
            if not success:
                return jsonify({'success': False, 'error': message}), 500
            logger.info(f"Imported {len(formatted_sequences)} sequences to project {project_path}")

        response_payload = {
            'success': True,
            'sequences': formatted_sequences,
            'message': message
        }
        if updated_project is not None:
            response_payload['project'] = updated_project

        return jsonify(response_payload)

    except Exception as e:
        logger.error(f"Import error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sequence_bp.route('/translate', methods=['POST'])
def translate():
    """Translate DNA sequence to protein."""
    try:
        data = request.get_json()
        sequence = data.get('sequence', '')
        frame = data.get('frame', 1)

        if not sequence:
            return jsonify({'success': False, 'error': 'No sequence provided'})

        # Validate sequence
        is_valid, error = validate_sequence(sequence, 'nucleotide')
        if not is_valid:
            return jsonify({'success': False, 'error': error})

        protein = translate_dna(sequence, frame)

        return jsonify({
            'success': True,
            'protein': protein,
            'frame': frame,
            'length': len(protein)
        })

    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/reverse-complement', methods=['POST'])
def rev_comp():
    """Get reverse complement of DNA sequence."""
    try:
        data = request.get_json()
        sequence = data.get('sequence', '')

        if not sequence:
            return jsonify({'success': False, 'error': 'No sequence provided'})

        rc = reverse_complement(sequence)

        return jsonify({
            'success': True,
            'reverse_complement': rc,
            'length': len(rc)
        })

    except Exception as e:
        logger.error(f"Reverse complement error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/find-orfs', methods=['POST'])
def orfs():
    """Find open reading frames in sequence."""
    try:
        data = request.get_json()
        sequence = data.get('sequence', '')
        min_length = data.get('min_length', 100)

        if not sequence:
            return jsonify({'success': False, 'error': 'No sequence provided'})

        orf_list = find_orfs(sequence, min_length)

        return jsonify({
            'success': True,
            'orfs': orf_list,
            'count': len(orf_list)
        })

    except Exception as e:
        logger.error(f"ORF finding error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/stats', methods=['POST'])
def stats():
    """Calculate sequence statistics."""
    try:
        data = request.get_json()
        sequence = data.get('sequence', '')

        if not sequence:
            return jsonify({'success': False, 'error': 'No sequence provided'})

        statistics = calculate_sequence_stats(sequence)

        return jsonify({
            'success': True,
            'stats': statistics
        })

    except Exception as e:
        logger.error(f"Stats calculation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/export', methods=['POST'])
def export():
    """Export sequences as FASTA."""
    try:
        data = request.get_json()
        sequences = data.get('sequences', [])

        if not sequences:
            return jsonify({'success': False, 'error': 'No sequences provided'})

        # Convert to tuple format, include annotation if present
        lines = []
        for s in sequences:
            header = s['id']
            if s.get('description'):
                header += ' ' + s['description']
            if s.get('annotation'):
                header += ' [' + s['annotation'] + ']'
            lines.append(f">{header}")
            seq = s['sequence']
            for i in range(0, len(seq), 60):
                lines.append(seq[i:i+60])

        fasta_text = '\n'.join(lines)

        return jsonify({
            'success': True,
            'fasta': fasta_text
        })

    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


# Project Management Routes

@sequence_bp.route('/projects', methods=['GET'])
def get_projects():
    """List all projects."""
    try:
        projects = list_projects()
        return jsonify({'success': True, 'projects': projects})
    except Exception as e:
        logger.error(f"Project listing error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects', methods=['POST'])
def create_new_project():
    """Create a new project."""
    try:
        data = request.get_json()
        path = (data.get('path') or '').strip()
        parent_path = (data.get('parent_path') or '').strip()
        name = (data.get('name') or '').strip()
        description = data.get('description', '')

        if not path and not name:
            return jsonify({'success': False, 'error': 'Project name is required'})

        success, project_data, message = create_project(path=path or None,
                                                       description=description,
                                                       parent_path=parent_path or None,
                                                       name=name or None)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Project creation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/folders', methods=['POST'])
def create_new_folder():
    """Create a new folder."""
    try:
        data = request.get_json()
        path = (data.get('path') or '').strip()
        parent_path = (data.get('parent_path') or '').strip()
        name = (data.get('name') or '').strip()

        if not path and not name:
            return jsonify({'success': False, 'error': 'Folder name is required'})

        success, message = create_folder(path=path or None,
                                         parent_path=parent_path or None,
                                         name=name or None)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        logger.error(f"Folder creation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<path:path>', methods=['GET'])
def get_project_by_path(path):
    """Get a project by its path."""
    try:
        success, project_data, message = get_project(path)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Project retrieval error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<path:path>', methods=['PUT'])
def update_project_by_path(path):
    """Update a project."""
    try:
        data = request.get_json()
        name = data.get('name')
        description = data.get('description')

        success, project_data, message = update_project(path, name, description)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Project update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<path:path>', methods=['DELETE'])
def delete_project_by_path(path):
    """Delete a project."""
    try:
        success, message = delete_project(path)

        return jsonify({
            'success': success,
            'message': message
        })

    except Exception as e:
        logger.error(f"Project deletion error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<path:path>/sequences', methods=['POST'])
def add_sequences(path):
    """Add sequences to a project."""
    try:
        data = request.get_json()
        sequences = data.get('sequences', [])

        if not sequences:
            return jsonify({'success': False, 'error': 'No sequences provided'})

        success, project_data, message = add_sequences_to_project(path, sequences)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Add sequences error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<path:path>/sequences/<sequence_id>', methods=['DELETE'])
def remove_sequence(path, sequence_id):
    """Remove a sequence from a project."""
    try:
        success, project_data, message = remove_sequence_from_project(path, sequence_id)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Remove sequence error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<path:path>/sequences/<sequence_id>', methods=['PUT'])
def update_sequence_in_project_route(path, sequence_id):
    """Update a sequence's details."""
    try:
        data = request.get_json()
        success, project_data, message = update_sequence_in_project(path, sequence_id, data)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Update sequence error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<path:path>/sequences/<sequence_id>/annotation', methods=['PUT'])
def update_annotation(path, sequence_id):
    """Update the annotation for a sequence."""
    try:
        data = request.get_json()
        annotation = data.get('annotation', '')

        success, project_data, message = update_sequence_annotation(path, sequence_id, annotation)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Update annotation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<path:path>/export', methods=['GET'])
def export_project(path):
    """Export all sequences from a project as FASTA."""
    try:
        format_type = request.args.get('format', 'fasta')
        success, result, count = export_project_sequences(path, format_type)

        if success:
            return jsonify({
                'success': True,
                'fasta': result,
                'count': count
            })
        else:
            return jsonify({
                'success': False,
                'error': result
            })

    except Exception as e:
        logger.error(f"Export project error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/collections/save', methods=['POST'])
def save_seq_collection():
    """Save current sequences as a new project/collection."""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '')
        sequences = data.get('sequences', [])

        if not name:
            return jsonify({'success': False, 'error': 'Collection name is required'})

        if not sequences:
            return jsonify({'success': False, 'error': 'No sequences to save'})

        success, project_data, message = save_collection(name, sequences, description)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Save collection error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/collections/<path:path>/load', methods=['GET'])
def load_seq_collection(path):
    """Load sequences from a project/collection."""
    try:
        success, sequences, message = load_collection(path)

        response = jsonify({
            'success': success,
            'sequences': sequences if success else [],
            'message': message
        })
        response.headers['Content-Type'] = 'application/json'
        return response

    except Exception as e:
        logger.error(f"Load collection error: {str(e)}")
        response = jsonify({'success': False, 'error': str(e), 'sequences': []})
        response.headers['Content-Type'] = 'application/json'
        return response


# Feature Annotation Routes

@sequence_bp.route('/feature-types', methods=['GET'])
def get_feature_type_list():
    """Get list of available feature types."""
    try:
        types = get_feature_types()
        return jsonify({'success': True, 'types': types})
    except Exception as e:
        logger.error(f"Get feature types error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<path:path>/sequences/<sequence_id>/features', methods=['POST'])
def add_feature(path, sequence_id):
    """Add a feature annotation to a sequence."""
    try:
        data = request.get_json()

        if not data.get('type') or not data.get('start') or not data.get('end'):
            return jsonify({'success': False, 'error': 'Feature type, start, and end are required'})

        feature = {
            'type': data.get('type'),
            'start': data.get('start'),
            'end': data.get('end'),
            'strand': data.get('strand', '+'),
            'label': data.get('label', ''),
            'color': data.get('color', '#4CAF50'),
            'qualifiers': data.get('qualifiers', {})
        }

        success, project_data, message = add_sequence_feature(path, sequence_id, feature)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Add feature error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<path:path>/sequences/<sequence_id>/features/<feature_id>', methods=['PUT'])
def update_feature(path, sequence_id, feature_id):
    """Update a feature annotation."""
    try:
        data = request.get_json()
        success, project_data, message = update_sequence_feature(
            path, sequence_id, feature_id, data
        )

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Update feature error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<path:path>/sequences/<sequence_id>/features/<feature_id>', methods=['DELETE'])
def remove_feature(path, sequence_id, feature_id):
    """Delete a feature annotation."""
    try:
        success, project_data, message = delete_sequence_feature(
            path, sequence_id, feature_id
        )

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Delete feature error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


# Sequence Extraction Routes

@sequence_bp.route('/set-source-fasta', methods=['POST'])
def set_source_fasta():
    """
    Set the source FASTA file for sequence extraction.
    Stores the file path in session for subsequent extraction operations.
    """
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        label = request.form.get('label', '').strip() or file.filename

        # Save the uploaded file (file_utils handles safe path + unique naming)
        filepath = save_uploaded_file(file)
        
        # Validate it's a valid FASTA file
        try:
            sequences = read_fasta_file(filepath)
            seq_count = len(sequences)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Invalid FASTA file: {e}'})
        
        # Persist in library
        entries = _load_source_fasta_library()
        entry_id = str(uuid4())
        entry = {
            'id': entry_id,
            'label': label,
            'filename': file.filename,
            'filepath': filepath,
            'sequence_count': seq_count,
            'uploaded_at': datetime.utcnow().isoformat() + 'Z'
        }
        entries.insert(0, entry)
        _save_source_fasta_library(entries)

        # Store current selection in session
        session[SOURCE_FASTA_KEY] = filepath
        session[SOURCE_FASTA_ID_KEY] = entry_id
        
        logger.info(f"Source FASTA set: {filepath} ({seq_count} sequences)")
        return jsonify({
            'success': True,
            'filepath': filepath,
            'filename': file.filename,
            'sequence_count': seq_count,
            'entry': entry,
            'library': entries,
            'message': f'Source FASTA set: {seq_count} sequences loaded'
        })

    except Exception as e:
        logger.error(f"Set source FASTA error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/get-source-fasta', methods=['GET'])
def get_source_fasta():
    """Get the current source FASTA file information."""
    try:
        filepath = session.get(SOURCE_FASTA_KEY)
        entry_id = session.get(SOURCE_FASTA_ID_KEY)
        entries = _load_source_fasta_library()
        entry = next((e for e in entries if e.get('id') == entry_id), None)

        if not filepath or not os.path.exists(filepath):
            return jsonify({
                'success': True,
                'has_source': False,
                'filepath': None,
                'filename': None,
                'entry_id': None,
                'library': entries
            })
        
        filename = os.path.basename(filepath)
        return jsonify({
            'success': True,
            'has_source': True,
            'filepath': filepath,
            'filename': filename,
            'entry_id': entry_id,
            'entry': entry,
            'library': entries
        })

    except Exception as e:
        logger.error(f"Get source FASTA error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/clear-source-fasta', methods=['POST'])
def clear_source_fasta():
    """Clear the source FASTA from session."""
    try:
        session.pop(SOURCE_FASTA_KEY, None)
        session.pop(SOURCE_FASTA_ID_KEY, None)
        return jsonify({'success': True, 'message': 'Source FASTA cleared'})
    except Exception as e:
        logger.error(f"Clear source FASTA error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/source-fasta-library', methods=['GET'])
def source_fasta_library():
    """List stored source FASTA entries."""
    try:
        entries = _load_source_fasta_library()
        return jsonify({'success': True, 'library': entries})
    except Exception as e:
        logger.error(f"Source FASTA library error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/delete-source-fasta', methods=['POST'])
def delete_source_fasta():
    """Delete a stored source FASTA entry and optionally the file."""
    try:
        data = request.get_json() or request.form
        entry_id = data.get('id')
        remove_file = str(data.get('remove_file', '')).lower() == 'true'

        if not entry_id:
            return jsonify({'success': False, 'error': 'No source FASTA id provided'})

        entries = _load_source_fasta_library()
        remaining = []
        removed_entry = None
        for e in entries:
            if e.get('id') == entry_id:
                removed_entry = e
            else:
                remaining.append(e)

        if not removed_entry:
            return jsonify({'success': False, 'error': 'Source FASTA not found'})

        # Remove file if requested and exists
        if remove_file:
            filepath = removed_entry.get('filepath')
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    logger.warning(f"Failed to delete FASTA file {filepath}: {e}")

        _save_source_fasta_library(remaining)

        # Clear session if current selection deleted
        if session.get(SOURCE_FASTA_ID_KEY) == entry_id:
            session.pop(SOURCE_FASTA_KEY, None)
            session.pop(SOURCE_FASTA_ID_KEY, None)

        return jsonify({'success': True, 'library': remaining, 'removed': removed_entry})
    except Exception as e:
        logger.error(f"Delete source FASTA error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/use-source-fasta', methods=['POST'])
def use_source_fasta():
    """Select an existing source FASTA from the library."""
    try:
        data = request.get_json()
        entry_id = data.get('id')
        if not entry_id:
            return jsonify({'success': False, 'error': 'No source FASTA id provided'})

        entries = _load_source_fasta_library()
        entry = next((e for e in entries if e.get('id') == entry_id), None)
        if not entry:
            return jsonify({'success': False, 'error': 'Source FASTA not found'})

        filepath = entry.get('filepath')
        if not filepath or not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'Source FASTA file is missing on disk. Please re-upload.'})

        session[SOURCE_FASTA_KEY] = filepath
        session[SOURCE_FASTA_ID_KEY] = entry_id

        return jsonify({'success': True, 'entry': entry})
    except Exception as e:
        logger.error(f"Use source FASTA error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/parse-gene-ids', methods=['POST'])
def parse_gene_ids():
    """
    Parse gene IDs from text input.
    Extracts gene IDs from various formats including BLAST result tables.
    """
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text.strip():
            return jsonify({'success': False, 'error': 'No text provided'})
        
        gene_ids = parse_gene_ids_from_text(text)
        
        return jsonify({
            'success': True,
            'gene_ids': gene_ids,
            'count': len(gene_ids)
        })

    except Exception as e:
        logger.error(f"Parse gene IDs error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/extract-by-ids', methods=['POST'])
def extract_by_ids():
    """
    Extract sequences from source FASTA by gene IDs.
    Uses fuzzy matching for flexible ID matching.
    """
    try:
        data = request.get_json()
        gene_ids = data.get('gene_ids', [])
        source_fasta_id = data.get('source_fasta_id')
        source_fasta = data.get('source_fasta') or session.get(SOURCE_FASTA_KEY)
        entries = None
        if source_fasta_id:
            entries = _load_source_fasta_library()
            entry = next((e for e in entries if e.get('id') == source_fasta_id), None)
            if entry:
                source_fasta = entry.get('filepath')
                session[SOURCE_FASTA_KEY] = source_fasta
                session[SOURCE_FASTA_ID_KEY] = source_fasta_id
        
        if not gene_ids:
            return jsonify({'success': False, 'error': 'No gene IDs provided'})
        
        if not source_fasta:
            return jsonify({'success': False, 'error': 'No source FASTA file set. Please upload a source FASTA first.'})
        
        if not os.path.exists(source_fasta):
            return jsonify({'success': False, 'error': 'Source FASTA file not found. Please upload again.'})
        
        # Extract sequences with fuzzy matching
        result = extract_sequences_fuzzy(source_fasta, gene_ids)
        
        if not result['success']:
            return jsonify({'success': False, 'error': result.get('error', 'Extraction failed')})
        
        # Format sequences for response
        formatted_sequences = []
        for seq_id, seq in result['sequences']:
            seq_type = detect_sequence_type(seq)
            formatted_sequences.append({
                'id': seq_id,
                'sequence': seq,
                'length': len(seq),
                'type': seq_type
            })
        
        # Generate FASTA output
        fasta_lines = []
        for seq_data in formatted_sequences:
            fasta_lines.append(f">{seq_data['id']}")
            seq = seq_data['sequence']
            for i in range(0, len(seq), 60):
                fasta_lines.append(seq[i:i+60])
        fasta_output = '\n'.join(fasta_lines)
        
        return jsonify({
            'success': True,
            'sequences': formatted_sequences,
            'fasta': fasta_output,
            'matched_count': len(result['matched']),
            'unmatched_count': len(result['unmatched']),
            'matched_ids': result['matched'],
            'unmatched_ids': result['unmatched']
        })

    except Exception as e:
        logger.error(f"Extract by IDs error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
