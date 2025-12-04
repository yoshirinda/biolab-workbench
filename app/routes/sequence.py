"""
Sequence management routes for BioLab Workbench.
"""
from flask import Blueprint, render_template, request, jsonify
from app.core.sequence_utils import (
    parse_fasta, format_fasta, detect_sequence_type,
    translate_dna, reverse_complement, find_orfs,
    calculate_sequence_stats, validate_sequence
)
from app.core.project_manager import (
    list_projects, create_project, get_project, update_project, delete_project,
    add_sequences_to_project, remove_sequence_from_project,
    update_sequence_annotation, export_project_sequences,
    save_collection, load_collection,
    add_sequence_feature, update_sequence_feature, delete_sequence_feature,
    get_feature_types
)
from app.utils.file_utils import save_uploaded_file, read_fasta_file
from app.utils.logger import get_app_logger

sequence_bp = Blueprint('sequence', __name__)
logger = get_app_logger()


@sequence_bp.route('/')
def sequence_page():
    """Render the sequence management page."""
    projects = list_projects()
    return render_template('sequence.html', projects=projects)


@sequence_bp.route('/import', methods=['POST'])
def import_sequences():
    """Import sequences from file or text."""
    try:
        source = request.form.get('source', 'text')

        if source == 'file':
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file uploaded'})

            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'})

            filepath = save_uploaded_file(file)
            sequences = read_fasta_file(filepath)
            # Convert to 3-tuple format
            sequences = [(h.split()[0], ' '.join(h.split()[1:]), s) for h, s in sequences]

        else:
            text = request.form.get('text', '')
            if not text.strip():
                return jsonify({'success': False, 'error': 'No sequence text provided'})

            sequences = parse_fasta(text)

        result = []
        for seq_id, desc, seq in sequences:
            seq_type = detect_sequence_type(seq)
            result.append({
                'id': seq_id,
                'description': desc,
                'sequence': seq,
                'length': len(seq),
                'type': seq_type
            })

        logger.info(f"Imported {len(result)} sequences")
        return jsonify({'success': True, 'sequences': result})

    except Exception as e:
        logger.error(f"Import error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


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
        name = data.get('name', '').strip()
        description = data.get('description', '')

        if not name:
            return jsonify({'success': False, 'error': 'Project name is required'})

        success, project_data, message = create_project(name, description)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Project creation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<project_id>', methods=['GET'])
def get_project_by_id(project_id):
    """Get a project by ID."""
    try:
        success, project_data, message = get_project(project_id)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Project retrieval error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<project_id>', methods=['PUT'])
def update_project_by_id(project_id):
    """Update a project."""
    try:
        data = request.get_json()
        name = data.get('name')
        description = data.get('description')

        success, project_data, message = update_project(project_id, name, description)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Project update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<project_id>', methods=['DELETE'])
def delete_project_by_id(project_id):
    """Delete a project."""
    try:
        success, message = delete_project(project_id)

        return jsonify({
            'success': success,
            'message': message
        })

    except Exception as e:
        logger.error(f"Project deletion error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<project_id>/sequences', methods=['POST'])
def add_sequences(project_id):
    """Add sequences to a project."""
    try:
        data = request.get_json()
        sequences = data.get('sequences', [])

        if not sequences:
            return jsonify({'success': False, 'error': 'No sequences provided'})

        success, project_data, message = add_sequences_to_project(project_id, sequences)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Add sequences error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<project_id>/sequences/<sequence_id>', methods=['DELETE'])
def remove_sequence(project_id, sequence_id):
    """Remove a sequence from a project."""
    try:
        success, project_data, message = remove_sequence_from_project(project_id, sequence_id)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Remove sequence error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<project_id>/sequences/<sequence_id>/annotation', methods=['PUT'])
def update_annotation(project_id, sequence_id):
    """Update the annotation for a sequence."""
    try:
        data = request.get_json()
        annotation = data.get('annotation', '')

        success, project_data, message = update_sequence_annotation(
            project_id, sequence_id, annotation
        )

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Update annotation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<project_id>/export', methods=['GET'])
def export_project(project_id):
    """Export all sequences from a project as FASTA."""
    try:
        format_type = request.args.get('format', 'fasta')
        success, result, count = export_project_sequences(project_id, format_type)

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


@sequence_bp.route('/collections/<project_id>/load', methods=['GET'])
def load_seq_collection(project_id):
    """Load sequences from a project/collection."""
    try:
        success, sequences, message = load_collection(project_id)

        # Ensure we always return proper JSON with Content-Type header
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


@sequence_bp.route('/projects/<project_id>/sequences/<sequence_id>/features', methods=['POST'])
def add_feature(project_id, sequence_id):
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

        success, project_data, message = add_sequence_feature(project_id, sequence_id, feature)

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Add feature error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<project_id>/sequences/<sequence_id>/features/<feature_id>', methods=['PUT'])
def update_feature(project_id, sequence_id, feature_id):
    """Update a feature annotation."""
    try:
        data = request.get_json()

        success, project_data, message = update_sequence_feature(
            project_id, sequence_id, feature_id, data
        )

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Update feature error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@sequence_bp.route('/projects/<project_id>/sequences/<sequence_id>/features/<feature_id>', methods=['DELETE'])
def remove_feature(project_id, sequence_id, feature_id):
    """Delete a feature annotation."""
    try:
        success, project_data, message = delete_sequence_feature(
            project_id, sequence_id, feature_id
        )

        return jsonify({
            'success': success,
            'project': project_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Delete feature error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
