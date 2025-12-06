# BioLab Workbench 代码审计报告

## 一、原始脚本功能分析

### 1. uniprot_miner_v5.4.py - UniProt 序列检索
**核心功能**：从 UniProt 数据库检索蛋白质序列
- 支持多种分类学过滤（物种、门类）
- 交互式多选菜单（simple-term-menu）
- 自定义序列命名格式：`Gene_Species_ID`
- 输出 FASTA 和 TSV 元数据

**关键细节**：
- 使用 UniProt REST API
- 批量下载（100条/批次）
- 自动检测数据库类型（Reviewed/Unreviewed）
- 清洗物种名和基因名

**当前项目对应**：`app/routes/uniprot.py` + `uniprot.html`

---

### 2. blast_pipe.sh - BLAST 数据库管理与搜索
**核心功能**：BLAST 数据库建库和序列比对
- 自动路径转换（Windows ↔ WSL）
- 序列类型自动检测（nucl/prot）
- 轻量级数据库索引
- 支持文本粘贴或文件输入

**关键细节**：
- 使用 `makeblastdb` 建库
- E-value、覆盖度、相似度过滤
- 输出详细表格和可读摘要
- 数据库目录统一管理

**当前项目对应**：`app/routes/blast.py` + `app/core/blast_wrapper.py`

---

### 3. seq_aligner.py - 多序列比对工具
**核心功能**：序列比对和可视化
- 支持 MAFFT/ClustalW/MUSCLE
- 键盘交互式序列选择
- 比对结果可视化（pyMSAviz）
- Windows 路径自动转换

**关键细节**：
- 终端键盘控制（↑↓空格）
- 比对参数可配置
- 结果导出多种格式
- 集成可视化

**当前项目对应**：`app/routes/alignment.py` + `alignment.html`

---

### 4. view_clade.py - 系统发育树可视化
**核心功能**：ETE3 系统发育树渲染
- 自动检测物种前缀
- 交互式物种选择和配色
- 支持基因为中心扩展层级
- Bootstrap 值显示
- 圆形/矩形布局

**关键细节**：
- 使用 ETE3 库（headless 模式）
- 动态宽度计算（大树警告）
- 高亮目标基因
- SVG 输出

**当前项目对应**：`app/routes/tree.py` + `app/core/tree_visualizer.py`

---

### 5. blast-phylo_pipeline_gui.py - 系统发育分析流水线
**核心功能**：完整的系统发育分析流程
- HMM 序列搜索（hmmsearch）
- BLAST 过滤（比对验证）
- 长度过滤
- MAFFT 多序列比对
- ClipKIT 修剪
- IQ-TREE 建树

**关键工作流**：
```
蛋白质序列 → HMM搜索 → BLAST验证 → 长度过滤 → 
多序列比对 → 位点修剪 → 建树 → Bootstrap支持值
```

**关键细节**：
- Conda 环境集成
- 实时日志输出
- 参数高度可配置
- 中间文件命名规范
- ClipKIT 交互式检查器

**当前项目对应**：`app/routes/phylo.py` + `phylo.html`

---

## 二、现有项目实现问题

### 🔴 严重问题

#### 1. **系统发育流水线未完整实现**
- ❌ 缺少 HMM 搜索功能（hmmsearch）
- ❌ 缺少 ClipKIT 修剪步骤
- ❌ 缺少中间步骤的 BLAST 验证
- ❌ 缺少长度过滤功能
- ❌ IQ-TREE 参数不全（无 Bootstrap、无模型选择）

#### 2. **序列比对功能残缺**
- ❌ 只支持 MAFFT，缺少 ClustalW/MUSCLE
- ❌ 没有键盘交互选择序列
- ❌ 没有比对结果可视化
- ❌ 缺少参数配置（迭代次数等）

#### 3. **树可视化功能不完整**
- ⚠️ 物种前缀自动检测未实现
- ⚠️ 缺少交互式物种选择和配色
- ⚠️ 中心基因扩展功能有 bug（距离计算）
- ⚠️ 缺少动态宽度/字体缩放

#### 4. **UniProt 检索简化过度**
- ⚠️ 缺少交互式多选菜单
- ⚠️ 物种过滤选项减少
- ⚠️ 序列命名格式不一致

#### 5. **BLAST 功能问题**
- ⚠️ 自动检测程序 bug（已修复但需验证）
- ⚠️ 数据库列表逻辑有重复代码
- ⚠️ 缺少 BLAST 结果的高级过滤

---

### 🟡 设计问题

#### 1. **缺少统一的项目/任务管理**
- 原始脚本各自独立，现在需要统一的"项目"概念
- 中间文件命名不规范（`01_cleaned`, `02_hits` 等在 web 中无意义）
- 缺少任务历史和状态追踪

#### 2. **路径处理不统一**
- 原脚本大量使用 Windows ↔ WSL 路径转换
- Web 版应该完全使用服务器端路径
- 部分路径硬编码（`C:\Users\...`）

#### 3. **参数持久化缺失**
- 原脚本每次运行重新输入参数
- Web 版应保存常用参数配置
- 缺少参数模板功能

#### 4. **错误处理薄弱**
- 外部工具调用缺少超时控制
- 文件不存在时未妥善处理
- Conda 环境检测不完善

---

### 🟢 代码质量问题

#### 1. **重复代码**
- FASTA 解析逻辑在多处重复
- 路径转换函数重复
- 命令执行封装不统一

#### 2. **命名不规范**
- 部分变量使用拼音（如 `cishu`）
- 函数命名不一致（驼峰 vs 下划线）
- 魔术数字未定义常量

#### 3. **文档缺失**
- 核心函数缺少 docstring
- 复杂逻辑缺少注释
- API 接口文档不全

---

## 三、改进方案

### 🎯 优先级 P0（核心功能缺失）

#### 1. 完善系统发育流水线
```python
# 需要实现的完整流程
1. HMM Search (hmmsearch)
   - 支持多个 HMM profile
   - E-value 过滤
   - 结果合并去重

2. BLAST 验证
   - 对 HMM hits 进行 BLAST
   - 与 gold list 比对
   - 相似度/覆盖度过滤

3. 长度过滤
   - 计算序列长度分布
   - 交互式阈值选择
   - 生成过滤日志

4. ClipKIT 修剪
   - kpic-gappy 模式
   - gap 阈���配置
   - 位点保留统计

5. IQ-TREE 增强
   - Bootstrap 支持
   - 模型选择（MFP）
   - 分支支持值输出
```

**实现位置**：
- `app/routes/phylo.py`：添加新 endpoints
- `app/core/phylo_pipeline.py`：新建核心逻辑模块
- `app/templates/phylo.html`：完善 UI 流程

---

#### 2. 修复树可视化功能
```python
# 需要修复/增强
1. 自动物种前缀检测
   - 正则提取前缀
   - 去重排序
   
2. 交互式物种选择
   - 前端多选组件
   - 颜色分配算法
   
3. 中心基因距离计算
   - 修正 topology_only 参数
   - 添加半径范围验证
   
4. 动态布局优化
   - 大树自动圆形布局
   - 字体/间距自适应
```

**实现位置**：
- `app/core/tree_visualizer.py`：修复距离计算
- `app/templates/tree.html`：添加物种选择 UI

---

#### 3. 增强序列比对工具
```python
# 需要添加
1. 多工具支持
   - ClustalW wrapper
   - MUSCLE wrapper
   - 工具自动检测
   
2. 交互式序列选择
   - 前端复选框列表
   - 批量选择/取消
   
3. 结果可视化
   - pyMSAviz 集成
   - 保守位点高亮
   
4. 参数配置
   - MAFFT 迭代次数
   - ClustalW gap penalties
```

**实现位置**：
- `app/core/alignment_wrapper.py`：添加新工具支持
- `app/routes/alignment.py`：增强 API
- `app/templates/alignment.html`：改进 UI

---

### 🎯 优先级 P1（功能完善）

#### 4. 统一项目管理
```python
# 新建项目管理模块
class ProjectManager:
    - create_project(name, type)
    - save_intermediate_files(project_id, step, data)
    - track_pipeline_status(project_id)
    - export_project_archive(project_id)
```

#### 5. 参数配置持久化
```python
# 新建配置管理
class ConfigManager:
    - save_user_preset(tool, params)
    - load_preset(preset_name)
    - export_config_json()
```

#### 6. 任务队列与异步执行
```python
# 长时间任务后台化
- Celery/RQ 集成
- 实时进度推送（WebSocket）
- 任务历史查询
```

---

### 🎯 优先级 P2（代码质量）

#### 7. 重构重复代码
- 统一 FASTA parser（`app/core/fasta_utils.py`）
- 统一命令执行器（`app/core/command_runner.py`）
- 统一错误处理（自定义异常类）

#### 8. 完善文档
- 所有函数添加 docstring
- 生成 API 文档（Swagger）
- 编写用户手册

#### 9. 单元测试
- 核心工具 wrapper 测试
- API endpoint 测试
- 前端组件测试

---

## 四、具体改进建议

### 代码结构优化

```
app/
├── core/
│   ├── fasta_utils.py        # 统一 FASTA 解析
│   ├── command_runner.py     # 统一命令执行
│   ├── phylo_pipeline.py     # 完整系统发育流程
│   ├── hmm_wrapper.py        # HMM 搜索封装
│   ├── clipkit_wrapper.py    # ClipKIT 封装
│   └── iqtree_wrapper.py     # IQ-TREE 增强封装
├── utils/
│   ├── sequence_validator.py # 序列验证工具
│   └── file_converter.py     # 格式转换工具
└── models/
    ├── project.py            # 项目数据模型
    └── task.py               # 任务状态模型
```

### 配置文件改进

```python
# config.py 增强
class Config:
    # Conda 环境
    CONDA_ENV = os.environ.get('BIOLAB_CONDA_ENV', 'bio')
    
    # 工具路径（自动检测）
    TOOLS = {
        'hmmsearch': auto_detect_tool('hmmsearch'),
        'clipkit': auto_detect_tool('clipkit'),
        'iqtree': auto_detect_tool('iqtree'),
        'mafft': auto_detect_tool('mafft'),
        'muscle': auto_detect_tool('muscle'),
    }
    
    # 默认参数
    DEFAULT_PARAMS = {
        'hmm': {'evalue': 1e-5, 'cut_ga': True},
        'blast': {'evalue': 1e-5, 'pident': 30, 'qcovs': 50},
        'mafft': {'maxiterate': 1000, 'localpair': True},
        'clipkit': {'mode': 'kpic-gappy', 'gaps': 0.9},
        'iqtree': {'m': 'MFP', 'bb': 1000, 'bnni': True},
    }
```

---

## 五、立即修复的关键 Bug

### 1. 树可视化距离计算 ✅ 
```python
# 已修复但需验证
# app/core/tree_visualizer.py line 169
dist = target.get_distance(leaf, topology_only=True)
```

### 2. BLAST 自动检测 ✅
```python
# 已修复但需验证
# app/core/blast_wrapper.py
db_type = get_db_type(database)  # 使用元数据
program = select_blast_program(query_type, db_type)
```

### 3. 序列导出路径 ❌
```python
# 需要修复
# app/routes/sequence.py
# 返回相对路径而非绝对路径
rel_path = os.path.relpath(output_file, config.RESULTS_DIR)
```

---

## 六、测试建议

### 集成测试场景

1. **完整系统发育分析流程**
   - 上传蛋白序列
   - HMM 搜索
   - BLAST 过滤
   - 比对
   - ClipKIT
   - 建树
   - 可视化

2. **大规模数据处理**
   - 1000+ 序列比对
   - 大树渲染（>500 叶子）
   - 并发任务处理

3. **错误恢复**
   - 工具不存在
   - 输入文件格式错误
   - 磁盘空间不足

---

## 七、总结

### 当前完成度评估

| 模块 | 完成度 | 主要问题 |
|------|--------|----------|
| UniProt 检索 | 70% | 交互性不足 |
| BLAST | 85% | 自动检测需验证 |
| 序列比对 | 50% | 缺工具、缺可视化 |
| 系统发育流水线 | 30% | 核心步骤缺失 |
| 树可视化 | 75% | 物种选择、距离计算 |

### 下一步行动

**立即执行**：
1. 修复树可视化距离计算
2. 实现 HMM 搜索功能
3. 添加 ClipKIT 支持

**本周内完成**：
4. 完善 IQ-TREE 参数
5. 增强序列比对工具
6. 统一 FASTA 解析逻辑

**本月内完成**：
7. 项目管理系统
8. 参数配置持久化
9. 任务队列实现
10. 完整测试覆盖

---

**生成时间**：2025-12-06
**审计人**：GitHub Copilot (Claude Sonnet 4.5)
