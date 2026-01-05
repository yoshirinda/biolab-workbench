"""Project management for BioLab Workbench.
Handles sequence organization into projects/folders.
"""
import os
import json
from datetime import datetime
import config
from app.utils.logger import get_app_logger
from app.utils.path_utils import ensure_dir, safe_filename
from app.core.sequence_utils import layout_features, detect_sequence_type

logger = get_app_logger()

# Project data file name
PROJECT_FILE = 'project.json'


def _posix_path(path: str) -> str:
    """Normalize path separators to forward slashes for API/frontend consistency."""
    return path.replace('\\', '/')

def _to_fs_path(relative_path: str) -> str:
    """Convert a normalized relative path to a filesystem path under projects dir."""
    cleaned = _posix_path(relative_path)
    parts = [p for p in cleaned.split('/') if p]
    return os.path.join(get_projects_dir(), *parts)


def _normalize_path_input(path=None, parent_path=None, name=None):
    """
    Accept either a full path or parent/name parts and return a sanitized relative path
    plus the resolved filesystem path and leaf name.
    """
    candidate = (path or '').strip()
    if not candidate:
        parts = []
        if parent_path:
            parts.extend([safe_filename(p) for p in _posix_path(parent_path).split('/') if p])
        if name:
            parts.append(safe_filename(name))
        candidate = '/'.join([p for p in parts if p])

    path_parts = [safe_filename(p) for p in _posix_path(candidate).split('/') if p]
    if not path_parts or not all(path_parts):
        return False, None, None, None, "Invalid project/folder path or name"

    relative_path = '/'.join(path_parts)
    fs_path = os.path.join(get_projects_dir(), *path_parts)
    return True, relative_path, fs_path, path_parts[-1], None

def get_projects_dir():
    """Get the projects directory."""
    return config.PROJECTS_DIR

def _scan_directory_recursive(path, base_path):
    tree = []
    if not os.path.isdir(path):
        return tree

    for name in sorted(os.listdir(path)):
        full_path = os.path.join(path, name)
        if os.path.isdir(full_path):
            relative_path = _posix_path(os.path.relpath(full_path, base_path))
            if relative_path == '.':
                continue
            
            project_file = os.path.join(full_path, PROJECT_FILE)
            
            node = {
                'id': relative_path.replace('/', '_'),
                'name': name,
                'path': relative_path,
                'children': _scan_directory_recursive(full_path, base_path)
            }

            if os.path.exists(project_file):
                try:
                    with open(project_file, 'r', encoding='utf-8') as f:
                        project_data = json.load(f)
                        node.update(project_data)
                        node['is_project'] = True
                except Exception as e:
                    logger.warning(f"Could not read project {name}: {e}")
                    node['is_project'] = True
                    node['error'] = str(e)
            else:
                node['is_project'] = False
            
            # Always overwrite path to ensure it is normalized and relative
            node['path'] = relative_path
            tree.append(node)
            
    return tree

def list_projects():
    """
    List all projects in a hierarchical structure.
    Returns a tree of project/folder nodes.
    """
    projects_dir = get_projects_dir()
    ensure_dir(projects_dir)
    return _scan_directory_recursive(projects_dir, projects_dir)

def create_project(path=None, description='', parent_path=None, name=None):
    """
    Create a new project.
    Accepts either a single path string or parent_path + name for easier UX.
    Returns (success, project_data, message).
    """
    ok, relative_path, project_path, project_name, error = _normalize_path_input(path, parent_path, name)
    if not ok:
        return False, None, error

    project_id = relative_path.replace('/', '_')

    if os.path.exists(project_path):
        return False, None, f"Project or folder at '{relative_path}' already exists"

    try:
        ensure_dir(project_path)
        now = datetime.now().isoformat()
        project_data = {
            'id': project_id,
            'name': project_name,
            'path': relative_path,
            'description': description,
            'created': now,
            'modified': now,
            'sequences': [],
            'is_project': True
        }
        project_file = os.path.join(project_path, PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Created project: {relative_path}")
        return True, project_data, "Project created successfully"
    except Exception as e:
        logger.error(f"Failed to create project {relative_path}: {e}")
        return False, None, str(e)

def create_folder(path=None, parent_path=None, name=None):
    """
    Create a new folder; allows separate parent/name inputs for friendlier UI.
    """
    ok, relative_path, folder_path, folder_name, error = _normalize_path_input(path, parent_path, name)
    if not ok:
        return False, error

    if os.path.exists(folder_path):
        return False, f"Folder or project at '{relative_path}' already exists"

    try:
        ensure_dir(folder_path)
        logger.info(f"Created folder: {relative_path}")
        return True, "Folder created successfully"
    except Exception as e:
        logger.error(f"Failed to create folder {relative_path}: {e}")
        return False, str(e)

def get_project(path):
    """
    Get a project by its path relative to the projects directory.
    Returns (success, project_data, message).
    """
    normalized = _posix_path(path)
    if '..' in normalized or os.path.isabs(normalized):
        return False, None, "Invalid project path"
    
    project_path = _to_fs_path(normalized)
    project_file = os.path.join(project_path, PROJECT_FILE)

    if not os.path.exists(project_file):
        return False, None, "Project not found"

    try:
        with open(project_file, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
            project_data['path'] = normalized
            for seq in project_data.get('sequences', []):
                if 'features' in seq:
                    seq['feature_lanes'] = layout_features(seq['features'])
            return True, project_data, "Success"
    except Exception as e:
        logger.error(f"Failed to read project {normalized}: {e}")
        return False, None, str(e)

def update_project(path, name=None, description=None):
    """
    Update project metadata.
    Returns (success, project_data, message).
    """
    success, project_data, msg = get_project(path)
    if not success:
        return False, None, msg
    project_path = _to_fs_path(path)
    try:
        if name is not None:
            project_data['name'] = name
        if description is not None:
            project_data['description'] = description
        project_data['modified'] = datetime.now().isoformat()
        
        for seq in project_data.get('sequences', []):
            if 'feature_lanes' in seq:
                del seq['feature_lanes']

        project_file = os.path.join(project_path, PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        return True, project_data, "Project updated successfully"
    except Exception as e:
        logger.error(f"Failed to update project {path}: {e}")
        return False, None, str(e)

def delete_project(path):
    """
    Delete a project or folder.
    Returns (success, message).
    """
    normalized = _posix_path(path)
    if '..' in normalized or os.path.isabs(normalized):
        return False, "Invalid project path"
    
    project_path = _to_fs_path(normalized)
    if not os.path.exists(project_path):
        return False, "Project not found"
    try:
        import shutil
        shutil.rmtree(project_path)
        logger.info(f"Deleted project/folder: {normalized}")
        return True, "Project deleted successfully"
    except Exception as e:
        logger.error(f"Failed to delete project/folder {normalized}: {e}")
        return False, str(e)

def add_sequences_to_project(path, sequences):
    """
    Add sequences to a project.
    """
    success, project_data, msg = get_project(path)
    if not success:
        return False, None, msg
    project_path = _to_fs_path(path)
    try:
        existing_ids = {s['id'] for s in project_data.get('sequences', [])}
        added = 0
        for seq in sequences:
            if seq['id'] not in existing_ids:
                seq_entry = {
                    'id': seq['id'],
                    'description': seq.get('description', ''),
                    'sequence': seq['sequence'],
                    'type': seq.get('type', 'unknown'),
                    'length': len(seq['sequence']),
                    'annotation': seq.get('annotation', ''),
                    'features': seq.get('features', []),
                    'added': datetime.now().isoformat()
                }
                project_data.setdefault('sequences', []).append(seq_entry)
                added += 1
        project_data['modified'] = datetime.now().isoformat()
        
        for seq in project_data.get('sequences', []):
            if 'feature_lanes' in seq:
                del seq['feature_lanes']

        project_file = os.path.join(project_path, PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        return True, project_data, f"Added {added} sequences"
    except Exception as e:
        logger.error(f"Failed to add sequences to project {path}: {e}")
        return False, None, str(e)

def remove_sequence_from_project(path, sequence_id):
    """
    Remove a sequence from a project.
    """
    success, project_data, msg = get_project(path)
    if not success:
        return False, None, msg
    project_path = _to_fs_path(path)
    try:
        sequences = project_data.get('sequences', [])
        original_len = len(sequences)
        project_data['sequences'] = [s for s in sequences if s['id'] != sequence_id]
        if len(project_data['sequences']) == original_len:
            return False, None, "Sequence not found in project"
        project_data['modified'] = datetime.now().isoformat()

        for seq in project_data.get('sequences', []):
            if 'feature_lanes' in seq:
                del seq['feature_lanes']
                
        project_file = os.path.join(project_path, PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        return True, project_data, "Sequence removed"
    except Exception as e:
        logger.error(f"Failed to remove sequence from project {path}: {e}")
        return False, None, str(e)

def update_sequence_in_project(path, sequence_id, updates):
    """
    Update a sequence in a project.
    """
    success, project_data, msg = get_project(path)
    if not success:
        return False, None, msg
    project_path = _to_fs_path(path)
    try:
        found = False
        for seq in project_data.get('sequences', []):
            if seq['id'] == sequence_id:
                if 'description' in updates:
                    seq['description'] = updates['description']
                if 'sequence' in updates:
                    sequence_content = updates['sequence']
                    seq['sequence'] = sequence_content
                    seq['length'] = len(sequence_content)
                    seq['type'] = detect_sequence_type(sequence_content)
                seq['modified'] = datetime.now().isoformat()
                found = True
                break
        if not found:
            return False, None, "Sequence not found in project"
        project_data['modified'] = datetime.now().isoformat()
        
        for seq in project_data.get('sequences', []):
            if 'feature_lanes' in seq:
                del seq['feature_lanes']

        project_file = os.path.join(project_path, PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        return True, project_data, "Sequence updated"
    except Exception as e:
        logger.error(f"Failed to update sequence: {e}")
        return False, None, str(e)

def update_sequence_annotation(path, sequence_id, annotation):
    """
    Update the annotation for a sequence in a project.
    """
    success, project_data, msg = get_project(path)
    if not success:
        return False, None, msg
    project_path = _to_fs_path(path)
    try:
        found = False
        for seq in project_data.get('sequences', []):
            if seq['id'] == sequence_id:
                seq['annotation'] = annotation
                seq['modified'] = datetime.now().isoformat()
                found = True
                break
        if not found:
            return False, None, "Sequence not found in project"
        project_data['modified'] = datetime.now().isoformat()
        
        for seq in project_data.get('sequences', []):
            if 'feature_lanes' in seq:
                del seq['feature_lanes']

        project_file = os.path.join(project_path, PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        return True, project_data, "Annotation updated"
    except Exception as e:
        logger.error(f"Failed to update annotation: {e}")
        return False, None, str(e)

def export_project_sequences(path, format='fasta'):
    """
    Export all sequences from a project.
    """
    success, project_data, msg = get_project(path)
    if not success:
        return False, msg, 0
    sequences = project_data.get('sequences', [])
    if not sequences:
        return False, "No sequences in project", 0

    if format == 'fasta':
        lines = []
        for seq in sequences:
            header = seq['id']
            if seq.get('description'):
                header += ' ' + seq['description']
            if seq.get('annotation'):
                header += ' [' + seq['annotation'] + ']'
            lines.append(f">{header}")
            sequence = seq['sequence']
            for i in range(0, len(sequence), 60):
                lines.append(sequence[i:i+60])
        return True, '\n'.join(lines), len(sequences)
    else:
        return False, f"Unsupported format: {format}", 0

def save_collection(name, sequences, description=''):
    """
    Save a sequence collection as a new project at the root level.
    """
    success, project_data, msg = create_project(name, description)
    if not success:
        return False, None, msg
    return add_sequences_to_project(project_data['path'], sequences)

def load_collection(path):
    """
    Load a sequence collection from a project.
    """
    try:
        success, project_data, msg = get_project(path)
        if not success:
            return False, [], msg
        sequences = project_data.get('sequences', [])
        validated_sequences = []
        for seq in sequences:
            validated_seq = {
                'id': seq.get('id', 'unknown'),
                'description': seq.get('description', ''),
                'sequence': seq.get('sequence', ''),
                'type': seq.get('type', 'unknown'),
                'length': seq.get('length', len(seq.get('sequence', ''))),
                'annotation': seq.get('annotation', ''),
                'features': seq.get('features', []),
                'feature_lanes': layout_features(seq.get('features', []))
            }
            validated_sequences.append(validated_seq)
        return True, validated_sequences, "Loaded successfully"
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error when loading project {path}: {e}")
        return False, [], f"Failed to parse project data: {str(e)}"
    except Exception as e:
        logger.error(f"Error loading collection {path}: {e}")
        return False, [], str(e)

def add_sequence_feature(path, sequence_id, feature):
    """
    Add a feature annotation to a sequence.
    """
    success, project_data, msg = get_project(path)
    if not success:
        return False, None, msg
    project_path = _to_fs_path(path)
    try:
        import uuid
        found = False
        for seq in project_data.get('sequences', []):
            if seq['id'] == sequence_id:
                if 'features' not in seq:
                    seq['features'] = []
                
                feature_entry = {
                    'id': str(uuid.uuid4()),
                    'type': feature.get('type', 'region'),
                    'start': int(feature.get('start', 1)),
                    'end': int(feature.get('end', 1)),
                    'strand': feature.get('strand', '+'),
                    'label': feature.get('label', ''),
                    'color': feature.get('color', '#4CAF50'),
                    'qualifiers': feature.get('qualifiers', {}),
                    'created': datetime.now().isoformat()
                }
                seq['features'].append(feature_entry)
                seq['modified'] = datetime.now().isoformat()
                found = True
                break
        if not found:
            return False, None, "Sequence not found in project"
        project_data['modified'] = datetime.now().isoformat()

        for seq in project_data.get('sequences', []):
            if 'feature_lanes' in seq:
                del seq['feature_lanes']
                
        project_file = os.path.join(project_path, PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        return True, project_data, "Feature added"
    except Exception as e:
        logger.error(f"Failed to add feature: {e}")
        return False, None, str(e)

def update_sequence_feature(path, sequence_id, feature_id, feature_updates):
    """
    Update a feature annotation on a sequence.
    """
    success, project_data, msg = get_project(path)
    if not success:
        return False, None, msg
    project_path = _to_fs_path(path)
    try:
        found = False
        for seq in project_data.get('sequences', []):
            if seq['id'] == sequence_id:
                for feature in seq.get('features', []):
                    if feature['id'] == feature_id:
                        for key, value in feature_updates.items():
                            if key in ['type', 'start', 'end', 'strand', 'label', 'color', 'qualifiers']:
                                if key in ['start', 'end']:
                                    feature[key] = int(value)
                                else:
                                    feature[key] = value
                        feature['modified'] = datetime.now().isoformat()
                        found = True
                        break
                break
        if not found:
            return False, None, "Feature not found"
        project_data['modified'] = datetime.now().isoformat()

        for seq in project_data.get('sequences', []):
            if 'feature_lanes' in seq:
                del seq['feature_lanes']

        project_file = os.path.join(project_path, PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        return True, project_data, "Feature updated"
    except Exception as e:
        logger.error(f"Failed to update feature: {e}")
        return False, None, str(e)

def delete_sequence_feature(path, sequence_id, feature_id):
    """
    Delete a feature annotation from a sequence.
    """
    success, project_data, msg = get_project(path)
    if not success:
        return False, None, msg
    project_path = _to_fs_path(path)
    try:
        found = False
        for seq in project_data.get('sequences', []):
            if seq['id'] == sequence_id:
                original_len = len(seq.get('features', []))
                seq['features'] = [f for f in seq.get('features', []) if f['id'] != feature_id]
                if len(seq.get('features', [])) < original_len:
                    found = True
                    seq['modified'] = datetime.now().isoformat()
                break
        if not found:
            return False, None, "Feature not found"
        project_data['modified'] = datetime.now().isoformat()

        for seq in project_data.get('sequences', []):
            if 'feature_lanes' in seq:
                del seq['feature_lanes']

        project_file = os.path.join(project_path, PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        return True, project_data, "Feature deleted"
    except Exception as e:
        logger.error(f"Failed to delete feature: {e}")
        return False, None, str(e)

# Feature type definitions (Geneious-like)
import shutil

FEATURE_TYPES = [
    {'id': 'CDS', 'name': 'CDS (Coding Sequence)', 'color': '#4CAF50'},
    {'id': 'gene', 'name': 'Gene', 'color': '#2196F3'},
    {'id': 'exon', 'name': 'Exon', 'color': '#9C27B0'},
    {'id': 'intron', 'name': 'Intron', 'color': '#607D8B'},
    {'id': 'promoter', 'name': 'Promoter', 'color': '#FF9800'},
    {'id': 'domain', 'name': 'Domain', 'color': '#E91E63'},
    {'id': 'motif', 'name': 'Motif', 'color': '#00BCD4'},
    {'id': 'region', 'name': 'Region', 'color': '#795548'},
    {'id': 'misc_feature', 'name': 'Misc Feature', 'color': '#9E9E9E'},
    {'id': 'primer_bind', 'name': 'Primer Binding Site', 'color': '#CDDC39'},
    {'id': 'mutation', 'name': 'Mutation', 'color': '#F44336'},
    {'id': 'variation', 'name': 'Variation', 'color': '#FF5722'},
]

def get_feature_types():
    """Get list of available feature types."""
    return FEATURE_TYPES

def move_folder(source_path, dest_parent_path):
    """
    Move a folder or project to a new parent directory.
    source_path: relative path of the folder to move (e.g. "folder/subfolder")
    dest_parent_path: relative path of the new parent (e.g. "archive"). Use "" or "." for root.
    """
    source_normalized = _posix_path(source_path)
    dest_normalized = _posix_path(dest_parent_path) if dest_parent_path else ""
    
    if '..' in source_normalized or '..' in dest_normalized:
        return False, "Invalid path"

    full_source = _to_fs_path(source_normalized)
    full_dest_parent = _to_fs_path(dest_normalized) if dest_normalized else get_projects_dir()
    
    if not os.path.exists(full_source):
        return False, "Source folder not found"
    
    folder_name = os.path.basename(full_source)
    full_dest = os.path.join(full_dest_parent, folder_name)
    
    if os.path.exists(full_dest):
        return False, "Destination folder already exists"
        
    try:
        shutil.move(full_source, full_dest)
        return True, "Folder moved successfully"
    except Exception as e:
        logger.error(f"Failed to move folder: {e}")
        return False, str(e)

def copy_sequence(source_project_path, sequence_id, dest_project_path):
    """
    Copy a sequence from one project to another.
    """
    success, source_data, msg = get_project(source_project_path)
    if not success:
        return False, f"Source project error: {msg}"
    
    # Find sequence
    sequence = next((s for s in source_data.get('sequences', []) if s['id'] == sequence_id), None)
    if not sequence:
        return False, "Sequence not found"
        
    # Add to dest
    # We create a deep copy of the sequence to avoid reference issues
    import copy
    new_sequence = copy.deepcopy(sequence)
    
    # If copying to same project, append " Copy" to ID/Name
    if source_project_path == dest_project_path:
         new_sequence['id'] = f"{new_sequence['id']}_copy"
         new_sequence['description'] = f"{new_sequence.get('description', '')} (Copy)"

    return add_sequences_to_project(dest_project_path, [new_sequence])

def move_sequence(source_project_path, sequence_id, dest_project_path):
    """
    Move a sequence from one project to another.
    """
    # 1. Copy
    success, data, msg = copy_sequence(source_project_path, sequence_id, dest_project_path)
    if not success:
        return False, msg
    
    # 2. Delete from source
    # Only if copy was successful and it's not the same project (though copy logic handles same project by renaming, moving in same project is basically a no-op or rename, but let's allow the delete for consistency if requested, though typically move in same project is weird unless it's reordering which we don't support yet. Actually, let's just delete.)
    if source_project_path != dest_project_path:
        del_success, del_data, del_msg = remove_sequence_from_project(source_project_path, sequence_id)
        if not del_success:
            return False, f"Copied but failed to delete from source: {del_msg}"
            
    return True, "Sequence moved successfully"

