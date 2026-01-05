/**
 * Main Application - 集成所有组件
 * 真正可用的序列管理系统
 */
class BioLabApp {
    constructor() {
        this.projectTree = null;
        this.sequenceViewer = null;
        this.fileUploader = null;
        this.currentProject = null;
        this.currentSequence = null;
    }

    /**
     * 初始化应用
     */
    init() {
        console.log('Initializing BioLab Workbench...');
        
        // 初始化各个组件
        this.projectTree = new ProjectTree(
            'projectTreeContainer',
            (project, sequence) => {
                this.currentProject = project;
                this.currentSequence = sequence;
                this.sequenceViewer.loadSequence(project.path, sequence.id);
            }
        );

        this.sequenceViewer = new SequenceViewer(
            'sequenceViewerContainer',
            (sequence, project) => {
                this.currentSequence = sequence;
                this.currentProject = project;
            }
        );

        this.fileUploader = new FileUploader(
            'fileUploaderContainer',
            (files) => {
                if (this.currentProject) {
                    this.fileUploader.onUploadComplete = (uploadedFiles) => {
                        console.log('Files uploaded:', uploadedFiles);
                        // 上传完成后刷新项目树
                        this.projectTree.loadProjects();
                    };
                }
            }
        );

        // 初始化所有组件
        this.projectTree.init();
        this.sequenceViewer.init();
        this.fileUploader.init();
        
        // 绑定全局事件
        this.bindGlobalEvents();
        
        // 加载初始数据
        this.loadInitialData();
    }

    /**
     * 绑定全局事件
     */
    bindGlobalEvents() {
        // 键盘快捷键
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.saveCurrentSequence();
            }
        });

        // 页面卸载时保存状态
        window.addEventListener('beforeunload', () => {
            this.saveAppState();
        });
    }

    /**
     * 加载初始数据
     */
    async loadInitialData() {
        try {
            // 加载项目列表
            await this.projectTree.loadProjects();
            console.log('Initial data loaded successfully');
        } catch (error) {
            console.error('Failed to load initial data:', error);
        }
    }

    /**
     * 保存当前序列
     */
    async saveCurrentSequence() {
        if (!this.currentSequence || !this.currentProject) {
            console.log('No sequence to save');
            return;
        }

        try {
            // 获取当前序列数据
            const sequenceData = this.sequenceViewer.oveEditor?.getSequence();
            if (!sequenceData) {
                console.log('No sequence data to save');
                return;
            }

            // 更新序列
            const result = await window.sequenceManager.updateSequence(
                this.currentProject.path,
                this.currentSequence.id,
                {
                    sequence: sequenceData.sequence,
                    description: this.currentSequence.description
                }
            );

            if (result.success) {
                this.showMessage('序列保存成功', 'success');
            } else {
                this.showMessage('保存失败: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Save sequence error:', error);
            this.showMessage('保存失败: ' + error.message, 'error');
        }
    }

    /**
     * 保存应用状态
     */
    saveAppState() {
        const state = {
            currentProject: this.currentProject,
            currentSequence: this.currentSequence,
            timestamp: new Date().toISOString()
        };
        
        localStorage.setItem('biolabAppState', JSON.stringify(state));
    }

    /**
     * 恢复应用状态
     */
    restoreAppState() {
        try {
            const stateJson = localStorage.getItem('biolabAppState');
            if (stateJson) {
                const state = JSON.parse(stateJson);
                this.currentProject = state.currentProject || null;
                this.currentSequence = state.currentSequence || null;
                
                // 恢复组件状态
                if (this.currentProject) {
                    this.projectTree.selectProject(this.currentProject.path);
                }
                if (this.currentSequence) {
                    this.sequenceViewer.loadSequence(this.currentProject.path, this.currentSequence.id);
                }
                
                console.log('App state restored');
            }
        } catch (error) {
            console.error('Failed to restore app state:', error);
        }
    }

    /**
     * 显示消息
     */
    showMessage(message, type = 'info') {
        // 创建消息元素
        const messageDiv = document.createElement('div');
        messageDiv.className = `app-message ${type}`;
        messageDiv.textContent = message;
        
        // 添加到页面
        document.body.appendChild(messageDiv);
        
        // 3秒后自动移除
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        }, 3000);
    }

    /**
     * 显示错误消息
     */
    showError(message) {
        this.showMessage(message, 'error');
    }

    /**
     * 显示成功消息
     */
    showSuccess(message) {
        this.showMessage(message, 'success');
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    const app = new BioLabApp();
    app.init();
    
    // 将实例暴露到全局
    window.bioLabApp = app;
});
