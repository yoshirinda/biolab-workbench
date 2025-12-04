"""
Project management for BioLab Workbench.
Handles sequence organization into projects/folders.
"""
import os
import json
from datetime import datetime
import config
from app.utils.logger import get_app_logger
from app.utils.path_utils import ensure_dir, safe_filename

logger = get_app_logger()

# Project data file name
PROJECT_FILE = 'project.json'


def get_projects_dir():
    """Get the projects directory."""
    return config.PROJECTS_DIR


def list_projects():
    """
    List all projects.
    Returns list of project info dicts.
    """
    projects = []
    projects_dir = get_projects_dir()

    if not os.path.exists(projects_dir):
        return projects

    for name in os.listdir(projects_dir):
        project_path = os.path.join(projects_dir, name)
        if os.path.isdir(project_path):
            project_file = os.path.join(project_path, PROJECT_FILE)
            if os.path.exists(project_file):
                try:
                    with open(project_file, 'r', encoding='utf-8') as f:
                        project_data = json.load(f)
                        project_data['path'] = project_path
                        projects.append(project_data)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Could not read project {name}: {e}")
                    # Add basic project info if file is corrupted
                    projects.append({
                        'id': name,
                        'name': name,
                        'path': project_path,
                        'created': None,
                        'modified': None,
                        'description': ''
                    })

    return sorted(projects, key=lambda p: p.get('modified') or '', reverse=True)


def create_project(name, description=''):
    """
    Create a new project.
    Returns (success, project_data, message).
    """
    # Create safe project ID from name
    project_id = safe_filename(name)
    if not project_id:
        return False, None, "Invalid project name"

    project_path = os.path.join(get_projects_dir(), project_id)

    if os.path.exists(project_path):
        return False, None, f"Project '{name}' already exists"

    try:
        ensure_dir(project_path)

        now = datetime.now().isoformat()
        project_data = {
            'id': project_id,
            'name': name,
            'description': description,
            'created': now,
            'modified': now,
            'sequences': []
        }

        project_file = os.path.join(project_path, PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        project_data['path'] = project_path
        logger.info(f"Created project: {name}")
        return True, project_data, "Project created successfully"

    except Exception as e:
        logger.error(f"Failed to create project {name}: {e}")
        return False, None, str(e)


def get_project(project_id):
    """
    Get a project by ID.
    Returns (success, project_data, message).
    """
    project_path = os.path.join(get_projects_dir(), safe_filename(project_id))
    project_file = os.path.join(project_path, PROJECT_FILE)

    if not os.path.exists(project_file):
        return False, None, "Project not found"

    try:
        with open(project_file, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
            project_data['path'] = project_path
            return True, project_data, "Success"
    except Exception as e:
        logger.error(f"Failed to read project {project_id}: {e}")
        return False, None, str(e)


def update_project(project_id, name=None, description=None):
    """
    Update project metadata.
    Returns (success, project_data, message).
    """
    success, project_data, msg = get_project(project_id)
    if not success:
        return False, None, msg

    try:
        if name is not None:
            project_data['name'] = name
        if description is not None:
            project_data['description'] = description
        project_data['modified'] = datetime.now().isoformat()

        project_file = os.path.join(project_data['path'], PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        return True, project_data, "Project updated successfully"
    except Exception as e:
        logger.error(f"Failed to update project {project_id}: {e}")
        return False, None, str(e)


def delete_project(project_id):
    """
    Delete a project.
    Returns (success, message).
    """
    project_path = os.path.join(get_projects_dir(), safe_filename(project_id))

    if not os.path.exists(project_path):
        return False, "Project not found"

    try:
        import shutil
        shutil.rmtree(project_path)
        logger.info(f"Deleted project: {project_id}")
        return True, "Project deleted successfully"
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        return False, str(e)


def add_sequences_to_project(project_id, sequences):
    """
    Add sequences to a project.
    sequences: list of sequence dicts with id, description, sequence, type, annotation (optional), features (optional)
    Returns (success, project_data, message).
    """
    success, project_data, msg = get_project(project_id)
    if not success:
        return False, None, msg

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

        project_file = os.path.join(project_data['path'], PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        return True, project_data, f"Added {added} sequences"
    except Exception as e:
        logger.error(f"Failed to add sequences to project {project_id}: {e}")
        return False, None, str(e)


def remove_sequence_from_project(project_id, sequence_id):
    """
    Remove a sequence from a project.
    Returns (success, project_data, message).
    """
    success, project_data, msg = get_project(project_id)
    if not success:
        return False, None, msg

    try:
        sequences = project_data.get('sequences', [])
        original_len = len(sequences)
        project_data['sequences'] = [s for s in sequences if s['id'] != sequence_id]

        if len(project_data['sequences']) == original_len:
            return False, None, "Sequence not found in project"

        project_data['modified'] = datetime.now().isoformat()

        project_file = os.path.join(project_data['path'], PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        return True, project_data, "Sequence removed"
    except Exception as e:
        logger.error(f"Failed to remove sequence from project {project_id}: {e}")
        return False, None, str(e)


def update_sequence_annotation(project_id, sequence_id, annotation):
    """
    Update the annotation for a sequence in a project.
    Returns (success, project_data, message).
    """
    success, project_data, msg = get_project(project_id)
    if not success:
        return False, None, msg

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

        project_file = os.path.join(project_data['path'], PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        return True, project_data, "Annotation updated"
    except Exception as e:
        logger.error(f"Failed to update annotation: {e}")
        return False, None, str(e)


def export_project_sequences(project_id, format='fasta'):
    """
    Export all sequences from a project.
    Returns (success, fasta_text_or_error, count).
    """
    success, project_data, msg = get_project(project_id)
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
            # Write sequence in lines of 60 characters
            sequence = seq['sequence']
            for i in range(0, len(sequence), 60):
                lines.append(sequence[i:i+60])
        return True, '\n'.join(lines), len(sequences)
    else:
        return False, f"Unsupported format: {format}", 0


def save_collection(name, sequences, description=''):
    """
    Save a sequence collection as a new project.
    sequences: list of sequence dicts
    Returns (success, project_data, message).
    """
    success, project_data, msg = create_project(name, description)
    if not success:
        return False, None, msg

    return add_sequences_to_project(project_data['id'], sequences)


def load_collection(project_id):
    """
    Load a sequence collection from a project.
    Returns (success, sequences, message).
    """
    try:
        success, project_data, msg = get_project(project_id)
        if not success:
            return False, [], msg

        sequences = project_data.get('sequences', [])
        # Ensure all sequences have required fields
        validated_sequences = []
        for seq in sequences:
            validated_seq = {
                'id': seq.get('id', 'unknown'),
                'description': seq.get('description', ''),
                'sequence': seq.get('sequence', ''),
                'type': seq.get('type', 'unknown'),
                'length': seq.get('length', len(seq.get('sequence', ''))),
                'annotation': seq.get('annotation', ''),
                'features': seq.get('features', [])
            }
            validated_sequences.append(validated_seq)

        return True, validated_sequences, "Loaded successfully"
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error when loading project {project_id}: {e}")
        return False, [], f"Failed to parse project data: {str(e)}"
    except Exception as e:
        logger.error(f"Error loading collection {project_id}: {e}")
        return False, [], str(e)


def add_sequence_feature(project_id, sequence_id, feature):
    """
    Add a feature annotation to a sequence.
    feature: dict with type, start, end, strand (optional), label, color (optional), qualifiers (optional)
    Returns (success, project_data, message).
    """
    success, project_data, msg = get_project(project_id)
    if not success:
        return False, None, msg

    try:
        import uuid
        found = False
        for seq in project_data.get('sequences', []):
            if seq['id'] == sequence_id:
                # Initialize features list if not exists
                if 'features' not in seq:
                    seq['features'] = []
                
                # Add feature with unique ID (using full UUID for uniqueness)
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

        project_file = os.path.join(project_data['path'], PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        return True, project_data, "Feature added"
    except Exception as e:
        logger.error(f"Failed to add feature: {e}")
        return False, None, str(e)


def update_sequence_feature(project_id, sequence_id, feature_id, feature_updates):
    """
    Update a feature annotation on a sequence.
    Returns (success, project_data, message).
    """
    success, project_data, msg = get_project(project_id)
    if not success:
        return False, None, msg

    try:
        found = False
        for seq in project_data.get('sequences', []):
            if seq['id'] == sequence_id:
                for feature in seq.get('features', []):
                    if feature['id'] == feature_id:
                        # Update feature fields
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

        project_file = os.path.join(project_data['path'], PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        return True, project_data, "Feature updated"
    except Exception as e:
        logger.error(f"Failed to update feature: {e}")
        return False, None, str(e)


def delete_sequence_feature(project_id, sequence_id, feature_id):
    """
    Delete a feature annotation from a sequence.
    Returns (success, project_data, message).
    """
    success, project_data, msg = get_project(project_id)
    if not success:
        return False, None, msg

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

        project_file = os.path.join(project_data['path'], PROJECT_FILE)
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        return True, project_data, "Feature deleted"
    except Exception as e:
        logger.error(f"Failed to delete feature: {e}")
        return False, None, str(e)


# Feature type definitions (Geneious-like)
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
