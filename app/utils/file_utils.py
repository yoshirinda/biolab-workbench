"""
File utilities for BioLab Workbench.
"""
import os
import json
from datetime import datetime
import config
from app.utils.path_utils import ensure_dir, safe_filename


def create_result_dir(tool_name, task_name):
    """
    Create a result directory for a task.
    Format: {tool}_{task}_{YYYYMMDD_HHMMSS}/
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dir_name = f"{safe_filename(tool_name)}_{safe_filename(task_name)}_{timestamp}"
    result_path = os.path.join(config.RESULTS_DIR, dir_name)
    ensure_dir(result_path)
    return result_path


def save_params(result_dir, params):
    """
    Save run parameters to params.json in the result directory.
    """
    params_file = os.path.join(result_dir, 'params.json')
    with open(params_file, 'w', encoding='utf-8') as f:
        json.dump(params, f, indent=2, ensure_ascii=False)
    return params_file


def save_uploaded_file(file_storage, filename=None):
    """
    Save an uploaded file to the uploads directory.
    Returns the path to the saved file.
    """
    if filename is None:
        filename = file_storage.filename

    filename = safe_filename(filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    save_name = f"{timestamp}_{filename}"
    save_path = os.path.join(config.UPLOADS_DIR, save_name)

    file_storage.save(save_path)
    return save_path


def read_fasta_file(filepath):
    """
    Read a FASTA file and return list of (header, sequence) tuples.
    """
    sequences = []
    current_header = None
    current_seq = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if current_header is not None:
                    sequences.append((current_header, ''.join(current_seq)))
                current_header = line[1:]
                current_seq = []
            elif line:
                current_seq.append(line)

        if current_header is not None:
            sequences.append((current_header, ''.join(current_seq)))

    return sequences


def write_fasta_file(filepath, sequences):
    """
    Write sequences to a FASTA file.
    sequences: list of (header, sequence) tuples
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        for header, seq in sequences:
            f.write(f">{header}\n")
            # Write sequence in lines of 60 characters
            for i in range(0, len(seq), 60):
                f.write(seq[i:i+60] + '\n')


def list_files_in_dir(directory, extensions=None):
    """
    List files in a directory, optionally filtering by extension.
    """
    if not os.path.exists(directory):
        return []

    files = []
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            if extensions is None:
                files.append(filename)
            elif any(filename.endswith(ext) for ext in extensions):
                files.append(filename)

    return sorted(files)


def get_file_info(filepath):
    """
    Get information about a file.
    """
    if not os.path.exists(filepath):
        return None

    stat = os.stat(filepath)
    return {
        'name': os.path.basename(filepath),
        'path': filepath,
        'size': stat.st_size,
        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }
