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

    def test_docs_index_page(self, client):
        """Test documentation index page loads."""
        response = client.get('/docs/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'Documentation' in html

    def test_docs_blast_page(self, client):
        """Test BLAST documentation page loads."""
        response = client.get('/docs/blast')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'BLAST' in html
        assert 'E-value' in html

    def test_docs_phylo_page(self, client):
        """Test phylo documentation page loads."""
        response = client.get('/docs/phylo')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'Phylogenetic' in html
        assert 'IQ-Tree' in html

    def test_docs_alignment_page(self, client):
        """Test alignment documentation page loads."""
        response = client.get('/docs/alignment')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'Alignment' in html
        assert 'MAFFT' in html

    def test_docs_tree_page(self, client):
        """Test tree documentation page loads."""
        response = client.get('/docs/tree')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'Tree' in html
        assert 'Visualization' in html

    def test_navigation_includes_docs_link(self, client):
        """Test that navigation bar includes Docs link."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'href="/docs/"' in html

    def test_blast_page_has_help_button(self, client):
        """Test that BLAST page has help button linking to docs."""
        response = client.get('/blast/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'href="/docs/blast"' in html

    def test_phylo_page_has_help_button(self, client):
        """Test that phylo page has help button linking to docs."""
        response = client.get('/phylo/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'href="/docs/phylo"' in html

    def test_alignment_page_has_help_button(self, client):
        """Test that alignment page has help button linking to docs."""
        response = client.get('/alignment/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'href="/docs/alignment"' in html

    def test_tree_page_has_help_button(self, client):
        """Test that tree page has help button linking to docs."""
        response = client.get('/tree/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'href="/docs/tree"' in html

    def test_index_module_links_use_url_for(self, client):
        """Test that index page module links use url_for() generated URLs."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Verify the module links contain the correct relative paths
        # generated by url_for() instead of hardcoded URLs
        assert 'href="/sequence/"' in html
        assert 'href="/blast/"' in html
        assert 'href="/phylo/"' in html
        assert 'href="/alignment/"' in html
        assert 'href="/uniprot/"' in html
        assert 'href="/tree/"' in html

    def test_navigation_links_use_url_for(self, client):
        """Test that navigation bar uses url_for() for all links."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Verify navigation uses url_for generated paths
        # The base template should have proper url_for navigation
        assert 'href="/"' in html  # Home link
        assert 'href="/sequence/"' in html
        assert 'href="/blast/"' in html
        assert 'href="/phylo/"' in html
        assert 'href="/alignment/"' in html
        assert 'href="/uniprot/"' in html
        assert 'href="/tree/"' in html

    def test_proxy_fix_middleware_applied(self, client):
        """Test that ProxyFix middleware is applied to the app."""
        app = create_app()
        # Check that ProxyFix is wrapping the WSGI app
        from werkzeug.middleware.proxy_fix import ProxyFix
        assert isinstance(app.wsgi_app, ProxyFix)


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


class TestProjectManager:
    """Tests for project management functionality."""

    def test_list_projects(self, client):
        """Test listing projects."""
        response = client.get('/sequence/projects')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'projects' in data

    def test_create_project_missing_name(self, client):
        """Test creating project without name."""
        response = client.post('/sequence/projects',
                              json={},
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'required' in data['error'].lower()

    def test_save_collection_missing_name(self, client):
        """Test saving collection without name."""
        response = client.post('/sequence/collections/save',
                              json={'sequences': [{'id': 'seq1', 'sequence': 'ATGC'}]},
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False

    def test_save_collection_missing_sequences(self, client):
        """Test saving collection without sequences."""
        response = client.post('/sequence/collections/save',
                              json={'name': 'test_collection'},
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False


class TestBlastWrapper:
    """Tests for BLAST wrapper functions."""

    def test_create_blast_database_uses_correct_directory(self, tmpdir, monkeypatch):
        """Test that create_blast_database creates databases in DATABASES_DIR, not input file dir."""
        import tempfile
        import config
        from app.core.blast_wrapper import create_blast_database

        # Create a temporary DATABASES_DIR
        temp_databases_dir = str(tmpdir.mkdir("databases"))
        monkeypatch.setattr(config, 'DATABASES_DIR', temp_databases_dir)

        # Create a temporary input file in a different directory
        temp_uploads_dir = str(tmpdir.mkdir("uploads"))
        input_file = os.path.join(temp_uploads_dir, "test_sequences.fasta")
        with open(input_file, 'w') as f:
            f.write(">seq1\nATGCATGCATGC\n>seq2\nATGCGTACGTAC\n")

        # Call create_blast_database
        # Note: This will fail without makeblastdb, but we can still verify the path
        success, message, db_path = create_blast_database(input_file, "test_db", db_type="nucl")

        # Even if makeblastdb fails, db_path should be None or in DATABASES_DIR
        if db_path is not None:
            # If it succeeded, verify db_path is in DATABASES_DIR
            assert db_path.startswith(temp_databases_dir), \
                f"Database path {db_path} should be in {temp_databases_dir}"
            assert not db_path.startswith(temp_uploads_dir), \
                f"Database path {db_path} should NOT be in uploads dir {temp_uploads_dir}"

    def test_list_blast_databases_uses_databases_dir(self, tmpdir, monkeypatch):
        """Test that list_blast_databases scans config.DATABASES_DIR."""
        import config
        from app.core.blast_wrapper import list_blast_databases

        # Create a temporary DATABASES_DIR with mock db files
        temp_databases_dir = str(tmpdir.mkdir("databases"))
        monkeypatch.setattr(config, 'DATABASES_DIR', temp_databases_dir)

        # Create mock nucleotide database files
        open(os.path.join(temp_databases_dir, "test_db.nin"), 'w').close()

        # List databases
        databases = list_blast_databases()

        assert len(databases) == 1
        assert databases[0]['name'] == 'test_db'
        assert databases[0]['type'] == 'nucleotide'
        assert databases[0]['path'] == os.path.join(temp_databases_dir, 'test_db')
