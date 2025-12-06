/**
 * Pipeline UI Orchestration JavaScript
 * Handles interactive phylogenetic pipeline workflow
 */

// Central pipeline state object
const pipelineState = {
    step0: { output: null, running: false, completed: false },
    step1: { output: null, running: false, completed: false },
    step2: { output: null, running: false, completed: false },
    step2_5: { output: null, running: false, completed: false },
    step3: { output: null, running: false, completed: false },
    step4: { output: null, running: false, completed: false },
    step5: { output: null, running: false, completed: false },
    step6: { output: null, running: false, completed: false },
    step7: { output: null, running: false, completed: false }
};

// Step configuration
const stepConfig = {
    step0: { name: 'Clean Headers', endpoint: '/phylo/run-step/step1' },
    step1: { name: 'HMM Search', endpoint: '/phylo/hmm-search' },
    step2: { name: 'BLAST Search', endpoint: '/blast/search' },
    step2_5: { name: 'BLAST Filter', endpoint: '/phylo/run-step/step2_5' },
    step3: { name: 'Length Filter', endpoint: '/phylo/run-step/step2_8' },
    step4: { name: 'Alignment', endpoint: '/alignment/align-multi' },
    step5: { name: 'ClipKIT', endpoint: '/phylo/clipkit-trim' },
    step6: { name: 'IQ-TREE', endpoint: '/phylo/iqtree-infer' }
};

/**
 * Initialize pipeline orchestration
 */
document.addEventListener('DOMContentLoaded', function() {
    initializePipeline();
    setupEventListeners();
    addTogglesAndButtons();
});

/**
 * Initialize pipeline components
 */
function initializePipeline() {
    // Add status badges to each step
    document.querySelectorAll('.pipeline-step').forEach(step => {
        const stepId = step.dataset.step;
        if (!stepId) return;
        
        const stepHeader = step.querySelector('h4');
        if (stepHeader) {
            const badge = document.createElement('span');
            badge.className = 'badge bg-secondary ms-2 step-status';
            badge.id = `status-${stepId}`;
            badge.textContent = 'Ready';
            stepHeader.appendChild(badge);
        }
        
        // Add toggle for using previous output
        addContinueWithPreviousToggle(step);
    });
    
    // Add full pipeline button
    addFullPipelineButton();
}

/**
 * Add toggle for "Continue with previous output"
 */
function addContinueWithPreviousToggle(step) {
    const stepId = step.dataset.step;
    if (!stepId || stepId === 'step0') return;
    
    const inputPathField = step.querySelector('input[type="text"][id*="Path"], input[type="text"][id*="path"]');
    if (!inputPathField) return;
    
    // Check if toggle already exists
    const existingToggle = document.getElementById(`usePrevOutput-${stepId}`);
    if (existingToggle) return;
    
    const toggleContainer = document.createElement('div');
    toggleContainer.className = 'form-check mb-2';
    toggleContainer.innerHTML = `
        <input class="form-check-input" type="checkbox" id="usePrevOutput-${stepId}">
        <label class="form-check-label" for="usePrevOutput-${stepId}">
            Use previous output
        </label>
    `;
    
    inputPathField.parentNode.insertBefore(toggleContainer, inputPathField);
    
    // Add event listener
    const toggle = toggleContainer.querySelector('input');
    toggle.addEventListener('change', function() {
        if (this.checked) {
            const prevStepId = getPreviousStepId(stepId);
            if (prevStepId && pipelineState[prevStepId].output) {
                inputPathField.value = pipelineState[prevStepId].output;
                inputPathField.disabled = true;
            } else {
                showAlert('warning', 'No previous output available');
                this.checked = false;
            }
        } else {
            inputPathField.disabled = false;
        }
    });
}

/**
 * Add full pipeline run button
 */
function addFullPipelineButton() {
    const container = document.querySelector('.container');
    if (!container) return;
    
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-primary mt-4';
    alertDiv.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div>
                <i class="bi bi-play-circle"></i>
                <strong>Run Full Pipeline:</strong> Execute all steps sequentially from Step 0 to Step 6
            </div>
            <button class="btn btn-primary" id="runFullPipelineBtn">
                <i class="bi bi-lightning"></i> Run Full Pipeline
            </button>
        </div>
    `;
    
    container.appendChild(alertDiv);
    
    document.getElementById('runFullPipelineBtn').addEventListener('click', runFullPipeline);
}

/**
 * Setup event listeners for all step forms
 */
function setupEventListeners() {
    Object.keys(stepConfig).forEach(stepId => {
        const stepElement = document.getElementById(stepId);
        if (!stepElement) return;
        
        const form = stepElement.querySelector('form');
        if (form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                runStep(stepId);
            });
        }
    });
}

/**
 * Run a single pipeline step
 */
async function runStep(stepId) {
    if (pipelineState[stepId].running) {
        showAlert('info', 'Step already running...');
        return;
    }
    
    const config = stepConfig[stepId];
    if (!config) return;
    
    const stepElement = document.getElementById(stepId);
    const form = stepElement.querySelector('form');
    
    // Update UI to running state
    updateStepStatus(stepId, 'running');
    
    try {
        // Prepare form data
        const formData = prepareStepFormData(stepId, form);
        if (!formData) return;
        
        // Make API call
        const response = await fetch(config.endpoint, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Update state with output path
            const outputPath = extractOutputPath(result, stepId);
            pipelineState[stepId].output = outputPath;
            pipelineState[stepId].completed = true;
            
            // Update UI with results
            displayStepResults(stepId, result);
            updateStepStatus(stepId, 'completed');
            
            // Auto-populate next step input
            autoPopulateNextStep(stepId);
            
            showAlert('success', `${config.name} completed successfully`);
        } else {
            updateStepStatus(stepId, 'error');
            showAlert('danger', `${config.name} failed: ${result.error}`);
        }
    } catch (error) {
        updateStepStatus(stepId, 'error');
        showAlert('danger', `${config.name} error: ${error.message}`);
    } finally {
        pipelineState[stepId].running = false;
    }
}

/**
 * Prepare form data for API call
 */
function prepareStepFormData(stepId, form) {
    const formData = new FormData();
    const stepElement = document.getElementById(stepId);
    
    // Handle file upload or path input
    const fileInput = stepElement.querySelector('input[type="file"]');
    const pathInput = stepElement.querySelector('input[type="text"][id*="Path"], input[type="text"][id*="path"]');
    
    if (fileInput && fileInput.files && fileInput.files.length > 0) {
        formData.append('file', fileInput.files[0]);
    } else if (pathInput && pathInput.value.trim()) {
        formData.append('file_path', pathInput.value.trim());
    } else {
        // Try to use previous output
        const prevStepId = getPreviousStepId(stepId);
        if (prevStepId && pipelineState[prevStepId].output) {
            formData.append('file_path', pipelineState[prevStepId].output);
        } else {
            showAlert('warning', 'Please provide input file or path');
            return null;
        }
    }
    
    // Add step-specific parameters
    addStepSpecificParams(stepId, formData, stepElement);
    
    return formData;
}

/**
 * Add step-specific parameters to form data
 */
function addStepSpecificParams(stepId, formData, stepElement) {
    switch (stepId) {
        case 'step1':
            // HMM Search parameters
            const hmmProfiles = stepElement.querySelector('#hmmProfiles');
            if (hmmProfiles) {
                const profiles = Array.from(hmmProfiles.selectedOptions).map(opt => opt.value);
                profiles.forEach(p => formData.append('hmm_files[]', p + '.hmm'));
            }
            const hmmEvalue = stepElement.querySelector('#hmmEvalue');
            if (hmmEvalue) formData.append('evalue', hmmEvalue.value);
            const hmmCutGA = stepElement.querySelector('#hmmCutGA');
            if (hmmCutGA) formData.append('cut_ga', hmmCutGA.checked);
            break;
            
        case 'step2':
            // BLAST parameters
            const blastDbPath = stepElement.querySelector('#blastDbPath');
            if (blastDbPath) formData.append('database', blastDbPath.value);
            const blastEvalue = stepElement.querySelector('#blastEvalue');
            if (blastEvalue) formData.append('evalue', blastEvalue.value);
            const blastMaxTargets = stepElement.querySelector('#blastMaxTargets');
            if (blastMaxTargets) formData.append('max_hits', blastMaxTargets.value);
            const blastThreads = stepElement.querySelector('#blastThreads');
            if (blastThreads) formData.append('num_threads', blastThreads.value);
            break;
            
        case 'step2_5':
            // BLAST Filter parameters
            formData.append('step', 'step2_5');
            const goldListSelect = stepElement.querySelector('#goldListSelect');
            if (goldListSelect) formData.append('gold_list', goldListSelect.value);
            const blastPident = stepElement.querySelector('#blastPident');
            if (blastPident) formData.append('pident', blastPident.value);
            const blastQcovs = stepElement.querySelector('#blastQcovs');
            if (blastQcovs) formData.append('qcovs', blastQcovs.value);
            break;
            
        case 'step3':
            // Length Filter parameters
            const minLength = stepElement.querySelector('#minLength');
            if (minLength) formData.append('min_length', minLength.value);
            const maxLength = stepElement.querySelector('#maxLength');
            if (maxLength) formData.append('max_length', maxLength.value);
            break;
            
        case 'step4':
            // Alignment parameters
            const alignTool = stepElement.querySelector('#alignTool');
            if (alignTool) formData.append('tool', alignTool.value);
            const mafftAlgorithm = stepElement.querySelector('#mafftAlgorithm');
            if (mafftAlgorithm) formData.append('mafft_algorithm', mafftAlgorithm.value);
            formData.append('threads', 4);
            break;
            
        case 'step5':
            // ClipKIT parameters
            const clipkitMode = stepElement.querySelector('#clipkitMode');
            if (clipkitMode) formData.append('mode', clipkitMode.value);
            const clipkitGaps = stepElement.querySelector('#clipkitGaps');
            if (clipkitGaps) formData.append('gaps', clipkitGaps.value);
            break;
            
        case 'step6':
            // IQ-TREE parameters
            const iqtreeModel = stepElement.querySelector('#iqtreeModel');
            if (iqtreeModel) formData.append('model', iqtreeModel.value);
            const iqtreeBootstrap = stepElement.querySelector('#iqtreeBootstrap');
            if (iqtreeBootstrap) formData.append('bootstrap', iqtreeBootstrap.value);
            const iqtreeBootstrapType = stepElement.querySelector('#iqtreeBootstrapType');
            if (iqtreeBootstrapType) formData.append('bootstrap_type', iqtreeBootstrapType.value);
            const iqtreeAlrt = stepElement.querySelector('#iqtreeAlrt');
            if (iqtreeAlrt) formData.append('alrt', iqtreeAlrt.checked);
            const iqtreeBnni = stepElement.querySelector('#iqtreeBnni');
            if (iqtreeBnni) formData.append('bnni', iqtreeBnni.checked);
            break;
    }
}

/**
 * Extract output path from API response
 */
function extractOutputPath(result, stepId) {
    // Different endpoints return different structures
    if (result.output_file) return result.output_file;
    if (result.output) return result.output;
    if (result.output_files) {
        if (result.output_files.main) return result.output_files.main;
        if (result.output_files.fasta) return result.output_files.fasta;
        if (result.output_files.treefile) return result.output_files.treefile;
        if (result.output_files.hits) return result.output_files.hits;
        if (result.output_files.hits_fasta) return result.output_files.hits_fasta;
    }
    return null;
}

/**
 * Display step results in the UI
 */
function displayStepResults(stepId, result) {
    const resultDiv = document.getElementById(`result${stepId.replace('step', '')}`);
    if (!resultDiv) return;
    
    const resultsContainer = resultDiv.querySelector('div[id$="Results"]');
    if (!resultsContainer) return;
    
    let html = '';
    
    // Add summary stats
    if (result.stats) {
        html += createStatsTable(result.stats);
    }
    
    // Add command info
    if (result.command || result.commands) {
        html += createCommandBlock(result.command || result.commands);
    }
    
    // Add download link
    const outputPath = extractOutputPath(result, stepId);
    if (outputPath) {
        html += createDownloadLink(outputPath);
    }
    
    // Add copy path button
    if (outputPath) {
        html += createCopyPathButton(outputPath);
    }
    
    resultsContainer.innerHTML = html;
    resultDiv.classList.add('show');
}

/**
 * Create stats table HTML
 */
function createStatsTable(stats) {
    let html = '<div class="alert alert-info"><strong>Summary Statistics:</strong><table class="table table-sm mt-2">';
    
    Object.entries(stats).forEach(([key, value]) => {
        if (typeof value !== 'object') {
            html += `<tr><td>${key}:</td><td>${value}</td></tr>`;
        }
    });
    
    html += '</table></div>';
    return html;
}

/**
 * Create command block HTML
 */
function createCommandBlock(command) {
    const commandStr = Array.isArray(command) ? command.join('\n') : command;
    return `
        <div class="mb-3">
            <label class="form-label">Command executed:</label>
            <div class="input-group">
                <textarea class="form-control" rows="2" readonly>${commandStr}</textarea>
                <button class="btn btn-outline-secondary" onclick="copyToClipboard('${commandStr.replace(/'/g, "\\'")}')">
                    <i class="bi bi-clipboard"></i>
                </button>
            </div>
        </div>
    `;
}

/**
 * Create download link HTML
 */
function createDownloadLink(outputPath) {
    const downloadUrl = `/phylo/download?path=${encodeURIComponent(outputPath)}`;
    return `
        <div class="mt-2">
            <a href="${downloadUrl}" class="btn btn-success btn-sm">
                <i class="bi bi-download"></i> Download Result
            </a>
        </div>
    `;
}

/**
 * Create copy path button HTML
 */
function createCopyPathButton(outputPath) {
    return `
        <button class="btn btn-outline-secondary btn-sm mt-2" onclick="copyToClipboard('${outputPath}')">
            <i class="bi bi-clipboard"></i> Copy Path
        </button>
    `;
}

/**
 * Update step status badge
 */
function updateStepStatus(stepId, status) {
    const badge = document.getElementById(`status-${stepId}`);
    if (!badge) return;
    
    badge.className = 'badge ms-2 step-status';
    
    switch (status) {
        case 'running':
            badge.classList.add('bg-warning');
            badge.textContent = 'Running...';
            break;
        case 'completed':
            badge.classList.add('bg-success');
            badge.textContent = 'Completed';
            break;
        case 'error':
            badge.classList.add('bg-danger');
            badge.textContent = 'Error';
            break;
        default:
            badge.classList.add('bg-secondary');
            badge.textContent = 'Ready';
    }
    
    // Update step border color
    const stepElement = document.getElementById(stepId);
    if (stepElement) {
        stepElement.classList.remove('active', 'completed');
        if (status === 'completed') {
            stepElement.classList.add('completed');
        } else if (status === 'running') {
            stepElement.classList.add('active');
        }
    }
}

/**
 * Auto-populate next step input field
 */
function autoPopulateNextStep(stepId) {
    const nextStepId = getNextStepId(stepId);
    if (!nextStepId) return;
    
    const nextStepElement = document.getElementById(nextStepId);
    if (!nextStepElement) return;
    
    const outputPath = pipelineState[stepId].output;
    if (!outputPath) return;
    
    const pathInput = nextStepElement.querySelector('input[type="text"][id*="Path"], input[type="text"][id*="path"]');
    if (pathInput && !pathInput.value) {
        pathInput.value = outputPath;
    }
}

/**
 * Run full pipeline sequentially
 */
async function runFullPipeline() {
    const steps = ['step0', 'step1', 'step2', 'step2_5', 'step3', 'step4', 'step5', 'step6'];
    
    showAlert('info', 'Starting full pipeline execution...');
    
    for (const stepId of steps) {
        await runStep(stepId);
        
        // Wait a bit between steps
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Stop if step failed
        if (!pipelineState[stepId].completed) {
            showAlert('warning', `Full pipeline stopped at ${stepConfig[stepId].name}`);
            return;
        }
    }
    
    showAlert('success', 'Full pipeline completed successfully!');
}

/**
 * Get previous step ID
 */
function getPreviousStepId(stepId) {
    const stepOrder = ['step0', 'step1', 'step2', 'step2_5', 'step3', 'step4', 'step5', 'step6', 'step7'];
    const index = stepOrder.indexOf(stepId);
    return index > 0 ? stepOrder[index - 1] : null;
}

/**
 * Get next step ID
 */
function getNextStepId(stepId) {
    const stepOrder = ['step0', 'step1', 'step2', 'step2_5', 'step3', 'step4', 'step5', 'step6', 'step7'];
    const index = stepOrder.indexOf(stepId);
    return index < stepOrder.length - 1 ? stepOrder[index + 1] : null;
}

/**
 * Add toggles and buttons to existing steps
 */
function addTogglesAndButtons() {
    // This is handled in initializePipeline()
}

/**
 * Copy text to clipboard (helper function)
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showAlert('success', 'Copied to clipboard!');
    } catch (err) {
        showAlert('warning', 'Failed to copy to clipboard');
    }
}

/**
 * Show alert message (helper function)
 */
function showAlert(type, message) {
    const alertContainer = document.querySelector('.container');
    if (!alertContainer) return;
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show mt-2`;
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    alertContainer.appendChild(alertDiv);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.classList.remove('show');
            setTimeout(() => alertDiv.remove(), 150);
        }
    }, 5000);
}
