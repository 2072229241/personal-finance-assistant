# 更新日志

本项目所有值得注意的变更都记录在此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。当前版本与 `SKILL.md` frontmatter 及
`scripts/finance_engine.py` 中的 `__version__` 保持一致。

## [1.0.0] - 2026-10-30

开源首发版本。

### 新增

- 财务引擎 `scripts/finance_engine.py`，零第三方依赖，提供 11 组子命令：
  `add` / `list` / `report` / `budget` / `goal` / `rate` / `fund` / `dca` / `allocate` / `comp` / `plan`。
- 收支录入支持 `--json` / `--csv` / `--text` 三种输入，自动分类与多币种换算。
- 月/季/年消费分析报表，含储蓄率、分类、账户、币种四个维度与预算执行标注。
- 储蓄与债务目标追踪（进度条、剩余额、每月所需节奏）。
- 基金持仓管理、定投计划与按月幂等执行、三档风险偏好的资产配置与再平衡对照。
- 薪酬结构建模与「由目标反推业绩门槛」的目标规划能力。
- `references/` 知识文档 6 份，`assets/ledger_template.csv` 空账本模板。
- 冒烟测试 `tests/test_engine.sh`、端到端示例 `examples/quickstart.sh`。

### 变更

- 数据目录默认值由特定产品的配置路径改为中立的 `~/.personal-finance-assistant/`，
  原路径可通过 `--data-dir` 或环境变量 `FINANCE_DATA` 指定。
- 移除 SKILL.md 中与特定运行环境绑定的私有元数据字段，frontmatter 改为通用元数据
  （`version` / `license` / `tags` / `allowed-tools`）。
- 文档中的平台专有表述与检索工具名改为通用说法，便于在任意 Agent 运行时中使用。

### 修复

- 修复 `goal update --current <金额>` 被解析但不生效的问题（进度更新后仍显示旧值）；
  `--amount` 保留为等价别名。
- 修复自由文本金额解析中符号被重复取反的问题：「今天买菜 -58」此前会被记为收入 +58。
- 账本模板去除 BOM 头（BOM 会导致 CSV 首列名解析为 `\ufeffid`）。
- 移除引擎中一处重复的章节注释。
