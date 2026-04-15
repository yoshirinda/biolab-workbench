"""
File utilities for BioLab Workbench.
"""
import os
import json
import sys
import shlex
import socket
import hashlib
import platform
import subprocess
from datetime import datetime
from flask import request, has_request_context
import config
from app.utils.path_utils import ensure_dir, safe_filename


def create_result_dir(tool_name, task_name):
    """
    Create a result directory for a task.
    Format: {tool}_{task}_{YYYYMMDD_HHMMSS_ffffff}/
    Falls back to an incremented suffix if a collision still occurs.
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    base_name = f"{safe_filename(tool_name)}_{safe_filename(task_name)}_{timestamp}"
    result_path = os.path.join(config.RESULTS_DIR, base_name)

    if not os.path.exists(result_path):
        ensure_dir(result_path)
        return result_path

    # Extremely rare collision fallback.
    idx = 1
    while True:
        candidate = os.path.join(config.RESULTS_DIR, f"{base_name}_{idx}")
        if not os.path.exists(candidate):
            ensure_dir(candidate)
            return candidate
        idx += 1


def _run_version_command(binary_name):
    """Best-effort tool version detection."""
    probes = [
        [binary_name, '--version'],
        [binary_name, '-version'],
        [binary_name, '-v'],
    ]
    for cmd in probes:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=6,
                check=False
            )
            output = (proc.stdout or proc.stderr or '').strip()
            if output:
                line = output.splitlines()[0].strip()
                return line[:200]
        except Exception:
            continue
    return None


def detect_tool_versions(tool_names):
    """
    Resolve tool versions for a list of binary names.
    Returns dict: {tool_name: version_or_none}
    """
    versions = {}
    for name in (tool_names or []):
        if not name:
            continue
        binary = os.path.basename(str(name)).strip()
        if binary and binary not in versions:
            versions[binary] = _run_version_command(binary)
    return versions


def sha256_of_file(filepath, max_bytes=256 * 1024 * 1024):
    """
    Compute SHA256 for a file.
    Returns (sha256_hex_or_none, skipped_reason_or_none)
    """
    if not os.path.isfile(filepath):
        return None, 'not_a_file'
    size = os.path.getsize(filepath)
    if size > max_bytes:
        return None, f'skipped_large_file>{max_bytes}'

    digest = hashlib.sha256()
    with open(filepath, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest(), None


def _normalize_path_entries(entries):
    """
    Convert various path container shapes into a list of:
    {'label': <optional>, 'path': <str>}
    """
    normalized = []
    if not entries:
        return normalized

    if isinstance(entries, str):
        return [{'path': entries}]

    if isinstance(entries, dict):
        for label, path in entries.items():
            if isinstance(path, str):
                normalized.append({'label': str(label), 'path': path})
            elif isinstance(path, (list, tuple, set)):
                for idx, value in enumerate(path):
                    if isinstance(value, str):
                        normalized.append({'label': f"{label}[{idx}]", 'path': value})
        return normalized

    if isinstance(entries, (list, tuple, set)):
        for item in entries:
            if isinstance(item, str):
                normalized.append({'path': item})
            elif isinstance(item, dict) and isinstance(item.get('path'), str):
                record = {'path': item['path']}
                if item.get('label'):
                    record['label'] = str(item['label'])
                normalized.append(record)
        return normalized

    return normalized


def _file_record(path_entry):
    path = path_entry.get('path')
    label = path_entry.get('label')
    absolute = os.path.abspath(path) if path else None
    exists = bool(absolute and os.path.exists(absolute))
    is_file = bool(absolute and os.path.isfile(absolute))

    item = {
        'path': absolute or path,
        'exists': exists,
        'is_file': is_file,
    }
    if label:
        item['label'] = label

    if exists:
        try:
            stat = os.stat(absolute)
            item['size'] = stat.st_size
            item['modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        except Exception:
            pass

    if is_file:
        digest, skipped_reason = sha256_of_file(absolute)
        item['sha256'] = digest
        if skipped_reason:
            item['sha256_note'] = skipped_reason

    return item


def _normalize_commands(commands):
    if not commands:
        return []
    if isinstance(commands, str):
        return [commands]
    if isinstance(commands, (list, tuple, set)):
        result = []
        for cmd in commands:
            if isinstance(cmd, str) and cmd.strip():
                result.append(cmd)
        return result
    return []


def _extract_tools_from_commands(commands):
    """
    Best-effort extraction of main tool binaries from command strings.
    """
    tools = []
    wrappers = {'conda', 'bash', 'sh', 'zsh'}
    for command in _normalize_commands(commands):
        try:
            tokens = shlex.split(command)
        except Exception:
            tokens = command.strip().split()
        if not tokens:
            continue

        tool = None
        if tokens[0] == 'conda':
            # Common pattern: conda run -n <env> <tool> ...
            if '--' in tokens:
                idx = tokens.index('--')
                if idx + 1 < len(tokens):
                    tool = tokens[idx + 1]
            else:
                for idx, token in enumerate(tokens):
                    if token in {'run', '-n', '--name', '-p', '--prefix'}:
                        continue
                    if idx > 0 and tokens[idx - 1] in {'-n', '--name', '-p', '--prefix'}:
                        continue
                    if token.startswith('-'):
                        continue
                    if token not in wrappers:
                        tool = token
                        break
        else:
            tool = tokens[0]

        if tool:
            bin_name = os.path.basename(tool)
            if bin_name and bin_name not in tools:
                tools.append(bin_name)
    return tools


def write_result_manifest(
    result_dir,
    domain,
    action,
    input_files=None,
    output_files=None,
    params=None,
    commands=None,
    tools=None,
    notes=None
):
    """
    Emit manifest.json inside result_dir for reproducibility/audit.
    """
    ensure_dir(result_dir)
    now = datetime.now().isoformat()

    normalized_inputs = [_file_record(item) for item in _normalize_path_entries(input_files)]
    normalized_outputs = [_file_record(item) for item in _normalize_path_entries(output_files)]
    command_list = _normalize_commands(commands)

    inferred_tools = list(tools or [])
    if not inferred_tools:
        inferred_tools = _extract_tools_from_commands(command_list)
    tool_versions = detect_tool_versions(inferred_tools)

    request_info = None
    if has_request_context():
        request_info = {
            'method': request.method,
            'path': request.path,
            'remote_addr': request.remote_addr,
            'user_agent': request.user_agent.string if request.user_agent else None,
        }

    manifest = {
        'schema_version': '1.0',
        'created_at': now,
        'domain': domain,
        'action': action,
        'result_dir': os.path.abspath(result_dir),
        'inputs': normalized_inputs,
        'outputs': normalized_outputs,
        'params': params or {},
        'commands': command_list,
        'tool_versions': tool_versions,
        'runtime': {
            'python_version': sys.version.split()[0],
            'platform': platform.platform(),
            'hostname': socket.gethostname(),
        }
    }
    if request_info:
        manifest['request'] = request_info
    if notes:
        manifest['notes'] = notes

    manifest_path = os.path.join(result_dir, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return manifest_path


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


def resolve_input_file(request_obj=None):
    """
    Resolve input file from either a server-side path or an uploaded file.
    
    This helper enables pipeline step chaining by accepting either:
    1. A file_path parameter pointing to a previously generated result
    2. A freshly uploaded file
    
    Args:
        request_obj: Flask request object (defaults to current request)
    
    Returns:
        str: Absolute path to the input file
    
    Raises:
        ValueError: If no valid input is provided or path is invalid/unsafe
    """
    if request_obj is None:
        request_obj = request
    
    # Prefer file_path (server-side path for chaining)
    file_path = request_obj.form.get('file_path', '').strip()
    if not file_path:
        file_path = request_obj.form.get('input_path', '').strip()
    
    if file_path:
        # Security check: ensure path is within allowed directories
        abs_path = os.path.abspath(file_path)
        results_dir = os.path.abspath(config.RESULTS_DIR)
        uploads_dir = os.path.abspath(config.UPLOADS_DIR)
        
        # Check if path is within RESULTS_DIR or UPLOADS_DIR
        if not (abs_path.startswith(results_dir + os.sep) or 
                abs_path.startswith(uploads_dir + os.sep)):
            raise ValueError(
                f"Invalid file path: must be within results or uploads directory. "
                f"Provided path resolves to: {abs_path}"
            )
        
        # Check if file exists
        if not os.path.exists(abs_path):
            raise ValueError(f"File not found: {file_path}")
        
        # Check if it's actually a file
        if not os.path.isfile(abs_path):
            raise ValueError(f"Path is not a file: {file_path}")
        
        return abs_path
    
    # Fall back to uploaded file
    if 'file' in request_obj.files:
        file = request_obj.files['file']
        if file and file.filename:
            return save_uploaded_file(file)
    
    raise ValueError(
        "No input file provided. Please either upload a file or provide a file_path parameter."
    )


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


def find_latest_pipeline_file(search_dir, step_prefixes):
    """
    Find the most recent file in a directory that matches a list of step prefixes.
    
    Args:
        search_dir (str): The directory to search in.
        step_prefixes (list): A list of prefixes to look for (e.g., ['step2_5_', 'step2_']).
    
    Returns:
        str: The full path to the latest file found, or None if no match.
    """
    latest_file = None
    latest_time = 0

    if not os.path.isdir(search_dir):
        return None

    for filename in os.listdir(search_dir):
        for prefix in step_prefixes:
            if filename.startswith(prefix):
                filepath = os.path.join(search_dir, filename)
                if os.path.isfile(filepath):
                    mod_time = os.path.getmtime(filepath)
                    if mod_time > latest_time:
                        latest_time = mod_time
                        latest_file = filepath
    
    return latest_file
