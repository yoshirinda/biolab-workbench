"""
Basic tests for BioLab Workbench.
"""
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.core.sequence_utils import (
    detect_sequence_type, parse_fasta, format_fasta,
    translate_dna, reverse_complement, find_orfs,
    calculate_sequence_stats, validate_sequence
)


@pytest.fixture
def client():
    """Create a test client."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestSequenceUtils:
    """Tests for sequence utility functions."""

    def test_detect_sequence_type_dna(self):
        """Test DNA detection."""
        assert detect_sequence_type("ATGCATGCATGC") == "nucleotide"
        assert detect_sequence_type("atgcatgcatgc") == "nucleotide"

    def test_detect_sequence_type_protein(self):
        """Test protein detection."""
        assert detect_sequence_type("MKVLWAALLVTFLAGCQA") == "protein"
        assert detect_sequence_type("ACDEFGHIKLMNPQRSTVWY") == "protein"

    def test_parse_fasta(self):
        """Test FASTA parsing."""
        fasta_text = ">seq1 description\nATGC\nATGC\n>seq2\nMKVL"
        sequences = parse_fasta(fasta_text)

        assert len(sequences) == 2
        assert sequences[0][0] == "seq1"
        assert sequences[0][1] == "description"
        assert sequences[0][2] == "ATGCATGC"
        assert sequences[1][0] == "seq2"
        assert sequences[1][2] == "MKVL"

    def test_format_fasta(self):
        """Test FASTA formatting."""
        sequences = [("seq1", "desc", "ATGC"), ("seq2", "", "MKVL")]
        fasta = format_fasta(sequences)

        assert ">seq1 desc" in fasta
        assert "ATGC" in fasta
        assert ">seq2" in fasta

    def test_translate_dna(self):
        """Test DNA translation."""
        # ATG = M (Methionine)
        assert translate_dna("ATG", frame=1) == "M"

        # Test stop codon
        assert translate_dna("ATGTAA", frame=1) == "M*"

    def test_reverse_complement(self):
        """Test reverse complement."""
        assert reverse_complement("ATGC") == "GCAT"
        assert reverse_complement("AAAA") == "TTTT"

    def test_find_orfs(self):
        """Test ORF finding."""
        # Simple sequence with one ORF
        seq = "ATGATGATGATGATGATGATGATGATGATGATGATGATGATGATG" + "TAA"  # ATG...TAA
        orfs = find_orfs(seq, min_length=30)
        assert len(orfs) >= 1

    def test_calculate_sequence_stats_dna(self):
        """Test DNA statistics calculation."""
        stats = calculate_sequence_stats("ATGCATGC")

        assert stats["length"] == 8
        assert stats["type"] == "nucleotide"
        assert "gc_content" in stats
        assert stats["a_count"] == 2
        assert stats["t_count"] == 2

    def test_calculate_sequence_stats_protein(self):
        """Test protein statistics calculation."""
        stats = calculate_sequence_stats("MKVLWAALLVTFLAGCQA")

        assert stats["length"] == 18
        assert stats["type"] == "protein"
        assert "aa_composition" in stats

    def test_validate_sequence_valid_dna(self):
        """Test valid DNA validation."""
        is_valid, error = validate_sequence("ATGCATGC", "nucleotide")
        assert is_valid is True
        assert error is None

    def test_validate_sequence_valid_protein(self):
        """Test valid protein validation."""
        is_valid, error = validate_sequence("MKVLWA", "protein")
        assert is_valid is True
        assert error is None

    def test_validate_sequence_empty(self):
        """Test empty sequence validation."""
        is_valid, error = validate_sequence("", "auto")
        assert is_valid is False
        assert "Empty" in error


class TestRoutes:
    """Tests for Flask routes."""

    def test_index_page(self, client):
        """Test index page loads."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'BioLab Workbench' in response.data

    def test_sequence_page(self, client):
        """Test sequence page loads."""
        response = client.get('/sequence/')
        assert response.status_code == 200

    def test_blast_page(self, client):
        """Test BLAST page loads."""
        response = client.get('/blast/')
        assert response.status_code == 200

    def test_phylo_page(self, client):
        """Test phylo page loads."""
        response = client.get('/phylo/')
        assert response.status_code == 200

    def test_alignment_page(self, client):
        """Test alignment page loads."""
        response = client.get('/alignment/')
        assert response.status_code == 200

    def test_uniprot_page(self, client):
        """Test UniProt page loads."""
        response = client.get('/uniprot/')
        assert response.status_code == 200

    def test_tree_page(self, client):
        """Test tree page loads."""
        response = client.get('/tree/')
        assert response.status_code == 200


class TestSequenceAPI:
    """Tests for sequence API endpoints."""

    def test_import_sequences_text(self, client):
        """Test sequence import from text."""
        response = client.post('/sequence/import', data={
            'source': 'text',
            'text': '>seq1\nATGCATGC'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert len(data['sequences']) == 1

    def test_translate_endpoint(self, client):
        """Test translation endpoint."""
        response = client.post('/sequence/translate',
                              json={'sequence': 'ATGATGATG', 'frame': 1},
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'protein' in data

    def test_reverse_complement_endpoint(self, client):
        """Test reverse complement endpoint."""
        response = client.post('/sequence/reverse-complement',
                              json={'sequence': 'ATGC'},
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['reverse_complement'] == 'GCAT'

    def test_stats_endpoint(self, client):
        """Test stats endpoint."""
        response = client.post('/sequence/stats',
                              json={'sequence': 'ATGCATGC'},
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'stats' in data
        assert data['stats']['length'] == 8
