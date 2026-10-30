#!/usr/bin/env bash
#
# 冒烟测试：验证各子命令可用且与文档约定一致。
# 使用临时数据目录，不读写任何真实账本。
#
# 用法：bash tests/test_engine.sh   （或 make test）
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="$REPO_ROOT/scripts/finance_engine.py"
DATA_DIR="$(mktemp -d)/finance"
E=(python3 "$ENGINE" --data-dir "$DATA_DIR")

PASS=0
FAIL=0

# check <用例名> <期望输出中包含的关键字> <命令...>
check() {
  local desc="$1" keyword="$2"
  shift 2
  local out
  if ! out="$("$@" 2>&1)"; then
    FAIL=$((FAIL + 1)); echo "✗ $desc（命令返回非零）"; echo "$out"
    return
  fi
  if grep -qF -- "$keyword" <<<"$out"; then
    PASS=$((PASS + 1)); echo "✓ $desc"
  else
    FAIL=$((FAIL + 1)); echo "✗ $desc（未找到关键字：$keyword）"; echo "$out"
  fi
}

echo "== 基础 =="
check "--version 输出版本号" "1.0.0" python3 "$ENGINE" --version
check "--help 可用" "usage" python3 "$ENGINE" --help

echo "== 记账 =="
check "add --json 录入 5 笔（USD 按 7.1 换算）" "→ CNY -355.0" \
  "${E[@]}" add --json "$(cat "$REPO_ROOT/examples/sample_transactions.json")"
check "add --csv 导入账单" "已录入 5 笔" \
  "${E[@]}" add --csv "$REPO_ROOT/examples/sample_import.csv"
check "add --text 兜底解析（支出记负）" "支出 CNY -58.0" \
  "${E[@]}" add --text "今天买菜 -58" --account 现金

echo "== 查询与报表 =="
check "list 汇总收支" "共 11 笔" "${E[@]}" list
check "list 按分类过滤" "共 1 笔" "${E[@]}" list --category 交通
check "report 生成月报" "财务分析报告" "${E[@]}" report --period month --when 2026-10
check "report 含储蓄率" "储蓄率" "${E[@]}" report --period month --when 2026-10
check "report 季度报表" "Q4" "${E[@]}" report --period quarter --when 2026-4
check "report 年度报表" "2026年" "${E[@]}" report --period year --when 2026

echo "== 预算 / 目标 / 汇率 =="
check "budget set" "预算已设置" "${E[@]}" budget set 餐饮 500
check "budget list" "餐饮" "${E[@]}" budget list
check "goal add 储蓄目标" "目标已创建 #1" \
  "${E[@]}" goal add --type savings --name "旅行基金" --amount 30000 --date 2027-10-01
check "goal update 进度" "目标 #1 已更新" "${E[@]}" goal update --id 1 --current 12500
check "goal update 后进度真实生效" "进度：12500.00" "${E[@]}" goal list
check "goal 进度条与节奏" "需每月" "${E[@]}" goal list
check "rate set 汇率" "汇率已更新" "${E[@]}" rate set USD 7.20
check "rate list" "USD" "${E[@]}" rate list

echo "== 基金与定投 =="
check "fund add 登记申购" "已登记基金持仓" \
  "${E[@]}" fund add --code 110011 --name "易方达中小盘混合" --type 混合型 --amount 10000 --nav 3.45
check "fund update 净值" "已更新净值" "${E[@]}" fund update --code 110011 --nav 3.52
check "dca add 建计划" "定投计划 #1" \
  "${E[@]}" dca add --code 110011 --name "易方达中小盘混合" --amount 1000 \
  --account 招行储蓄卡 --day 5 --start 2026-11-01
check "dca execute 执行定投" "定投执行完成" "${E[@]}" dca execute --month 2026-11
check "dca execute 同月幂等" "已执行" "${E[@]}" dca execute --month 2026-11
check "fund list 汇总市值" "合计" "${E[@]}" fund list

echo "== 资产配置 =="
check "allocate 输出配置表" "月度资产配置方案" \
  "${E[@]}" allocate --monthly 3000 --risk medium --assets 50000
check "allocate 再平衡对照" "再平衡对照" \
  "${E[@]}" allocate --monthly 3000 --risk high --assets 50000

echo "== 薪酬与目标规划 =="
check "comp set 完整结构" "薪酬结构已保存" \
  "${E[@]}" comp set --json '{"period":"month","base":5000,
    "commission":[{"up_to":100000,"rate":0.05},{"up_to":200000,"rate":0.08},{"up_to":null,"rate":0.12}],
    "bonus":[{"type":"target","threshold":200000,"amount":8000}],"deductions":1000,"currency":"CNY"}'
check "comp show 展示结构" "底薪：5000.00" "${E[@]}" comp show
check "plan 直接收入目标" "业绩门槛" "${E[@]}" plan --target-income 30000
check "plan 积累型目标" "每月需净收入" \
  "${E[@]}" plan --goal-amount 300000 --months 12 --monthly-expense 8000 --avg-deal 5000 --workdays 22
check "plan 底薪覆盖时提示" "无需额外业绩" "${E[@]}" plan --target-income 1000

echo "== 数据与模板 =="
if [ -f "$DATA_DIR/ledger.csv" ] && [ -f "$DATA_DIR/goals.json" ] && [ -f "$DATA_DIR/funds.json" ]; then
  PASS=$((PASS + 1)); echo "✓ 数据文件全部生成"
else
  FAIL=$((FAIL + 1)); echo "✗ 数据文件缺失"
fi

if python3 -c "
import csv,sys
ok = True
for p in sys.argv[1:]:
    rows = list(csv.reader(open(p, encoding='utf-8')))
    if rows[0][0] != 'id':      # 含 BOM 时首列名会变成 '\ufeffid'
        print('BOM/表头异常:', p)
        ok = False
sys.exit(0 if ok else 1)
" "$REPO_ROOT/assets/ledger_template.csv" "$REPO_ROOT/examples/sample_import.csv"; then
  PASS=$((PASS + 1)); echo "✓ CSV 文件无 BOM 且表头正确"
else
  FAIL=$((FAIL + 1)); echo "✗ CSV 文件异常（含 BOM 或表头错误）"
fi

echo
echo "———————————————————————"
echo "通过 $PASS 项，失败 $FAIL 项"

rm -rf "$(dirname "$DATA_DIR")"
[ "$FAIL" -eq 0 ] || exit 1
