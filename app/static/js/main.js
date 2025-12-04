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

/**
 * Display executed command in a copyable block
 * @param {string} containerId - ID of the container element
 * @param {string} command - Command string to display
 */
function displayCommand(containerId, command) {
    if (!command) return;

    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
        <div class="command-display">
            <div class="command-header">
                <span class="command-label"><i class="bi bi-terminal"></i> Executed Command</span>
                <button class="copy-btn" onclick="copyCommand(this, '${encodeURIComponent(command)}')">
                    <i class="bi bi-clipboard"></i> Copy
                </button>
            </div>
            <pre>${escapeHtml(command)}</pre>
        </div>
    `;
    container.classList.remove('d-none');
}

/**
 * Copy command to clipboard
 * @param {HTMLElement} btn - The button element
 * @param {string} encodedCommand - URL-encoded command string
 */
function copyCommand(btn, encodedCommand) {
    const command = decodeURIComponent(encodedCommand);
    navigator.clipboard.writeText(command).then(() => {
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check"></i> Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.innerHTML = originalHtml;
            btn.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        showAlert('danger', 'Failed to copy command to clipboard');
    });
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Create an SSE connection for streaming console output
 * @param {string} url - SSE endpoint URL
 * @param {string} consoleId - ID of the console output container
 * @param {Function} onComplete - Callback when stream completes
 */
function createSSEConnection(url, consoleId, onComplete) {
    const consoleEl = document.getElementById(consoleId);
    if (!consoleEl) return null;

    const eventSource = new EventSource(url);

    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);

        if (data.done) {
            eventSource.close();
            if (onComplete) {
                onComplete(data.returncode === 0);
            }
            return;
        }

        if (data.line) {
            const line = document.createElement('div');
            line.className = 'log-line';

            // Colorize based on content
            if (data.line.toLowerCase().includes('error')) {
                line.classList.add('error');
            } else if (data.line.toLowerCase().includes('warning')) {
                line.classList.add('warning');
            }

            line.textContent = data.line;
            consoleEl.appendChild(line);

            // Auto-scroll to bottom
            consoleEl.scrollTop = consoleEl.scrollHeight;
        }
    };

    eventSource.onerror = function(error) {
        console.error('SSE error:', error);
        eventSource.close();
        if (onComplete) {
            onComplete(false);
        }
    };

    return eventSource;
}

/**
 * Clear console output
 * @param {string} consoleId - ID of the console output container
 */
function clearConsole(consoleId) {
    const consoleEl = document.getElementById(consoleId);
    if (consoleEl) {
        consoleEl.innerHTML = '';
    }
}

/**
 * Append message to console
 * @param {string} consoleId - ID of the console output container
 * @param {string} message - Message to append
 * @param {string} type - Message type (info, warning, error)
 */
function appendToConsole(consoleId, message, type = 'info') {
    const consoleEl = document.getElementById(consoleId);
    if (!consoleEl) return;

    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.textContent = message;
    consoleEl.appendChild(line);
    consoleEl.scrollTop = consoleEl.scrollHeight;
}
