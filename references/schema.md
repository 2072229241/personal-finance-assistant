# 数据模型与 schema（个人财务助理）

本文件定义 skill 使用的所有数据结构。引擎脚本 `scripts/finance_engine.py` 按此规范读写；
Agent 在从截图 / 自由文本中抽取交易时，也应产出与此一致的字段。

---

## 1. 规范交易（Canonical Transaction）

每一笔收支都归一化为以下字段。金额统一为**带符号浮点数**：收入为正、支出为负。

| 字段         | 类型    | 必填 | 说明 |
|--------------|---------|------|------|
| `id`         | int     | 自动 | 账本内唯一自增编号 |
| `date`       | string  | 是   | 交易日期 `YYYY-MM-DD` |
| `account`    | string  | 是   | 账户名（支持多账户，如「招行储蓄卡」「支付宝」「美元信用卡」「现金」） |
| `currency`   | string  | 是   | 币种代码（ISO 4217：CNY/USD/EUR/JPY/GBP/HKD…） |
| `amount`     | number  | 是   | 原币金额，**带符号**（收入 + / 支出 −） |
| `amount_base`| number  | 自动 | 换算到基准币种后的金额（带符号），`= amount × fx_rate` |
| `fx_rate`    | number  | 自动 | 录入时所用汇率（1 原币 = ? 基准币） |
| `category`   | string  | 是   | 分类（见第 4 节标准分类） |
| `subcategory`| string  | 否   | 子类（可选，细化分类） |
| `merchant`   | string  | 否   | 商户 / 收款方 |
| `note`       | string  | 否   | 备注 |
| `confidence` | number  | 自动 | 分类置信度 0–1（显式分类=1.0，关键词命中=0.7，兜底=0.3） |

### 账本文件（ledger.csv）
- 路径默认 `~/.personal-finance-assistant/ledger.csv`（可用 `--data-dir` 或环境变量 `FINANCE_DATA` 覆盖）。
- 表头即上表全部列；引擎以追加方式写入，可跨会话累计。
- 可直接用 `assets/ledger_template.csv` 作为空模板手动填充。

### 录入输入格式（add 子命令）
- `--json`：JSON 数组，元素含 `date/account/currency/amount/category/merchant/note` 等键
  （键名兼容中英文别名，如 `金额`/`amt`、`账户`/`acc`、`商户`/`payee`）。
- `--csv`：CSV 文件，列名同上。
- `--text`：极简自由文本兜底解析（仅用于 LLM 抽取失败时的应急）。

---

## 2. 预算（budgets.json）
- 结构：`{ "<分类>": <月度限额(基准币种)> }`
- 示例：`{ "餐饮": 500, "购物": 2000 }`
- 命令：`finance_engine.py budget set <分类> <金额>`

---

## 3. 汇率（rates.json）
- 结构：`{ "base": "CNY", "rates": { "CNY": 1.0, "USD": 7.1, ... } }`
- `rates[x]` 表示「1 单位 x 币种 = ? 基准币种」。
- 命令：`finance_engine.py rate set <币种> <值> [--base <基准币>]`
- **换算冻结原则**：`fx_rate` 在录入时按当时汇率写入并锁定，保证历史趋势一致；
  若后续更新汇率，仅影响新录入交易，不回溯改写历史 `amount_base`。

---

## 4. 目标（goals.json）
- 数组，每个目标：
  ```
  {
    "id": int,
    "type": "savings" | "debt",
    "name": string,
    "target_amount": number,   // 储蓄目标金额 / 债务初始金额（基准币种）
    "target_date": "YYYY-MM-DD",
    "current_amount": number,  // 储蓄：已攒；债务：剩余未还
    "start_amount": number,    // 债务初始金额（用于计算偿债进度）
    "currency": string,
    "note": string
  }
  ```
- 进度计算：
  - 储蓄：`进度% = current / target`；剩余 = `target − current`。
  - 债务：`偿债% = (start − current) / start`；剩余 = `current`（向 0 收敛）。
- 命令：`finance_engine.py goal add/update/delete/list`

---

## 5. 基金持仓（funds.json）
- 数组，每支基金一条：
  ```
  {
    "code": "110011",            // 基金代码
    "name": "易方达中小盘混合",
    "type": "混合型",             // 货币型/债券型/指数型/股票型/混合型/QDII/ETF
    "shares": 2898.55,           // 持有份额
    "principal": 10000.00,       // 累计投入本金（申购+定投）
    "nav": 3.60,                 // 最新单位净值（用户或 LLM 提供）
    "nav_date": "2026-10-30",
    "auto_dca": true             // 是否纳入月度定投计划
  }
  ```
- 市值 = `shares × nav`；收益 = 市值 − 本金；收益率 = 收益 ÷ 本金。
- 命令：`finance_engine.py fund add / update / list`（人民币计价，单位为元）。

## 6. 定投计划（dca_plans.json）
- 数组，每个计划：
  ```
  {
    "id": int,
    "code": "510300",
    "name": "沪深300ETF",
    "amount_per_month": 1000.00,  // 每月定投金额（元）
    "source_account": "招行储蓄卡",
    "day_of_month": 5,            // 每月扣款日
    "start_date": "2026-11-01",
    "status": "active",           // active / paused
    "last_executed": "2026-10"    // 最近执行月份，防止重复
  }
  ```
- 执行：`finance_engine.py dca execute [--month YYYY-MM]`，对每支 active 计划按当时
  `nav` 计算份额并入账（写入 ledger 的「金融/定投」支出，更新 funds 持仓）。同月重复执行自动跳过。
- 命令：`finance_engine.py dca add / list / pause / resume / execute`。

## 7. 资产配置预设（allocate）
- 按风险等级 low/medium/high 给出资产类别目标比例（合计 100%），对应建议基金类型：
  货币型(应急) / 债券型(固收+) / 指数型(宽基) / 混合型+股票型(主动行业) / QDII(海外)。
- 命令：`finance_engine.py allocate --monthly <每月可投> --risk <等级> [--assets <总资产>]`
- 传入 `--assets` 时输出「当前持仓 vs 目标」的再平衡对照（按基金 type 聚合）。

## 8. 薪酬结构与目标规划（comp.json）

- 用户的薪酬结构（持久化，配置一次即可反复用于目标反推）：
  ```
  {
    "period": "month",           // month / quarter / year
    "base": 5000.00,             // 底薪
    "commission": [              // 阶梯提成（累进），按业绩区间
      {"up_to": 100000, "rate": 0.05},
      {"up_to": 200000, "rate": 0.08},
      {"up_to": null,    "rate": 0.12}   // null = 无上限
    ],
    "bonus": [                   // 奖金规则（随业绩非递减）
      {"type": "target", "threshold": 200000, "amount": 8000},  // 达标一次性
      {"type": "tiered", "tiers": [{"perf": 300000, "amount": 10000}]}  // 取已达档最高额
    ],
    "deductions": 1000.00,        // 社保/税等固定扣除
    "currency": "CNY"
  }
  ```
- 计算公式：`净收入 = 底薪 + 阶梯提成(业绩) + 奖金(业绩) − 扣除`。
- 反推：给定目标净收入，因收入随业绩单调非递减，用二分法求最小业绩门槛（见
  `scripts/finance_engine.py` 的 `required_performance`）。
- 命令：`finance_engine.py comp set / show`（配置/查看）、`plan`（反推业绩）。

## 9. 标准分类体系（11 类）
餐饮 · 交通 · 居住 · 购物 · 娱乐 · 医疗健康 · 教育 · 人情社交 · 金融 · 收入 · 其他

分类关键词映射见 `references/category_keywords.md`。
