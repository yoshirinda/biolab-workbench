# BioLab Workbench - 系统升级总结

## 升级日期
2024年 - 基于原始 5 个 CLI 脚本的完整功能集成

## 原始脚本分析
基于以下 5 个原始脚本进行了完整的功能审计和集成:
1. `uniprot_miner_v5.4.py` - UniProt 数据挖掘
2. `blast_pipe.sh` - BLAST 管道
3. `seq_aligner.py` - 多序列比对
4. `view_clade.py` - 树可视化
5. `blast-phylo_pipeline_gui.py` - 完整系统发育流程

详细审计报告见: [AUDIT_REPORT.md](AUDIT_REPORT.md)

---

## 新增核心模块

### 1. 统一 FASTA 工具库 (`app/utils/fasta_utils.py`)
**功能**: 消除代码重复,提供统一的序列文件处理接口

**主要函数**:
- `parse_fasta()` - 解析 FASTA 文件
- `write_fasta()` - 写入 FASTA 文件
- `validate_fasta_format()` - 验证 FASTA 格式
- `filter_by_length()` - 按长度过滤序列
- `deduplicate_sequences()` - 去重
- `group_by_species()` - 按物种前缀分组
- `get_fasta_stats()` - 统计信息

**优势**: 
- 所有模块共享统一接口
- 减少 ~500 行重复代码
- 更好的错误处理

---

### 2. HMM 搜索包装器 (`app/core/hmm_wrapper.py`)
**功能**: HMMER hmmsearch 集成,支持蛋白质结构域检测

**主要函数**:
- `run_hmmsearch()` - 单个 HMM profile 搜索
- `run_hmmsearch_multi()` - 多个 profile 批量搜索
- `parse_hmmsearch_domtblout()` - 解析结果表
- `extract_hit_sequences()` - 提取匹配序列
- `get_hmm_info()` - 获取 HMM profile 信息

**特性**:
- E-value 阈值过滤
- GA (gathering threshold) 支持
- 多 profile 并行搜索
- 自动序列提取

**API 端点**:
- `POST /phylo/hmm-search` - 运行 HMM 搜索
- `GET /phylo/hmm-info/<filename>` - 获取 HMM profile 信息

---

### 3. ClipKIT 包装器 (`app/core/clipkit_wrapper.py`)
**功能**: 比对修剪,去除保守性差的区域

**主要函数**:
- `run_clipkit()` - 运行 ClipKIT 修剪
- `analyze_alignment_conservation()` - 分析保守性
- `suggest_clipkit_mode()` - 自动推荐修剪模式
- `compare_before_after_trimming()` - 修剪前后对比

**支持的模式**:
- `kpic-gappy` - 保留 parsimony-informative 和常量位点 (推荐)
- `kpic` - 只保留 parsimony-informative 和常量
- `kpi-gappy` - 保留 parsimony-informative (含 gap)
- `kpi` - 只保留 parsimony-informative
- `gappy` - 只去除全 gap 列

**智能推荐**:
- 根据 gap 百分比自动选择最佳模式
- 提供推荐理由说明

**API 端点**:
- `POST /phylo/clipkit-trim` - 运行 ClipKIT
- `POST /phylo/suggest-clipkit-mode` - 获取模式推荐

---

### 4. 增强版 IQ-TREE 包装器 (`app/core/iqtree_wrapper.py`)
**功能**: 最大似然法系统发育树构建

**主要函数**:
- `run_iqtree()` - 完整建树流程
- `run_iqtree_modelfinder()` - ModelFinder 自动模型选择
- `parse_iqtree_log()` - 解析日志文件
- `extract_bootstrap_support()` - 提取 Bootstrap 支持率
- `summarize_bootstrap_support()` - 支持率统计

**特性**:
- ModelFinder - 自动选择最佳替换模型
- UFBoot / Standard Bootstrap
- SH-aLRT 测试
- 减少分支长度相关性 (BNNI)
- Bootstrap 支持率统计分析

**API 端点**:
- `POST /phylo/iqtree-infer` - 运行 IQ-TREE
- `POST /phylo/modelfinder` - 运行 ModelFinder

---

### 5. 多工具比对包装器 (`app/core/alignment_wrapper.py`)
**功能**: 支持 MAFFT/ClustalW/MUSCLE 的统一接口

**主要函数**:
- `run_alignment()` - 统一比对接口
- `_run_mafft()` - MAFFT 实现
- `_run_clustalw()` - ClustalW 实现
- `_run_muscle()` - MUSCLE 实现 (支持 v3 和 v5)
- `select_sequences_interactive()` - 交互式序列选择
- `get_available_tools()` - 检测可用工具

**MAFFT 算法**:
- `auto` - 自动选择
- `linsi` - L-INS-i (最准确,适合<200序列)
- `ginsi` - G-INS-i (全局比对)
- `einsi` - E-INS-i (考虑扩展)

**ClustalW 参数**:
- Gap open/extension penalty
- 替换矩阵 (BLOSUM, PAM, etc.)

**MUSCLE 参数**:
- 最大迭代次数
- Diagonal optimization

**API 端点**:
- `POST /alignment/align-multi` - 多工具比对
- `POST /alignment/select-sequences` - 序列选择
- `GET /alignment/tools-check` - 检查可用工具

---

### 6. pyMSAviz 可视化包装器 (`app/core/msaviz_wrapper.py`)
**功能**: 高质量比对可视化

**主要函数**:
- `visualize_alignment_pymsaviz()` - 基础可视化
- `create_custom_visualization()` - 自定义可视化
- `visualize_alignment_region()` - 区域可视化
- `get_available_color_schemes()` - 获取配色方案

**配色方案**:
- `Zappo` - 理化性质 (默认)
- `Taylor` - Taylor 经典配色
- `Hydrophobicity` - 疏水性
- `Buried_Index` - 埋藏指数
- `Identity` - 单色
- `Clustal` - ClustalX 配色
- `Nucleotide` - 核酸配色

**输出格式**:
- PNG (默认)
- SVG (矢量)
- JPG
- PDF

**高级选项**:
- 自定义 DPI
- 序列包装 (wrap)
- 显示/隐藏一致性序列
- 网格线
- 一致性阈值调整

**API 端点**:
- `POST /alignment/visualize-pymsaviz` - 基础可视化
- `POST /alignment/visualize-custom` - 自定义可视化
- `POST /alignment/visualize-region` - 区域可视化
- `GET /alignment/pymsaviz-color-schemes` - 获取配色方案

---

### 7. 完整系统发育流程页面 (`/pipeline`)
**功能**: 一站式系统发育分析流程

**流程步骤**:
1. **HMM 搜索** - 蛋白质结构域检测
2. **BLAST 搜索** - 同源序列筛选
3. **长度过滤** - 去除异常长度序列
4. **多序列比对** - MAFFT/ClustalW/MUSCLE
5. **ClipKIT 修剪** - 去除低质量区域
6. **IQ-TREE 建树** - 最大似然法推断
7. **树可视化** - ETE3 可视化

**交互特性**:
- 步骤式界面,清晰的进度指示
- 每步完成后显示结果摘要
- 自动传递中间文件
- 智能参数推荐 (ClipKIT 模式, IQ-TREE 模型)
- 一键跳转到树可视化

**模板支持**:
- ACO 分析模板
- 快速比对模板
- 完整分析模板

---

## 功能增强

### BLAST 模块增强
✅ **修复**: 自动程序选择 - 空字符串现在正确处理为 `None`
✅ **改进**: 更好的错误提示

### 树可视化模块增强
✅ **修复**: 中心基因距离计算 - 使用 `topology_only=True` 参数
✅ **新增**: 多格式支持 (Newick/Nexus/PhyloXML)
✅ **新增**: 中心基因裁剪,可调半径
✅ **改进**: 物种前缀自动检测
✅ **改进**: 物种颜色选择 UI

### Phylo 模块全面升级
✅ **新增**: HMM 搜索端点 (单/多 profile)
✅ **新增**: ClipKIT 修剪端点
✅ **新增**: ClipKIT 模式推荐
✅ **新增**: IQ-TREE 推断端点
✅ **新增**: ModelFinder 端点
✅ **新增**: Bootstrap 支持率统计

### Alignment 模块全面升级
✅ **新增**: ClustalW 支持
✅ **新增**: MUSCLE 支持 (v3/v5)
✅ **新增**: 交互式序列选择
✅ **新增**: pyMSAviz 可视化
✅ **新增**: 自定义可视化选项
✅ **新增**: 区域可视化

---

## 技术改进

### 代码质量
- **消除重复**: 统一 FASTA 处理减少 ~500 行重复代码
- **模块化**: 每个工具独立包装器,便于测试和维护
- **错误处理**: 完善的异常捕获和用户友好的错误消息
- **日志记录**: 详细的操作日志便于调试

### 性能优化
- **并行处理**: HMM 多 profile 搜索支持并行
- **线程控制**: MAFFT/BLAST/IQ-TREE 线程数可配置
- **文件管理**: 结果按时间戳组织,避免冲突

### 用户体验
- **智能推荐**: ClipKIT 模式和 IQ-TREE 模型自动推荐
- **进度反馈**: 流程页面清晰的步骤指示
- **参数预设**: 常用参数默认值基于最佳实践
- **结果摘要**: 每步显示关键统计信息

---

## API 端点总结

### Phylo 端点 (`/phylo/*`)
```
POST /phylo/hmm-search          # HMM 搜索
GET  /phylo/hmm-info/<file>     # HMM profile 信息
POST /phylo/clipkit-trim        # ClipKIT 修剪
POST /phylo/suggest-clipkit-mode # ClipKIT 模式推荐
POST /phylo/iqtree-infer        # IQ-TREE 建树
POST /phylo/modelfinder         # ModelFinder
```

### Alignment 端点 (`/alignment/*`)
```
POST /alignment/align-multi         # 多工具比对
POST /alignment/select-sequences    # 序列选择
GET  /alignment/tools-check         # 检查可用工具
POST /alignment/visualize-pymsaviz  # pyMSAviz 可视化
POST /alignment/visualize-custom    # 自定义可视化
POST /alignment/visualize-region    # 区域可视化
GET  /alignment/pymsaviz-color-schemes # 配色方案列表
```

### Pipeline 端点 (`/pipeline/*`)
```
GET  /pipeline/                  # 流程页面
POST /pipeline/clean-headers     # 清理 FASTA 序列头, 保证安全唯一
POST /pipeline/filter-length     # 按长度过滤 FASTA
POST /pipeline/run-full          # 运行完整流程
GET  /pipeline/status/<job_id>   # 查询任务状态
GET  /pipeline/templates         # 流程模板列表
```

### 维护端点
```
POST /blast/delete-database      # 删除 BLAST 数据库及元数据
POST /sequence/delete-source-fasta # 删除源 FASTA 库条目(可选删除文件)
```

---

## 与原始脚本对比

### 功能完整度

| 功能模块 | 原始实现 | 新实现 | 状态 |
|---------|---------|--------|------|
| UniProt 下载 | ✅ | ✅ | 已完成 |
| BLAST 搜索 | ✅ | ✅ | 已完成 + 增强 |
| HMM 搜索 | ✅ | ✅ | **新增** |
| 长度过滤 | ✅ | ✅ | 已完成 |
| MAFFT 比对 | ✅ | ✅ | 已完成 |
| ClustalW 比对 | ✅ | ✅ | **新增** |
| MUSCLE 比对 | ✅ | ✅ | **新增** |
| ClipKIT 修剪 | ✅ | ✅ | **新增** |
| IQ-TREE 建树 | ✅ | ✅ | **新增** + 增强 |
| Bootstrap 分析 | ✅ | ✅ | **新增** |
| ModelFinder | ✅ | ✅ | **新增** |
| ETE3 可视化 | ✅ | ✅ | 已完成 + 增强 |
| pyMSAviz 可视化 | ✅ | ✅ | **新增** |
| 完整流程 | ✅ | ✅ | **新增** 流程页面 |

### 用户体验改进

| 方面 | 原始 CLI | 新 Web UI |
|------|---------|-----------|
| 界面 | 终端文本 | 现代化 Web UI |
| 交互 | 键盘输入 | 表单 + 按钮 |
| 可视化 | 弹出窗口 | 网页内嵌 |
| 文件管理 | 手动路径 | 自动组织 |
| 错误处理 | 终端输出 | 友好提示 |
| 多任务 | 串行执行 | 支持并发 |
| 结果保存 | 指定目录 | 自动归档 |

---

## 测试建议

### 单元测试
1. `test_fasta_utils.py` - FASTA 处理函数
2. `test_hmm_wrapper.py` - HMM 搜索
3. `test_clipkit_wrapper.py` - ClipKIT 修剪
4. `test_iqtree_wrapper.py` - IQ-TREE 建树
5. `test_alignment_wrapper.py` - 多工具比对
6. `test_msaviz_wrapper.py` - pyMSAviz 可视化

### 集成测试
1. 完整流程测试 (HMM → BLAST → 比对 → 建树)
2. 多格式支持测试 (Newick/Nexus/PhyloXML)
3. 大文件性能测试
4. 并发请求测试

### 用户验收测试
1. 重现原始 `blast-phylo_pipeline_gui.py` 的分析流程
2. 验证结果一致性
3. 测试错误恢复
4. 测试跨浏览器兼容性

---

## 部署检查清单

### 环境依赖
- [x] Python 3.8+
- [x] Flask
- [x] Biopython
- [x] ETE3
- [x] HMMER (hmmsearch)
- [x] BLAST+
- [x] MAFFT
- [ ] ClustalW (可选)
- [ ] MUSCLE (可选)
- [ ] ClipKIT
- [ ] IQ-TREE
- [ ] pyMSAviz (可选)

### 配置检查
- [x] `config.py` - 路径配置
- [x] `config.CONDA_ENV` - Conda 环境名
- [x] `config.USE_CONDA` - 是否使用 Conda
- [x] `config.HMM_PROFILES_DIR` - HMM profiles 目录
- [x] `config.GOLD_LISTS_DIR` - Gold lists 目录
- [x] `config.RESULTS_DIR` - 结果目录

### 目录结构
```
biolab-workbench/
├── app/
│   ├── core/
│   │   ├── hmm_wrapper.py          # ✅ 新增
│   │   ├── clipkit_wrapper.py      # ✅ 新增
│   │   ├── iqtree_wrapper.py       # ✅ 新增
│   │   ├── alignment_wrapper.py    # ✅ 新增
│   │   └── msaviz_wrapper.py       # ✅ 新增
│   ├── utils/
│   │   └── fasta_utils.py          # ✅ 新增
│   ├── routes/
│   │   ├── phylo.py               # ✅ 增强
│   │   ├── alignment.py           # ✅ 增强
│   │   ├── tree.py                # ✅ 增强
│   │   └── pipeline.py            # ✅ 新增
│   └── templates/
│       └── pipeline.html           # ✅ 新增
├── AUDIT_REPORT.md                # ✅ 新增
└── IMPLEMENTATION_SUMMARY.md      # ✅ 本文件
```

---

## 下一步计划

### 短期目标
1. **任务队列系统** - 长时间运行的任务后台执行
2. **进度条** - 实时显示任务进度
3. **结果缓存** - 避免重复计算
4. **批量处理** - 支持多个输入文件

### 中期目标
1. **项目管理** - 保存和恢复分析项目
2. **参数模板** - 保存常用参数配置
3. **结果比较** - 比较多次分析结果
4. **导出报告** - 生成 PDF/HTML 报告

### 长期目标
1. **用户系统** - 多用户支持和权限管理
2. **云端部署** - Docker 容器化
3. **分布式计算** - 支持集群计算
4. **机器学习** - 参数优化建议

---

## 致谢

本次升级基于以下原始脚本:
- `uniprot_miner_v5.4.py` - UniProt 数据挖掘
- `blast_pipe.sh` - BLAST 管道
- `seq_aligner.py` - 多序列比对
- `view_clade.py` - 树可视化
- `blast-phylo_pipeline_gui.py` - 系统发育流程

感谢原作者的优秀工作,为本项目提供了坚实的基础!

---

**文档版本**: 1.0
**最后更新**: 2024年
**维护者**: BioLab Workbench Team
