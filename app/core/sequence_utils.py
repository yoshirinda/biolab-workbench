"""
Sequence processing utilities for BioLab Workbench.
"""
import re
from Bio.Seq import Seq
from Bio.SeqUtils import gc_fraction, molecular_weight


# Standard codon table
CODON_TABLE = {
    'TTT': 'F', 'TTC': 'F', 'TTA': 'L', 'TTG': 'L',
    'TCT': 'S', 'TCC': 'S', 'TCA': 'S', 'TCG': 'S',
    'TAT': 'Y', 'TAC': 'Y', 'TAA': '*', 'TAG': '*',
    'TGT': 'C', 'TGC': 'C', 'TGA': '*', 'TGG': 'W',
    'CTT': 'L', 'CTC': 'L', 'CTA': 'L', 'CTG': 'L',
    'CCT': 'P', 'CCC': 'P', 'CCA': 'P', 'CCG': 'P',
    'CAT': 'H', 'CAC': 'H', 'CAA': 'Q', 'CAG': 'Q',
    'CGT': 'R', 'CGC': 'R', 'CGA': 'R', 'CGG': 'R',
    'ATT': 'I', 'ATC': 'I', 'ATA': 'I', 'ATG': 'M',
    'ACT': 'T', 'ACC': 'T', 'ACA': 'T', 'ACG': 'T',
    'AAT': 'N', 'AAC': 'N', 'AAA': 'K', 'AAG': 'K',
    'AGT': 'S', 'AGC': 'S', 'AGA': 'R', 'AGG': 'R',
    'GTT': 'V', 'GTC': 'V', 'GTA': 'V', 'GTG': 'V',
    'GCT': 'A', 'GCC': 'A', 'GCA': 'A', 'GCG': 'A',
    'GAT': 'D', 'GAC': 'D', 'GAA': 'E', 'GAG': 'E',
    'GGT': 'G', 'GGC': 'G', 'GGA': 'G', 'GGG': 'G',
}

# Amino acid specific characters (not in DNA/RNA)
AA_ONLY_CHARS = set('EFILPQ')


def detect_sequence_type(sequence):
    """
    Detect if sequence is nucleotide or protein.
    Check for amino acid-specific characters (E, F, I, L, P, Q).
    Returns: 'nucleotide' or 'protein'
    """
    sequence = sequence.upper().replace(' ', '').replace('\n', '')

    # Remove ambiguous characters
    for char in 'XNBZ-':
        sequence = sequence.replace(char, '')

    # Check for amino acid-specific characters
    seq_chars = set(sequence)
    if seq_chars & AA_ONLY_CHARS:
        return 'protein'

    return 'nucleotide'


def parse_fasta(text):
    """
    Parse FASTA format text into list of (id, description, sequence) tuples.
    """
    sequences = []
    current_id = None
    current_desc = ''
    current_seq = []

    for line in text.strip().split('\n'):
        line = line.strip()
        if line.startswith('>'):
            if current_id is not None:
                sequences.append((current_id, current_desc, ''.join(current_seq)))
            header_parts = line[1:].split(None, 1)
            current_id = header_parts[0] if header_parts else ''
            current_desc = header_parts[1] if len(header_parts) > 1 else ''
            current_seq = []
        elif line and current_id is not None:
            current_seq.append(line)

    if current_id is not None:
        sequences.append((current_id, current_desc, ''.join(current_seq)))

    return sequences


def format_fasta(sequences, line_width=60):
    """
    Format sequences to FASTA string.
    sequences: list of (id, description, sequence) or (header, sequence) tuples
    """
    lines = []
    for item in sequences:
        if len(item) == 3:
            seq_id, desc, seq = item
            header = f"{seq_id} {desc}".strip() if desc else seq_id
        else:
            header, seq = item
        lines.append(f">{header}")
        for i in range(0, len(seq), line_width):
            lines.append(seq[i:i+line_width])
    return '\n'.join(lines)


def clean_fasta_headers(sequences):
    """
    Clean FASTA headers - keep only the first space-separated ID.
    """
    cleaned = []
    for item in sequences:
        if len(item) == 3:
            seq_id, _, seq = item
        else:
            header, seq = item
            seq_id = header.split()[0]
        cleaned.append((seq_id, '', seq))
    return cleaned


def translate_dna(sequence, frame=1):
    """
    Translate DNA sequence to protein.
    frame: 1, 2, 3 for forward frames, -1, -2, -3 for reverse frames
    Returns: protein sequence
    """
    sequence = sequence.upper().replace(' ', '').replace('\n', '')

    if frame < 0:
        # Reverse complement
        sequence = str(Seq(sequence).reverse_complement())
        frame = abs(frame)

    # Adjust for reading frame
    sequence = sequence[frame-1:]

    # Translate
    protein = []
    for i in range(0, len(sequence) - 2, 3):
        codon = sequence[i:i+3]
        if codon in CODON_TABLE:
            protein.append(CODON_TABLE[codon])
        else:
            protein.append('X')  # Unknown codon

    return ''.join(protein)


def reverse_complement(sequence):
    """
    Get reverse complement of DNA sequence.
    """
    sequence = sequence.upper().replace(' ', '').replace('\n', '')
    return str(Seq(sequence).reverse_complement())


def find_orfs(sequence, min_length=100):
    """
    Find all open reading frames in a DNA sequence.
    Returns list of (start, end, frame, length, sequence) tuples.
    """
    sequence = sequence.upper().replace(' ', '').replace('\n', '')
    orfs = []

    # Check all 6 reading frames
    for frame in [1, 2, 3, -1, -2, -3]:
        if frame > 0:
            dna = sequence
            offset = frame - 1
        else:
            dna = str(Seq(sequence).reverse_complement())
            offset = abs(frame) - 1

        # Find ORFs
        protein = translate_dna(dna[offset:], frame=1)
        start = None

        for i, aa in enumerate(protein):
            if aa == 'M' and start is None:
                start = i
            elif aa == '*' and start is not None:
                length = (i - start) * 3
                if length >= min_length:
                    orf_seq = protein[start:i]
                    if frame > 0:
                        nt_start = offset + start * 3
                        nt_end = offset + i * 3 + 3
                    else:
                        nt_end = len(sequence) - offset - start * 3
                        nt_start = len(sequence) - offset - i * 3 - 3
                    orfs.append({
                        'start': nt_start,
                        'end': nt_end,
                        'frame': frame,
                        'length': length,
                        'protein_length': i - start,
                        'sequence': orf_seq
                    })
                start = None

    return sorted(orfs, key=lambda x: -x['protein_length'])


def calculate_sequence_stats(sequence, seq_type='auto'):
    """
    Calculate sequence statistics.
    Returns dict with stats.
    """
    sequence = sequence.upper().replace(' ', '').replace('\n', '').replace('-', '')

    if seq_type == 'auto':
        seq_type = detect_sequence_type(sequence)

    stats = {
        'length': len(sequence),
        'type': seq_type,
    }

    if seq_type == 'nucleotide':
        stats['gc_content'] = gc_fraction(sequence) * 100
        stats['a_count'] = sequence.count('A')
        stats['t_count'] = sequence.count('T')
        stats['g_count'] = sequence.count('G')
        stats['c_count'] = sequence.count('C')
        try:
            stats['molecular_weight'] = molecular_weight(sequence, seq_type='DNA')
        except Exception:
            stats['molecular_weight'] = None
    else:
        # Amino acid composition
        aa_counts = {}
        for aa in sequence:
            aa_counts[aa] = aa_counts.get(aa, 0) + 1
        stats['aa_composition'] = aa_counts
        try:
            stats['molecular_weight'] = molecular_weight(sequence, seq_type='protein')
        except Exception:
            stats['molecular_weight'] = None

    return stats


def validate_sequence(sequence, seq_type='auto'):
    """
    Validate sequence for invalid characters.
    Returns (is_valid, error_message).
    """
    sequence = sequence.upper().replace(' ', '').replace('\n', '').replace('-', '')

    if not sequence:
        return False, "Empty sequence"

    if seq_type == 'auto':
        seq_type = detect_sequence_type(sequence)

    if seq_type == 'nucleotide':
        valid_chars = set('ATGCNRYSWKMBDHV')
    else:
        valid_chars = set('ACDEFGHIKLMNPQRSTVWXY*')

    invalid_chars = set(sequence) - valid_chars
    if invalid_chars:
        return False, f"Invalid characters: {', '.join(sorted(invalid_chars))}"

    return True, None
