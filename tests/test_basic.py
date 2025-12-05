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

        # Create mock nucleotide database files using context manager
        db_file_path = os.path.join(temp_databases_dir, "test_db.nin")
        with open(db_file_path, 'w'):
            pass

        # List databases
        databases = list_blast_databases()

        assert len(databases) == 1
        assert databases[0]['name'] == 'test_db'
        assert databases[0]['type'] == 'nucleotide'
        assert databases[0]['path'] == os.path.join(temp_databases_dir, 'test_db')

    def test_extract_from_fasta(self, tmpdir):
        """Test extracting sequences from FASTA file by IDs."""
        from app.core.blast_wrapper import extract_from_fasta

        # Create a test FASTA file
        source_fasta = str(tmpdir.join("source.fasta"))
        with open(source_fasta, 'w') as f:
            f.write(">seq1 description\nATGCATGC\n>seq2\nGGGGGGGG\n>seq3 other\nCCCCCCCC\n")

        output_file = str(tmpdir.join("output.fasta"))
        hit_ids = ['seq1', 'seq3']

        success, count = extract_from_fasta(source_fasta, hit_ids, output_file)

        assert success is True
        assert count == 2
        assert os.path.exists(output_file)

        with open(output_file, 'r') as f:
            content = f.read()
            assert '>seq1 description' in content
            assert '>seq3 other' in content
            assert 'ATGCATGC' in content
            assert 'CCCCCCCC' in content
            assert 'seq2' not in content

    def test_get_source_fasta(self, tmpdir):
        """Test retrieving source FASTA path from metadata."""
        from app.core.blast_wrapper import save_database_metadata, get_source_fasta

        # Create a test source FASTA file
        source_fasta = str(tmpdir.join("source.fasta"))
        with open(source_fasta, 'w') as f:
            f.write(">seq1\nATGC\n")

        # Create metadata
        db_path = str(tmpdir.join("test_db"))
        save_database_metadata(db_path, source_fasta, 'nucl', 'Test DB')

        # Verify metadata file was created
        assert os.path.exists(db_path + '.meta.json')

        # Retrieve source FASTA
        result = get_source_fasta(db_path)
        assert result == source_fasta

    def test_get_source_fasta_missing_metadata(self, tmpdir):
        """Test get_source_fasta returns None when metadata is missing."""
        from app.core.blast_wrapper import get_source_fasta

        db_path = str(tmpdir.join("nonexistent_db"))
        result = get_source_fasta(db_path)
        assert result is None

    def test_add_tsv_header(self, tmpdir):
        """Test adding header to TSV file."""
        from app.core.blast_wrapper import add_tsv_header

        # Create a test TSV file without header
        tsv_file = str(tmpdir.join("result.tsv"))
        with open(tsv_file, 'w') as f:
            f.write("query1\tsubject1\t99.5\t100\t0\t0\t1\t100\t1\t100\t1e-50\t200\n")

        add_tsv_header(tsv_file, 'tsv')

        with open(tsv_file, 'r') as f:
            content = f.read()
            lines = content.strip().split('\n')
            assert len(lines) == 2
            assert lines[0].startswith('qseqid')
            assert 'query1' in lines[1]

    def test_parse_blast_tsv_skips_header(self, tmpdir):
        """Test that parse_blast_tsv skips header row."""
        from app.core.blast_wrapper import parse_blast_tsv

        # Create a TSV file with header
        tsv_file = str(tmpdir.join("result.tsv"))
        with open(tsv_file, 'w') as f:
            f.write("qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen\tqstart\tqend\tsstart\tsend\tevalue\tbitscore\n")
            f.write("query1\tsubject1\t99.5\t100\t0\t0\t1\t100\t1\t100\t1e-50\t200\n")

        hits = parse_blast_tsv(tsv_file)
        assert len(hits) == 1
        assert hits[0]['qseqid'] == 'query1'
        assert hits[0]['sseqid'] == 'subject1'


class TestPhyloPipeline:
    """Tests for phylogenetic pipeline functions."""

    def test_parse_hmmsearch_tblout(self, tmpdir):
        """Test parsing hmmsearch tblout file."""
        from app.core.phylo_pipeline import parse_hmmsearch_tblout

        # Create a mock tblout file
        tblout_content = """# target name              accession  query name
seq1                       -          PF00001.1
seq2                       -          PF00001.1
seq3                       -          PF00001.1
# [ok]
"""
        tblout_file = str(tmpdir.join('test.tbl'))
        with open(tblout_file, 'w') as f:
            f.write(tblout_content)

        hits = parse_hmmsearch_tblout(tblout_file)
        assert len(hits) == 3
        assert 'seq1' in hits
        assert 'seq2' in hits
        assert 'seq3' in hits

    def test_extract_sequences_by_ids(self, tmpdir):
        """Test extracting sequences by IDs."""
        from app.core.phylo_pipeline import extract_sequences_by_ids

        # Create a test FASTA file
        input_file = str(tmpdir.join('input.fasta'))
        with open(input_file, 'w') as f:
            f.write(">seq1\nATGCATGC\n>seq2\nGGGGGGGG\n>seq3\nCCCCCCCC\n")

        output_file = str(tmpdir.join('output.fasta'))
        ids = {'seq1', 'seq3'}

        count = extract_sequences_by_ids(input_file, ids, output_file)

        assert count == 2
        assert os.path.exists(output_file)

        with open(output_file, 'r') as f:
            content = f.read()
            assert '>seq1' in content
            assert '>seq3' in content
            assert '>seq2' not in content

    def test_step2_hmmsearch_multiple_normalizes_input(self):
        """Test that step2_hmmsearch_multiple normalizes single file to list."""
        from app.core.phylo_pipeline import step2_hmmsearch_multiple

        # Test with None
        success, output, message, commands = step2_hmmsearch_multiple(
            '/nonexistent/input.fasta', None, '/tmp', cut_ga=True
        )
        assert success is False
        assert 'No HMM files' in message

        # Test with empty list
        success, output, message, commands = step2_hmmsearch_multiple(
            '/nonexistent/input.fasta', [], '/tmp', cut_ga=True
        )
        assert success is False
        assert 'No HMM files' in message

    def test_conda_env_config(self):
        """Test that CONDA_ENV configuration uses fallback correctly."""
        import config
        # CONDA_ENV should be set (either from environment or 'bio' default)
        assert config.CONDA_ENV is not None
        assert len(config.CONDA_ENV) > 0


class TestDownloadRoutes:
    """Tests for download route functionality."""

    def test_blast_download_relative_path(self, client, tmpdir, monkeypatch):
        """Test BLAST download route handles relative paths with ?path= parameter."""
        import config

        # Set up temporary results directory
        temp_results_dir = str(tmpdir.mkdir("results"))
        monkeypatch.setattr(config, 'RESULTS_DIR', temp_results_dir)

        # Create a test file
        test_file = os.path.join(temp_results_dir, "test_file.fasta")
        with open(test_file, 'w') as f:
            f.write(">seq1\nATGC\n")

        # Test with query parameter (current implementation)
        response = client.get('/blast/download?path=test_file.fasta')
        assert response.status_code == 200

    def test_blast_download_denies_path_traversal(self, client, tmpdir, monkeypatch):
        """Test BLAST download route blocks path traversal attempts."""
        import config

        temp_results_dir = str(tmpdir.mkdir("results"))
        monkeypatch.setattr(config, 'RESULTS_DIR', temp_results_dir)

        # Create a file outside results dir
        outside_file = str(tmpdir.join("outside.txt"))
        with open(outside_file, 'w') as f:
            f.write("secret")

        # Try to access it via path traversal using query parameter
        response = client.get('/blast/download?path=../outside.txt')
        assert response.status_code == 403

    def test_alignment_download_handles_html(self, client, tmpdir, monkeypatch):
        """Test alignment download route handles HTML files."""
        import config

        temp_results_dir = str(tmpdir.mkdir("results"))
        monkeypatch.setattr(config, 'RESULTS_DIR', temp_results_dir)

        # Create a test HTML file
        test_file = os.path.join(temp_results_dir, "alignment.html")
        with open(test_file, 'w') as f:
            f.write("<html><body>Test</body></html>")

        response = client.get('/alignment/download/alignment.html')
        assert response.status_code == 200


class TestAlignmentTools:
    """Tests for alignment tools functionality."""

    def test_export_alignment_html(self, tmpdir):
        """Test export_alignment_html generates valid HTML."""
        from app.core.alignment_tools import export_alignment_html

        sequences = [
            ("seq1", "MKVLWAALLVT"),
            ("seq2", "MKVLWAALLVT"),
            ("seq3", "MKVLWAALLIT"),
        ]

        output_file = str(tmpdir.join("test_alignment.html"))
        success, message = export_alignment_html(sequences, output_file)

        assert success is True
        assert os.path.exists(output_file)

        with open(output_file, 'r') as f:
            content = f.read()
            assert '<!DOCTYPE html>' in content
            assert 'Alignment Visualization' in content
            assert 'seq1' in content
            assert 'consensus' in content.lower()

    def test_export_alignment_html_empty(self, tmpdir):
        """Test export_alignment_html handles empty sequences."""
        from app.core.alignment_tools import export_alignment_html

        output_file = str(tmpdir.join("empty_alignment.html"))
        success, message = export_alignment_html([], output_file)

        assert success is True
        assert os.path.exists(output_file)


class TestFuzzyMatching:
    """Tests for fuzzy gene ID matching functionality."""

    def test_normalize_gene_id_basic(self):
        """Test basic gene ID normalization."""
        from app.core.sequence_utils import normalize_gene_id

        # Test case insensitivity
        normalized, original = normalize_gene_id("Mp3g11110")
        assert normalized == "mp3g11110"
        assert original == "Mp3g11110"

    def test_normalize_gene_id_with_version(self):
        """Test gene ID normalization with version suffix."""
        from app.core.sequence_utils import normalize_gene_id

        # Test version suffix removal
        normalized, original = normalize_gene_id("Mp3g11110.1")
        assert normalized == "mp3g11110"
        assert original == "Mp3g11110.1"

        normalized, original = normalize_gene_id("AT1G01010.2")
        assert normalized == "at1g01010"
        assert original == "AT1G01010.2"

    def test_parse_gene_ids_from_blast_table(self):
        """Test parsing gene IDs from BLAST-like table format."""
        from app.core.sequence_utils import parse_gene_ids_from_text

        text = """ACO2_Arabidopsis_thaliana_Q41931\tMp3g11110.1\t31.9%
ACO1_Oryza_sativa\tOs01g0100100\t28.5%
Some_gene\tAT1G01010.1\t45.0%"""

        gene_ids = parse_gene_ids_from_text(text)

        assert "Mp3g11110.1" in gene_ids
        assert "Os01g0100100" in gene_ids
        assert "AT1G01010.1" in gene_ids

    def test_parse_gene_ids_simple_list(self):
        """Test parsing gene IDs from simple line-by-line list."""
        from app.core.sequence_utils import parse_gene_ids_from_text

        text = """Mp3g11110.1
AT1G01010.1
Os01g0100100"""

        gene_ids = parse_gene_ids_from_text(text)

        assert len(gene_ids) == 3
        assert "Mp3g11110.1" in gene_ids
        assert "AT1G01010.1" in gene_ids
        assert "Os01g0100100" in gene_ids

    def test_parse_gene_ids_removes_duplicates(self):
        """Test that duplicate gene IDs are removed."""
        from app.core.sequence_utils import parse_gene_ids_from_text

        text = """Mp3g11110.1
Mp3g11110.1
AT1G01010.1"""

        gene_ids = parse_gene_ids_from_text(text)

        # Should have only unique IDs
        assert len(gene_ids) == 2
        assert gene_ids.count("Mp3g11110.1") == 1

    def test_extract_sequences_fuzzy_exact_match(self, tmpdir):
        """Test fuzzy extraction with exact match."""
        from app.core.sequence_utils import extract_sequences_fuzzy

        # Create test FASTA file
        source_fasta = str(tmpdir.join("source.fasta"))
        with open(source_fasta, 'w') as f:
            f.write(">Mp3g11110.1 description\nATGCATGC\n>Mp3g22220.1\nGGGGGGGG\n")

        result = extract_sequences_fuzzy(source_fasta, ["Mp3g11110.1"])

        assert result['success'] is True
        assert len(result['sequences']) == 1
        assert result['sequences'][0][0] == "Mp3g11110.1"

    def test_extract_sequences_fuzzy_case_insensitive(self, tmpdir):
        """Test fuzzy extraction with case-insensitive matching."""
        from app.core.sequence_utils import extract_sequences_fuzzy

        source_fasta = str(tmpdir.join("source.fasta"))
        with open(source_fasta, 'w') as f:
            f.write(">Mp3g11110.1 description\nATGCATGC\n>Mp3g22220.1\nGGGGGGGG\n")

        # Search with lowercase
        result = extract_sequences_fuzzy(source_fasta, ["mp3g11110.1"])

        assert result['success'] is True
        assert len(result['sequences']) == 1

    def test_extract_sequences_fuzzy_version_agnostic(self, tmpdir):
        """Test fuzzy extraction matching with/without version suffix."""
        from app.core.sequence_utils import extract_sequences_fuzzy

        source_fasta = str(tmpdir.join("source.fasta"))
        with open(source_fasta, 'w') as f:
            f.write(">Mp3g11110.1 description\nATGCATGC\n>Mp3g22220.1\nGGGGGGGG\n")

        # Search without version suffix
        result = extract_sequences_fuzzy(source_fasta, ["Mp3g11110"])

        assert result['success'] is True
        assert len(result['sequences']) == 1

    def test_extract_sequences_fuzzy_unmatched(self, tmpdir):
        """Test fuzzy extraction reports unmatched IDs."""
        from app.core.sequence_utils import extract_sequences_fuzzy

        source_fasta = str(tmpdir.join("source.fasta"))
        with open(source_fasta, 'w') as f:
            f.write(">Mp3g11110.1\nATGCATGC\n")

        result = extract_sequences_fuzzy(source_fasta, ["Mp3g11110.1", "NonExistent123"])

        assert result['success'] is True
        assert len(result['matched']) == 1
        assert len(result['unmatched']) == 1
        assert "NonExistent123" in result['unmatched']

    def test_extract_from_fasta_fuzzy(self, tmpdir):
        """Test extract_from_fasta with fuzzy matching enabled."""
        from app.core.blast_wrapper import extract_from_fasta

        source_fasta = str(tmpdir.join("source.fasta"))
        with open(source_fasta, 'w') as f:
            f.write(">Mp3g11110.1 description\nATGCATGC\n>Mp3g22220.1\nGGGGGGGG\n>Mp3g33330.1\nCCCCCCCC\n")

        output_file = str(tmpdir.join("output.fasta"))
        # Search with mixed case and without version
        hit_ids = ['mp3g11110', 'Mp3g33330']

        success, count = extract_from_fasta(source_fasta, hit_ids, output_file, fuzzy_match=True)

        assert success is True
        assert count == 2

        with open(output_file, 'r') as f:
            content = f.read()
            assert 'Mp3g11110.1' in content
            assert 'Mp3g33330.1' in content


class TestSequenceExtractionRoutes:
    """Tests for sequence extraction API routes."""

    def test_parse_gene_ids_endpoint(self, client):
        """Test parse-gene-ids endpoint."""
        response = client.post('/sequence/parse-gene-ids',
                              json={'text': 'Mp3g11110.1\nAT1G01010.1'},
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'gene_ids' in data
        assert len(data['gene_ids']) >= 1

    def test_parse_gene_ids_empty_text(self, client):
        """Test parse-gene-ids with empty text."""
        response = client.post('/sequence/parse-gene-ids',
                              json={'text': ''},
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False

    def test_extract_by_ids_no_source(self, client):
        """Test extract-by-ids without source FASTA."""
        response = client.post('/sequence/extract-by-ids',
                              json={'gene_ids': ['Mp3g11110.1']},
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        # Should fail because no source FASTA is set
        assert data['success'] is False
        assert 'source' in data['error'].lower()

    def test_get_source_fasta_none(self, client):
        """Test get-source-fasta when none is set."""
        response = client.get('/sequence/get-source-fasta')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['has_source'] is False


class TestAlignmentVisualization:
    """Tests for alignment visualization functionality."""

    def test_check_pymsaviz_available(self):
        """Test pymsaviz availability check."""
        from app.core.alignment_tools import check_pymsaviz_available
        # Should return a boolean
        result = check_pymsaviz_available()
        assert isinstance(result, bool)

    def test_export_alignment_visualization_html(self, tmpdir):
        """Test HTML export fallback."""
        from app.core.alignment_tools import export_alignment_visualization

        sequences = [
            ("seq1", "MKVLWAALLVT"),
            ("seq2", "MKVLWAALLVT"),
        ]

        output_dir = str(tmpdir)
        success, output_file, message = export_alignment_visualization(
            sequences, output_dir, "test_viz", output_format='html'
        )

        assert success is True
        assert output_file is not None
        assert output_file.endswith('.html')
        assert os.path.exists(output_file)

    def test_check_pymsaviz_endpoint(self, client):
        """Test check-pymsaviz endpoint."""
        response = client.get('/alignment/check-pymsaviz')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'available' in data
