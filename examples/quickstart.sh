#!/usr/bin/env bash
#
# 端到端示例：在临时数据目录中跑通「记账 → 报表 → 预算 → 目标 → 基金定投 → 资产配置 → 目标规划」
# 全程不触碰你的真实账本，结束后自动清理临时目录。
#
# 用法：./examples/quickstart.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="$REPO_ROOT/scripts/finance_engine.py"
DATA_DIR="$(mktemp -d)/quickstart-finance"

E="python3 $ENGINE --data-dir $DATA_DIR"

step() { printf '\n\033[1;36m▶ %s\033[0m\n' "$1"; }

step "0. 环境检查（数据目录：${DATA_DIR}）"
python3 "$ENGINE" --version

step "1. 记 5 笔账（工资 / 咖啡 / 房租 / 海淘 / 外卖）"
$E add --json "$(cat "$REPO_ROOT/examples/sample_transactions.json")"

step "2. 再导入一份 CSV 账单"
$E add --csv "$REPO_ROOT/examples/sample_import.csv"

step "3. 设置月度预算"
$E budget set 餐饮 500
$E budget set 购物 2000
$E budget set 居住 3000

step "4. 建立储蓄目标"
$E goal add --type savings --name "旅行基金" --amount 30000 --date 2027-10-01 --current 8000
$E goal update --id 1 --current 12500

step "5. 维护汇率"
$E rate set USD 7.20

step "6. 生成 2026 年 10 月消费报告"
$E report --period month --when 2026-10

step "7. 基金持仓与定投"
$E fund add --code 110011 --name "易方达中小盘混合" --type 混合型 --amount 10000 --nav 3.45
$E dca add --code 110011 --name "易方达中小盘混合" --amount 1000 \
   --account 招行储蓄卡 --day 5 --start 2026-11-01
$E fund update --code 110011 --nav 3.52
$E dca execute --month 2026-11
$E dca execute --month 2026-11   # 同月重复执行会被跳过
$E fund list

step "8. 月度资产配置方案"
$E allocate --monthly 3000 --risk medium --assets 50000

step "9. 薪酬结构与业绩门槛反推"
$E comp set --json '{
  "period":"month","base":5000,
  "commission":[{"up_to":100000,"rate":0.05},
                {"up_to":200000,"rate":0.08},
                {"up_to":null,   "rate":0.12}],
  "bonus":[{"type":"target","threshold":200000,"amount":8000}],
  "deductions":1000,"currency":"CNY"}'
$E plan --goal-amount 300000 --months 12 --monthly-expense 8000 --avg-deal 5000 --workdays 22

step "10. 查询账本"
$E list --limit 5

step "完成"
rm -rf "$(dirname "$DATA_DIR")"
echo "✅ 演示结束，临时数据目录已清理"
