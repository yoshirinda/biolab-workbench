from flask import Blueprint, request
import re
from app.utils.decorators import api_route, validate_json, log_request
from app.utils.errors import ValidationError
from app.core.project_manager import (
    add_sequences_to_project,
    move_sequence,
    copy_sequence,
    remove_sequence_from_project,
    update_sequence_in_project,
    add_sequence_feature,
    update_sequence_feature,
    delete_sequence_feature,
    get_feature_types,
    get_project
)
from app.core.sequence_utils import (
    parse_upload_file,
    detect_sequence_type,
    extract_sequences_fuzzy,
    parse_gene_ids_from_text,
    load_source_fasta_library
)
from app.utils.logger import get_app_logger
import os
import tempfile

logger = get_app_logger()
sequences_bp = Blueprint('sequences', __name__, url_prefix='/sequences')


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


@sequences_bp.route('/sources', methods=['GET'])
@api_route
def get_source_library():
    """
    Get the list of available source FASTA files (databases).
    """
    library = load_source_fasta_library()
    return [
        {
            **entry,
            'exists': bool(entry.get('filepath') and os.path.exists(entry.get('filepath')))
        }
        for entry in library
    ]

@sequences_bp.route('/extract', methods=['POST'])
@api_route
@validate_json('target_project', 'gene_ids')
@log_request
def extract_sequences():
    """
    Extract sequences based on gene IDs.
    Source can be a 'source_project' OR a 'source_fasta_id' (database).
    """
    data = request.get_json()
    source_project = data.get('source_project')
    source_fasta_id = data.get('source_fasta_id')
    target_project = data['target_project']
    gene_ids_text = data['gene_ids']
    use_latest_database = bool(data.get('use_latest_database', False))
    strict_single_id_raw = data.get('strict_single_id', None)

    library = load_source_fasta_library()
    if not source_project and not source_fasta_id and not use_latest_database:
        # Prefer database mode when available for better UX.
        if library:
            source_fasta_id = library[0].get('id')
        else:
            raise ValidationError("Either source_project or source_fasta_id is required")
    elif not source_fasta_id and use_latest_database:
        latest_available = next(
            (e for e in library if e.get('filepath') and os.path.exists(e.get('filepath'))),
            None
        )
        if latest_available:
            source_fasta_id = latest_available.get('id')

    tmp_path = None

    try:
        # Determine Source Path
        if source_fasta_id:
            # Case A: Extract from Source FASTA Library (Database)
            entry = next((e for e in library if e['id'] == source_fasta_id), None)
            if not entry:
                # Do not silently switch to an unrelated database when an explicit ID was provided.
                raise ValidationError(f"Source FASTA database not found: {source_fasta_id}")
            
            source_path = entry.get('filepath')
            if (not source_path or not os.path.exists(source_path)) and use_latest_database:
                fallback_entry = next(
                    (e for e in library if e.get('filepath') and os.path.exists(e.get('filepath'))),
                    None
                )
                if fallback_entry:
                    entry = fallback_entry
                    source_fasta_id = entry.get('id')
                    source_path = entry.get('filepath')

            if not source_path or not os.path.exists(source_path):
                raise ValidationError("Source FASTA file is missing on server disk")
            
            # Use this path directly
            tmp_path = None 
            
        else:
            # Case B: Extract from another Project
            success, project_data, msg = get_project(source_project)
            if not success:
                raise ValidationError(f"Source project error: {msg}")
                
            sequences = project_data.get('sequences', [])
            if not sequences:
                raise ValidationError("Source project is empty")
                
            # Dump to temp fasta
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.fasta') as tmp:
                for seq in sequences:
                    header = f"{seq['id']} {seq.get('description', '')}"
                    tmp.write(f">{header}\n{seq['sequence']}\n")
                tmp_path = tmp.name
            source_path = tmp_path

        # Parse IDs
        gene_ids = parse_gene_ids_from_text(gene_ids_text)
        if not gene_ids:
             raise ValidationError("No valid gene IDs found in input text")
        if len(gene_ids) > 50000:
            raise ValidationError("Too many IDs in one request (max: 50000)")

        # Safety default: single-ID extraction should be precision-first unless explicitly disabled.
        if strict_single_id_raw is None:
            strict_single_id = (len(gene_ids) == 1)
            strict_mode_source = 'auto'
        else:
            strict_single_id = _as_bool(strict_single_id_raw, default=False)
            strict_mode_source = 'user'

        # Perform Extraction
        result = extract_sequences_fuzzy(
            source_path,
            gene_ids,
            strict_single_id=strict_single_id
        )
        
        if not result['success']:
            raise ValidationError(result['error'])
            
        extracted_seqs = []
        source_label = source_fasta_id if source_fasta_id else source_project
        
        for seq_id, seq_content in result['sequences']:
            extracted_seqs.append({
                'id': seq_id,
                'description': f"Extracted from {source_label}",
                'sequence': seq_content,
                'type': detect_sequence_type(seq_content)
            })
            
        saved_count = 0
        if extracted_seqs:
            add_success, _, add_msg = add_sequences_to_project(target_project, extracted_seqs)
            if not add_success:
                raise ValidationError(f"Failed to save results: {add_msg}")
            match = re.search(r'Added\s+(\d+)\s+sequences', str(add_msg))
            if match:
                saved_count = int(match.group(1))
        unmatched = result['unmatched']
        unmatched_preview = unmatched[:20]
        extracted_ids = [seq_id for seq_id, _ in result.get('sequences', [])]

        return {
            'message': f"Matched {len(result['matched'])} IDs, added {saved_count} new sequences",
            'source_mode': 'database' if source_fasta_id else 'project',
            'source_fasta_id': source_fasta_id,
            'source_project': source_project,
            'strict_single_id': strict_single_id,
            'strict_mode_source': strict_mode_source,
            'requested_count': len(gene_ids),
            'matched_count': len(result['matched']),
            'extracted_count': len(extracted_seqs),
            'saved_count': saved_count,
            'unmatched_count': len(unmatched),
            'matched': result['matched'],
            'unmatched': unmatched,
            'unmatched_preview': unmatched_preview,
            'extracted_ids': extracted_ids[:50]
        }
        
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

@sequences_bp.route('/import', methods=['POST'])
@api_route
@log_request
def import_sequences():
    """
    Import sequences from uploaded file.
    Supports FASTA, GenBank, SnapGene, etc.
    Form data:
        file: The uploaded file
        project_path: The target project path
    """
    if 'file' not in request.files:
        raise ValidationError("No file uploaded")
    
    file = request.files['file']
    project_path = request.form.get('project_path')
    
    if not project_path:
        raise ValidationError("Target project path required")

    if not file.filename:
        raise ValidationError("No selected file")

    content = file.read() # Read as bytes
    
    parsed_sequences = parse_upload_file(content, file.filename)
    
    if not parsed_sequences:
        raise ValidationError("No sequences found in file or unsupported format")

    # parse_upload_file already returns the correct structure, 
    # but we ensure IDs are unique or clean if needed.
    # The structure is compatible with add_sequences_to_project.

    success, result, msg = add_sequences_to_project(project_path, parsed_sequences)
    if not success:
        raise ValidationError(msg)

    return {'message': msg, 'count': len(parsed_sequences)}

@sequences_bp.route('/move', methods=['POST'])
@api_route
@validate_json('source_project', 'sequence_id', 'dest_project')
@log_request
def move_sequence_route():
    """
    Move a sequence from one project to another.
    """
    data = request.get_json()
    success, msg = move_sequence(
        data['source_project'],
        data['sequence_id'],
        data['dest_project']
    )
    if not success:
        raise ValidationError(msg)
    return {'message': msg}

@sequences_bp.route('/copy', methods=['POST'])
@api_route
@validate_json('source_project', 'sequence_id', 'dest_project')
@log_request
def copy_sequence_route():
    """
    Copy a sequence from one project to another.
    """
    data = request.get_json()
    success, msg = copy_sequence(
        data['source_project'],
        data['sequence_id'],
        data['dest_project']
    )
    if not success:
        raise ValidationError(msg)
    return {'message': msg}

@sequences_bp.route('/<path:project_path>/<sequence_id>', methods=['DELETE'])
@api_route
@log_request
def delete_sequence(project_path, sequence_id):
    """
    Delete a sequence from a project.
    """
    success, result, msg = remove_sequence_from_project(project_path, sequence_id)
    if not success:
        raise ValidationError(msg)
    return {'message': msg}

@sequences_bp.route('/<path:project_path>/<sequence_id>', methods=['PUT'])
@api_route
@log_request
def update_sequence(project_path, sequence_id):
    """
    Update sequence data.
    """
    data = request.get_json()
    success, result, msg = update_sequence_in_project(project_path, sequence_id, data)
    if not success:
        raise ValidationError(msg)
    return {'message': msg}

@sequences_bp.route('/<path:project_path>/<sequence_id>/rename', methods=['POST'])
@api_route
@validate_json('new_name')
@log_request
def rename_sequence(project_path, sequence_id):
    """
    Rename a sequence (change its ID).
    """
    data = request.get_json()
    new_name = data['new_name'].strip()
    if not new_name:
        raise ValidationError("New name cannot be empty")

    # verify new name doesn't exist? add_sequences will handle it but we should check logic
    # We implement rename as: Get -> Modify ID -> Add -> Remove Old
    # This requires project_manager to support this atomic-ish op or we do it here
    
    from app.core.project_manager import get_project, add_sequences_to_project, remove_sequence_from_project
    
    success, project_data, msg = get_project(project_path)
    if not success:
        raise ValidationError(msg)
        
    # Check if new name exists
    if any(s['id'] == new_name for s in project_data.get('sequences', [])):
        raise ValidationError(f"Sequence '{new_name}' already exists in this folder")

    # Find target
    target_seq = next((s for s in project_data.get('sequences', []) if s['id'] == sequence_id), None)
    if not target_seq:
        raise ValidationError("Sequence not found")
        
    # Clone and rename
    import copy
    new_seq = copy.deepcopy(target_seq)
    new_seq['id'] = new_name
    # Update modified time
    from datetime import datetime
    new_seq['modified'] = datetime.now().isoformat()
    
    # Add new
    # We use a direct list manipulation here to be safer/atomic if we were in project_manager, 
    # but here we reuse existing functions.
    # CAUTION: If add fails, we shouldn't delete.
    
    success_add, _, msg_add = add_sequences_to_project(project_path, [new_seq])
    if not success_add:
        raise ValidationError(f"Failed to create new sequence: {msg_add}")
        
    # Delete old
    success_del, _, msg_del = remove_sequence_from_project(project_path, sequence_id)
    if not success_del:
        # This is bad state (duplicate), but unlikely if get_project worked.
        logger.error(f"Renamed {sequence_id} to {new_name} but failed to delete old: {msg_del}")
        
    return {'message': f"Renamed to {new_name}"}

# Feature/Annotation Routes

@sequences_bp.route('/features/types', methods=['GET'])
@api_route
def list_feature_types():
    """Get available feature types."""
    return get_feature_types()

@sequences_bp.route('/<path:project_path>/<sequence_id>/features', methods=['POST'])
@api_route
@log_request
def add_feature(project_path, sequence_id):
    """Add a feature to a sequence."""
    data = request.get_json()
    success, result, msg = add_sequence_feature(project_path, sequence_id, data)
    if not success:
        raise ValidationError(msg)
    return {'message': msg}

@sequences_bp.route('/<path:project_path>/<sequence_id>/features/<feature_id>', methods=['PUT'])
@api_route
@log_request
def update_feature(project_path, sequence_id, feature_id):
    """Update a feature."""
    data = request.get_json()
    success, result, msg = update_sequence_feature(project_path, sequence_id, feature_id, data)
    if not success:
        raise ValidationError(msg)
    return {'message': msg}

@sequences_bp.route('/<path:project_path>/<sequence_id>/features/<feature_id>', methods=['DELETE'])
@api_route
@log_request
def delete_feature(project_path, sequence_id, feature_id):
    """Delete a feature."""
    success, result, msg = delete_sequence_feature(project_path, sequence_id, feature_id)
    if not success:
        raise ValidationError(msg)
    return {'message': msg}
