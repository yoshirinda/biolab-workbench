# 真正可用的序列管理界面实施计划

## 问题分析

### 当前问题:
1. ❌ **没有真正的文件上传** - 只有前端演示
2. ❌ **文件树是假的** - 无法与后端交互
3. ❌ **按钮都是摆设** - 没有连接到后端 API
4. ❌ **没有项目管理** - 无法创建/删除/编辑项目
5. ❌ **没有序列导入** - 无法真正上传文件

### 已有的后端 API:
✅ `/sequence/import` - 导入序列
✅ `/sequence/projects` - 项目管理
✅ `/sequence/projects/<path>` - 获取/更新/删除项目
✅ `/sequence/projects/<path>/sequences` - 序列管理
✅ `/sequence/projects/<path>/sequences/<id>/features` - 特征管理
✅ 完整的项目文件系统存储

---

## 正确的实施方案

### 架构设计

```
┌─────────────────────────────────────────┐
│          Flask 后端 (已有)               │
│  - 项目管理 API                          │
│  - 序列存储 (JSON 文件)                  │
│  - 特征注释                              │
└────────────┬────────────────────────────┘
             │ REST API
             │
┌────────────▼────────────────────────────┐
│          前端界面 (需重写)               │
│  - 真实的文件上传                        │
│  - 与后端同步的项目树                    │
│  - 完整的 CRUD 操作                      │
│  - OVE 编辑器集成                        │
└─────────────────────────────────────────┘
```

### 核心功能实现

#### 1. 项目树管理 (完全基于后端)

```typescript
// 从后端加载项目树
async function loadProjects() {
  const response = await fetch('/sequence/projects');
  const data = await response.json();
  if (data.success) {
    renderProjectTree(data.projects);
  }
}

// 创建新项目 (真实 API 调用)
async function createProject(name, parent_path, description) {
  const response = await fetch('/sequence/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, parent_path, description })
  });
  return await response.json();
}

// 删除项目 (真实 API 调用)
async function deleteProject(path) {
  const response = await fetch(`/sequence/projects/${encodeURIComponent(path)}`, {
    method: 'DELETE'
  });
  return await response.json();
}
```

#### 2. 文件上传 (真实功能)

```typescript
// 真实的文件上传到后端
async function uploadSequenceFile(file, projectPath) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('source', 'file');
  formData.append('project_path', projectPath);
  
  const response = await fetch('/sequence/import', {
    method: 'POST',
    body: formData
  });
  
  return await response.json();
}
```

#### 3. 序列查看器 (OVE + 后端数据)

```typescript
// 从后端获取序列详情
async function loadSequence(projectPath, sequenceId) {
  const response = await fetch(`/sequence/projects/${projectPath}`);
  const data = await response.json();
  
  if (data.success) {
    const seq = data.project.sequences.find(s => s.id === sequenceId);
    displayInOVE(seq);
  }
}
```

---

## 实施步骤

### 阶段 1: 核心基础设施 (今天完成)

- [ ] 创建 `SequenceManager` 类 - 封装所有 API 调用
- [ ] 创建 `ProjectTree` 组件 - 真实的树形结构
- [ ] 实现文件上传功能 - 连接到 `/sequence/import`
- [ ] 测试基本的 CRUD 操作

### 阶段 2: 用户界面 (明天)

- [ ] 项目树右键菜单 (新建/删除/重命名)
- [ ] 文件拖拽上传
- [ ] 序列列表显示
- [ ] OVE 编辑器集成

### 阶段 3: 高级功能 (后天)

- [ ] 特征注释编辑
- [ ] 批量操作
- [ ] 搜索和过滤
- [ ] 导出功能

---

## 技术选型(修正)

### ❌ 不使用 (之前的错误)
- React (增加复杂度,与现有项目不符)
- 独立的前端应用
- 模拟数据

### ✅ 正确使用
- **纯 JavaScript + Vanilla DOM** (与现有项目一致)
- **直接集成到现有模板** (`sequence_v2.html`)
- **完全依赖后端 API**
- **OVE 通过 UMD 包引入**

---

## 文件结构

```
app/
├── routes/
│   └── sequence.py          # ✅ 已有完整 API
├── templates/
│   └── sequence_v2.html     # 🔄 需要完全重写
└── static/
    └── js/
        ├── sequence-manager.js      # 新建: API 封装
        ├── project-tree.js          # 新建: 项目树管理
        ├── sequence-viewer.js       # 新建: OVE 集成
        └── file-uploader.js         # 新建: 文件上传
```

---

## 核心代码示例

### sequence-manager.js (API 封装层)

```javascript
class SequenceManager {
  async getProjects() {
    const res = await fetch('/sequence/projects');
    return await res.json();
  }
  
  async createProject(name, parentPath, description) {
    const res = await fetch('/sequence/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, parent_path: parentPath, description })
    });
    return await res.json();
  }
  
  async importSequences(file, projectPath) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source', 'file');
    formData.append('project_path', projectPath);
    
    const res = await fetch('/sequence/import', {
      method: 'POST',
      body: formData
    });
    return await res.json();
  }
  
  async getProject(path) {
    const res = await fetch(`/sequence/projects/${encodeURIComponent(path)}`);
    return await res.json();
  }
  
  async deleteProject(path) {
    const res = await fetch(`/sequence/projects/${encodeURIComponent(path)}`, {
      method: 'DELETE'
    });
    return await res.json();
  }
  
  async deleteSequence(projectPath, sequenceId) {
    const res = await fetch(
      `/sequence/projects/${encodeURIComponent(projectPath)}/sequences/${sequenceId}`,
      { method: 'DELETE' }
    );
    return await res.json();
  }
}
```

---

## 验证清单

### 基本功能测试
- [ ] 页面加载时自动显示现有项目
- [ ] 点击"新建项目"按钮,真的创建项目
- [ ] 选择项目,点击"导入"上传文件,真的导入序列
- [ ] 点击序列,在右侧显示详情
- [ ] 右键项目,选择"删除",真的删除
- [ ] 刷新页面,数据还在(持久化)

### 高级功能测试
- [ ] 拖拽文件上传
- [ ] 批量导入多个文件
- [ ] 编辑序列详情
- [ ] 添加/编辑特征注释
- [ ] 导出为不同格式

---

## 下一步行动

1. **立即开始**: 重写 `sequence_v2.html` 的 JavaScript 部分
2. **创建 API 封装类**: `sequence-manager.js`
3. **实现真实的项目树**: 从后端加载数据
4. **测试基本流程**: 创建项目 → 导入序列 → 查看
5. **逐步添加功能**: 编辑、删除、导出等

---

## 时间估算

- **第1天** (4-6小时): API 封装 + 基础 UI
- **第2天** (4-6小时): 完整功能实现
- **第3天** (2-3小时): 测试和优化

**总计**: 10-15 小时的实际开发工作

---

## 总结

之前的问题在于:
- ❌ 只做了前端演示,没有后端集成
- ❌ 使用了 React,但项目是纯 Flask
- ❌ 创建了独立组件,但没有连接 API

正确的做法是:
- ✅ 完全基于现有后端 API
- ✅ 使用项目已有的技术栈
- ✅ 真实的数据持久化
- ✅ 每个按钮都有实际功能