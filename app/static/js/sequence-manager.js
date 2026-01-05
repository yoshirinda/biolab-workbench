/**
 * Sequence Manager - API 封装类
 * 提供与后端 API 的完整集成
 */
class SequenceManager {
    constructor() {
        this.baseURL = '/sequence';
        this.projects = [];
        this.currentProject = null;
        this.currentSequence = null;
    }

    /**
     * 获取所有项目
     */
    async getProjects() {
        try {
            const response = await fetch(this.baseURL + '/projects');
            const data = await response.json();
            if (data.success) {
                this.projects = data.projects;
                return data.projects;
            } else {
                throw new Error(data.error || 'Failed to get projects');
            }
        } catch (error) {
            console.error('Get projects error:', error);
            throw error;
        }
    }

    /**
     * 创建新项目
     */
    async createProject(name, parentPath = null, description = '') {
        try {
            const response = await fetch(this.baseURL + '/projects', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: name,
                    parent_path: parentPath,
                    description: description
                })
            });
            const data = await response.json();
            if (data.success) {
                await this.getProjects(); // 刷新项目列表
                return data.project;
            } else {
                throw new Error(data.error || 'Failed to create project');
            }
        } catch (error) {
            console.error('Create project error:', error);
            throw error;
        }
    }

    /**
     * 获取项目详情
     */
    async getProject(path) {
        try {
            const response = await fetch(this.baseURL + '/projects/' + encodeURIComponent(path));
            const data = await response.json();
            if (data.success) {
                return data.project;
            } else {
                throw new Error(data.error || 'Failed to get project');
            }
        } catch (error) {
            console.error('Get project error:', error);
            throw error;
        }
    }

    /**
     * 更新项目
     */
    async updateProject(path, name, description) {
        try {
            const response = await fetch(this.baseURL + '/projects/' + encodeURIComponent(path), {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: name,
                    description: description
                })
            });
            const data = await response.json();
            if (data.success) {
                await this.getProjects(); // 刷新项目列表
                return data.project;
            } else {
                throw new Error(data.error || 'Failed to update project');
            }
        } catch (error) {
            console.error('Update project error:', error);
            throw error;
        }
    }

    /**
     * 删除项目
     */
    async deleteProject(path) {
        try {
            const response = await fetch(this.baseURL + '/projects/' + encodeURIComponent(path), {
                method: 'DELETE'
            });
            const data = await response.json();
            if (data.success) {
                await this.getProjects(); // 刷新项目列表
                return true;
            } else {
                throw new Error(data.error || 'Failed to delete project');
            }
        } catch (error) {
            console.error('Delete project error:', error);
            throw error;
        }
    }

    /**
     * 创建新文件夹
     */
    async createFolder(name, parentPath = null) {
        try {
            const response = await fetch(this.baseURL + '/folders', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: name,
                    parent_path: parentPath
                })
            });
            const data = await response.json();
            if (data.success) {
                await this.getProjects(); // 刷新项目列表
                return true;
            } else {
                throw new Error(data.error || 'Failed to create folder');
            }
        } catch (error) {
            console.error('Create folder error:', error);
            throw error;
        }
    }

    /**
     * 导入序列到项目
     */
    async importSequences(file, projectPath) {
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('source', 'file');
            formData.append('project_path', projectPath);

            const response = await fetch(this.baseURL + '/import', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.success) {
                return {
                    sequences: data.sequences,
                    project: data.project
                };
            } else {
                throw new Error(data.error || 'Failed to import sequences');
            }
        } catch (error) {
            console.error('Import sequences error:', error);
            throw error;
        }
    }

    /**
     * 添加序列到项目
     */
    async addSequencesToProject(projectPath, sequences) {
        try {
            const response = await fetch(this.baseURL + '/projects/' + encodeURIComponent(projectPath) + '/sequences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sequences: sequences
                })
            });
            const data = await response.json();
            if (data.success) {
                return {
                    sequences: data.sequences,
                    project: data.project
                };
            } else {
                throw new Error(data.error || 'Failed to add sequences');
            }
        } catch (error) {
            console.error('Add sequences error:', error);
            throw error;
        }
    }

    /**
     * 删除序列
     */
    async deleteSequence(projectPath, sequenceId) {
        try {
            const response = await fetch(this.baseURL + '/projects/' + encodeURIComponent(projectPath) + '/sequences/' + sequenceId, {
                method: 'DELETE'
            });
            const data = await response.json();
            if (data.success) {
                return {
                    sequences: data.sequences,
                    project: data.project
                };
            } else {
                throw new Error(data.error || 'Failed to delete sequence');
            }
        } catch (error) {
            console.error('Delete sequence error:', error);
            throw error;
        }
    }

    /**
     * 更新序列
     */
    async updateSequence(projectPath, sequenceId, updateData) {
        try {
            const response = await fetch(this.baseURL + '/projects/' + encodeURIComponent(projectPath) + '/sequences/' + sequenceId, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(updateData)
            });
            const data = await response.json();
            if (data.success) {
                return {
                    sequences: data.sequences,
                    project: data.project
                };
            } else {
                throw new Error(data.error || 'Failed to update sequence');
            }
        } catch (error) {
            console.error('Update sequence error:', error);
            throw error;
        }
    }

    /**
     * 导出项目序列
     */
    async exportProject(projectPath, format = 'fasta') {
        try {
            const response = await fetch(this.baseURL + '/projects/' + encodeURIComponent(projectPath) + '/export?format=' + format);
            const data = await response.json();
            if (data.success) {
                return {
                    fasta: data.fasta,
                    count: data.count
                };
            } else {
                throw new Error(data.error || 'Failed to export project');
            }
        } catch (error) {
            console.error('Export project error:', error);
            throw error;
        }
    }

    /**
     * 获取特征类型
     */
    async getFeatureTypes() {
        try {
            const response = await fetch(this.baseURL + '/feature-types');
            const data = await response.json();
            if (data.success) {
                return data.types;
            } else {
                throw new Error(data.error || 'Failed to get feature types');
            }
        } catch (error) {
            console.error('Get feature types error:', error);
            throw error;
        }
    }

    /**
     * 添加特征
     */
    async addFeature(projectPath, sequenceId, feature) {
        try {
            const response = await fetch(this.baseURL + '/projects/' + encodeURIComponent(projectPath) + '/sequences/' + sequenceId + '/features', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(feature)
            });
            const data = await response.json();
            if (data.success) {
                return {
                    sequences: data.sequences,
                    project: data.project
                };
            } else {
                throw new Error(data.error || 'Failed to add feature');
            }
        } catch (error) {
            console.error('Add feature error:', error);
            throw error;
        }
    }

    /**
     * 更新特征
     */
    async updateFeature(projectPath, sequenceId, featureId, feature) {
        try {
            const response = await fetch(this.baseURL + '/projects/' + encodeURIComponent(projectPath) + '/sequences/' + sequenceId + '/features/' + featureId, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(feature)
            });
            const data = await response.json();
            if (data.success) {
                return {
                    sequences: data.sequences,
                    project: data.project
                };
            } else {
                throw new Error(data.error || 'Failed to update feature');
            }
        } catch (error) {
            console.error('Update feature error:', error);
            throw error;
        }
    }

    /**
     * 删除特征
     */
    async deleteFeature(projectPath, sequenceId, featureId) {
        try {
            const response = await fetch(this.baseURL + '/projects/' + encodeURIComponent(projectPath) + '/sequences/' + sequenceId + '/features/' + featureId, {
                method: 'DELETE'
            });
            const data = await response.json();
            if (data.success) {
                return {
                    sequences: data.sequences,
                    project: data.project
                };
            } else {
                throw new Error(data.error || 'Failed to delete feature');
            }
        } catch (error) {
            console.error('Delete feature error:', error);
            throw error;
        }
    }

    /**
     * 序列工具函数
     */
    async translateSequence(sequence, frame = 1) {
        try {
            const response = await fetch(this.baseURL + '/translate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sequence: sequence,
                    frame: frame
                })
            });
            const data = await response.json();
            if (data.success) {
                return data;
            } else {
                throw new Error(data.error || 'Failed to translate sequence');
            }
        } catch (error) {
            console.error('Translate sequence error:', error);
            throw error;
        }
    }

    async reverseComplement(sequence) {
        try {
            const response = await fetch(this.baseURL + '/reverse-complement', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sequence: sequence
                })
            });
            const data = await response.json();
            if (data.success) {
                return data;
            } else {
                throw new Error(data.error || 'Failed to get reverse complement');
            }
        } catch (error) {
            console.error('Reverse complement error:', error);
            throw error;
        }
    }

    async findORFs(sequence, minLength = 100) {
        try {
            const response = await fetch(this.baseURL + '/find-orfs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sequence: sequence,
                    min_length: minLength
                })
            });
            const data = await response.json();
            if (data.success) {
                return data;
            } else {
                throw new Error(data.error || 'Failed to find ORFs');
            }
        } catch (error) {
            console.error('Find ORFs error:', error);
            throw error;
        }
    }

    async getSequenceStats(sequence) {
        try {
            const response = await fetch(this.baseURL + '/stats', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sequence: sequence
                })
            });
            const data = await response.json();
            if (data.success) {
                return data;
            } else {
                throw new Error(data.error || 'Failed to get sequence stats');
            }
        } catch (error) {
            console.error('Get sequence stats error:', error);
            throw error;
        }
    }
}

// 全局实例
window.sequenceManager = new SequenceManager();