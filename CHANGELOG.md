# Changelog

## [Latest] - 2024

### Fixed
- 修复下载功能 404 错误：下载路由现在使用查询参数 `?path=...` 而不是路径参数
  - 更新 `/phylo/download` 路由从 `<path:filepath>` 改为查询参数格式
  - 前端 `downloadLink()` 函数生成的 URL 格式现在与后端匹配

### Enhanced
- 添加 BLAST 过滤统计信息（参考原始脚本 blast-phylo_pipeline_gui.py）
  - `step2_5_blast_filter()` 现在返回详细统计：total_in, kept, deleted, deleted_ids[]
  - 生成过滤日志文件 `step2_5_blast_filter.log` 包含完整的删除 ID 列表
  - 前端显示过滤摘要和前10条删除的序列 ID

- 添加长度过滤统计信息（参考原始脚本）
  - `step2_8_length_filter()` 现在返回详细统计：threshold, kept, deleted, deleted_with_lengths[]
  - 生成过滤日志文件 `step2_8_length_filter.log` 包含完整的删除序列及长度
  - 前端显示过滤摘要和前10条删除的序列（带长度信息）

- 在 pipeline.html 中添加 BLAST Filter (Step 2.5)
  - 用户可以根据 Gold Standard List 过滤 BLAST 结果
  - 支持 pident (identity) 和 qcovs (coverage) 阈值设置
  - 显示详细的过滤统计和删除序列列表

### Changed
- 合并重复的 Phylo 界面
  - phylo.html (旧 tab 界面) → pipeline.html (新 step-by-step 界面)
  - `/phylo/` 路由现在渲染 `pipeline.html` 而不是 `phylo.html`
  - 导航栏移除重复的 "Pipeline" 链接，只保留 "Phylo" 链接
  - 所有 phylo 功能现在通过统一的 pipeline.html 界面访问

### Updated
- 更新 `/phylo/run-step` 路由处理新的统计返回值
  - Step 2.5 (BLAST filter) 和 Step 2.8 (length filter) 现在返回 4 个值
  - 路由自动检测返回值数量并提取 stats 字段
  - 统计信息通过 JSON response 的 `stats` 字段传递给前端

- 更新 `/pipeline/filter-length` 路由
  - 现在调用 `step2_8_length_filter()` 而不是简单的 `filter_by_length()`
  - 返回完整的统计信息以匹配原始脚本功能

## Notes
所有更改都保留了原始 blast-phylo_pipeline_gui.py 脚本的核心功能，确保：
- 过滤统计信息格式与原始脚本一致
- 日志文件记录详细的删除序列信息
- 用户体验通过单一、清晰的界面得到改善
