# 个人财务助理 · personal-finance-assistant

> 一个「**大模型理解 + 本地引擎计算**」的个人财务 Agent Skill：你把账单、截图或一句话交给它，它负责记账、出报表、看预算、追目标，并给出能落地的节流与理财建议。

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](./scripts/finance_engine.py)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](./CHANGELOG.md)

---

## 一、项目简介

个人记账的难点从来不是「记」，而是「记完之后没人帮你看」。本项目把一个完整的个人财务流程拆成两段：

| 环节 | 负责方 | 职责 |
|------|--------|------|
| **理解** | 大模型 / Agent | 从截图、PDF、CSV、自然语言（「今天星巴克 38」）中抽取结构化交易，并用自然语言解读报表、给出建议 |
| **计算** | `scripts/finance_engine.py` | 纯本地的确定性计算：分类兜底、多币种换算、账本持久化、报表与反推求解 |

这个分工带来两个关键性质：

1. **结果可复现、可审计**——金额、储蓄率、业绩门槛都由脚本算出来，不依赖模型的「心算」。
2. **数据不出本机**——引擎没有任何网络请求、不接银行 API、不依赖任何第三方服务，所有账目只是你本地目录里的一个 CSV 和几个 JSON。

引擎为**零依赖纯标准库**实现（仅 `argparse / csv / json / pathlib`），Python 3.8+ 直接可跑，无需 `pip install`。

---

## 二、核心功能

| 能力 | 说明 | 子命令 |
|------|------|--------|
| 收支录入 | 支持 JSON / CSV / 自由文本三种输入，自动分类 | `add` |
| 交易查询 | 按账户 / 分类 / 币种 / 日期区间筛选 | `list` |
| 消费分析 | 月 / 季 / 年报表，含储蓄率、分类、账户、币种四个维度 | `report` |
| 预算执行 | 按分类设月度限额，报表内直接标注超支 | `budget` |
| 目标追踪 | 储蓄与债务目标的进度条、剩余额、每月所需 | `goal` |
| 多币种 | ISO 4217 币种 + 可配置汇率表，换算值录入时冻结 | `rate` |
| 基金持仓 | 申购登记、净值更新、市值 / 收益 / 收益率 | `fund` |
| 基金定投 | 建计划、暂停恢复、按月幂等执行（按净值算份额） | `dca` |
| 资产配置 | low/medium/high 三档配置表 + 现有持仓再平衡对照 | `allocate` |
| 薪酬建模 | 底薪 / 阶梯提成 / 达标奖 / 阶梯奖 / 固定扣除 | `comp` |
| 目标规划 | 由目标金额反推所需业绩门槛与工作节奏 | `plan` |

### 适用场景

- **懒人记账**：不想装 App，直接把支付宝/微信/银行账单截图或 CSV 丢给智能体。
- **月度复盘**：每月自动出一份消费报告 + 三条可执行建议（而不只是一堆数字）。
- **攒钱目标**：旅行基金、买房首付、信用卡清债的进度与节奏提醒。
- **外币场景**：美元工资、海淘、留学消费，按发生时的汇率入账。
- **基金定投**：每月固定日扣款的定投执行纪律，配合资产配置比例。
- **销售/业绩岗**：按自己的薪酬结构反推「想一年存 30 万，每月得做多少业绩」。

> 不适用场景：需要对接银行 API 自动同步流水、需要实时行情与自动抓净值、需要多人协作账本、需要精确个税/社保计算。

---

## 三、安装

### 方式 A：作为 Agent Skill 安装（推荐）

本仓库遵循通用 **Agent Skills** 规范（根目录下 `SKILL.md` + `scripts/` + `references/` + `assets/`），可直接放进任意兼容该规范的智能体运行时：

```bash
# Claude Code / 通用 Agent Skills 运行时
git clone https://github.com/2072229241/personal-finance-assistant.git \
  ~/.claude/skills/personal-finance-assistant

# WorkBuddy 用户
git clone https://github.com/2072229241/personal-finance-assistant.git \
  ~/.workbuddy/skills/personal-finance-assistant
```

安装后直接用自然语言驱动即可：「记一笔今天午饭 38」「生成本月消费报告」。

### 方式 B：当作命令行工具单独使用

```bash
git clone https://github.com/2072229241/personal-finance-assistant.git
cd personal-finance-assistant
python3 scripts/finance_engine.py --version      # 验证可用，输出 finance_engine 1.0.0
```

零依赖，无需虚拟环境。也可以把它加入 PATH：

```bash
ln -s "$(pwd)/scripts/finance_engine.py" /usr/local/bin/finance
finance --help
```

**要求**：Python 3.8 及以上（macOS / Linux / Windows 均可）。

---

## 四、快速开始

以下示例假定你把引擎路径存成变量（按需替换其中一种）：

```bash
ENGINE="python3 ./scripts/finance_engine.py"                                        # 仓库内直接跑
ENGINE="python3 ~/.claude/skills/personal-finance-assistant/scripts/finance_engine.py"  # 安装为 skill 后
```

### 1. 记三笔账

```bash
$ENGINE add --json '[
  {"date":"2026-10-01","account":"招行储蓄卡","currency":"CNY","amount":12000,
   "category":"收入","merchant":"公司","note":"10月工资"},
  {"date":"2026-10-03","account":"支付宝","currency":"CNY","amount":-38.5,
   "merchant":"星巴克","note":"咖啡"},
  {"date":"2026-10-08","account":"美元信用卡","currency":"USD","amount":-50,
   "merchant":"Amazon","note":"海淘"}
]'
```

输出：

```
✅ 已录入 3 笔交易到 ~/.personal-finance-assistant/ledger.csv
  #1 2026-10-01 [招行储蓄卡] 收入 CNY 12000.0 → CNY 12000.0 | 收入 | 公司 (置信度 1.0)
  #2 2026-10-03 [支付宝] 支出 CNY -38.5 → CNY -38.5 | 餐饮 | 星巴克 (置信度 0.7)
  #3 2026-10-08 [美元信用卡] 支出 USD -50.0 → CNY -355.0 | 购物 | Amazon (置信度 0.7)
```

> 置信度 1.0 = 你（或 Agent）显式给出了 `category`，0.7 = 由关键词兜底判定。
> USD 那笔按内置汇率 7.10 换算为 −355.00 CNY 入账。

### 2. 出本月报表

```bash
$ENGINE report --period month --when 2026-10
$ENGINE report --period quarter --when 2026-4
$ENGINE report --period year    --when 2026
```

### 3. 设预算、建目标

```bash
$ENGINE budget set 餐饮 500
$ENGINE goal add --type savings --name "旅行基金" --amount 30000 --date 2027-10-01 --current 8000
```

### 4. 一句话跑通全流程

仓库内提供了可执行的示例脚本，直接照抄改数即可：

```bash
cp assets/ledger_template.csv ~/my-ledger.csv      # 可选：拿到空账本模板
./examples/quickstart.sh                            # 在临时目录演示完整链路
```

---

## 五、目录结构

```
personal-finance-assistant/
├── SKILL.md                  # Skill 主入口（frontmatter 元数据 + 触发条件 + 工作流 + 资源索引）
├── README.md                 # 你正在看的这份说明
├── LICENSE                   # MIT 许可证
├── CHANGELOG.md              # 版本记录（遵循 Keep a Changelog）
├── CONTRIBUTING.md           # 贡献指南
├── Makefile                  # 常用任务入口（make test / make install / make clean）
├── assets/
│   └── ledger_template.csv   # 空账本模板，表头即引擎可识别的列
├── scripts/
│   └── finance_engine.py     # 核心引擎，零依赖，全部子命令在此
├── references/               # 供 Agent 按需渐进加载的知识文档
│   ├── schema.md             # 数据模型：交易/预算/汇率/目标/基金/定投/薪酬的字段与格式
│   ├── category_keywords.md  # 自动分类关键词字典与金额符号约定
│   ├── report_templates.md   # 报表结构、各区块含义、资产配置方案模板
│   ├── advice.md             # 节流/理财/目标节奏/定投的建议启发式
│   ├── fund_selection.md     # 选基方法论、资产配置模型、定投策略与风险提示
│   ├── comp_planning.md      # 薪酬抽取、目标换算、业绩反推与工作规划方法论
│   └── multi_currency.md     # 多币种识别、换算冻结与多账户规则
├── examples/
│   ├── sample_transactions.json  # add --json 的输入样例
│   ├── sample_import.csv         # add --csv 的输入样例
│   └── quickstart.sh             # 端到端演示脚本
├── tests/
│   └── test_engine.sh        # 冒烟测试：覆盖主要子命令，make test 调用
└── docs/
    └── PUBLISHING.md         # 维护者：从创建仓库到推送代码的步骤
```

**为什么这样组织**：`SKILL.md` 保持精简，只放触发条件与工作流骨架；细节文档放在 `references/`，由 Agent 在需要时按需读取，避免一次性占用过多上下文——这是 Agent Skills 的渐进式披露（progressive disclosure）约定。

---

## 六、配置参数

### 全局参数

| 参数 | 说明 |
|------|------|
| `--data-dir <DIR>` | 数据目录。也可用环境变量 `FINANCE_DATA`。默认 `~/.personal-finance-assistant/` |
| `--version` | 输出引擎版本 |
| `--help` | 查看帮助 |

### 数据目录下生成的文件

| 文件 | 内容 |
|------|------|
| `ledger.csv` | 账本，每笔收支一行（追加写入，可跨会话累计） |
| `rates.json` | 汇率表：`{"base":"CNY","rates":{"CNY":1.0,"USD":7.10,...}}` |
| `budgets.json` | 按分类的月度限额 |
| `goals.json` | 储蓄 / 债务目标 |
| `funds.json` | 基金持仓（份额、本金、净值） |
| `dca_plans.json` | 定投计划 |
| `comp.json` | 薪酬结构 |

### 常用参数速查

```bash
# 录入：--json（数组或单个对象） / --csv（文件） / --text（兜底自由文本）
add        --json '<[{...}]>' | --csv <file> | --text '今天买菜 -58'
# 查询：--account --category --currency --since --until --limit
list       --since 2026-10-01 --category 餐饮 --limit 20
# 报表：--period month|quarter|year，--when 指定周期
report     --period month --when 2026-10
# 预算
budget     set <分类> <月度限额> | list
# 目标
goal       add --type savings|debt --name <名> --amount <额> --date <YYYY-MM-DD> [--current <已攒>]
           update --id <n> [--current <已攒/剩余>] [--date <日>] [--note <备注>]
           delete --id <n> | list
# 汇率
rate       set <币种> <值> [--base <基准币>] | list
# 基金
fund       add --code <代码> [--name <名>] [--type <类型>] --amount <金额> [--nav <净值>] [--shares <份额>]
fund       update --code <代码> --nav <最新净值> [--nav-date YYYY-MM-DD]
fund       list
# 定投
dca        add --code <代码> --amount <月投额> --account <扣款账户> [--day <日>] [--start <YYYY-MM-DD>]
dca        list | pause --id <n> | resume --id <n> | execute [--month YYYY-MM]
# 资产配置
allocate   --monthly <每月可投> --risk low|medium|high [--assets <可配总资产>]
# 薪酬
comp       set --json '<结构>' | set --base <底薪> --rate <提成率> --deductions <扣除> | show
# 目标规划
plan       --target-income <目标净收入>
           --goal-amount <总额> --months <月数> [--monthly-expense <月开销>]
           [--avg-deal <客单价>] [--workdays <工作日数>]
```

### 约定速记

- **金额符号**：收入为正、支出为负。文本含「工资/退款/收入」判为正，「花/付/买/还款」判为负。
- **标准分类（11 类）**：餐饮 · 交通 · 居住 · 购物 · 娱乐 · 医疗健康 · 教育 · 人情社交 · 金融 · 收入 · 其他。
- **币种**：ISO 4217，内置 CNY/USD/EUR/JPY/GBP/HKD 的参考汇率（**仅作占位，请自行更新**）。
- **汇率冻结**：录入时的汇率写入 `fx_rate` 并锁定，之后改汇率不影响历史记录。

---

## 七、示例用法

### 场景 A：导入 CSV 账单

```bash
# examples/sample_import.csv 的列名与账本一致，可直接导入
$ENGINE add --csv examples/sample_import.csv
$ENGINE list --since 2026-10-01 --limit 10
```

### 场景 B：多币种

```bash
$ENGINE rate set USD 7.20            # 1 USD = 7.20 CNY
$ENGINE rate set JPY 0.048
$ENGINE add --json '[{"date":"2026-10-12","account":"美元信用卡","currency":"USD",
                      "amount":-120,"merchant":"Hotel","note":"东京住宿"}]'
$ENGINE report --period month --when 2026-10     # 「币种维度（原币）」区块可核对账单
```

### 场景 C：储蓄目标与偿债目标

```bash
$ENGINE goal add --type savings --name "旅行基金" --amount 30000 --date 2027-10-01
$ENGINE goal add --type debt    --name "信用卡欠款" --amount 20000 --current 20000 --date 2027-06-30
$ENGINE goal update --id 1 --current 12500
$ENGINE goal list
```

进度更新后输出含进度条与节奏提醒（「剩 N 个月」随运行日期变化）：

```
#1 旅行基金（储蓄）
  [████████░░░░░░░░░░░░] 41.7%
  进度：12500.00 / 30000.00 CNY | 剩余：17500.00
  目标日：2027-10-01（剩 12 个月） | 需每月 1458.33
```

### 场景 D：基金定投与资产配置

```bash
# 1) 登记申购（份额 = 金额 ÷ 净值，自动记一笔「金融/申购」支出）
$ENGINE fund add --code 110011 --name "易方达中小盘混合" --type 混合型 --amount 10000 --nav 3.45

# 2) 建定投计划，每月 5 日扣款
$ENGINE dca add --code 110011 --name "易方达中小盘混合" --amount 1000 \
                --account 招行储蓄卡 --day 5 --start 2026-11-01

# 3) 先更新净值，再按月执行（同月重复执行会自动跳过）
$ENGINE fund update --code 110011 --nav 3.52
$ENGINE dca execute --month 2026-11

# 4) 看配置与再平衡
$ENGINE allocate --monthly 3000 --risk medium --assets 50000
$ENGINE fund list
```

### 场景 E：按薪酬结构反推业绩门槛

```bash
# 1) 一次性配好薪酬结构（阶梯提成 + 达标奖 + 固定扣除）
$ENGINE comp set --json '{
  "period":"month","base":5000,
  "commission":[{"up_to":100000,"rate":0.05},
                {"up_to":200000,"rate":0.08},
                {"up_to":null,   "rate":0.12}],
  "bonus":[{"type":"target","threshold":200000,"amount":8000}],
  "deductions":1000,"currency":"CNY"}'

# 2) 问：一年存 30 万（月开销 8000），每月得做多少业绩？
$ENGINE plan --goal-amount 300000 --months 12 --monthly-expense 8000 \
             --avg-deal 5000 --workdays 22
```

输出：

```
# 🎯 目标规划 · 业绩反推（目标 300000.00 在 12 个月内达成（含月开销 8000.00） → 每月需净收入 33000.00）

## 达成目标所需业绩门槛：266,666.67 CNY（/month）

## 对应收入说明（在该业绩下）
- 底薪：5000.00
- 提成（业绩 0–100,000，5.0%）：5,000.00
- 提成（业绩 100,000–200,000，8.0%）：8,000.00
- 提成（业绩 200,000–∞，12.0%）：8,000.00
- 奖金：8,000.00
- 扣除（社保/税等）：-1000.00
- **净收入合计：33,000.00**（目标 33,000.00）

## 工作规划参考（按平均客单价 5,000.00）
- 需成交约 53 单/month
- 日均业绩目标：12,121.21；日均约 2.4 单（按 22 个工作日）

## 业绩—收入对照
- 业绩 213,333 → 净收入 26,600.00
- 业绩 266,667 → 净收入 33,000.00
- 业绩 320,000 → 净收入 39,400.00
```

> 门槛是「理论最小值」。实操建议按 110%–120% 设行动线：本例把月行动线设在 30 万左右更安全。

### 与智能体配合时的完整链路

```
截图 / PDF / CSV / 一句话
        ↓  [Agent 抽取]  产出规范交易 JSON（date/account/currency/amount/category/merchant/note）
        ↓  [引擎落盘]    add --json → ledger.csv（校验、分类兜底、换算、写入）
        ↓  [引擎出报表]  report / budget / goal / fund / dca / allocate / plan
        ↓  [Agent 解读]  叠加对话式建议（异常点、历史对比、下一步动作）
```

---

## 八、常见问题

<details>
<summary><b>我的账本存在哪里？能换位置吗？</b></summary>

默认在 `~/.personal-finance-assistant/`。三种改法任选其一：

```bash
export FINANCE_DATA=~/Documents/my-finance     # 环境变量，持久化建议写进 ~/.zshrc / ~/.bashrc
$ENGINE --data-dir ~/Documents/my-finance report --period month   # 单次指定
```

多账本（如家庭账与个人账分开）用 `--data-dir` 切换即可。
</details>

<details>
<summary><b>我的账单数据会被上传吗？</b></summary>

不会。引擎是纯本地脚本，代码里没有任何网络请求、日志上报或第三方依赖（可自行 `grep -rE "requests|urllib|http" scripts/` 验证）。数据仅以 CSV / JSON 明文存在本机，便于你自己备份或用 Git 私有仓库管理。
</details>

<details>
<summary><b>汇率是实时的吗？</b></summary>

不是。`rates.json` 里的 CNY/USD/EUR/JPY/GBP/HKD 只是**占位参考值**，请按实际需要更新：

```bash
$ENGINE rate set USD 7.24
```

汇率在录入时写入 `fx_rate` 并冻结，更新汇率只影响之后的记录，不会改写历史——这样可以保证历史趋势口径一致。大额跨币决策前请自行核实实时汇率。
</details>

<details>
<summary><b>分类错了怎么改？</b></summary>

引擎只做关键词兜底分类。要纠正某笔，直接以显式分类重新录入该笔并删除旧记录，也可用文本编辑器打开 `ledger.csv` 直接改 `category` 列。若希望长期生效，把「商户 → 分类」的个性化规则告诉你的 Agent，它会在抽取阶段优先应用。
</details>

<details>
<summary><b>净值为什么必须手动填？</b></summary>

引擎刻意不接入任何行情接口，以保证离线可用与数据主权。净值可以由你手动 `fund update --nav` 写入，也可以让 Agent 通过联网搜索公开净值后代填。定投执行前必须保证对应基金有净值，否则该计划会被跳过并提示。
</details>

<details>
<summary><b>能直接导入支付宝 / 微信账单吗？</b></summary>

能，但需要先转成引擎认识的列名（`date,account,currency,amount,category,merchant,note`）：

```bash
$ENGINE add --csv ./wechat_bill.csv
```

多数导出的账单列名不同，最省事的做法是把原始 CSV 直接丢给你的 Agent，让它做列名映射与方向判断。
</details>

<details>
<summary><b>跨账户转账会重复计入消费吗？</b></summary>

按约定，跨账户转账记为两笔（A 账户支出、B 账户收入），`merchant` 标注「转账」。这样两个账户余额都对得上，且因为一正一负，不会虚增总支出。
</details>

<details>
<summary><b>plan 提示「不可行」是什么意思？</b></summary>

说明按当前薪酬结构，即使业绩做到极大也达不到目标净收入，引擎会给出封顶收入。处理方式：调高底薪/提成率、降低目标金额、或延长达成月数。
</details>

<details>
<summary><b>定投同月执行了两次会重复扣款吗？</b></summary>

不会。`dca execute` 记录 `last_executed` 月份，同月重复执行会跳过并提示。
</details>

<details>
<summary><b>可以直接把账本提交到 Git 吗？</b></summary>

技术上可以，但**强烈不建议提交到公开仓库**——账本包含你的真实收支。本仓库的 `.gitignore` 默认忽略数据目录；若你在本仓库内测试，请使用 `--data-dir /tmp/...`。
</details>

---

## 九、贡献方式

欢迎提 Issue 和 PR。请先阅读 [CONTRIBUTING.md](./CONTRIBUTING.md)，要点如下：

1. **Fork → 新建分支**（`feat/xxx`、`fix/xxx`、`docs/xxx`）。
2. **改动脚本必须补测试**：在 `tests/` 下补一条冒烟用例，并保证 `make test` 通过。
3. **保持零依赖**：不要引入任何第三方包，引擎必须能在裸 Python 3.8 下运行。
4. **文档与代码同步改**：`references/` 里的格式约定与 `scripts/` 的实现必须一致。
5. **Commit 信息**建议遵循 [Conventional Commits](https://www.conventionalcommits.org/)（`feat:` / `fix:` / `docs:`）。
6. 提交 PR 时说明：改了什么、为什么要改、如何验证。

**最需要的几类贡献**：更多账单格式（银行/支付宝/微信/信用卡）的导入样例、更细的分类关键词、报表的图表输出、英文版文档、以及 Windows 路径兼容性的验证。

---

## 十、开源许可

本项目基于 **MIT License** 开源，详见 [LICENSE](./LICENSE)。你可以自由使用、修改、分发，包括商用，仅需保留版权声明。

### 免责声明

本项目是**个人记账与规划工具**，不是持牌金融服务：

- 内置汇率为人工维护的近似值，非实时行情；
- 所有理财、选基、节流建议均为通用参考，**不构成投资、税务或法律意见**；
- 基金净值会波动，历史业绩不代表未来表现，不承诺任何收益；
- 涉及高息债务、大额资产配置或税务筹划，请咨询持牌专业人士。

---

## 附：维护者发布流程

从创建 GitHub 仓库到推送代码的完整命令，见 [docs/PUBLISHING.md](./docs/PUBLISHING.md)。
