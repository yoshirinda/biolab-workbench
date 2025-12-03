"""
Sequence management routes for BioLab Workbench.
"""
from flask import Blueprint, render_template, request, jsonify
from app.core.sequence_utils import (
    parse_fasta, format_fasta, detect_sequence_type,
    translate_dna, reverse_complement, find_orfs,
    calculate_sequence_stats, validate_sequence
)
from app.utils.file_utils import save_uploaded_file, read_fasta_file
from app.utils.logger import get_app_logger

sequence_bp = Blueprint('sequence', __name__)
logger = get_app_logger()


@sequence_bp.route('/')
def sequence_page():
    """Render the sequence management page."""
    return render_template('sequence.html')


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

        # Convert to tuple format
        seq_tuples = [(s['id'], s.get('description', ''), s['sequence']) for s in sequences]
        fasta_text = format_fasta(seq_tuples)

        return jsonify({
            'success': True,
            'fasta': fasta_text
        })

    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
