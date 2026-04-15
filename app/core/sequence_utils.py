"""
Sequence processing utilities for BioLab Workbench.
"""
import re
import io
import os
import json
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqUtils import gc_fraction, molecular_weight
import config

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

# Pre-compiled Regex Patterns
KV_PAIR_PATTERN = re.compile(r'(\w+)=([\w.:-]+)')
TOKEN_SPLIT_PATTERN = re.compile(r'[\s,;|]+')
VERSION_SUFFIX_PATTERN = re.compile(r'[._-]v?\d+$')
NON_ID_CHARS_PATTERN = re.compile(r'^[<>\[\]\(\)\{\}"\'`]+|[<>\[\]\(\)\{\}"\'`]+$')

NON_GENE_TOKENS = {
    'query', 'subject', 'evalue', 'bitscore', 'identity', 'length', 'score',
    'description', 'protein', 'gene', 'transcript', 'result', 'results',
    'and', 'or', 'from', 'with', 'without', 'the', 'for', 'table',
    'unknown', 'hypothetical', 'putative', 'predicted', 'chromosome'
}

PIPE_PREFIX_TOKENS = {'sp', 'tr', 'gi', 'ref', 'gb', 'emb', 'dbj', 'lcl'}

SOURCE_FASTA_LIBRARY_FILE = os.path.join(config.UPLOADS_DIR, 'source_fasta_library.json')

def load_source_fasta_library():
    """Load the source FASTA library from disk."""
    if os.path.exists(SOURCE_FASTA_LIBRARY_FILE):
        try:
            with open(SOURCE_FASTA_LIBRARY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_source_fasta_library(entries):
    """Save the source FASTA library to disk."""
    os.makedirs(os.path.dirname(SOURCE_FASTA_LIBRARY_FILE), exist_ok=True)
    with open(SOURCE_FASTA_LIBRARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

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


def parse_upload_file(content: bytes, filename: str):
    """
    Parse uploaded file content using Biopython.
    Supports FASTA, GenBank, and SnapGene (if Biopython supports it or via extension).
    Returns list of sequence dictionaries.
    """
    filename = filename.lower()
    sequences = []
    
    # Determine format based on extension
    fmt = 'fasta' # default
    if filename.endswith(('.gb', '.gbk', '.genbank')):
        fmt = 'genbank'
    elif filename.endswith('.dna'):
        fmt = 'snapgene' # Bio.SeqIO might need 'snapgene' plugin or treat as binary
    
    try:
        # Use StringIO for text formats, BytesIO for binary might be needed for some
        # Biopython's SeqIO.parse takes a handle.
        
        handle = io.StringIO(content.decode('utf-8')) if fmt in ['fasta', 'genbank'] else io.BytesIO(content)
        
        # SnapGene support in Biopython is strictly speaking 'snapgene' in recent versions
        # If not, we might fail. Let's stick to standard formats first.
        
        for record in SeqIO.parse(handle, fmt):
            # Extract features
            features = []
            for f in record.features:
                qualifiers = {}
                for k, v in f.qualifiers.items():
                    # Flatten lists to strings if len 1
                    qualifiers[k] = v[0] if len(v) == 1 else v
                    
                features.append({
                    'type': f.type,
                    'start': int(f.location.start) + 1, # Convert 0-based to 1-based
                    'end': int(f.location.end),
                    'strand': '+' if f.location.strand != -1 else '-',
                    'label': qualifiers.get('label') or qualifiers.get('gene') or qualifiers.get('note') or f.type,
                    'color': '#4CAF50', # Default color
                    'qualifiers': qualifiers
                })
            
            sequences.append({
                'id': record.id,
                'description': record.description,
                'sequence': str(record.seq),
                'type': 'nucleotide', # GenBank usually nucleotide
                'length': len(record.seq),
                'annotation': '',
                'features': features
            })
            
    except Exception as e:
        # Fallback to simple FASTA if parsing fails and it looks like text
        try:
            text = content.decode('utf-8')
            if text.strip().startswith('>'):
                return parse_fasta(text)
        except:
            pass
        return []

    return sequences

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
    normalized = VERSION_SUFFIX_PATTERN.sub('', normalized)
    
    return (normalized, original)


def _cleanup_id_token(token):
    cleaned = NON_ID_CHARS_PATTERN.sub('', (token or '').strip())
    cleaned = cleaned.strip(',;.:')
    return cleaned


def _looks_like_gene_id(token):
    """
    Heuristic filter to avoid extracting common words as gene IDs.
    """
    token = _cleanup_id_token(token)
    if not token or len(token) < 3 or len(token) > 120:
        return False
    if any(ch.isspace() for ch in token):
        return False
    if '/' in token or '\\' in token:
        return False
    if re.fullmatch(
        r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',
        token
    ):
        # Avoid treating UUIDs as gene IDs.
        return False
    if not re.fullmatch(r'[A-Za-z0-9._|:-]+', token):
        return False
    if token.count('-') >= 2 and not any(ch in token for ch in '._|:'):
        # Avoid slug/project-like names such as MP-phy-11clade-9.
        return False

    lower = token.lower()
    if lower in NON_GENE_TOKENS:
        return False

    # Pure numbers are not gene IDs
    if re.fullmatch(r'[+-]?\d+(\.\d+)?', token):
        return False

    # Typical IDs contain letters plus digits or separators.
    has_alpha = any(ch.isalpha() for ch in token)
    has_digit = any(ch.isdigit() for ch in token)
    has_sep = any(ch in '._-:|' for ch in token)
    if has_alpha and (has_digit or has_sep):
        return True

    return False


def _extract_token_variants(token):
    """
    Return possible ID candidates from one token.
    Handles pipe-separated headers such as sp|Q9XYZ1|NAME.
    """
    token = _cleanup_id_token(token)
    if not token:
        return []

    variants = [token]
    if '|' in token:
        parts = [p.strip() for p in token.split('|') if p.strip()]
        for part in parts:
            if part.lower() not in PIPE_PREFIX_TOKENS:
                variants.append(part)
    if ':' in token and '=' not in token:
        parts = [p.strip() for p in token.split(':') if p.strip()]
        variants.extend(parts)

    dedup = []
    seen = set()
    for item in variants:
        if item and item not in seen:
            seen.add(item)
            dedup.append(item)
    return dedup


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
    seen_normalized = set()
    
    lines = text.strip().split('\n')

    for raw_line in lines:
        line = raw_line.strip().lstrip('>')  # accept FASTA headers directly
        if not line or line.startswith('#'):
            continue

        candidates = []

        # Collect IDs from key=value pairs first (high confidence)
        for key, val in KV_PAIR_PATTERN.findall(line):
            if key.lower() in ['id', 'locus', 'gene', 'transcript', 'mrna', 'protein', 'pacid', 'name']:
                candidates.extend(_extract_token_variants(val))

        # Try tab-separated (BLAST-like) second column as high confidence
        fields = line.split('\t')
        if len(fields) >= 2:
            candidates.extend(_extract_token_variants(fields[1]))
            if len(fields) >= 1:
                candidates.extend(_extract_token_variants(fields[0]))

        # Fallback: token scan
        tokens = TOKEN_SPLIT_PATTERN.split(line)
        for token in tokens:
            candidates.extend(_extract_token_variants(token))

        for token in candidates:
            if not _looks_like_gene_id(token):
                continue
            normalized, _ = normalize_gene_id(token)
            if normalized and normalized not in seen_normalized:
                seen_normalized.add(normalized)
                gene_ids.append(token)
    
    return gene_ids


def _parse_header_ids(header):
    """
    Helper to extract all possible IDs from a FASTA header line.
    """
    header_ids = set()
    parts = header.split(None, 1)
    if not parts:
        return header_ids
        
    primary_id = parts[0]
    for variant in _extract_token_variants(primary_id):
        if _looks_like_gene_id(variant):
            header_ids.add(variant)

    if len(parts) > 1:
        tail = parts[1]
        # Key=value pairs
        for key, value in KV_PAIR_PATTERN.findall(tail):
            if key.lower() in ['locus', 'id', 'gene', 'pacid', 'transcript', 'mrna', 'protein']:
                for variant in _extract_token_variants(value):
                    if _looks_like_gene_id(variant):
                        header_ids.add(variant)

        # Token split for other IDs
        for token in TOKEN_SPLIT_PATTERN.split(tail):
            for variant in _extract_token_variants(token):
                if _looks_like_gene_id(variant):
                    header_ids.add(variant)
                
    return header_ids


def _parse_primary_header_ids(header):
    """
    Extract only primary header IDs (first token and its pipe/colon variants).
    Used by strict matching mode to avoid accidental matches from description text.
    """
    header_ids = set()
    parts = header.split(None, 1)
    if not parts:
        return header_ids

    primary_id = parts[0]
    for variant in _extract_token_variants(primary_id):
        if _looks_like_gene_id(variant):
            header_ids.add(variant)

    return header_ids


def extract_sequences_fuzzy(source_fasta, gene_ids, output_file=None, strict_single_id=False):
    """
    Extract sequences from a FASTA file using fuzzy matching.
    
    Supports:
    - Exact match
    - Case-insensitive matching
    - Version suffix agnostic matching (Mp3g11110 matches Mp3g11110.1)
    - Matching against common identifiers in the header
    
    Args:
        source_fasta: Path to source FASTA file
        gene_ids: List of gene IDs to extract
        output_file: Optional output file path
        strict_single_id: If True and only one ID is provided, disable fuzzy matching
                          and match by exact ID (case-insensitive) only.
    
    Returns:
        dict: Result dictionary
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
    original_ids_order = []
    original_ids_set = set()
    for gid in gene_ids:
        if gid not in original_ids_set:
            original_ids_set.add(gid)
            original_ids_order.append(gid)
    
    for gid in original_ids_order:
        normalized, original = normalize_gene_id(gid)
        if normalized:
            if normalized not in fuzzy_index:
                fuzzy_index[normalized] = original

    strict_mode = bool(strict_single_id and len(original_ids_order) == 1)
    strict_exact_lookup = {gid.lower(): gid for gid in original_ids_order} if strict_mode else {}
    target_match_count = len(original_ids_order)

    extracted = []
    matched_ids = set()
    
    try:
        with open(source_fasta, 'r', encoding='utf-8') as f:
            current_header = None
            current_seq_parts = []
            
            def process_current_sequence():
                if current_header is None:
                    return

                match_found = False

                primary_id = current_header.split(None, 1)[0] if current_header else ''
                if primary_id:
                    if strict_mode:
                        matched_key = strict_exact_lookup.get(primary_id.lower())
                        if matched_key:
                            matched_ids.add(matched_key)
                            match_found = True
                    else:
                        if primary_id in original_ids_set:
                            matched_ids.add(primary_id)
                            match_found = True
                        else:
                            norm_primary, _ = normalize_gene_id(primary_id)
                            matched_key = fuzzy_index.get(norm_primary)
                            if matched_key:
                                matched_ids.add(matched_key)
                                match_found = True

                # Fallback to broader header parsing only when primary token did not match.
                header_ids = set()
                if not match_found:
                    header_ids = _parse_primary_header_ids(current_header) if strict_mode else _parse_header_ids(current_header)

                # Check for a match
                for hid in header_ids:
                    if strict_mode:
                        matched_key = strict_exact_lookup.get(hid.lower())
                        if matched_key:
                            matched_ids.add(matched_key)
                            match_found = True
                    else:
                        # Exact match
                        if hid in original_ids_set:
                            matched_ids.add(hid)
                            match_found = True
                        else:
                            # Fuzzy match
                            norm_hid, _ = normalize_gene_id(hid)
                            if norm_hid in fuzzy_index:
                                matched_ids.add(fuzzy_index[norm_hid])
                                match_found = True
                    
                    if match_found:
                        break
                
                if match_found:
                    extracted.append((current_header, ''.join(current_seq_parts)))

            for line in f:
                line = line.strip()
                if line.startswith('>'):
                    process_current_sequence()
                    if len(matched_ids) >= target_match_count:
                        # All targets were found; stop scanning large FASTA files early.
                        break
                    current_header = line[1:]
                    current_seq_parts = []
                elif line:
                    current_seq_parts.append(line)
            
            if len(matched_ids) < target_match_count:
                # Handle last sequence only when we did not early-break above.
                process_current_sequence()

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'sequences': [],
            'matched': [],
            'unmatched': list(gene_ids)
        }
    
    # Calculate unmatched
    unmatched = [gid for gid in original_ids_order if gid not in matched_ids]
    matched = [gid for gid in original_ids_order if gid in matched_ids]
    
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
                'matched': matched,
                'unmatched': unmatched
            }
    
    return {
        'success': True,
        'sequences': [(h.split(None, 1)[0], s) for h, s in extracted],
        'matched': matched,
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
