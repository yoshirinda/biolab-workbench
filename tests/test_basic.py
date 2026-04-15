"""
Basic tests for BioLab Workbench.
"""
import pytest
import sys
import os
import io

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

    def test_index_page_has_new_user_starter_tracks(self, client):
        """Home page should expose newcomer-oriented starter tracks."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'New User Starter Tracks' in html
        assert 'Find Homologs Quickly' in html

    def test_index_page_has_runtime_context(self, client):
        """Home page should show runtime context for reproducibility/debugging."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'Runtime Context' in html
        assert 'Conda Env' in html

    def test_index_page_has_system_readiness_panel(self, client):
        """Home page should show tool readiness panel for newcomers."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'System Readiness' in html
        assert 'BLAST search (blastn)' in html
        assert 'Not checked (test mode)' in html

    def test_sequence_page(self, client):
        """Test sequence page loads."""
        response = client.get('/sequence/')
        assert response.status_code == 200

    def test_sequence_page_uses_react_shell(self, client):
        """Main sequence page should serve the React app shell."""
        response = client.get('/sequence/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert '<div id="root"></div>' in html
        assert 'react/assets/index.js' in html

    def test_blast_page(self, client):
        """Test BLAST page loads."""
        response = client.get('/blast/')
        assert response.status_code == 200

    def test_blast_page_has_result_interpretation_panel(self, client):
        """BLAST page should expose a result interpretation container."""
        response = client.get('/blast/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'blastInterpretation' in html

    def test_phylo_page(self, client):
        """Test phylo page loads."""
        response = client.get('/phylo/')
        assert response.status_code == 200

    def test_phylo_page_has_step_interpretation_blocks(self, client):
        """Phylo pipeline should expose per-step interpretation placeholders."""
        response = client.get('/phylo/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'hmmInterpretation' in html
        assert 'pipelineBlastInterpretation' in html
        assert 'iqtreeInterpretation' in html

    def test_alignment_page(self, client):
        """Test alignment page loads."""
        response = client.get('/alignment/')
        assert response.status_code == 200

    def test_alignment_page_has_result_interpretation_panel(self, client):
        """Alignment page should expose a result interpretation card."""
        response = client.get('/alignment/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'alignmentInterpretationCard' in html
        assert 'alignmentInterpretation' in html

    def test_uniprot_page(self, client):
        """Test UniProt page loads."""
        response = client.get('/uniprot/')
        assert response.status_code == 200

    def test_uniprot_page_has_result_interpretation_panel(self, client):
        """UniProt page should expose a result interpretation container."""
        response = client.get('/uniprot/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'uniprotInterpretation' in html
        assert 'uniprotScientificHints' in html

    def test_uniprot_search_rejects_invalid_limit(self, client):
        """UniProt search should validate numeric limits before upstream calls."""
        response = client.post('/uniprot/search', json={
            'query': 'kinase',
            'limit': 100000
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'limit' in data['error'].lower()

    def test_uniprot_search_rejects_invalid_database_type(self, client):
        """UniProt search should reject unsupported database type values."""
        response = client.post('/uniprot/search', json={
            'query': 'kinase',
            'database_type': 'swissprot'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'database_type' in data['error']

    def test_tree_page_avoids_inline_onclick_handlers(self, client):
        """Tree page should avoid inline onclick handlers for safer JS wiring."""
        response = client.get('/tree/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'onclick=' not in html

    def test_uniprot_page_uses_non_blocking_alert_patterns(self, client):
        """UniProt page should avoid native alert() usage in interactive flows."""
        response = client.get('/uniprot/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'alert(' not in html
        assert 'common-taxon-btn' in html

    def test_alignment_run_rejects_unavailable_tool(self, client, monkeypatch):
        """Alignment run should fail fast with actionable error when tool is unavailable."""
        from app.routes import alignment as alignment_routes

        monkeypatch.setattr(
            alignment_routes,
            'check_available_tools',
            lambda force=False: {'mafft': False, 'clustalw': False, 'muscle': False}
        )

        response = client.post('/alignment/run', data={
            'sequences': '>seq1\nATGCATGC\n>seq2\nATGCATGA\n',
            'tool': 'mafft'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'not available' in data['error'].lower()

    def test_tree_page(self, client):
        """Test tree page loads."""
        response = client.get('/tree/')
        assert response.status_code == 200

    def test_tree_page_has_main_visualize_submit_handler(self, client):
        """Tree page should wire the main visualize form without requiring clade-only input."""
        response = client.get('/tree/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert "document.getElementById('visualizeForm').addEventListener('submit'" in html
        assert 'collectVisualizationSettings()' in html

    def test_tree_page_supports_pipeline_tree_preload(self, client):
        """Tree page should support opening a generated tree directly from the pipeline flow."""
        response = client.get('/tree/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'preloadTreeFromQuery()' in html
        assert "params.get('tree_file')" in html

    def test_tree_page_has_result_interpretation_panel(self, client):
        """Tree page should expose a result interpretation container."""
        response = client.get('/tree/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'treeInterpretation' in html
        assert 'supportMetric' in html
        assert 'supportThresholdGuidance' in html

    def test_tree_extract_clade_passes_v_scale(self, client, monkeypatch, tmp_path):
        """Tree clade extraction should forward V. Scale to the renderer."""
        from app.routes import tree as tree_routes

        tree_file = tmp_path / 'test.nwk'
        tree_file.write_text('(A:1,B:1);', encoding='utf-8')
        captured = {}

        def fake_run_in_process(func, **kwargs):
            captured.update(kwargs)
            return True, 'result_dir', 'tree.svg', 'ok', {
                'leaf_count': 2,
                'levels_up': 1,
                'support_stats': None
            }

        monkeypatch.setattr(tree_routes, 'run_in_process', fake_run_in_process)

        response = client.post('/tree/extract-clade', json={
            'tree_file': str(tree_file),
            'target_gene': 'A',
            'levels_up': 1,
            'layout': 'rectangular',
            'font_size': 10,
            'v_scale': 1.7
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert captured['v_scale'] == 1.7

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

    def test_normalize_blast_scoring_options_requires_reward_penalty_pair(self):
        from app.core.blast_wrapper import normalize_blast_scoring_options

        success, message, normalized, warnings = normalize_blast_scoring_options(
            program='blastn',
            reward=1,
            penalty=None
        )

        assert success is False
        assert 'provided together' in message
        assert normalized is None

    def test_normalize_blast_scoring_options_rejects_unsupported_blastn_pair(self):
        from app.core.blast_wrapper import normalize_blast_scoring_options

        success, message, normalized, warnings = normalize_blast_scoring_options(
            program='blastn',
            reward=3,
            penalty=-4
        )

        assert success is False
        assert 'Unsupported blastn reward/penalty pair' in message
        assert normalized is None

    def test_normalize_blast_scoring_options_rejects_tblastx_word_size_out_of_range(self):
        from app.core.blast_wrapper import normalize_blast_scoring_options

        success, message, normalized, warnings = normalize_blast_scoring_options(
            program='tblastx',
            word_size=5
        )

        assert success is False
        assert 'between 2 and 3 for tblastx' in message
        assert normalized is None

    def test_normalize_blast_scoring_options_sets_blastn_short_default_word_size(self):
        from app.core.blast_wrapper import normalize_blast_scoring_options

        success, message, normalized, warnings = normalize_blast_scoring_options(
            program='blastn',
            task='blastn-short',
            word_size=None
        )

        assert success is True
        assert normalized['word_size'] == 7
        assert warnings


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

    def test_step2_5_blast_filter_runs_command_and_filters(self, monkeypatch, tmpdir):
        """Ensure step2_5_blast_filter runs blastp and filters sequences by gold list."""
        from app.core import phylo_pipeline

        input_fasta = tmpdir.join('input.fasta')
        input_fasta.write(
            '>seq1 description\nMKTAYIAKQRQISFVKSH\n>seq2 other\nAAAAAAAAAAAA\n'
        )
        gold_file = tmpdir.join('gold.txt')
        gold_file.write('GOLD.ID.1\n')

        db_base = tmpdir.join('mock_db')
        for ext in ('.pin', '.psq', '.phr'):
            tmpdir.join(f'mock_db{ext}').write('')

        captured = []

        def fake_run(cmd, shell, capture_output, text, timeout):
            captured.append(cmd)
            class Dummy:
                returncode = 0
                stdout = 'seq1\tGOLD.ID.1\t80\t90\nseq2\tOTHER\t50\t10\n'
                stderr = ''
            return Dummy()

        monkeypatch.setattr(phylo_pipeline.subprocess, 'run', fake_run)

        success, output, message, stats, command = phylo_pipeline.step2_5_blast_filter(
            str(input_fasta),
            str(gold_file),
            str(tmpdir),
            pident_threshold=60,
            qcovs_threshold=60,
            blast_db_path=str(db_base),
            evalue=1e-6,
            max_target_seqs=10,
            threads=8
        )

        assert captured, 'blastp command was not invoked'
        assert 'blastp' in captured[0]
        assert '-outfmt' in captured[0]
        assert success is True
        assert 'blastp' in command
        assert '-max_target_seqs 10' in command
        assert '-num_threads 8' in command
        assert os.path.exists(stats['raw_output_file'])
        with open(stats['raw_output_file'], 'r') as fh:
            header = fh.readline().strip()
            assert header == 'qseqid\tsseqid\tpident\tqcovs'
        with open(output, 'r') as fh:
            data = fh.read()
            assert '>seq1' in data
            assert '>seq2' not in data
        assert stats['kept'] == 1
        assert stats['deleted'] == 1
        assert stats['database'].endswith('mock_db')

    def test_step2_5_blast_filter_missing_db(self, tmpdir):
        """Missing BLAST database should return a graceful error."""
        from app.core import phylo_pipeline

        input_fasta = tmpdir.join('input.fasta')
        input_fasta.write('>seq1\nMKTAYIAKQRQISFVKSH\n')
        gold_file = tmpdir.join('gold.txt')
        gold_file.write('SEQ1\n')

        success, output, message, stats, command = phylo_pipeline.step2_5_blast_filter(
            str(input_fasta),
            str(gold_file),
            str(tmpdir),
            blast_db_path=str(tmpdir.join('missing_db'))
        )

        assert success is False
        assert 'blast database' in message.lower()
        assert stats is None

    def test_step2_5_blast_filter_zero_hits(self, monkeypatch, tmpdir):
        """When BLAST returns zero hits, the function should succeed with zero kept sequences."""
        from app.core import phylo_pipeline

        input_fasta = tmpdir.join('input.fasta')
        input_fasta.write('>seq1\nMKTAYIAKQRQISFVKSH\n')
        gold_file = tmpdir.join('gold.txt')
        gold_file.write('SEQ1\n')
        db_base = tmpdir.join('mock_db_zero')
        for ext in ('.pin', '.psq', '.phr'):
            tmpdir.join(f'mock_db_zero{ext}').write('')

        def fake_run(cmd, shell, capture_output, text, timeout):
            class Dummy:
                returncode = 0
                stdout = ''
                stderr = ''
            return Dummy()

        monkeypatch.setattr(phylo_pipeline.subprocess, 'run', fake_run)

        success, output, message, stats, command = phylo_pipeline.step2_5_blast_filter(
            str(input_fasta),
            str(gold_file),
            str(tmpdir),
            blast_db_path=str(db_base)
        )

        assert success is True
        assert stats['kept'] == 0
        assert stats['deleted'] == 1
        assert stats['total_hits'] == 0
        assert os.path.exists(stats['log_file'])
        assert 'No sequences' in message or '0' in message

    def test_conda_env_config(self):
        """Test that CONDA_ENV configuration uses fallback correctly."""
        import config
        # CONDA_ENV should be set (either from environment or 'bio' default)
        assert config.CONDA_ENV is not None
        assert len(config.CONDA_ENV) > 0

class TestBlastSearchValidation:
    """Tests for BLAST search input validation and parameter parsing."""

    def test_blast_search_rejects_invalid_output_format(self, client):
        response = client.post('/blast/search', data={
            'query_text': '>q1\nATGCATGC\n',
            'database': 'dummy_db',
            'output_format': 'xml'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Invalid output_format' in data['error']

    def test_blast_search_rejects_invalid_evalue_format(self, client):
        response = client.post('/blast/search', data={
            'query_text': '>q1\nATGCATGC\n',
            'database': 'dummy_db',
            'evalue': 'abc'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Invalid evalue' in data['error']

    def test_blast_search_rejects_too_small_evalue(self, client):
        response = client.post('/blast/search', data={
            'query_text': '>q1\nATGCATGC\n',
            'database': 'dummy_db',
            'evalue': '1e-301'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'too small' in data['error']

    def test_blast_search_accepts_scientific_notation_evalue(self, client, tmpdir, monkeypatch):
        from app.routes import blast as blast_routes

        captured = {}
        result_dir = str(tmpdir.mkdir('blast_result'))
        result_txt = os.path.join(result_dir, 'blast_result.txt')
        with open(result_txt, 'w') as f:
            f.write('Mock BLAST output\n')

        def fake_run_blast(**kwargs):
            captured.update(kwargs)
            output_files = {
                'main': result_txt,
                'program': kwargs.get('program') or 'blastn',
                'query_type': 'nucleotide',
                'db_type': 'nucleotide',
                'meta': {}
            }
            return True, result_dir, output_files, 'mock-blast-command'

        monkeypatch.setattr(blast_routes, 'run_blast', fake_run_blast)

        response = client.post('/blast/search', data={
            'query_text': '>q1\nATGCATGC\n',
            'database': 'dummy_db',
            'output_format': 'txt',
            'evalue': '2E-20',
            'max_hits': '10'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert captured['evalue'] == pytest.approx(2e-20)
        assert captured['max_hits'] == 10


class TestPhyloSupportValidation:
    """Tests for phylogenetic support parameter validation."""

    def test_iqtree_infer_rejects_unaligned_input(self, client, tmpdir, monkeypatch):
        import config

        results_dir = str(tmpdir.mkdir('results'))
        uploads_dir = str(tmpdir.mkdir('uploads'))
        monkeypatch.setattr(config, 'RESULTS_DIR', results_dir)
        monkeypatch.setattr(config, 'UPLOADS_DIR', uploads_dir)

        alignment_file = os.path.join(results_dir, 'unaligned.fasta')
        with open(alignment_file, 'w') as f:
            f.write('>seq1\nAAAAAA\n>seq2\nAAA\n')

        response = client.post('/phylo/iqtree-infer', data={
            'file_path': alignment_file,
            'model': 'MFP',
            'bootstrap': '1000',
            'bootstrap_type': 'ufboot'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'equal-length sequences' in data['error']

    def test_iqtree_infer_rejects_protein_model_on_nucleotide_alignment(self, client, tmpdir, monkeypatch):
        import config

        results_dir = str(tmpdir.mkdir('results'))
        uploads_dir = str(tmpdir.mkdir('uploads'))
        monkeypatch.setattr(config, 'RESULTS_DIR', results_dir)
        monkeypatch.setattr(config, 'UPLOADS_DIR', uploads_dir)

        alignment_file = os.path.join(results_dir, 'alignment.fasta')
        with open(alignment_file, 'w') as f:
            f.write('>seq1\nATGCATGC\n>seq2\nATGTATGC\n')

        response = client.post('/phylo/iqtree-infer', data={
            'file_path': alignment_file,
            'model': 'LG+G4',
            'bootstrap': '1000',
            'bootstrap_type': 'ufboot'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'protein-oriented' in data['error']

    def test_iqtree_infer_rejects_low_ufboot(self, client, tmpdir, monkeypatch):
        import config

        results_dir = str(tmpdir.mkdir('results'))
        uploads_dir = str(tmpdir.mkdir('uploads'))
        monkeypatch.setattr(config, 'RESULTS_DIR', results_dir)
        monkeypatch.setattr(config, 'UPLOADS_DIR', uploads_dir)

        alignment_file = os.path.join(results_dir, 'alignment.fasta')
        with open(alignment_file, 'w') as f:
            f.write('>seq1\nAAAA\n>seq2\nAAAT\n')

        response = client.post('/phylo/iqtree-infer', data={
            'file_path': alignment_file,
            'model': 'MFP',
            'bootstrap': '500',
            'bootstrap_type': 'ufboot'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Ultrafast bootstrap requires >= 1000 replicates' in data['error']

    def test_iqtree_infer_rejects_low_alrt_replicates(self, client, tmpdir, monkeypatch):
        import config

        results_dir = str(tmpdir.mkdir('results'))
        uploads_dir = str(tmpdir.mkdir('uploads'))
        monkeypatch.setattr(config, 'RESULTS_DIR', results_dir)
        monkeypatch.setattr(config, 'UPLOADS_DIR', uploads_dir)

        alignment_file = os.path.join(results_dir, 'alignment.fasta')
        with open(alignment_file, 'w') as f:
            f.write('>seq1\nAAAA\n>seq2\nAAAT\n')

        response = client.post('/phylo/iqtree-infer', data={
            'file_path': alignment_file,
            'model': 'MFP',
            'bootstrap': '1000',
            'bootstrap_type': 'ufboot',
            'alrt': 'true',
            'alrt_replicates': '500'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'alrt_replicates' in data['error']

    def test_iqtree_infer_disables_bnni_for_standard_bootstrap(self, client, tmpdir, monkeypatch):
        import config
        from app.routes import phylo as phylo_routes

        results_dir = str(tmpdir.mkdir('results'))
        uploads_dir = str(tmpdir.mkdir('uploads'))
        monkeypatch.setattr(config, 'RESULTS_DIR', results_dir)
        monkeypatch.setattr(config, 'UPLOADS_DIR', uploads_dir)

        alignment_file = os.path.join(results_dir, 'alignment.fasta')
        with open(alignment_file, 'w') as f:
            f.write('>seq1\nAAAA\n>seq2\nAAAT\n')

        captured = {}

        class DummyPopen:
            def poll(self):
                return None

        def fake_run_iqtree(**kwargs):
            captured.update(kwargs)
            output_prefix = os.path.join(results_dir, 'iqtree_test')
            return DummyPopen(), results_dir, {
                'treefile': output_prefix + '.treefile',
                'log': output_prefix + '.log',
                'iqtree': output_prefix + '.iqtree'
            }, output_prefix

        monkeypatch.setattr(phylo_routes, 'run_iqtree', fake_run_iqtree)

        response = client.post('/phylo/iqtree-infer', data={
            'file_path': alignment_file,
            'model': 'MFP',
            'bootstrap': '200',
            'bootstrap_type': 'boot',
            'bnni': 'true'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert captured['bnni'] is False
        assert data['warnings']


class TestScientificParameterNormalization:
    """Tests for route-level normalization of scientific parameters."""

    def test_modelfinder_rejects_unaligned_input(self, client, tmpdir, monkeypatch):
        import config

        results_dir = str(tmpdir.mkdir('results'))
        uploads_dir = str(tmpdir.mkdir('uploads'))
        monkeypatch.setattr(config, 'RESULTS_DIR', results_dir)
        monkeypatch.setattr(config, 'UPLOADS_DIR', uploads_dir)

        input_file = os.path.join(results_dir, 'unaligned.fasta')
        with open(input_file, 'w') as f:
            f.write('>seq1\nMKTAYIAK\n>seq2\nMKTI\n')

        response = client.post('/phylo/modelfinder', data={'file_path': input_file})

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'equal-length sequences' in data['error']

    def test_hmm_search_ignores_dom_evalue_when_cut_ga_enabled(self, client, tmpdir, monkeypatch):
        import config
        from app.routes import phylo as phylo_routes

        results_dir = str(tmpdir.mkdir('results'))
        uploads_dir = str(tmpdir.mkdir('uploads'))
        hmm_dir = str(tmpdir.mkdir('hmms'))
        monkeypatch.setattr(config, 'RESULTS_DIR', results_dir)
        monkeypatch.setattr(config, 'UPLOADS_DIR', uploads_dir)
        monkeypatch.setattr(config, 'HMM_PROFILES_DIR', hmm_dir)

        input_file = os.path.join(results_dir, 'input.fasta')
        with open(input_file, 'w') as f:
            f.write('>seq1\nMKTAYIAKQRQISFVKSH\n>seq2\nAAAAAAAAAAAAAA\n')

        hmm_name = 'test.hmm'
        hmm_path = os.path.join(hmm_dir, hmm_name)
        with open(hmm_path, 'w') as f:
            f.write('HMMER3/f\n')

        captured = {}

        def fake_step2_hmmsearch_multiple(input_file, hmm_paths, output_dir, cut_ga, evalue, dom_evalue, threads):
            captured.update({
                'cut_ga': cut_ga,
                'evalue': evalue,
                'dom_evalue': dom_evalue,
                'threads': threads,
            })
            output = os.path.join(output_dir, 'hits.fasta')
            with open(output, 'w') as f:
                f.write('>seq1\nMKTAYIAKQRQISFVKSH\n')
            return True, output, 'ok', ['mock-hmmsearch']

        monkeypatch.setattr(phylo_routes, 'step2_hmmsearch_multiple', fake_step2_hmmsearch_multiple)

        response = client.post('/phylo/hmm-search', data={
            'file_path': input_file,
            'hmm_files[]': hmm_name,
            'cut_ga': 'true',
            'dom_evalue': '1e-3'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert captured['cut_ga'] is True
        assert captured['dom_evalue'] is None
        assert data['warnings']

    def test_clipkit_trim_ignores_gap_threshold_for_smart_gap(self, client, tmpdir, monkeypatch):
        import config
        from app.routes import phylo as phylo_routes

        results_dir = str(tmpdir.mkdir('results'))
        uploads_dir = str(tmpdir.mkdir('uploads'))
        monkeypatch.setattr(config, 'RESULTS_DIR', results_dir)
        monkeypatch.setattr(config, 'UPLOADS_DIR', uploads_dir)

        input_file = os.path.join(results_dir, 'alignment.fasta')
        with open(input_file, 'w') as f:
            f.write('>seq1\nAAAA--AA\n>seq2\nAAAAAA--\n')

        captured = {}

        def fake_run_clipkit(input_file, mode='kpic-gappy', gaps=0.9):
            captured.update({'mode': mode, 'gaps': gaps})
            output = os.path.join(results_dir, 'trimmed.fasta')
            log_file = output + '.log'
            with open(output, 'w') as f:
                f.write('>seq1\nAAAAAA\n>seq2\nAAAAAA\n')
            with open(log_file, 'w') as f:
                f.write('mock log')
            return True, results_dir, output, log_file, {
                'input_length': 8,
                'output_length': 6,
                'percent_kept': 75.0,
                'input_seq_count': 2,
                'output_seq_count': 2
            }

        monkeypatch.setattr(phylo_routes, 'run_clipkit', fake_run_clipkit)

        response = client.post('/phylo/clipkit-trim', data={
            'file_path': input_file,
            'mode': 'smart-gap',
            'gaps': '0.3'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert captured['mode'] == 'smart-gap'
        assert captured['gaps'] is None
        assert data['warnings']

    def test_run_step_step4_passes_gap_threshold_to_clipkit(self, client, tmpdir, monkeypatch):
        import config
        from app.routes import phylo as phylo_routes

        results_dir = str(tmpdir.mkdir('results'))
        uploads_dir = str(tmpdir.mkdir('uploads'))
        monkeypatch.setattr(config, 'RESULTS_DIR', results_dir)
        monkeypatch.setattr(config, 'UPLOADS_DIR', uploads_dir)

        input_file = os.path.join(results_dir, 'alignment.fasta')
        with open(input_file, 'w') as f:
            f.write('>seq1\nAAAA--AA\n>seq2\nAAAAAA--\n')

        captured = {}

        def fake_step4_clipkit(input_file, output_dir, mode='kpic-gappy', gaps=None):
            captured.update({'mode': mode, 'gaps': gaps})
            output = os.path.join(output_dir, 'trimmed.fasta')
            with open(output, 'w') as f:
                f.write('>seq1\nAAAAAA\n>seq2\nAAAAAA\n')
            return True, output, 'ok', 'mock-clipkit'

        monkeypatch.setattr(phylo_routes, 'step4_clipkit', fake_step4_clipkit)

        response = client.post('/phylo/run-step/step4', data={
            'file_path': input_file,
            'clipkit_mode': 'gappy',
            'gaps': '0.7'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert captured['mode'] == 'gappy'
        assert captured['gaps'] == pytest.approx(0.7)

    def test_alignment_run_rejects_single_sequence(self, client):
        response = client.post('/alignment/run', data={
            'sequences': '>seq1\nATGCATGC\n',
            'tool': 'mafft'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'At least two FASTA sequences' in data['error']

    def test_alignment_run_rejects_mixed_sequence_types(self, client, monkeypatch):
        from app.routes import alignment as alignment_routes

        monkeypatch.setattr(
            alignment_routes,
            'check_available_tools',
            lambda force=False: {'mafft': True, 'clustalw': True, 'muscle': True}
        )

        response = client.post('/alignment/run', data={
            'sequences': '>dna1\nATGCATGC\n>prot1\nMKWVTFIS\n',
            'tool': 'mafft'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'mixture of nucleotide and protein sequences' in data['error']

    def test_alignment_run_rejects_clustalw_matrix_mismatch(self, client, monkeypatch):
        from app.routes import alignment as alignment_routes

        monkeypatch.setattr(
            alignment_routes,
            'check_available_tools',
            lambda force=False: {'mafft': True, 'clustalw': True, 'muscle': True}
        )

        response = client.post('/alignment/run', data={
            'sequences': '>dna1\nATGCATGC\n>dna2\nATGCATGA\n',
            'tool': 'clustalw',
            'matrix': 'BLOSUM'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'dna alignments must use dna matrices' in data['error'].lower()

    def test_hmm_search_defaults_domain_evalue_to_sequence_evalue(self, client, monkeypatch, tmpdir):
        import config
        from app.routes import phylo as phylo_routes

        uploads_dir = str(tmpdir.mkdir('uploads'))
        results_dir = str(tmpdir.mkdir('results'))
        hmm_dir = str(tmpdir.mkdir('hmms'))
        monkeypatch.setattr(config, 'UPLOADS_DIR', uploads_dir)
        monkeypatch.setattr(config, 'RESULTS_DIR', results_dir)
        monkeypatch.setattr(config, 'HMM_PROFILES_DIR', hmm_dir)
        monkeypatch.setattr(phylo_routes.config, 'UPLOADS_DIR', uploads_dir)
        monkeypatch.setattr(phylo_routes.config, 'RESULTS_DIR', results_dir)
        monkeypatch.setattr(phylo_routes.config, 'HMM_PROFILES_DIR', hmm_dir)
        monkeypatch.setattr(phylo_routes, 'create_result_dir', lambda domain, action: results_dir)

        hmm_path = os.path.join(hmm_dir, 'test_profile.hmm')
        with open(hmm_path, 'w', encoding='utf-8') as handle:
            handle.write('HMMER3/f [mock]\nNAME test_profile\n//\n')

        captured = {}

        def fake_hmmsearch(input_file, hmm_paths, output_dir, cut_ga, evalue, dom_evalue, threads):
            captured.update({
                'cut_ga': cut_ga,
                'evalue': evalue,
                'dom_evalue': dom_evalue,
                'threads': threads,
                'hmm_paths': hmm_paths
            })
            output_file = os.path.join(output_dir, 'hits.fasta')
            with open(output_file, 'w', encoding='utf-8') as handle:
                handle.write('>hit1\nMKWVTFIS\n')
            return True, output_file, 'ok', ['hmmsearch mock']

        monkeypatch.setattr(phylo_routes, 'step2_hmmsearch_multiple', fake_hmmsearch)

        response = client.post('/phylo/hmm-search', data={
            'file': (io.BytesIO(b'>seq1\nMKWVTFIS\n'), 'input.faa'),
            'hmm_files[]': 'test_profile.hmm',
            'cut_ga': 'false',
            'evalue': '1e-6'
        }, content_type='multipart/form-data')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert captured['cut_ga'] is False
        assert captured['evalue'] == pytest.approx(1e-6)
        assert captured['dom_evalue'] == pytest.approx(1e-6)
        assert data['threshold_settings']['cut_ga'] is False
        assert data['threshold_settings']['domain_evalue'] == pytest.approx(1e-6)
        assert data['warnings']


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

    def test_alignment_stats_distinguish_conserved_variable_and_gap_columns(self, tmpdir):
        """Alignment stats should track residue conservation separately from gap burden."""
        from app.core.alignment_wrapper import _calculate_alignment_stats

        alignment_file = str(tmpdir.join("test_alignment.fasta"))
        with open(alignment_file, 'w') as f:
            f.write(">seq1\nA-CA\n>seq2\nA-TA\n>seq3\nA--A\n")

        stats = _calculate_alignment_stats(alignment_file)

        assert stats['num_sequences'] == 3
        assert stats['alignment_length'] == 4
        assert stats['conserved_positions'] == 2
        assert stats['variable_positions'] == 1
        assert stats['gap_affected_positions'] == 1
        assert stats['gap_only_positions'] == 1

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


class TestTreeSupportParsing:
    """Tests for tree support parsing and summarization."""

    def test_get_tree_info_detects_internal_support_labels(self, tmpdir):
        """Tree info should detect numeric internal support labels from node names."""
        from app.core.tree_visualizer import get_tree_info

        tree_file = str(tmpdir.join("supported.tree"))
        with open(tree_file, 'w') as f:
            f.write("((A:1,B:1)95:1,C:1);")

        info, error = get_tree_info(tree_file)

        assert error is None
        assert info is not None
        assert info['has_support'] is True

    def test_summarize_bootstrap_support_uses_trailing_value_for_composite_labels(self, tmpdir):
        """Composite support labels like SH-aLRT/UFBoot should summarize the trailing value."""
        from app.core.iqtree_wrapper import summarize_bootstrap_support

        tree_file = str(tmpdir.join("composite_support.treefile"))
        with open(tree_file, 'w') as f:
            f.write("((A:1,B:1)80/95:1,(D:1,E:1)60/70:1,C:1);")

        stats = summarize_bootstrap_support(tree_file)

        assert stats['count'] == 2
        assert stats['composite_support_labels'] is True
        assert stats['support_metric_used'] == 'trailing'
        assert stats['mean'] == pytest.approx(82.5)
        assert stats['strong_support'] == 1
        assert stats['moderate_support'] == 1
        assert stats['weak_support'] == 0

    def test_tree_visualizer_support_metric_can_use_leading_value(self):
        """Tree visualizer summaries should allow explicit leading-value support selection."""
        from ete3 import Tree
        from app.core.tree_visualizer import _summarize_bootstrap_support

        tree = Tree("((A:1,B:1)80/95:1,(D:1,E:1)60/70:1,C:1);", format=1)
        stats = _summarize_bootstrap_support(tree, low_threshold=70, support_metric='leading')

        assert stats['composite_support_labels'] is True
        assert stats['support_metric_used'] == 'leading'
        assert stats['support_metric_label'] == 'leading value'
        assert stats['support_mean'] == pytest.approx(70.0)
        assert stats['support_other_mean'] == pytest.approx(82.5)
        assert stats['low_support_count'] == 1
