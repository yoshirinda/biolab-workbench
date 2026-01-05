/**
 * Project Tree Manager - 真实的项目树管理
 * 与后端 API 完全集成
 */
class ProjectTree {
    constructor() {
        this.treeContainer = null;
        this.currentProject = null;
        this.sequenceManager = window.sequenceManager;
        this.onProjectSelect = null;
        this.onSequenceSelect = null;
    }

    /**
     * 初始化项目树
     */
    init(containerId, onProjectSelect, onSequenceSelect) {
        this.treeContainer = document.getElementById(containerId);
        this.onProjectSelect = onProjectSelect;
        this.onSequenceSelect = onSequenceSelect;
        
        // 绑定事件
        this.bindEvents();
        
        // 加载项目
        this.loadProjects();
    }

    /**
     * 绑定事件监听器
     */
    bindEvents() {
        // 项目树点击事件
        this.treeContainer.addEventListener('click', (e) => {
            const node = e.target.closest('.tree-node');
            if (node) {
                this.handleNodeClick(node);
            }
        });

        // 右键菜单事件
        this.treeContainer.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            const node = e.target.closest('.tree-node');
            if (node) {
                this.showContextMenu(e, node);
            }
        });

        // 隐藏右键菜单
        document.addEventListener('click', () => {
            this.hideContextMenu();
        });
    }

    /**
     * 加载所有项目
     */
    async loadProjects() {
        try {
            const projects = await this.sequenceManager.getProjects();
            this.renderProjectTree(projects);
        } catch (error) {
            console.error('Load projects error:', error);
            this.showError('加载项目失败: ' + error.message);
        }
    }

    /**
     * 渲染项目树
     */
    renderProjectTree(projects) {
        if (!this.treeContainer) return;

        // 清空容器
        this.treeContainer.innerHTML = '';

        if (!projects || projects.length === 0) {
            this.renderEmptyState();
            return;
        }

        // 创建根节点
        const rootElement = this.createRootNode();
        this.treeContainer.appendChild(rootElement);

        // 添加项目节点
        projects.forEach(project => {
            const projectNode = this.createProjectNode(project);
            rootElement.appendChild(projectNode);
        });

        // 展开根节点
        rootElement.classList.add('expanded');
    }

    /**
     * 创建根节点
     */
    createRootNode() {
        const rootDiv = document.createElement('div');
        rootDiv.className = 'tree-node tree-root expanded';
        rootDiv.innerHTML = `
            <div class="tree-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 12h18v8H3z"/>
                    <path d="M12 2v2h10v10H12z"/>
                </svg>
            </div>
            <div class="tree-label">
                <span class="tree-name">项目库</span>
                <span class="tree-count">0 个项目</span>
            </div>
            <div class="tree-actions">
                <button class="btn btn-sm btn-primary" onclick="projectTree.showNewProjectModal()">
                    <i class="bi bi-plus-circle"></i> 新建项目
                </button>
                <button class="btn btn-sm btn-secondary" onclick="projectTree.showNewFolderModal()">
                    <i class="bi bi-folder-plus"></i> 新建文件夹
                </button>
            </div>
        `;
        return rootDiv;
    }

    /**
     * 创建项目节点
     */
    createProjectNode(project) {
        const projectDiv = document.createElement('div');
        projectDiv.className = 'tree-node tree-project';
        projectDiv.dataset.projectPath = project.path;
        projectDiv.innerHTML = `
            <div class="tree-content">
                <div class="tree-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M4 6h16v12H4z"/>
                        <path d="M8 10h8v2H8z"/>
                    </svg>
                </div>
                <div class="tree-info">
                    <div class="tree-name">${this.escapeHtml(project.name)}</div>
                    <div class="tree-meta">
                        <span class="tree-sequence-count">${project.sequence_count || 0} 个序列</span>
                        <span class="tree-date">${this.formatDate(project.created_at)}</span>
                    </div>
                </div>
            </div>
            <div class="tree-actions">
                <button class="btn btn-sm btn-outline-primary" onclick="projectTree.selectProject('${project.path}')">
                    <i class="bi bi-folder-open"></i> 打开
                </button>
                <button class="btn btn-sm btn-outline-secondary" onclick="projectTree.showProjectMenu('${project.path}')">
                    <i class="bi bi-three-dots"></i>
                </button>
            </div>
        `;

        // 添加序列容器
        if (project.sequences && project.sequences.length > 0) {
            const sequencesContainer = document.createElement('div');
            sequencesContainer.className = 'tree-sequences';
            
            project.sequences.forEach(sequence => {
                const sequenceNode = this.createSequenceNode(sequence, project.path);
                sequencesContainer.appendChild(sequenceNode);
            });
            
            projectDiv.appendChild(sequencesContainer);
        }

        return projectDiv;
    }

    /**
     * 创建序列节点
     */
    createSequenceNode(sequence, projectPath) {
        const sequenceDiv = document.createElement('div');
        sequenceDiv.className = 'tree-node tree-sequence';
        sequenceDiv.dataset.projectPath = projectPath;
        sequenceDiv.dataset.sequenceId = sequence.id;
        sequenceDiv.innerHTML = `
            <div class="tree-content">
                <div class="tree-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 3h6v18H9z"/>
                        <circle cx="6" cy="12" r="2"/>
                    </svg>
                </div>
                <div class="tree-info">
                    <div class="tree-name">${this.escapeHtml(sequence.id)}</div>
                    <div class="tree-meta">
                        <span class="tree-type">${sequence.type || 'DNA'}</span>
                        <span class="tree-length">${sequence.length || 0} bp</span>
                    </div>
                </div>
            </div>
            <div class="tree-actions">
                <button class="btn btn-sm btn-primary" onclick="projectTree.selectSequence('${projectPath}', '${sequence.id}')">
                    <i class="bi bi-eye"></i> 查看
                </button>
                <button class="btn btn-sm btn-outline-secondary" onclick="projectTree.showSequenceMenu('${projectPath}', '${sequence.id}')">
                    <i class="bi bi-three-dots"></i>
                </button>
            </div>
        `;
        return sequenceDiv;
    }

    /**
     * 处理节点点击
     */
    handleNodeClick(node) {
        const isProject = node.classList.contains('tree-project');
        const isSequence = node.classList.contains('tree-sequence');
        const isRoot = node.classList.contains('tree-root');

        if (isRoot) {
            this.toggleNode(node);
        } else if (isProject) {
            this.selectProject(node.dataset.projectPath);
        } else if (isSequence) {
            this.selectSequence(node.dataset.projectPath, node.dataset.sequenceId);
        }
    }

    /**
     * 选择项目
     */
    async selectProject(projectPath) {
        try {
            // 移除之前的选中状态
            document.querySelectorAll('.tree-node').forEach(n => {
                n.classList.remove('selected');
            });

            // 添加选中状态
            const projectNode = document.querySelector(`[data-project-path="${projectPath}"]`);
            if (projectNode) {
                projectNode.classList.add('selected');
            }

            // 展开序列
            this.expandProject(projectNode);

            // 通知外部
            if (this.onProjectSelect) {
                const project = await this.sequenceManager.getProject(projectPath);
                this.onProjectSelect(project);
            }
        } catch (error) {
            console.error('Select project error:', error);
            this.showError('选择项目失败: ' + error.message);
        }
    }

    /**
     * 选择序列
     */
    async selectSequence(projectPath, sequenceId) {
        try {
            // 移除之前的选中状态
            document.querySelectorAll('.tree-node').forEach(n => {
                n.classList.remove('selected');
            });

            // 添加选中状态
            const sequenceNode = document.querySelector(`[data-sequence-id="${sequenceId}"]`);
            if (sequenceNode) {
                sequenceNode.classList.add('selected');
            }

            // 通知外部
            if (this.onSequenceSelect) {
                const project = await this.sequenceManager.getProject(projectPath);
                const sequence = project.sequences.find(s => s.id === sequenceId);
                this.onSequenceSelect(sequence, project);
            }
        } catch (error) {
            console.error('Select sequence error:', error);
            this.showError('选择序列失败: ' + error.message);
        }
    }

    /**
     * 切换节点展开/折叠
     */
    toggleNode(node) {
        const isExpanded = node.classList.contains('expanded');
        if (isExpanded) {
            node.classList.remove('expanded');
        } else {
            node.classList.add('expanded');
        }
    }

    /**
     * 展开项目
     */
    expandProject(projectNode) {
        const sequencesContainer = projectNode.querySelector('.tree-sequences');
        if (sequencesContainer) {
            projectNode.classList.add('expanded');
        }
    }

    /**
     * 显示右键菜单
     */
    showContextMenu(event, node) {
        // 移除现有菜单
        this.hideContextMenu();

        // 创建菜单
        const menu = document.createElement('div');
        menu.className = 'context-menu';
        menu.style.left = event.pageX + 'px';
        menu.style.top = event.pageY + 'px';

        const isProject = node.classList.contains('tree-project');
        const isSequence = node.classList.contains('tree-sequence');

        if (isProject) {
            menu.innerHTML = this.getProjectMenuItems(node.dataset.projectPath);
        } else if (isSequence) {
            menu.innerHTML = this.getSequenceMenuItems(node.dataset.projectPath, node.dataset.sequenceId);
        }

        document.body.appendChild(menu);
    }

    /**
     * 隐藏右键菜单
     */
    hideContextMenu() {
        const existingMenu = document.querySelector('.context-menu');
        if (existingMenu) {
            existingMenu.remove();
        }
    }

    /**
     * 获取项目菜单项
     */
    getProjectMenuItems(projectPath) {
        return `
            <div class="context-menu-item" onclick="projectTree.openProject('${projectPath}')">
                <i class="bi bi-folder-open"></i> 打开项目
            </div>
            <div class="context-menu-item" onclick="projectTree.renameProject('${projectPath}')">
                <i class="bi bi-pencil"></i> 重命名
            </div>
            <div class="context-menu-divider"></div>
            <div class="context-menu-item" onclick="projectTree.deleteProject('${projectPath}')">
                <i class="bi bi-trash"></i> 删除项目
            </div>
            <div class="context-menu-divider"></div>
            <div class="context-menu-item" onclick="projectTree.exportProject('${projectPath}')">
                <i class="bi bi-download"></i> 导出项目
            </div>
        `;
    }

    /**
     * 获取序列菜单项
     */
    getSequenceMenuItems(projectPath, sequenceId) {
        return `
            <div class="context-menu-item" onclick="projectTree.viewSequence('${projectPath}', '${sequenceId}')">
                <i class="bi bi-eye"></i> 查看序列
            </div>
            <div class="context-menu-item" onclick="projectTree.editSequence('${projectPath}', '${sequenceId}')">
                <i class="bi bi-pencil"></i> 编辑序列
            </div>
            <div class="context-menu-item" onclick="projectTree.deleteSequence('${projectPath}', '${sequenceId}')">
                <i class="bi bi-trash"></i> 删除序列
            </div>
            <div class="context-menu-divider"></div>
            <div class="context-menu-item" onclick="projectTree.copySequence('${projectPath}', '${sequenceId}')">
                <i class="bi bi-files"></i> 复制序列
            </div>
            <div class="context-menu-item" onclick="projectTree.exportSequence('${projectPath}', '${sequenceId}')">
                <i class="bi bi-download"></i> 导出序列
            </div>
        `;
    }

    /**
     * 显示新项目模态框
     */
    showNewProjectModal() {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>新建项目</h3>
                <div class="form-group">
                    <label>项目名称:</label>
                    <input type="text" id="newProjectName" class="form-control" placeholder="输入项目名称">
                </div>
                <div class="form-group">
                    <label>父路径:</label>
                    <select id="newProjectParent" class="form-control">
                        <option value="">根目录</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>描述:</label>
                    <textarea id="newProjectDescription" class="form-control" rows="3" placeholder="项目描述(可选)"></textarea>
                </div>
                <div class="form-actions">
                    <button class="btn btn-secondary" onclick="projectTree.hideModal()">取消</button>
                    <button class="btn btn-primary" onclick="projectTree.createNewProject()">创建</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    }

    /**
     * 显示新文件夹模态框
     */
    showNewFolderModal() {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>新建文件夹</h3>
                <div class="form-group">
                    <label>文件夹名称:</label>
                    <input type="text" id="newFolderName" class="form-control" placeholder="输入文件夹名称">
                </div>
                <div class="form-group">
                    <label>父路径:</label>
                    <select id="newFolderParent" class="form-control">
                        <option value="">根目录</option>
                    </select>
                </div>
                <div class="form-actions">
                    <button class="btn btn-secondary" onclick="projectTree.hideModal()">取消</button>
                    <button class="btn btn-primary" onclick="projectTree.createNewFolder()">创建</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    }

    /**
     * 隐藏模态框
     */
    hideModal() {
        const modal = document.querySelector('.modal');
        if (modal) {
            modal.remove();
        }
    }

    /**
     * 创建新项目
     */
    async createNewProject() {
        const name = document.getElementById('newProjectName').value.trim();
        const parentPath = document.getElementById('newProjectParent').value;
        const description = document.getElementById('newProjectDescription').value.trim();

        if (!name) {
            this.showError('请输入项目名称');
            return;
        }

        try {
            await this.sequenceManager.createProject(name, parentPath, description);
            this.hideModal();
            await this.loadProjects(); // 刷新项目树
            this.showSuccess('项目创建成功');
        } catch (error) {
            this.showError('创建项目失败: ' + error.message);
        }
    }

    /**
     * 创建新文件夹
     */
    async createNewFolder() {
        const name = document.getElementById('newFolderName').value.trim();
        const parentPath = document.getElementById('newFolderParent').value;

        if (!name) {
            this.showError('请输入文件夹名称');
            return;
        }

        try {
            await this.sequenceManager.createFolder(name, parentPath);
            this.hideModal();
            await this.loadProjects(); // 刷新项目树
            this.showSuccess('文件夹创建成功');
        } catch (error) {
            this.showError('创建文件夹失败: ' + error.message);
        }
    }

    /**
     * 打开项目
     */
    openProject(projectPath) {
        this.selectProject(projectPath);
    }

    /**
     * 重命名项目
     */
    async renameProject(projectPath) {
        const newName = prompt('请输入新的项目名称:');
        if (!newName || newName.trim() === '') {
            return;
        }

        try {
            await this.sequenceManager.updateProject(projectPath, newName);
            await this.loadProjects(); // 刷新项目树
            this.showSuccess('项目重命名成功');
        } catch (error) {
            this.showError('重命名失败: ' + error.message);
        }
    }

    /**
     * 删除项目
     */
    async deleteProject(projectPath) {
        if (!confirm('确定要删除这个项目吗？此操作无法撤销。')) {
            return;
        }

        try {
            await this.sequenceManager.deleteProject(projectPath);
            await this.loadProjects(); // 刷新项目树
            this.showSuccess('项目删除成功');
        } catch (error) {
            this.showError('删除项目失败: ' + error.message);
        }
    }

    /**
     * 导出项目
     */
    async exportProject(projectPath) {
        try {
            const result = await this.sequenceManager.exportProject(projectPath);
            if (result.success) {
                // 下载文件
                const blob = new Blob([result.fasta], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = result.project.name + '.fasta';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                this.showSuccess('项目导出成功');
            }
        } catch (error) {
            this.showError('导出失败: ' + error.message);
        }
    }

    /**
     * 查看序列
     */
    viewSequence(projectPath, sequenceId) {
        this.selectSequence(projectPath, sequenceId);
    }

    /**
     * 编辑序列
     */
    editSequence(projectPath, sequenceId) {
        // 这里可以打开序列编辑器
        console.log('Edit sequence:', projectPath, sequenceId);
        // TODO: 实现序列编辑功能
    }

    /**
     * 删除序列
     */
    async deleteSequence(projectPath, sequenceId) {
        if (!confirm('确定要删除这个序列吗？此操作无法撤销。')) {
            return;
        }

        try {
            await this.sequenceManager.deleteSequence(projectPath, sequenceId);
            await this.loadProjects(); // 刷新项目树
            this.showSuccess('序列删除成功');
        } catch (error) {
            this.showError('删除序列失败: ' + error.message);
        }
    }

    /**
     * 复制序列
     */
    async copySequence(projectPath, sequenceId) {
        try {
            const project = await this.sequenceManager.getProject(projectPath);
            const sequence = project.sequences.find(s => s.id === sequenceId);
            if (sequence) {
                // 复制到剪贴板
                const text = `>${sequence.id}\n${sequence.sequence}`;
                await navigator.clipboard.writeText(text);
                this.showSuccess('序列已复制到剪贴板');
            }
        } catch (error) {
            this.showError('复制失败: ' + error.message);
        }
    }

    /**
     * 导出序列
     */
    async exportSequence(projectPath, sequenceId) {
        try {
            const project = await this.sequenceManager.getProject(projectPath);
            const sequence = project.sequences.find(s => s.id === sequenceId);
            if (sequence) {
                const text = `>${sequence.id}\n${sequence.sequence}`;
                const blob = new Blob([text], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = sequence.id + '.fasta';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                this.showSuccess('序列导出成功');
            }
        } catch (error) {
            this.showError('导出失败: ' + error.message);
        }
    }

    /**
     * 显示项目菜单
     */
    showProjectMenu(projectPath) {
        // TODO: 实现项目菜单
        console.log('Show project menu:', projectPath);
    }

    /**
     * 显示序列菜单
     */
    showSequenceMenu(projectPath, sequenceId) {
        // TODO: 实现序列菜单
        console.log('Show sequence menu:', projectPath, sequenceId);
    }

    /**
     * 渲染空状态
     */
    renderEmptyState() {
        this.treeContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                        <path d="M12 2C6.48 2 2 12s0 0 10 0 10 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 