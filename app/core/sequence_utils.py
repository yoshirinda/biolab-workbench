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

# Common gene ID patterns for plants and model organisms (compiled at module level)
# Pattern examples: Mp3g11110.1, AT1G01010.1, Os01g0100100, Zm00001d002345, etc.
GENE_ID_PATTERN = re.compile(
    r'\b('
    r'[A-Za-z]{2,4}\d+g\d+(?:\.\d+)?|'   # Mp3g11110.1, AT1G01010.1
    r'[A-Za-z]{2,10}\d{2,}(?:\.\d+)?|'      # ATCG00280.1, generic letters+digits(+version)
    r'Os\d{2}g\d{7}|'                        # Os01g0100100 (Rice)
    r'LOC_Os\d{2}g\d{5}(?:\.\d+)?|'        # LOC_Os01g01010.1
    r'GRMZM\d+G\d+(?:_[A-Z]\d+)?|'          # GRMZM2G001000 (Maize)
    r'Solyc\d{2}g\d{6}(?:\.\d+)?|'         # Solyc01g001000.1 (Tomato)
    r'Potri\.\d{3}G\d{6}(?:\.\d+)?|'      # Potri.001G001000.1 (Poplar)
    r'Pp\d+s\d+(?:\.\d+)?|'                # Pp3c1_12345 (Physcomitrella)
    r'[A-Za-z]\d+\.\d+|'                    # Generic: A12345.1
    r'[A-Za-z]{1,6}_[A-Za-z0-9]+|'             # Gene_Name format
    r'[A-Z][a-z]{0,4}\d+[gG]\d+(?:\.\d+)?' # General gene format
    r')\b'
)


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


def normalize_gene_id(gene_id):
    """
    Normalize a gene ID for fuzzy matching.
    
    Handles:
    - Case insensitivity (Mp3g11110 -> mp3g11110)
    - Version suffix removal (Mp3g11110.1 -> mp3g11110)
    - Common formats: Mp3g11110.1, AT1G01010.1, Os01g0100100, etc.
    
    Returns:
        tuple: (normalized_id, original_id)
    """
    if not gene_id:
        return ('', gene_id)
    
    original = gene_id.strip()
    normalized = original.lower()
    
    # Remove version suffix (e.g., .1, .2, etc.)
    # Common patterns: .1, .2, _v1, -1, etc.
    normalized = re.sub(r'[._-]v?\d+$', '', normalized)
    
    return (normalized, original)


def parse_gene_ids_from_text(text):
    """
    Parse gene IDs from various text formats.
    
    Supports:
    - Tab-separated BLAST results (extracts second column as hit ID)
    - Whitespace/tab separated fields
    - Simple line-by-line IDs
    - Common gene ID patterns (Mp3g11110.1, AT1G01010.1, Os01g0100100, etc.)
    
    Args:
        text: Input text containing gene IDs
    
    Returns:
        list: Extracted gene IDs
    """
    gene_ids = []
    
    lines = text.strip().split('\n')

    for raw_line in lines:
        line = raw_line.strip().lstrip('>')  # accept FASTA headers directly
        if not line or line.startswith('#'):
            continue

        # Collect IDs from key=value pairs first
        kv_pairs = re.findall(r'(\w+)=([\w.:-]+)', line)
        for key, val in kv_pairs:
            if key.lower() in ['id', 'locus', 'gene', 'transcript', 'mrna', 'protein', 'pacid']:
                match = GENE_ID_PATTERN.search(val)
                if match:
                    gene_ids.append(match.group(1))
                elif re.match(r'^[\w.-]+$', val):
                    gene_ids.append(val)

        # Try tab-separated (BLAST-like) second column
        fields = line.split('\t')
        if len(fields) >= 2:
            potential_id = fields[1].strip()
            match = GENE_ID_PATTERN.search(potential_id)
            if match:
                gene_ids.append(match.group(1))
            elif potential_id and re.match(r'^[\w.-]+$', potential_id):
                gene_ids.append(potential_id)

        # Find any gene-like IDs across the full line
        matches = GENE_ID_PATTERN.findall(line)
        if matches:
            gene_ids.extend(matches)
            continue

        # Fallback: split by whitespace or comma and test tokens
        tokens = re.split(r'[\s,;|]+', line)
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            match = GENE_ID_PATTERN.search(token)
            if match:
                gene_ids.append(match.group(1))
            elif re.match(r'^[\w.-]+$', token):
                gene_ids.append(token)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_ids = []
    for gid in gene_ids:
        if gid not in seen:
            seen.add(gid)
            unique_ids.append(gid)
    
    return unique_ids


def extract_sequences_fuzzy(source_fasta, gene_ids, output_file=None):
    """
    Extract sequences from a FASTA file using fuzzy matching.
    
    Supports:
    - Exact match
    - Case-insensitive matching
    - Version suffix agnostic matching (Mp3g11110 matches Mp3g11110.1)
    - Matching against common identifiers in the header (locus, id, gene, pacid, transcript)
    
    Args:
        source_fasta: Path to source FASTA file
        gene_ids: List of gene IDs to extract
        output_file: Optional output file path
    
    Returns:
        dict: {
            'success': bool,
            'sequences': list of (id, sequence) tuples,
            'matched': list of matched IDs,
            'unmatched': list of IDs that weren't found,
            'output_file': path if written
        }
    """
    if not gene_ids:
        return {
            'success': False,
            'error': 'No gene IDs provided',
            'sequences': [],
            'matched': [],
            'unmatched': []
        }
    
    # Build fuzzy index for requested gene IDs
    fuzzy_index = {}
    original_ids = set(gene_ids)
    for gid in gene_ids:
        normalized, original = normalize_gene_id(gid)
        if normalized:
            if normalized not in fuzzy_index:
                fuzzy_index[normalized] = original
    
    extracted = []
    matched_ids = set()
    
    try:
        with open(source_fasta, 'r', encoding='utf-8') as f:
            current_header = None
            current_seq = []
            
            def process_sequence():
                if current_header is None:
                    return

                # Extract all possible IDs from the header
                header_ids = set()
                parts = current_header.split(None, 1)
                primary_id = parts[0]
                header_ids.add(primary_id)

                tail = parts[1] if len(parts) > 1 else ''
                # Key=value pairs
                for key, value in re.findall(r'(\w+)=([\w.:-]+)', tail):
                    if key.lower() in ['locus', 'id', 'gene', 'pacid', 'transcript', 'mrna', 'protein']:
                        header_ids.add(value)

                # Also split tail into tokens for plain IDs (handles headers like ">id desc")
                for token in re.split(r'[\s,;|]+', tail):
                    token = token.strip()
                    if not token:
                        continue
                    # Strip trailing commas/semicolons
                    token = token.strip(',;')
                    if GENE_ID_PATTERN.search(token):
                        header_ids.add(token)

                # Check for a match
                for hid in header_ids:
                    # Exact match
                    if hid in original_ids:
                        extracted.append((current_header, ''.join(current_seq)))
                        matched_ids.add(hid)
                        return
                    # Fuzzy match
                    norm_hid, _ = normalize_gene_id(hid)
                    if norm_hid in fuzzy_index:
                        extracted.append((current_header, ''.join(current_seq)))
                        matched_ids.add(fuzzy_index[norm_hid])
                        return

            for line in f:
                line = line.strip()
                if line.startswith('>'):
                    process_sequence()
                    current_header = line[1:]
                    current_seq = []
                elif line:
                    current_seq.append(line)
            
            # Handle last sequence
            process_sequence()

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'sequences': [],
            'matched': [],
            'unmatched': list(gene_ids)
        }
    
    # Calculate unmatched
    unmatched = [gid for gid in gene_ids if gid not in matched_ids]
    
    # Write output file if requested
    if output_file and extracted:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                for header, seq in extracted:
                    f.write(f">{header}\n")
                    for i in range(0, len(seq), 60):
                        f.write(seq[i:i+60] + '\n')
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to write output: {e}',
                'sequences': extracted,
                'matched': list(matched_ids),
                'unmatched': unmatched
            }
    
    return {
        'success': True,
        'sequences': [(h.split(None, 1)[0], s) for h, s in extracted],
        'matched': list(matched_ids),
        'unmatched': unmatched,
        'output_file': output_file if output_file else None
    }


def layout_features(features):
    """
    Arrange features into lanes to prevent visual overlap.

    Args:
        features (list): A list of feature dictionaries. Each dict must have
                         'start' and 'end' keys.

    Returns:
        list: A list of lists, where each inner list is a "lane" of
              non-overlapping feature dictionaries.
    """
    if not features:
        return []

    # Sort features by their start coordinate
    sorted_features = sorted(features, key=lambda f: f['start'])

    lanes = []
    for feature in sorted_features:
        placed = False
        # Try to place the feature in an existing lane
        for lane in lanes:
            # A feature can be placed if it doesn't overlap with the last feature in the lane.
            # Overlap check: feature['start'] < last_feature_in_lane['end']
            if feature['start'] >= lane[-1]['end']:
                lane.append(feature)
                placed = True
                break
        
        # If it could not be placed in any existing lane, create a new one
        if not placed:
            lanes.append([feature])

    return lanes
