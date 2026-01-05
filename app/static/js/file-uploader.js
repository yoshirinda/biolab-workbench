/**
 * File Uploader - 真实的文件上传功能
 * 支持拖拽上传和文件选择上传
 */
class FileUploader {
    constructor() {
        this.dropZone = null;
        this.fileInput = null;
        this.uploadButton = null;
        this.progressBar = null;
        this.statusText = null;
        this.sequenceManager = window.sequenceManager;
        this.onUploadComplete = null;
        this.onUploadProgress = null;
    }

    /**
     * 初始化上传器
     */
    init(containerId, onUploadComplete, onUploadProgress) {
        this.dropZone = document.getElementById(containerId);
        this.onUploadComplete = onUploadComplete;
        this.onUploadProgress = onUploadProgress;
        
        if (!this.dropZone) {
            console.error('Drop zone container not found');
            return;
        }

        // 创建上传界面
        this.createUploadInterface();
        
        // 绑定事件
        this.bindEvents();
    }

    /**
     * 创建上传界面
     */
    createUploadInterface() {
        this.dropZone.innerHTML = `
            <div class="upload-area">
                <div class="upload-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                        <path d="M14 2v6h20v12H14z"/>
                        <path d="M20 12h4v4h-4v-4H20z"/>
                        <circle cx="12" cy="12" r="2"/>
                    </svg>
                </div>
                <div class="upload-text">
                    <h4>拖拽文件到此处</h4>
                    <p>或点击选择文件</p>
                    <p class="upload-hint">支持 .gb, .fasta, .fa, .fna, .dna 等格式</p>
                </div>
                <input type="file" id="fileInput" class="file-input" multiple accept=".gb,.genbank,.fasta,.fa,.faa,.fna,.dna" />
                <button class="btn btn-primary" id="uploadButton">
                    <i class="bi bi-upload"></i> 选择文件上传
                </button>
            </div>
            <div class="upload-progress" id="uploadProgress" style="display: none;">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div class="progress-text" id="progressText">上传中...</div>
            </div>
        `;

        // 获取元素引用
        this.fileInput = this.dropZone.querySelector('#fileInput');
        this.uploadButton = this.dropZone.querySelector('#uploadButton');
        this.progressBar = this.dropZone.querySelector('#progressFill');
        this.statusText = this.dropZone.querySelector('#progressText');
        this.uploadProgress = this.dropZone.querySelector('#uploadProgress');
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        // 文件选择
        this.fileInput.addEventListener('change', (e) => {
            this.handleFiles(e.target.files);
        });

        // 按钮点击
        this.uploadButton.addEventListener('click', () => {
            this.fileInput.click();
        });

        // 拖拽事件
        this.dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.dropZone.classList.add('dragover');
        });

        this.dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            this.dropZone.classList.remove('dragover');
        });

        this.dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.dropZone.classList.remove('dragover');
            this.handleFiles(e.dataTransfer.files);
        });
    }

    /**
     * 处理文件
     */
    async handleFiles(files) {
        if (!files || files.length === 0) {
            this.showError('请选择文件');
            return;
        }

        // 显示进度条
        this.showProgress();

        try {
            // 处理每个文件
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                await this.uploadFile(file, i + 1, files.length);
            }
            
            this.hideProgress();
            this.showSuccess(`成功上传 ${files.length} 个文件`);
            
            // 通知外部
            if (this.onUploadComplete) {
                this.onUploadComplete(files);
            }
            
        } catch (error) {
            this.hideProgress();
            this.showError('上传失败: ' + error.message);
        }
    }

    /**
     * 上传单个文件
     */
    async uploadFile(file, current, total) {
        const formData = new FormData();
        formData.append('file', file);

        // 使用 XMLHttpRequest 以便跟踪上传进度
        const xhr = new XMLHttpRequest();
        
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                this.updateProgress(percentComplete, current, total);
            }
        });

        xhr.addEventListener('load', () => {
            console.log(`File ${file.name} uploaded successfully`);
        });

        xhr.addEventListener('error', (e) => {
            console.error(`File ${file.name} upload failed:`, e);
        });

        xhr.open('POST', '/sequence/import');
        xhr.send(formData);
    }

    /**
     * 显示进度条
     */
    showProgress() {
        this.uploadProgress.style.display = 'block';
        this.progressBar.style.width = '0%';
        this.statusText.textContent = '准备上传...';
    }

    /**
     * 更新进度条
     */
    updateProgress(percent, current, total) {
        this.progressBar.style.width = percent + '%';
        this.statusText.textContent = `上传中: ${current}/${total} (${Math.round(percent)}%)`;
        
        // 通知进度
        if (this.onUploadProgress) {
            this.onUploadProgress(percent, current, total);
        }
    }

    /**
     * 隐藏进度条
     */
    hideProgress() {
        this.uploadProgress.style.display = 'none';
    }

    /**
     * 显示成功消息
     */
    showSuccess(message) {
        this.showMessage(message, 'success');
    }

    /**
     * 显示错误消息
     */
    showError(message) {
        this.showMessage(message, 'error');
    }

    /**
     * 显示消息
     */
    showMessage(message, type = 'info') {
        // 创建消息元素
        const messageDiv = document.createElement('div');
        messageDiv.className = `upload-message ${type}`;
        messageDiv.textContent = message;
        
        // 添加到页面
        this.dropZone.appendChild(messageDiv);
        
        // 3秒后自动移除
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        }, 3000);
    }

    /**
     * 重置上传器
     */
    reset() {
        if (this.fileInput) {
            this.fileInput.value = '';
        }
        this.hideProgress();
    }
}

// 全局实例
window.fileUploader = new FileUploader();