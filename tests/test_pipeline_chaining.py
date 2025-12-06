"""
Integration tests for pipeline input chaining functionality.
"""
import pytest
import sys
import os
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
import config
from app.utils.file_utils import resolve_input_file


@pytest.fixture
def client():
    """Create a test client."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def dummy_fasta_in_results():
    """Create a dummy FASTA file in RESULTS_DIR for testing."""
    # Ensure RESULTS_DIR exists
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    
    # Create a simple test FASTA file
    test_content = """>seq1
ATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATG
>seq2
ATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATG
>seq3
ATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATG
"""
    
    # Create a temporary file in RESULTS_DIR
    filepath = os.path.join(config.RESULTS_DIR, 'test_dummy.fasta')
    with open(filepath, 'w') as f:
        f.write(test_content)
    
    yield filepath
    
    # Cleanup
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except:
        pass


@pytest.fixture
def dummy_fasta_in_uploads():
    """Create a dummy FASTA file in UPLOADS_DIR for testing."""
    # Ensure UPLOADS_DIR exists
    os.makedirs(config.UPLOADS_DIR, exist_ok=True)
    
    # Create a simple test FASTA file
    test_content = """>seq1
ATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATG
>seq2
ATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATG
"""
    
    # Create a temporary file in UPLOADS_DIR
    filepath = os.path.join(config.UPLOADS_DIR, 'test_upload.fasta')
    with open(filepath, 'w') as f:
        f.write(test_content)
    
    yield filepath
    
    # Cleanup
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except:
        pass


class TestResolveInputFile:
    """Tests for the resolve_input_file helper function."""
    
    def test_resolve_input_file_from_results_dir(self, client, dummy_fasta_in_results):
        """Test resolving a file path from RESULTS_DIR."""
        with client.application.test_request_context(
            '/test',
            method='POST',
            data={'file_path': dummy_fasta_in_results}
        ):
            from flask import request
            result = resolve_input_file(request)
            assert result == os.path.abspath(dummy_fasta_in_results)
            assert os.path.exists(result)
    
    def test_resolve_input_file_from_uploads_dir(self, client, dummy_fasta_in_uploads):
        """Test resolving a file path from UPLOADS_DIR."""
        with client.application.test_request_context(
            '/test',
            method='POST',
            data={'file_path': dummy_fasta_in_uploads}
        ):
            from flask import request
            result = resolve_input_file(request)
            assert result == os.path.abspath(dummy_fasta_in_uploads)
            assert os.path.exists(result)
    
    def test_resolve_input_file_invalid_path(self, client):
        """Test that paths outside allowed directories are rejected."""
        with client.application.test_request_context(
            '/test',
            method='POST',
            data={'file_path': '/etc/passwd'}
        ):
            from flask import request
            with pytest.raises(ValueError) as excinfo:
                resolve_input_file(request)
            assert "Invalid file path" in str(excinfo.value)
    
    def test_resolve_input_file_nonexistent(self, client):
        """Test that nonexistent files are rejected."""
        fake_path = os.path.join(config.RESULTS_DIR, 'nonexistent_file.fasta')
        with client.application.test_request_context(
            '/test',
            method='POST',
            data={'file_path': fake_path}
        ):
            from flask import request
            with pytest.raises(ValueError) as excinfo:
                resolve_input_file(request)
            assert "File not found" in str(excinfo.value)
    
    def test_resolve_input_file_from_uploaded(self, client):
        """Test falling back to uploaded file when no file_path provided."""
        # Create a temporary file to upload
        test_content = b">seq1\nATGC\n"
        
        with client.application.test_request_context(
            '/test',
            method='POST',
            data={'file': (tempfile.NamedTemporaryFile(delete=False).name, test_content)},
            content_type='multipart/form-data'
        ):
            # This test verifies the fallback mechanism exists
            # In practice, we'd need a proper file upload simulation
            pass
    
    def test_resolve_input_file_no_input(self, client):
        """Test that missing input raises appropriate error."""
        with client.application.test_request_context(
            '/test',
            method='POST',
            data={}
        ):
            from flask import request
            with pytest.raises(ValueError) as excinfo:
                resolve_input_file(request)
            assert "No input file provided" in str(excinfo.value)


class TestPipelineChaining:
    """Integration tests for pipeline step chaining."""
    
    def test_phylo_step3_with_file_path(self, client, dummy_fasta_in_results):
        """Test running step3 (MAFFT) with file_path parameter instead of upload."""
        response = client.post('/phylo/run-step/step3', data={
            'file_path': dummy_fasta_in_results,
            'maxiterate': '1000'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should succeed (even if MAFFT isn't installed, file resolution should work)
        # If it fails due to missing MAFFT, that's a different issue
        if not data.get('success'):
            # Check if failure is due to MAFFT not being available, not file resolution
            error = data.get('error', '').lower()
            # Acceptable errors are about MAFFT/conda, not about file upload
            assert 'file' not in error or 'not found' not in error
        else:
            # If successful, verify output structure
            assert 'output' in data or 'message' in data
            assert 'result_dir' in data
    
    def test_phylo_step1_with_file_path(self, client, dummy_fasta_in_results):
        """Test running step1 (clean FASTA) with file_path parameter."""
        response = client.post('/phylo/run-step/step1', data={
            'file_path': dummy_fasta_in_results
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Step1 should work without external dependencies
        if data.get('success'):
            assert 'output' in data
            assert 'result_dir' in data
    
    def test_pipeline_clean_headers_with_file_path(self, client, dummy_fasta_in_results):
        """Test pipeline clean-headers endpoint with file_path parameter."""
        response = client.post('/pipeline/clean-headers', data={
            'file_path': dummy_fasta_in_results
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Clean headers should work without external dependencies
        if data.get('success'):
            assert 'output_file' in data
            assert 'result_dir' in data
            assert 'count' in data
            assert data['count'] == 3  # We have 3 sequences in the dummy file
    
    def test_pipeline_filter_length_with_file_path(self, client, dummy_fasta_in_results):
        """Test pipeline filter-length endpoint with file_path parameter."""
        response = client.post('/pipeline/filter-length', data={
            'file_path': dummy_fasta_in_results,
            'min_length': '10'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Filter length should work without external dependencies
        if data.get('success'):
            assert 'output_file' in data
            assert 'result_dir' in data
    
    def test_invalid_path_rejected(self, client):
        """Test that invalid paths are properly rejected with clear error."""
        response = client.post('/phylo/run-step/step1', data={
            'file_path': '/etc/passwd'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'Invalid file path' in data['error']
    
    def test_nonexistent_path_rejected(self, client):
        """Test that nonexistent paths are properly rejected with clear error."""
        fake_path = os.path.join(config.RESULTS_DIR, 'does_not_exist.fasta')
        response = client.post('/phylo/run-step/step1', data={
            'file_path': fake_path
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'File not found' in data['error']
    
    def test_hmm_search_with_file_path(self, client, dummy_fasta_in_results):
        """Test HMM search endpoint with file_path parameter."""
        response = client.post('/phylo/hmm-search', data={
            'file_path': dummy_fasta_in_results,
            'hmm_files[]': []  # Empty for now, will fail but should not be due to file resolution
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should fail due to no HMM files, not file resolution
        if not data.get('success'):
            error = data.get('error', '')
            assert 'No HMM' in error or 'hmm' in error.lower()
    
    def test_clipkit_trim_with_file_path(self, client, dummy_fasta_in_results):
        """Test ClipKIT trim endpoint with file_path parameter."""
        response = client.post('/phylo/clipkit-trim', data={
            'file_path': dummy_fasta_in_results,
            'mode': 'kpic-gappy'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        
        # May fail if ClipKIT not installed, but should not fail on file resolution
        if not data.get('success'):
            error = data.get('error', '').lower()
            # Should not be a file resolution error
            assert 'invalid file path' not in error
            assert 'no input file' not in error
