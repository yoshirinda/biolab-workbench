"""
Runtime tool readiness checks for homepage diagnostics.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time

import config

_CACHE = {
    'ts': 0.0,
    'data': None
}


def _build_probe_commands(command: str):
    argv = shlex.split(command)
    candidates = []

    if config.USE_CONDA and config.CONDA_ENV and shutil.which('conda'):
        candidates.append(['conda', 'run', '-n', config.CONDA_ENV, *argv])

    candidates.append(argv)
    return candidates


def _extract_first_line(text: str) -> str:
    for line in (text or '').splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:200]
    return ''


def _run_probe(command: str, timeout: int = 12):
    last_info = 'command not available'

    for argv in _build_probe_commands(command):
        executable = argv[0]
        if shutil.which(executable) is None:
            last_info = f"{executable}: command not found"
            continue

        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=os.environ.copy()
            )
        except Exception as exc:
            last_info = f"{type(exc).__name__}: {exc}"
            continue

        info = _extract_first_line(result.stdout) or _extract_first_line(result.stderr)
        if result.returncode == 0:
            return True, info or 'ok'

        last_info = info or f"exit code {result.returncode}"

    return False, last_info


def get_system_tool_health(force: bool = False, ttl_seconds: int = 120, testing_mode: bool = False):
    """
    Return tool readiness list for newcomer diagnostics.
    """
    tool_defs = [
        {
            'key': 'blast_search',
            'label': 'BLAST search (blastn)',
            'commands': ['blastn -version']
        },
        {
            'key': 'blast_db',
            'label': 'BLAST database build (makeblastdb)',
            'commands': ['makeblastdb -version']
        },
        {
            'key': 'hmmer',
            'label': 'HMMER (hmmsearch)',
            'commands': ['hmmsearch -h']
        },
        {
            'key': 'mafft',
            'label': 'MAFFT',
            'commands': ['mafft --version']
        },
        {
            'key': 'iqtree',
            'label': 'IQ-TREE',
            'commands': ['iqtree -version', 'iqtree2 -version']
        }
    ]

    if testing_mode:
        return [
            {
                'key': item['key'],
                'label': item['label'],
                'available': None,
                'status_text': 'Not checked (test mode)',
                'detail': 'Skipped during tests'
            }
            for item in tool_defs
        ]

    now = time.time()
    if not force and _CACHE['data'] is not None and now - _CACHE['ts'] < ttl_seconds:
        return _CACHE['data']

    result = []
    for item in tool_defs:
        available = False
        detail = 'command not available'
        for cmd in item['commands']:
            ok, info = _run_probe(cmd)
            if ok:
                available = True
                detail = info
                break
            detail = info
        result.append({
            'key': item['key'],
            'label': item['label'],
            'available': available,
            'status_text': 'Ready' if available else 'Missing',
            'detail': detail
        })

    _CACHE['ts'] = now
    _CACHE['data'] = result
    return result
