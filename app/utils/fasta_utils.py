"""
Unified FASTA file utilities for BioLab Workbench.
Consolidates FASTA parsing/writing logic from multiple modules.
"""
import os
import re
from typing import List, Tuple, Dict, Optional
from app.utils.logger import get_app_logger

logger = get_app_logger()


def parse_fasta(text_or_file: str) -> List[Tuple[str, str, str]]:
    """
    Parse FASTA format text or file.
    
    Args:
        text_or_file: FASTA text content or file path
        
    Returns:
        List of (id, description, sequence) tuples
    """
    # Check if input is a file path
    if os.path.exists(text_or_file):
        try:
            with open(text_or_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read FASTA file: {e}")
            return []
    else:
        content = text_or_file
    
    sequences = []
    current_id = None
    current_desc = ""
    current_seq = []
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('>'):
            # Save previous sequence
            if current_id is not None:
                sequences.append((
                    current_id,
                    current_desc,
                    ''.join(current_seq)
                ))
            
            # Parse header
            header = line[1:]
            parts = header.split(None, 1)
            current_id = parts[0] if parts else header
            current_desc = parts[1] if len(parts) > 1 else ""
            current_seq = []
        else:
            # Sequence line - remove whitespace and non-letter chars except dash
            clean_seq = ''.join(c for c in line if c.isalpha() or c == '-')
            if clean_seq:
                current_seq.append(clean_seq)
    
    # Save last sequence
    if current_id is not None:
        sequences.append((
            current_id,
            current_desc,
            ''.join(current_seq)
        ))
    
    return sequences


def write_fasta(sequences: List[Tuple[str, str, str]], output_path: str, line_width: int = 60):
    """
    Write sequences to FASTA file.
    
    Args:
        sequences: List of (id, description, sequence) tuples
        output_path: Output file path
        line_width: Characters per line for sequence (default 60)
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for seq_id, desc, seq in sequences:
                # Write header
                if desc:
                    f.write(f">{seq_id} {desc}\n")
                else:
                    f.write(f">{seq_id}\n")
                
                # Write sequence in lines
                for i in range(0, len(seq), line_width):
                    f.write(seq[i:i+line_width] + '\n')
        
        logger.info(f"Wrote {len(sequences)} sequences to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to write FASTA: {e}")
        return False


def calculate_sequence_lengths(sequences: List[Tuple[str, str, str]]) -> Dict[str, int]:
    """
    Calculate sequence lengths.
    
    Returns:
        Dict of {id: length}
    """
    return {seq_id: len(seq) for seq_id, _, seq in sequences}


def filter_by_length(sequences: List[Tuple[str, str, str]], 
                     min_length: Optional[int] = None,
                     max_length: Optional[int] = None) -> Tuple[List[Tuple[str, str, str]], List[str]]:
    """
    Filter sequences by length.
    
    Returns:
        (filtered_sequences, removed_ids)
    """
    filtered = []
    removed = []
    
    for seq_id, desc, seq in sequences:
        length = len(seq)
        keep = True
        
        if min_length and length < min_length:
            keep = False
        if max_length and length > max_length:
            keep = False
        
        if keep:
            filtered.append((seq_id, desc, seq))
        else:
            removed.append(seq_id)
    
    return filtered, removed


def deduplicate_sequences(sequences: List[Tuple[str, str, str]], 
                         by_id: bool = True,
                         by_sequence: bool = False) -> Tuple[List[Tuple[str, str, str]], List[str]]:
    """
    Remove duplicate sequences.
    
    Args:
        by_id: Remove sequences with duplicate IDs
        by_sequence: Remove sequences with identical sequences
        
    Returns:
        (unique_sequences, duplicate_ids)
    """
    seen_ids = set()
    seen_seqs = set()
    unique = []
    duplicates = []
    
    for seq_id, desc, seq in sequences:
        is_dup = False
        
        if by_id and seq_id in seen_ids:
            is_dup = True
        if by_sequence and seq in seen_seqs:
            is_dup = True
        
        if not is_dup:
            unique.append((seq_id, desc, seq))
            seen_ids.add(seq_id)
            seen_seqs.add(seq)
        else:
            duplicates.append(seq_id)
    
    return unique, duplicates


def clean_headers(
    sequences: List[Tuple[str, str, str]],
    replace_with: str = '_'
) -> Tuple[List[Tuple[str, str, str]], Dict[str, str]]:
    """
    Sanitize FASTA headers to remove spaces/special characters and enforce uniqueness.

    Args:
        sequences: List of (id, desc, seq)
        replace_with: Replacement character for illegal symbols

    Returns:
        (cleaned_sequences, id_map) where id_map maps original IDs to cleaned IDs
    """
    cleaned = []
    id_map: Dict[str, str] = {}
    used = set()

    for seq_id, desc, seq in sequences:
        # Replace whitespace with underscores and strip unsafe characters
        safe_id = re.sub(r'\s+', replace_with, seq_id)
        safe_id = re.sub(r'[^A-Za-z0-9_.-]', replace_with, safe_id)
        safe_id = safe_id.strip(replace_with) or 'seq'

        base = safe_id
        counter = 1
        while safe_id in used:
            safe_id = f"{base}_{counter}"
            counter += 1

        used.add(safe_id)
        id_map[seq_id] = safe_id
        cleaned.append((safe_id, desc, seq))

    return cleaned, id_map


def extract_species_prefix(seq_id: str, pattern: str = r'^([a-zA-Z_]+)') -> Optional[str]:
    """
    Extract species prefix from sequence ID using regex.
    
    Args:
        seq_id: Sequence identifier
        pattern: Regex pattern for prefix extraction
        
    Returns:
        Prefix string or None
    """
    match = re.match(pattern, seq_id)
    return match.group(1) if match else None


def group_by_species(sequences: List[Tuple[str, str, str]], 
                     prefix_pattern: str = r'^([a-zA-Z_]+)') -> Dict[str, List[Tuple[str, str, str]]]:
    """
    Group sequences by species prefix.
    
    Returns:
        Dict of {species_prefix: sequences_list}
    """
    groups = {}
    
    for seq_tuple in sequences:
        seq_id = seq_tuple[0]
        prefix = extract_species_prefix(seq_id, prefix_pattern)
        
        if prefix:
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append(seq_tuple)
    
    return groups


def validate_fasta_format(text: str) -> Tuple[bool, str]:
    """
    Validate FASTA format.
    
    Returns:
        (is_valid, error_message)
    """
    lines = text.strip().split('\n')
    
    if not lines:
        return False, "Empty input"
    
    if not lines[0].startswith('>'):
        return False, "First line must be a header starting with '>'"
    
    has_sequence = False
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        if line.startswith('>'):
            if not has_sequence:
                return False, "Header without sequence"
            has_sequence = False
        else:
            has_sequence = True
            # Check for invalid characters
            if not all(c.isalpha() or c == '-' or c.isspace() for c in line):
                return False, f"Invalid characters in sequence line: {line[:50]}"
    
    if not has_sequence:
        return False, "Last header has no sequence"
    
    return True, ""


def get_fasta_stats(sequences: List[Tuple[str, str, str]]) -> Dict:
    """
    Calculate statistics for FASTA sequences.
    
    Returns:
        Dict with count, total_length, avg_length, min_length, max_length
    """
    if not sequences:
        return {
            'count': 0,
            'total_length': 0,
            'avg_length': 0,
            'min_length': 0,
            'max_length': 0
        }
    
    lengths = [len(seq) for _, _, seq in sequences]
    
    return {
        'count': len(sequences),
        'total_length': sum(lengths),
        'avg_length': sum(lengths) / len(lengths),
        'min_length': min(lengths),
        'max_length': max(lengths)
    }
