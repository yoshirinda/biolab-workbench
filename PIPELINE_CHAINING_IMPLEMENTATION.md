# Pipeline Input Chaining Implementation

## Overview

This implementation enables pipeline step chaining by allowing each pipeline step to accept either a freshly uploaded file or a previously generated server-side path. This matches the CLI's ability to reuse intermediate files and eliminates the need to re-upload files between pipeline steps.

## Changes Made

### 1. New Helper Function: `resolve_input_file`

**Location:** `app/utils/file_utils.py`

A new helper function that:
- Prefers `request.form['file_path']` over uploaded files
- Validates that the path resides within `config.RESULTS_DIR` or `config.UPLOADS_DIR` (security check)
- Falls back to `save_uploaded_file()` if no path is provided
- Raises clear `ValueError` exceptions for invalid/unsafe paths

**Security Features:**
- Path traversal prevention (only allows paths within results/uploads directories)
- File existence verification
- File type validation (ensures it's a file, not a directory)

**Usage:**
```python
from app.utils.file_utils import resolve_input_file

try:
    input_file = resolve_input_file(request)
    # Use input_file for processing
except ValueError as e:
    return jsonify({'success': False, 'error': str(e)})
```

### 2. Refactored Routes

#### `app/routes/phylo.py`

All endpoints have been updated to use `resolve_input_file()`:
- `/run-full` - Full pipeline execution
- `/run-step/<step>` - Individual pipeline steps (step1-step5, step2_5, step2_7, step2_8, step4_5)
- `/hmm-search` - HMM profile search
- `/clipkit-trim` - ClipKIT trimming
- `/suggest-clipkit-mode` - Mode suggestion
- `/iqtree-infer` - IQ-TREE inference
- `/modelfinder` - ModelFinder

#### `app/routes/pipeline.py`

Legacy pipeline routes updated:
- `/pipeline/clean-headers` - FASTA header cleaning
- `/pipeline/filter-length` - Sequence length filtering

### 3. Integration Tests

**Location:** `tests/test_pipeline_chaining.py`

Comprehensive test suite covering:
- Helper function validation (14 tests)
  - Resolving paths from RESULTS_DIR
  - Resolving paths from UPLOADS_DIR
  - Invalid path rejection (path traversal prevention)
  - Nonexistent file handling
  - Missing input error handling
  - Fallback to uploaded files
  
- Integration tests with actual routes
  - Step chaining with file_path parameter
  - Invalid path rejection with clear errors
  - Multiple endpoints (phylo steps, pipeline routes)

All tests pass successfully.

### 4. Documentation

**Location:** `app/templates/docs/phylo.html`

Added a new "Pipeline Step Chaining" section that documents:
- How to use the `file_path` parameter
- API usage examples (both file upload and path chaining)
- Security notes about path restrictions
- Example workflow

## API Changes

### Before (Upload Only)
```bash
POST /phylo/run-step/step3
Content-Type: multipart/form-data

file: (binary file data)
maxiterate: 1000
```

### After (Upload OR Path)
```bash
# Option 1: Upload (backward compatible)
POST /phylo/run-step/step3
Content-Type: multipart/form-data

file: (binary file data)
maxiterate: 1000

# Option 2: Use server-side path (NEW)
POST /phylo/run-step/step3
Content-Type: application/x-www-form-urlencoded

file_path: /path/to/results/phylo_step1_20231215_123456/cleaned.fasta
maxiterate: 1000
```

## Error Handling

Clear error messages for common issues:

1. **Invalid Path (Outside Allowed Directories)**
   ```json
   {
     "success": false,
     "error": "Invalid file path: must be within results or uploads directory. Provided path resolves to: /etc/passwd"
   }
   ```

2. **File Not Found**
   ```json
   {
     "success": false,
     "error": "File not found: /path/to/nonexistent/file.fasta"
   }
   ```

3. **Path is Not a File**
   ```json
   {
     "success": false,
     "error": "Path is not a file: /path/to/directory"
   }
   ```

4. **No Input Provided**
   ```json
   {
     "success": false,
     "error": "No input file provided. Please either upload a file or provide a file_path parameter."
   }
   ```

## Backward Compatibility

All changes are fully backward compatible:
- Existing code that uploads files continues to work without modification
- The `file_path` parameter is optional
- No breaking changes to existing APIs

## Testing

Run the new tests:
```bash
source .venv/bin/activate
python -m pytest tests/test_pipeline_chaining.py -v
```

All 14 tests pass, covering:
- 6 helper function tests
- 8 integration tests with actual routes

## Benefits

1. **Efficiency**: No need to re-upload files between pipeline steps
2. **Automation**: Enables programmatic pipeline chaining via API
3. **Consistency**: Matches CLI workflow where intermediate files can be reused
4. **Security**: Robust path validation prevents unauthorized file access
5. **User Experience**: Clearer error messages guide users when paths are invalid
6. **Documentation**: Comprehensive docs help users understand and use the feature

## Example Workflow

```python
import requests

# Step 1: Clean FASTA
response1 = requests.post('http://localhost:5000/phylo/run-step/step1', 
                         files={'file': open('input.fasta', 'rb')})
output1 = response1.json()['output']

# Step 2: Use output from step 1 as input to step 3 (no re-upload!)
response3 = requests.post('http://localhost:5000/phylo/run-step/step3',
                         data={'file_path': output1, 'maxiterate': 1000})
output3 = response3.json()['output']

# Step 3: Use output from step 3 as input to step 4
response4 = requests.post('http://localhost:5000/phylo/run-step/step4',
                         data={'file_path': output3, 'clipkit_mode': 'kpic-gappy'})
output4 = response4.json()['output']

# And so on...
```
