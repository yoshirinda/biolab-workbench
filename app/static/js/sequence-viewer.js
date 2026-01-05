/**
 * Sequence Viewer - 序列查看器
 * 集成 OVE 编辑器
 */
class SequenceViewer {
    constructor() {
        this.container = null;
        this.sequenceManager = window.sequenceManager;
        this.currentSequence = null;
        this.currentProject = null;
        this.onSequenceUpdate = null;
        this.oveEditor = null;
    }

    /**
     * 初始化序列查看器
     */
    init(containerId, onSequenceUpdate) {
        this.container = document.getElementById(containerId);
        this.onSequenceUpdate = onSequenceUpdate;
        
        if (!this.container) {
            console.error('Sequence viewer container not found');
            return;
        }

        // 创建查看器界面
        this.createViewerInterface();
        
        // 绑定事件
        this.bindEvents();
    }

    /**
     * 创建查看器界面
     */
    createViewerInterface() {
        this.container.innerHTML = `
            <div class="sequence-viewer">
                <div class="viewer-header">
                    <div class="viewer-title">
                        <h3 id="sequenceTitle">选择一个序列</h3>
                        <div class="viewer-actions">
                            <button class="btn btn-sm btn-outline-primary" onclick="sequenceViewer.editSequence()">
                                <i class="bi bi-pencil"></i> 编辑
                            </button>
                            <button class="btn btn-sm btn-outline-secondary" onclick="sequenceViewer.copySequence()">
                                <i class="bi bi-files"></i> 复制
                            </button>
                            <button class="btn btn-sm btn-outline-secondary" onclick="sequenceViewer.exportSequence()">
                                <i class="bi bi-download"></i> 导出
                            </button>
                        </div>
                    </div>
                    <div class="viewer-stats" id="sequenceStats">
                        <span class="stat-item">长度: <span id="sequenceLength">-</span> bp</span>
                        <span class="stat-item">类型: <span id="sequenceType">-</span></span>
                        <span class="stat-item">GC含量: <span id="sequenceGC">-</span>%</span>
                    </div>
                </div>
                <div class="viewer-content" id="sequenceContent">
                    <div class="no-sequence-message">
                        <i class="bi bi-arrow-up-circle"></i>
                        <p>请从左侧项目树中选择一个序列查看</p>
                        <p>或使用上传功能导入新序列</p>
                    </div>
                </div>
                <div class="viewer-tools">
                    <div class="tool-section">
                        <h4>序列工具</h4>
                        <div class="tool-buttons">
                            <button class="btn btn-outline-primary" onclick="sequenceViewer.translateSequence()">
                                <i class="bi bi-arrow-repeat"></i> 翻译
                            </button>
                            <button class="btn btn-outline-primary" onclick="sequenceViewer.reverseComplement()">
                                <i class="bi bi-arrow-left-right"></i> 反向互补
                            </button>
                            <button class="btn btn-outline-primary" onclick="sequenceViewer.findORFs()">
                                <i class="bi bi-search"></i> 查找ORF
                            </button>
                            <button class="btn btn-outline-primary" onclick="sequenceViewer.getStats()">
                                <i class="bi bi-bar-chart"></i> 统计信息
                            </button>
                        </div>
                    </div>
                    <div class="tool-section">
                        <h4>特征注释</h4>
                        <div class="feature-tools">
                            <button class="btn btn-outline-primary" onclick="sequenceViewer.showFeatureEditor()">
                                <i class="bi bi-bookmark-plus"></i> 添加特征
                            </button>
                            <button class="btn btn-outline-secondary" onclick="sequenceViewer.exportWithFeatures()">
                                <i class="bi bi-download"></i> 导出带特征
                            </button>
                        </div>
                    </div>
                </div>
                <div class="ove-editor" id="oveEditor">
                    <!-- OVE 编辑器将在这里渲染 -->
                </div>
            </div>
        `;
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        // 这里可以添加更多事件监听器
        console.log('Sequence viewer initialized');
    }

    /**
     * 加载序列
     */
    async loadSequence(projectPath, sequenceId) {
        try {
            // 获取项目信息
            const project = await this.sequenceManager.getProject(projectPath);
            if (!project.success) {
                throw new Error(project.error || 'Failed to get project');
            }

            // 查找序列
            const sequence = project.sequences.find(s => s.id === sequenceId);
            if (!sequence) {
                throw new Error('Sequence not found');
            }

            this.currentSequence = sequence;
            this.currentProject = project;
            
            // 更新界面
            this.updateSequenceDisplay();
            
            // 临时禁用 OVE 初始化，避免加载错误导致页面异常
            // this.initOVEEditor(sequence);

            // 显示友好提示，表明图形编辑器开发中
            this.showOVEPlaceholder();
            
            // 通知外部
            if (this.onSequenceUpdate) {
                this.onSequenceUpdate(sequence, project);
            }
            
        } catch (error) {
            console.error('Load sequence error:', error);
            this.showError('加载序列失败: ' + error.message);
        }
    }

    /**
     * 更新序列显示
     */
    updateSequenceDisplay() {
        if (!this.currentSequence) {
            this.showEmptyState();
            return;
        }

        // 更新标题
        document.getElementById('sequenceTitle').textContent = this.currentSequence.id;
        
        // 更新统计信息
        document.getElementById('sequenceLength').textContent = this.currentSequence.length || 0;
        document.getElementById('sequenceType').textContent = this.currentSequence.type || 'DNA';
        document.getElementById('sequenceGC').textContent = this.calculateGC(this.currentSequence.sequence || '');
        
        // 显示序列内容
        this.displaySequenceContent();
    }

    /**
     * 显示空状态
     */
    showEmptyState() {
        document.getElementById('sequenceTitle').textContent = '选择一个序列';
        document.getElementById('sequenceLength').textContent = '-';
        document.getElementById('sequenceType').textContent = '-';
        document.getElementById('sequenceGC').textContent = '-';
        
        document.getElementById('sequenceContent').innerHTML = `
            <div class="no-sequence-message">
                <i class="bi bi-arrow-up-circle"></i>
                <p>请从左侧项目树中选择一个序列查看</p>
                <p>或使用上传功能导入新序列</p>
            </div>
        `;
    }

    /**
     * 显示序列内容
     */
    displaySequenceContent() {
        const contentDiv = document.getElementById('sequenceContent');
        if (!this.currentSequence) {
            return;
        }

        // 显示序列文本
        const sequenceText = this.formatSequenceText(this.currentSequence.sequence);
        contentDiv.innerHTML = `
            <div class="sequence-text-container">
                <div class="sequence-header">
                    <h4>序列文本</h4>
                    <button class="btn btn-sm btn-outline-secondary" onclick="sequenceViewer.copySequenceText()">
                        <i class="bi bi-files"></i> 复制序列
                    </button>
                </div>
                <div class="sequence-text">${sequenceText}</div>
            </div>
        `;
    }

    /**
     * 格式化序列文本
     */
    formatSequenceText(sequence) {
        if (!sequence) return '';
        
        // 每60个字符换行
        const lines = [];
        for (let i = 0; i < sequence.length; i += 60) {
            lines.push(sequence.substring(i, i + 60));
        }
        return lines.join('\n');
    }

    /**
     * 初始化 OVE 编辑器
     */
    initOVEEditor(sequence) {
        const oveContainer = document.getElementById('oveEditor');
        if (!oveContainer) {
            console.error('OVE editor container not found');
            return;
        }

        // 清空容器
        oveContainer.innerHTML = '';

        // 创建 OVE 编辑器
        const oveScript = document.createElement('script');
        oveScript.type = 'module';
        oveScript.src = '/static/js/ove-editor.js'; // 我们将创建这个文件
        
        // 设置序列数据
        const sequenceData = {
            name: sequence.id,
            sequence: sequence.sequence,
            circular: sequence.circular || false,
            features: (sequence.features || []).map(f => ({
                name: f.name,
                start: f.start - 1, // OVE 使用 0-based
                end: f.end - 1,
                type: f.type || 'misc_feature',
                strand: f.direction || 1,
                color: f.color || '#4CAF50'
            }))
        };

        // 初始化 OVE
        oveScript.onload = () => {
            if (window.oveEditor) {
                try {
                    window.oveEditor.loadSequence(sequenceData);
                    console.log('OVE editor initialized with sequence:', sequence.id);
                } catch (error) {
                    console.error('OVE editor initialization error:', error);
                }
            }
        };

        // 添加脚本到页面
        oveContainer.appendChild(oveScript);
    }

    /**
     * 编辑序列
     */
    editSequence() {
        if (!this.currentSequence) {
            this.showError('没有选择序列');
            return;
        }

        // 这里可以打开序列编辑对话框
        console.log('Edit sequence:', this.currentSequence.id);
        // TODO: 实现序列编辑功能
    }

    /**
     * 复制序列
     */
    async copySequence() {
        if (!this.currentSequence) {
            this.showError('没有选择序列');
            return;
        }

        try {
            const text = `>${this.currentSequence.id}\n${this.currentSequence.sequence}`;
            await navigator.clipboard.writeText(text);
            this.showSuccess('序列已复制到剪贴板');
        } catch (error) {
            this.showError('复制失败: ' + error.message);
        }
    }

    /**
     * 复制序列文本
     */
    copySequenceText() {
        const sequenceText = this.formatSequenceText(this.currentSequence.sequence);
        
        try {
            await navigator.clipboard.writeText(sequenceText);
            this.showSuccess('序列文本已复制到剪贴板');
        } catch (error) {
            this.showError('复制失败: ' + error.message);
        }
    }

    /**
     * 导出序列
     */
    async exportSequence() {
        if (!this.currentSequence) {
            this.showError('没有选择序列');
            return;
        }

        try {
            const fastaText = `>${this.currentSequence.id}\n${this.currentSequence.sequence}`;
            const blob = new Blob([fastaText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = this.currentSequence.id + '.fasta';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this.showSuccess('序列已导出为 FASTA 格式');
        } catch (error) {
            this.showError('导出失败: ' + error.message);
        }
    }

    /**
     * 导出带特征的序列
     */
    async exportWithFeatures() {
        if (!this.currentSequence) {
            this.showError('没有选择序列');
            return;
        }

        try {
            // 构造 GenBank 格式
            let genbankText = `LOCUS       ${this.currentSequence.id}\n`;
            genbankText += `DEFINITION  ${this.currentSequence.description || ''}\n`;
            genbankText += `ACCESSION   \n`;
            genbankText += `VERSION     \n`;
            genbankText += `SOURCE      \n`;
            genbankText += `  ORGANISM  \n`;
            genbankText += `FEATURES             Location/Qualifiers\n`;
            
            if (this.currentSequence.features) {
                this.currentSequence.features.forEach(feature => {
                    genbankText += `     ${feature.type}    ${feature.start}..${feature.end}\n`;
                    genbankText += `                     /label="${feature.name}"\n`;
                    if (feature.color) {
                        genbankText += `                     /color="${feature.color}"\n`;
                    }
                });
            }
            
            genbankText += `ORIGIN\n`;
            genbankText += this.formatSequenceText(this.currentSequence.sequence);
            genbankText += '//\n';

            const blob = new Blob([genbankText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = this.currentSequence.id + '.gb';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this.showSuccess('序列已导出为 GenBank 格式');
        } catch (error) {
            this.showError('导出失败: ' + error.message);
        }
    }

    /**
     * 翻译序列
     */
    async translateSequence() {
        if (!this.currentSequence || this.currentSequence.type !== 'nucleotide') {
            this.showError('请选择一个核苷酸序列');
            return;
        }

        try {
            const result = await this.sequenceManager.translateSequence(this.currentSequence.sequence, 1);
            if (result.success) {
                this.showTranslationDialog(result.protein, result.frame);
            } else {
                this.showError('翻译失败: ' + result.error);
            }
        } catch (error) {
            this.showError('翻译失败: ' + error.message);
        }
    }

    /**
     * 显示翻译对话框
     */
    showTranslationDialog(protein, frame) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>翻译结果</h3>
                <div class="translation-info">
                    <div class="info-item">
                        <strong>阅读框:</strong> ${frame}
                    </div>
                    <div class="info-item">
                        <strong>氨基酸序列:</strong>
                    </div>
                    <div class="protein-sequence">${protein}</div>
                    <div class="info-item">
                        <strong>长度:</strong> ${protein.length} aa
                    </div>
                </div>
                <div class="modal-actions">
                    <button class="btn btn-secondary" onclick="this.closeModal()">关闭</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        
        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        });
    }

    /**
     * 反向互补
     */
    async reverseComplement() {
        if (!this.currentSequence || this.currentSequence.type !== 'nucleotide') {
            this.showError('请选择一个核苷酸序列');
            return;
        }

        try {
            const result = await this.sequenceManager.reverseComplement(this.currentSequence.sequence);
            if (result.success) {
                this.showReverseComplementDialog(result.reverse_complement);
            } else {
                this.showError('反向互补失败: ' + result.error);
            }
        } catch (error) {
            this.showError('反向互补失败: ' + error.message);
        }
    }

    /**
     * 显示反向互补对话框
     */
    showReverseComplementDialog(rcSequence) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>反向互补结果</h3>
                <div class="rc-info">
                    <div class="info-item">
                        <strong>反向互补序列:</strong>
                    </div>
                    <div class="rc-sequence">${rcSequence}</div>
                    <div class="info-item">
                        <strong>长度:</strong> ${rcSequence.length} bp
                    </div>
                </div>
                <div class="modal-actions">
                    <button class="btn btn-secondary" onclick="this.closeModal()">关闭</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        
        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        });
    }

    /**
     * 查找ORF
     */
    async findORFs() {
        if (!this.currentSequence || this.currentSequence.type !== 'nucleotide') {
            this.showError('请选择一个核苷酸序列');
            return;
        }

        try {
            const result = await this.sequenceManager.findORFs(this.currentSequence.sequence, 100);
            if (result.success) {
                this.showORFsDialog(result.orfs);
            } else {
                this.showError('ORF查找失败: ' + result.error);
            }
        } catch (error) {
            this.showError('ORF查找失败: ' + error.message);
        }
    }

    /**
     * 显示ORF对话框
     */
    showORFsDialog(orfs) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>开放阅读框 (ORFs)</h3>
                <div class="orfs-info">
                    <div class="info-item">
                        <strong>找到 ${orfs.length} 个ORF</strong>
                    </div>
                    <div class="orfs-list">
                        ${orfs.map((orf, index) => `
                            <div class="orf-item">
                                <strong>ORF ${index + 1}:</strong>
                                <div>位置: ${orf.start}..${orf.end}</div>
                                <div>长度: ${orf.length} bp</div>
                                <div>序列: ${orf.sequence}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="modal-actions">
                    <button class="btn btn-secondary" onclick="this.closeModal()">关闭</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        
        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        });
    }

    /**
     * 获取统计信息
     */
    async getStats() {
        if (!this.currentSequence) {
            this.showError('请选择一个序列');
            return;
        }

        try {
            const result = await this.sequenceManager.getSequenceStats(this.currentSequence.sequence);
            if (result.success) {
                this.showStatsDialog(result.stats);
            } else {
                this.showError('获取统计失败: ' + result.error);
            }
        } catch (error) {
            this.showError('获取统计失败: ' + error.message);
        }
    }

    /**
     * 显示统计对话框
     */
    showStatsDialog(stats) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>序列统计信息</h3>
                <div class="stats-info">
                    <div class="stat-item">
                        <strong>长度:</strong> ${stats.length} bp
                    </div>
                    <div class="stat-item">
                        <strong>A含量:</strong> ${stats.a_count} (${stats.a_percent.toFixed(1)}%)
                    </div>
                    <div class="stat-item">
                        <strong>T含量:</strong> ${stats.t_count} (${stats.t_percent.toFixed(1)}%)
                    </div>
                    <div class="stat-item">
                        <strong>G含量:</strong> ${stats.g_count} (${stats.g_percent.toFixed(1)}%)
                    </div>
                    <div class="stat-item">
                        <strong>C含量:</strong> ${stats.c_count} (${stats.c_percent.toFixed(1)}%)
                    </div>
                    <div class="stat-item">
                        <strong>GC含量:</strong> ${stats.gc_percent.toFixed(1)}%
                    </div>
                    <div class="stat-item">
                        <strong>AT含量:</strong> ${stats.at_percent.toFixed(1)}%
                    </div>
                </div>
                <div class="modal-actions">
                    <button class="btn btn-secondary" onclick="this.closeModal()">关闭</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        
        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        };
    }

    /**
     * 显示特征编辑器
     */
    showFeatureEditor() {
        if (!this.currentSequence) {
            this.showError('请选择一个序列');
            return;
        }

        // 这里可以打开特征编辑对话框
        console.log('Show feature editor for sequence:', this.currentSequence.id);
        // TODO: 实现特征编辑功能
    }

    /**
     * 计算GC含量
     */
    calculateGC(sequence) {
        if (!sequence) return 0;
        
        const gc = (sequence.match(/[GCgc]/gi) || []).length;
        const total = sequence.length;
        return total > 0 ? ((gc / total) * 100).toFixed(1) : 0;
    }

    /**
     * 关闭模态框
     */
    closeModal() {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (modal.parentNode) {
                modal.parentNode.removeChild(modal);
            }
        });
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
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = message;
        
        // 添加到页面
        this.container.appendChild(messageDiv);
        
        // 3秒后自动移除
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        }, 3000);
    }
}

// 全局实例
window.sequenceViewer = new SequenceViewer();