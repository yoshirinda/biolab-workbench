/**
 * OVE Editor - Open Vector Editor 集成
 * 提供专业的序列编辑功能
 */
class OVEEditor {
    constructor() {
        this.container = null;
        this.sequenceManager = window.sequenceManager;
        this.currentSequence = null;
        this.currentProject = null;
        this.onSequenceUpdate = null;
        this.editorInstance = null;
    }

    /**
     * 初始化 OVE 编辑器
     */
    init(containerId, onSequenceUpdate) {
        this.container = document.getElementById(containerId);
        this.onSequenceUpdate = onSequenceUpdate;
        
        if (!this.container) {
            console.error('OVE editor container not found');
            return;
        }

        // 创建编辑器界面
        this.createEditorInterface();
        
        // 绑定事件
        this.bindEvents();
    }

    /**
     * 创建编辑器界面
     */
    createEditorInterface() {
        this.container.innerHTML = `
            <div class="ove-editor">
                <div class="editor-header">
                    <h3>序列编辑器</h3>
                    <div class="editor-actions">
                        <button class="btn btn-sm btn-outline-primary" onclick="oveEditor.toggleView()">
                            <i class="bi bi-eye"></i> 切换视图
                        </button>
                        <button class="btn btn-sm btn-outline-primary" onclick="oveEditor.showTools()">
                            <i class="bi bi-gear"></i> 工具
                        </button>
                        <button class="btn btn-sm btn-outline-primary" onclick="oveEditor.saveSequence()">
                            <i class="bi bi-save"></i> 保存
                        </button>
                        <button class="btn btn-sm btn-outline-secondary" onclick="oveEditor.exportSequence()">
                            <i class="bi bi-download"></i> 导出
                        </button>
                    </div>
                </div>
                <div class="editor-content" id="oveEditorContainer">
                    <!-- OVE 编辑器将在这里渲染 -->
                    <div class="editor-loading" id="editorLoading">
                        <div class="loading-spinner"></div>
                        <p>正在加载编辑器...</p>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        // 这里可以添加更多事件监听器
        console.log('OVE editor initialized');
    }

    /**
     * 加载序列到编辑器
     */
    async loadSequence(projectPath, sequenceId) {
        try {
            // 显示加载状态
            this.showLoading(true);
            
            // 获取序列信息
            const project = await this.sequenceManager.getProject(projectPath);
            const sequence = project.sequences.find(s => s.id === sequenceId);
            
            if (!sequence) {
                throw new Error('Sequence not found');
            }

            this.currentSequence = sequence;
            this.currentProject = project;
            
            // 初始化 OVE 编辑器
            await this.initOVEEditor(sequence);
            
            // 隐藏加载状态
            this.showLoading(false);
            
            // 通知外部
            if (this.onSequenceUpdate) {
                this.onSequenceUpdate(sequence, project);
            }
            
        } catch (error) {
            this.showLoading(false);
            this.showError('加载序列失败: ' + error.message);
        }
    }

    /**
     * 初始化 OVE 编辑器
     */
    async initOVEEditor(sequence) {
        try {
            // 检查 OVE 是否已加载
            if (typeof window.oveEditor === 'undefined') {
                // 动态加载 OVE 脚本
                await this.loadOVEScript();
            }

            // 等待 OVE 加载完成
            const maxWaitTime = 10000; // 10秒
            const startTime = Date.now();
            
            while (typeof window.oveEditor === 'undefined' && (Date.now() - startTime) < maxWaitTime) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }

            if (typeof window.oveEditor === 'undefined') {
                throw new Error('OVE editor failed to load');
            }

            // 准备序列数据
            const sequenceData = this.prepareSequenceData(sequence);
            
            // 初始化 OVE 编辑器
            window.oveEditor.loadSequence(sequenceData);
            
            // 设置保存回调
            window.oveEditor.onSave = (event, sequenceData) => {
                this.handleSave(event, sequenceData);
            };
            
            // 设置复制回调
            window.oveEditor.onCopy = (event, copiedData) => {
                this.handleCopy(event, copiedData);
            };
            
            console.log('OVE editor initialized with sequence:', sequence.id);
            
        } catch (error) {
            console.error('OVE editor initialization error:', error);
            this.showError('编辑器初始化失败: ' + error.message);
        }
    }

    /**
     * 加载 OVE 脚本
     */
    async loadOVEScript() {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.type = 'module';
            script.src = '/static/js/ove-editor-bundle.js';
            
            script.onload = () => {
                console.log('OVE editor bundle loaded');
                resolve();
            };
            
            script.onerror = (error) => {
                console.error('OVE editor bundle load error:', error);
                reject(error);
            };
            
            document.head.appendChild(script);
        });
    }

    /**
     * 准备序列数据给 OVE
     */
    prepareSequenceData(sequence) {
        return {
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
    }

    /**
     * 处理保存事件
     */
    async handleSave(event, sequenceData) {
        try {
            // 转换回我们的格式
            const updatedSequence = {
                id: sequenceData.name,
                sequence: sequenceData.sequence,
                circular: sequenceData.circular,
                features: sequenceData.features.map(f => ({
                    name: f.name,
                    start: f.start + 1, // 转换回 1-based
                    end: f.end + 1,
                    type: f.type,
                    direction: f.strand,
                    color: f.color
                })),
                type: this.currentSequence.type,
                description: this.currentSequence.description
            };

            // 更新后端
            const result = await this.sequenceManager.updateSequence(
                this.currentProject.path,
                this.currentSequence.id,
                updatedSequence
            );

            if (result.success) {
                this.showSuccess('序列保存成功');
                
                // 更新当前序列
                this.currentSequence = updatedSequence;
                
                // 通知外部
                if (this.onSequenceUpdate) {
                    this.onSequenceUpdate(updatedSequence, this.currentProject);
                }
            } else {
                throw new Error(result.error || 'Save failed');
            }
            
        } catch (error) {
            this.showError('保存失败: ' + error.message);
        }
    }

    /**
     * 处理复制事件
     */
    handleCopy(event, copiedData) {
        try {
            // 构造 GenBank 格式文本
            const genbankText = this.formatGenBankText(copiedData);
            
            // 复制到剪贴板
            await navigator.clipboard.writeText(genbankText);
            
            this.showSuccess('序列已复制到剪贴板 (带注释)');
            
        } catch (error) {
            this.showError('复制失败: ' + error.message);
        }
    }

    /**
     * 格式化 GenBank 文本
     */
    formatGenBankText(sequenceData) {
        let text = `LOCUS       ${sequenceData.name}\n`;
        text += `DEFINITION  ${sequenceData.description || ''}\n`;
        text += `ACCESSION   \n`;
        text += `VERSION     \n`;
        text += `SOURCE      \n`;
        text += `  ORGANISM  \n`;
        text += `FEATURES             Location/Qualifiers\n`;
        
        if (sequenceData.features && sequenceData.features.length > 0) {
            sequenceData.features.forEach(feature => {
                text += `     ${feature.type}    ${feature.start + 1}..${feature.end + 1}\n`;
                text += `                     /label="${feature.name}"\n`;
                if (feature.color) {
                    text += `                     /color="${feature.color}"\n`;
                }
                text += `                     /strand="${feature.strand === 1 ? '+' : '-'}"\n`;
            });
        }
        
        text += `ORIGIN\n`;
        
        // 格式化序列 (每行 60 个字符)
        const sequence = sequenceData.sequence || '';
        for (let i = 0; i < sequence.length; i += 60) {
            text += sequence.substring(i, i + 60) + '\n';
        }
        
        text += '//\n';
        
        return text;
    }

    /**
     * 切换视图
     */
    toggleView() {
        if (window.oveEditor) {
            const currentView = window.oveEditor.getViewer();
            const newView = currentView === 'both' ? 'circular' : 'both';
            window.oveEditor.setViewer(newView);
            
            this.showSuccess(`切换到 ${newView} 视图`);
        }
    }

    /**
     * 显示工具
     */
    showTools() {
        if (window.oveEditor) {
            // 这里可以显示 OVE 的工具面板
            this.showSuccess('工具面板已显示');
        }
    }

    /**
     * 保存序列
     */
    async saveSequence() {
        if (!this.currentSequence) {
            this.showError('没有选择序列');
            return;
        }

        try {
            // 触发保存
            if (window.oveEditor) {
                window.oveEditor.triggerSave();
            }
            
            this.showSuccess('序列保存中...');
            
        } catch (error) {
            this.showError('保存失败: ' + error.message);
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
            // 获取当前序列数据
            const sequenceData = window.oveEditor.getSequence();
            
            if (sequenceData) {
                // 导出为不同格式
                await this.exportAsFASTA(sequenceData);
                await this.exportAsGenBank(sequenceData);
                
                this.showSuccess('序列导出完成');
            }
            
        } catch (error) {
            this.showError('导出失败: ' + error.message);
        }
    }

    /**
     * 导出为 FASTA
     */
    async exportAsFASTA(sequenceData) {
        const fastaText = `>${sequenceData.name}\n${sequenceData.sequence}`;
        
        const blob = new Blob([fastaText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = sequenceData.name + '.fasta';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    /**
     * 导出为 GenBank
     */
    async exportAsGenBank(sequenceData) {
        const genbankText = this.formatGenBankText(sequenceData);
        
        const blob = new Blob([genbankText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = sequenceData.name + '.gb';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    /**
     * 显示加载状态
     */
    showLoading(show) {
        const loadingDiv = document.getElementById('editorLoading');
        if (loadingDiv) {
            loadingDiv.style.display = show ? 'block' : 'none';
        }
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
        messageDiv.className = `editor-message ${type}`;
        messageDiv.textContent = message;
        
        // 添加到容器
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
window.oveEditor = new OVEEditor();