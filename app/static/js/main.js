// BioLab Workbench Main JavaScript

/**
 * Show a Bootstrap alert
 * @param {string} type - Alert type (success, danger, warning, info)
 * @param {string} message - Alert message
 * @param {number} duration - Auto-dismiss duration in ms (0 for no auto-dismiss)
 */
function showAlert(type, message, duration = 5000) {
    const alertContainer = document.querySelector('main.container');
    if (!alertContainer) return;

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    alertContainer.insertBefore(alertDiv, alertContainer.firstChild);

    if (duration > 0) {
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.classList.remove('show');
                setTimeout(() => alertDiv.remove(), 150);
            }
        }, duration);
    }
}

/**
 * Format file size
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showAlert('success', 'Copied to clipboard', 2000);
    } catch (err) {
        showAlert('danger', 'Failed to copy to clipboard');
    }
}

/**
 * Download text as file
 * @param {string} content - File content
 * @param {string} filename - File name
 * @param {string} mimeType - MIME type
 */
function downloadTextFile(content, filename, mimeType = 'text/plain') {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * Parse FASTA format
 * @param {string} text - FASTA text
 * @returns {Array} Array of {id, description, sequence}
 */
function parseFasta(text) {
    const sequences = [];
    let currentId = null;
    let currentDesc = '';
    let currentSeq = [];

    const lines = text.trim().split('\n');
    for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine.startsWith('>')) {
            if (currentId !== null) {
                sequences.push({
                    id: currentId,
                    description: currentDesc,
                    sequence: currentSeq.join('')
                });
            }
            const headerParts = trimmedLine.substring(1).split(/\s+/);
            currentId = headerParts[0];
            currentDesc = headerParts.slice(1).join(' ');
            currentSeq = [];
        } else if (trimmedLine && currentId !== null) {
            currentSeq.push(trimmedLine);
        }
    }

    if (currentId !== null) {
        sequences.push({
            id: currentId,
            description: currentDesc,
            sequence: currentSeq.join('')
        });
    }

    return sequences;
}

/**
 * Detect sequence type
 * @param {string} sequence - Sequence string
 * @returns {string} 'nucleotide' or 'protein'
 */
function detectSequenceType(sequence) {
    const cleanSeq = sequence.toUpperCase().replace(/[^A-Z]/g, '');
    const aaOnlyChars = new Set(['E', 'F', 'I', 'L', 'P', 'Q']);
    for (const char of cleanSeq) {
        if (aaOnlyChars.has(char)) {
            return 'protein';
        }
    }
    return 'nucleotide';
}

/**
 * Debounce function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function(tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Handle navbar active state
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
});
