# Aider Conventions — 数据统计分析智能体

# 将此文件作为 Aider 的 conventions 文件加载：
# aider --conventions CONVENTIONS.md
# 或在 .aider.conf.yml 中配置 conventions 路径

---

## 项目说明

这是一个基于 Python 的数据统计分析智能体。所有统计计算必须由 scipy/statsmodels 执行，AI 只负责解释结果和生成报告。

## 关键路径

- 脚本目录：`C:\Users\NBLYX\Desktop\stat_agent\`
- 入口脚本：`main.py`（一键运行 data_loader → profiler → analysis → charts）
- 输出目录：`outputs/<timestamp_filename>/`
  - `data_profile.json` — 字段画像
  - `stats_results.json` — 统计推断结果
  - `charts/` — 可视化图表

## AI 行为约束

### DO
- 收到分析请求时先执行 `python main.py <file>`
- 基于 data_profile.json 提出分析问题
- 基于 stats_results.json 写报告
- 每个统计量引用 JSON 中的真实值
- 生成包含 7 章的标准报告

### DON'T
- 不要直接生成 p 值/t 值/F 值/R²
- 不要编造"数据表明..."
- 不要把相关性写成因果关系
