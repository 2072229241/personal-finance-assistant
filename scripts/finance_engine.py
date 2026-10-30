#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人财务助理 - 财务引擎 (finance_engine.py)

提供确定性的财务处理能力，作为「个人财务助理」skill 的核心计算与存储层：

  - 交易录入与规范化（支持多账户、多币种）
  - 自动分类（关键词规则，可由 LLM 预分类覆盖）
  - 币种换算（基于可配置汇率表，基准币种默认 CNY）
  - 账本持久化（CSV：ledger.csv）
  - 周期性消费分析 / 预算执行 / 储蓄率
  - 储蓄 / 债务目标追踪

设计原则：
  LLM 负责从截图 / 自由文本中抽取结构化交易（理解自然语言与图像），
  本引擎只负责确定性计算、校验与存储，保证结果可复现、可审计。

数据目录（默认 ~/.personal-finance-assistant/）下生成：
  ledger.csv   账本（每一笔收支）
  rates.json   汇率表（基准币种 + 各币种汇率）
  budgets.json 预算（按分类的月度限额，基准币种）
  goals.json   储蓄 / 债务目标
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

__version__ = "1.0.0"

# ----------------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------------
DEFAULT_BASE = "CNY"
DEFAULT_RATES = {
    "CNY": 1.0,
    "USD": 7.10,
    "EUR": 7.70,
    "JPY": 0.047,
    "GBP": 9.00,
    "HKD": 0.91,
}

LEDGER_COLUMNS = [
    "id", "date", "account", "currency", "amount",
    "category", "subcategory", "merchant", "note",
    "fx_rate", "amount_base", "confidence",
]

# 分类关键词字典：分类 -> 触发关键词（小写匹配，命中即归该类，先到先得）
# 该表是“兜底”分类器；若调用方已显式给出 category，则优先使用显式分类。
CATEGORY_KEYWORDS = {
    "餐饮": ["餐饮", "吃饭", "餐厅", "饭店", "食堂", "外卖", "美团", "饿了么",
             "星巴克", "瑞幸", "咖啡", "奶茶", "饮料", "零食", "菜", "cafe",
             "kfc", "mcdonald", "restaurant", "food", "dining", "meal"],
    "交通": ["交通", "地铁", "公交", "打车", "滴滴", "出租车", "加油", "中石油",
             "中石化", "高铁", "火车", "机票", "航班", "停车", "过路", "transport",
             "taxi", "fuel", "flight", "rail", "metro", "bus"],
    "居住": ["房租", "租金", "物业", "水电", "电费", "水费", "燃气", "煤气",
             "宽带", "网费", "家居", "装修", "housing", "rent", "utility"],
    "购物": ["购物", "淘宝", "天猫", "京东", "拼多多", "服饰", "衣服", "鞋",
             "数码", "手机", "电脑", "日用品", "美妆", "化妆品", "百货", "shopping",
             "amazon", "taobao", "jd", "tmall"],
    "娱乐": ["娱乐", "电影", "影视", "视频会员", "游戏", "steam", "旅游", "旅行",
             "景点", "运动", "健身", "ktv", "游乐园", "game", "movie", "travel",
             "fitness", "gym"],
    "医疗健康": ["医疗", "医院", "诊所", "药店", "药品", "门诊", "体检", "保险",
                 "医保", "health", "hospital", "pharmacy", "insurance", "medical"],
    "教育": ["教育", "课程", "培训", "学费", "书籍", "书", "网课", "考研", "考试",
             "education", "course", "book", "tuition", "class"],
    "人情社交": ["红包", "礼金", "礼物", "请客", "聚餐", "人情", "份子", "随礼",
                 "gift", "red packet", "social"],
    "金融": ["利息", "手续费", "服务费", "还款", "转账", "理财", "投资", "基金",
             "股票", "定投", "finance", "interest", "fee", "investment", "loan",
             "repayment"],
    "收入": ["工资", "薪水", "薪资", "奖金", "绩效", "兼职", "稿费", "投资回报",
             "分红", "报销", "退款", "红包收入", "收入", "salary", "income", "bonus",
             "refund", "dividend", "wage", "pay"],
    "其他": [],
}

VALID_CATEGORIES = list(CATEGORY_KEYWORDS.keys())


# ----------------------------------------------------------------------------
# 路径与配置加载
# ----------------------------------------------------------------------------
def resolve_data_dir(data_dir_arg):
    if data_dir_arg:
        d = Path(data_dir_arg)
    else:
        d = Path(os.environ.get("FINANCE_DATA", str(Path.home() / ".personal-finance-assistant")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def paths(data_dir):
    return {
        "ledger": data_dir / "ledger.csv",
        "rates": data_dir / "rates.json",
        "budgets": data_dir / "budgets.json",
        "goals": data_dir / "goals.json",
        "funds": data_dir / "funds.json",
        "dca": data_dir / "dca_plans.json",
        "comp": data_dir / "comp.json",
    }


def load_rates(p):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"base": DEFAULT_BASE, "rates": dict(DEFAULT_RATES)}


def save_rates(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_budgets(p):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def load_goals(p):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


# ----------------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------------
def _parse_date(s):
    s = str(s).strip()
    if not s:
        return date.today()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.match(r"(\d{1,2})月(\d{1,2})日?", s)
    if m:
        return date(date.today().year, int(m.group(1)), int(m.group(2)))
    if s in ("今天", "今日", "t"):
        return date.today()
    if s in ("昨天", "昨日", "y"):
        return date.today() - timedelta(days=1)
    raise ValueError(f"无法识别日期: {s}")


def _normalize_amount(value, currency):
    """把金额规范为带符号浮点数：收入为正、支出为负。
    value 可为：数字、带符号字符串、或含中文/符号的金额文本。"""
    s = str(value).strip()
    sign = 1.0
    # 显式负号
    if s.startswith("-"):
        sign = -1.0
        s = s[1:].strip()
    # 关键字判断（仅当未显式带负号时）
    if sign > 0 and re.search(r"(收入|工资|薪水|赚|收|退款|报销|分红|利息|奖金)", s):
        sign = 1.0
    if sign > 0 and re.search(r"(花|支出|付|消费|买|扣|还款|还)", s):
        sign = -1.0
    # 去掉货币符号与单位
    s = re.sub(r"[¥￥$€£元块刀]", "", s)
    s = s.replace(",", "").strip()
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        raise ValueError(f"无法识别金额: {value}")
    # 取绝对值后再套符号：避免「今天买菜 -58」这类句中负号与关键字判定重复取反
    num = abs(float(m.group(0)))
    return sign * num


def _detect_currency(text):
    t = str(text).lower()
    if "$" in text or "美元" in text or "美金" in text or "usd" in t:
        return "USD"
    if "€" in text or "欧元" in text or "eur" in t:
        return "EUR"
    if "£" in text or "英镑" in text or "gbp" in t:
        return "GBP"
    if "港币" in text or "hkd" in t or "hk$" in t:
        return "HKD"
    if "日元" in text or "円" in text or "jpy" in t:
        return "JPY"
    if "¥" in text or "￥" in text or "元" in text or "人民币" in text or "cny" in t:
        return "CNY"
    return "CNY"


def categorize(text, explicit=None):
    """返回 (category, confidence)。explicit 优先。"""
    if explicit and explicit in VALID_CATEGORIES:
        return explicit, 1.0
    if explicit and explicit:
        # 非标准分类名，记录但回退到关键词
        pass
    t = str(text).lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if cat == "其他":
            continue
        for kw in kws:
            if kw.lower() in t:
                return cat, 0.7
    return "其他", 0.3


def next_id(ledger_path):
    if not ledger_path.exists():
        return 1
    max_id = 0
    with ledger_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                max_id = max(max_id, int(row.get("id", 0)))
            except ValueError:
                pass
    return max_id + 1


def read_ledger(ledger_path):
    if not ledger_path.exists():
        return []
    with ledger_path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_rows(ledger_path, rows):
    write_header = not ledger_path.exists()
    with ledger_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        if write_header:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _as_float(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------------------
# 子命令实现
# ----------------------------------------------------------------------------
def cmd_add(args):
    p = paths(resolve_data_dir(args.data_dir))
    rates = load_rates(p["rates"])

    # 收集待录入交易
    raw_txns = []
    if args.json:
        raw_txns = json.loads(args.json)
        if isinstance(raw_txns, dict):
            raw_txns = [raw_txns]
    elif args.csv:
        with open(args.csv, encoding="utf-8") as f:
            raw_txns = list(csv.DictReader(f))
    elif args.text:
        raw_txns = [_parse_text_txn(args.text, args)]

    if not raw_txns:
        print("⚠️ 未提供任何交易数据。可用 --json / --csv / --text。")
        return 1

    base = rates.get("base", DEFAULT_BASE)
    rate_table = rates.get("rates", {})
    start_id = next_id(p["ledger"])
    rows = []
    for i, tx in enumerate(raw_txns):
        # 字段抽取（兼容不同键名）
        def g(*keys, default=""):
            for k in keys:
                if k in tx and tx[k] not in (None, ""):
                    return tx[k]
            return default

        currency = (str(g("currency", "币种", "cur")).upper() or _detect_currency(
            f"{g('merchant','商户','payee')} {g('note','备注')} {g('category','分类')}")).upper()
        if currency not in rate_table:
            print(f"⚠️ 币种 {currency} 无汇率，按 1.0 处理（请先 `rate set` 配置）。")
            rate_table[currency] = 1.0

        amount = _normalize_amount(g("amount", "金额", "amt"), currency)
        fx = rate_table[currency]
        amount_base = round(amount * fx, 2)

        cat, conf = categorize(
            f"{g('merchant','商户','payee')} {g('note','备注')} {g('category','分类')} {g('subcategory','子类')}",
            explicit=g("category", "分类") or None,
        )

        rec = {
            "id": start_id + i,
            "date": _parse_date(g("date", "日期", "time")).isoformat(),
            "account": g("account", "账户", "acc") or "未指定",
            "currency": currency,
            "amount": round(amount, 2),
            "category": cat,
            "subcategory": g("subcategory", "子类"),
            "merchant": g("merchant", "商户", "payee"),
            "note": g("note", "备注", "desc"),
            "fx_rate": fx,
            "amount_base": amount_base,
            "confidence": round(conf, 2),
        }
        rows.append(rec)

    append_rows(p["ledger"], rows)
    print(f"✅ 已录入 {len(rows)} 笔交易到 {p['ledger']}")
    for r in rows:
        tag = "收入" if r["amount"] > 0 else "支出"
        print(f"  #{r['id']} {r['date']} [{r['account']}] {tag} {r['currency']} "
              f"{r['amount']} → {base} {r['amount_base']} | {r['category']} | "
              f"{r['merchant']} (置信度 {r['confidence']})")
    return 0


def _parse_text_txn(text, args):
    """极简自由文本解析，作为 LLM 抽取失败时的兜底。"""
    currency = _detect_currency(text)
    account = args.account or "未指定"
    amount = _normalize_amount(text, currency)
    return {
        "date": date.today().isoformat(),
        "account": account,
        "currency": currency,
        "amount": amount,
        "merchant": "",
        "note": text,
    }


def cmd_list(args):
    p = paths(resolve_data_dir(args.data_dir))
    rows = read_ledger(p["ledger"])
    if args.account:
        rows = [r for r in rows if r["account"] == args.account]
    if args.category:
        rows = [r for r in rows if r["category"] == args.category]
    if args.currency:
        rows = [r for r in rows if r["currency"].upper() == args.currency.upper()]
    if args.since:
        d0 = _parse_date(args.since)
        rows = [r for r in rows if _parse_date(r["date"]) >= d0]
    if args.until:
        d1 = _parse_date(args.until)
        rows = [r for r in rows if _parse_date(r["date"]) <= d1]
    rows.sort(key=lambda r: r["date"])
    if not rows:
        print("（无匹配交易）")
        return 0
    inc = sum(_as_float(r["amount_base"]) for r in rows if _as_float(r["amount"]) > 0)
    exp = sum(-_as_float(r["amount_base"]) for r in rows if _as_float(r["amount"]) < 0)
    print(f"共 {len(rows)} 笔 | 收入 {inc:.2f} | 支出 {exp:.2f} | 净额 {inc-exp:.2f}（基准币种）")
    print("-" * 70)
    for r in rows[-args.limit:] if args.limit else rows:
        tag = "收入" if _as_float(r["amount"]) > 0 else "支出"
        print(f"{r['date']} #{r['id']} [{r['account']}] {tag} {r['currency']}"
              f"{r['amount']} | {r['category']} | {r['merchant']}")
    return 0


def _period_bounds(period, when):
    today = date.today()
    if period == "month":
        y, m = (today.year, today.month) if not when else (int(when[:4]), int(when[5:7]))
        first = date(y, m, 1)
        if m == 12:
            last = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(y, m + 1, 1) - timedelta(days=1)
        label = f"{y}年{m:02d}月"
    elif period == "quarter":
        y, q = (today.year, (today.month - 1) // 3 + 1) if not when else (int(when[:4]), int(when[5:]))
        m0 = (q - 1) * 3 + 1
        first = date(y, m0, 1)
        m1 = m0 + 3
        if m1 > 12:
            last = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(y, m1, 1) - timedelta(days=1)
        label = f"{y}年Q{q}"
    elif period == "year":
        y = today.year if not when else int(when[:4])
        first = date(y, 1, 1)
        last = date(y, 12, 31)
        label = f"{y}年"
    else:
        raise ValueError("period 必须是 month/quarter/year")
    return first, last, label


def cmd_report(args):
    p = paths(resolve_data_dir(args.data_dir))
    rows = read_ledger(p["ledger"])
    first, last, label = _period_bounds(args.period, args.when)
    rows = [r for r in rows if first <= _parse_date(r["date"]) <= last]

    budgets = load_budgets(p["budgets"])
    base = load_rates(p["rates"]).get("base", DEFAULT_BASE)

    income = sum(_as_float(r["amount_base"]) for r in rows if _as_float(r["amount"]) > 0)
    expense = sum(-_as_float(r["amount_base"]) for r in rows if _as_float(r["amount"]) < 0)

    # 分类汇总
    by_cat = {}
    for r in rows:
        if _as_float(r["amount"]) >= 0:
            continue
        c = r["category"] or "其他"
        by_cat[c] = by_cat.get(c, 0.0) + (-_as_float(r["amount_base"]))

    # 账户汇总
    by_acc = {}
    for r in rows:
        a = r["account"] or "未指定"
        by_acc[a] = by_acc.get(a, 0.0) + _as_float(r["amount_base"])

    # 币种汇总
    by_cur = {}
    for r in rows:
        cu = r["currency"]
        by_cur[cu] = by_cur.get(cu, 0.0) + _as_float(r["amount"])

    savings_rate = (income - expense) / income * 100 if income > 0 else 0.0
    net = income - expense

    print(f"# 📊 财务分析报告 · {label}（基准币种 {base}）")
    print()
    print(f"- 总收入：{income:.2f}")
    print(f"- 总支出：{expense:.2f}")
    print(f"- 净结余：{net:.2f}")
    print(f"- 储蓄率：{savings_rate:.1f}%（收入>0 时 = 净结余/收入）")
    print()

    print("## 分类支出 Top")
    if by_cat:
        for c, v in sorted(by_cat.items(), key=lambda x: -x[1]):
            pct = v / expense * 100 if expense else 0
            flag = ""
            if c in budgets:
                b = _as_float(budgets[c])
                if b > 0 and v > b:
                    flag = f"  ⚠️ 超预算（限 {b:.0f}，超 {v-b:.0f}）"
                elif b > 0:
                    flag = f"  ✓ 预算内（限 {b:.0f}，余 {b-v:.0f}）"
            print(f"- {c}：{v:.2f}（占支出 {pct:.1f}%）{flag}")
    else:
        print("（本期无支出记录）")
    print()

    print("## 账户维度")
    for a, v in sorted(by_acc.items(), key=lambda x: -x[1]):
        print(f"- {a}：{v:.2f}")
    print()

    print("## 币种维度（原币）")
    for cu, v in sorted(by_cur.items(), key=lambda x: -abs(x[1])):
        print(f"- {cu}：{v:.2f}")
    print()

    print("## 预算执行")
    if budgets:
        for c, b in budgets.items():
            actual = by_cat.get(c, 0.0)
            b = _as_float(b)
            status = "超支" if actual > b else "正常"
            print(f"- {c}：实际 {actual:.2f} / 预算 {b:.2f} → {status}")
    else:
        print("（未设置预算，使用 `budget set <分类> <金额>` 设置月度限额）")
    return 0


def cmd_budget(args):
    p = paths(resolve_data_dir(args.data_dir))
    budgets = load_budgets(p["budgets"])
    if args.action == "set":
        if args.category not in VALID_CATEGORIES:
            print(f"⚠️ 分类 '{args.category}' 不在标准分类中，仍会记录。标准分类：{VALID_CATEGORIES}")
        budgets[args.category] = float(args.amount)
        save_json(p["budgets"], budgets)
        print(f"✅ 预算已设置：{args.category} = {args.amount}（基准币种，月度）")
    else:
        if not budgets:
            print("（暂无预算）")
        for c, b in budgets.items():
            print(f"- {c}：{b}")
    return 0


def cmd_goal(args):
    p = paths(resolve_data_dir(args.data_dir))
    goals = load_goals(p["goals"])

    if args.action == "add":
        gid = max([g.get("id", 0) for g in goals], default=0) + 1
        goal = {
            "id": gid,
            "type": args.type,
            "name": args.name,
            "target_amount": float(args.amount),
            "target_date": args.date,
            "current_amount": float(args.current or 0),
            "start_amount": float(args.current or 0),
            "currency": load_rates(p["rates"]).get("base", DEFAULT_BASE),
            "note": args.note or "",
        }
        goals.append(goal)
        save_json(p["goals"], goals)
        print(f"✅ 目标已创建 #{gid}：{goal['name']}（{goal['type']}，目标 {goal['target_amount']} {goal['currency']}）")

    elif args.action == "update":
        g = _find_goal(goals, args.id)
        if not g:
            print("⚠️ 未找到目标"); return 1
        # --current 为更新进度的首选写法；--amount 保留为等价别名
        if args.current is not None:
            g["current_amount"] = float(args.current)
        elif args.amount is not None:
            g["current_amount"] = float(args.amount)
        if args.date:
            g["target_date"] = args.date
        if args.note:
            g["note"] = args.note
        save_json(p["goals"], goals)
        print(f"✅ 目标 #{args.id} 已更新")

    elif args.action == "delete":
        before = len(goals)
        goals = [g for g in goals if g.get("id") != args.id]
        save_json(p["goals"], goals)
        print(f"{'✅' if len(goals) < before else '⚠️ 未找到'} 已删除目标 #{args.id}")

    # 展示（list / add / update / delete 后都打印最新状态）
    print_goal_status(goals)
    return 0


def _find_goal(goals, gid):
    for g in goals:
        if g.get("id") == gid:
            return g
    return None


def print_goal_status(goals):
    if not goals:
        print("（暂无目标）")
        return
    print("\n## 🎯 目标追踪")
    today = date.today()
    for g in goals:
        ta = _as_float(g["target_amount"])
        cur = _as_float(g["current_amount"])
        start = _as_float(g.get("start_amount", cur))
        try:
            td = _parse_date(g.get("target_date", ""))
        except Exception:
            td = None
        if g["type"] == "savings":
            pct = cur / ta * 100 if ta else 0
            remain = max(ta - cur, 0)
            progress = cur
            target_disp = ta
        else:  # debt：current 为剩余债务，目标 0
            payoff = (start - cur) / start * 100 if start else 0
            remain = max(cur, 0)
            pct = payoff
            progress = start - cur
            target_disp = start
        months_left = None
        if td:
            months_left = (td.year - today.year) * 12 + (td.month - today.month)
        need_per_month = remain / months_left if (months_left and months_left > 0) else None
        bar_len = 20
        filled = int(bar_len * min(max(pct, 0), 100) / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        kind = "储蓄" if g["type"] == "savings" else "偿债"
        print(f"\n#{g['id']} {g['name']}（{kind}）")
        print(f"  [{bar}] {pct:.1f}%")
        print(f"  进度：{progress:.2f} / {target_disp:.2f} {g.get('currency','')} | 剩余：{remain:.2f}")
        if td:
            print(f"  目标日：{td.isoformat()}（剩 {months_left} 个月）"
                  + (f" | 需每月 {need_per_month:.2f}" if need_per_month is not None else " | 已超时"))


def cmd_rate(args):
    p = paths(resolve_data_dir(args.data_dir))
    rates = load_rates(p["rates"])
    if args.action == "set":
        rates.setdefault("rates", {})[args.currency.upper()] = float(args.value)
        if args.base:
            rates["base"] = args.base.upper()
        save_rates(p["rates"], rates)
        print(f"✅ 汇率已更新：1 {args.currency.upper()} = {args.value} {rates['base']}")
    else:
        print(f"基准币种：{rates.get('base', DEFAULT_BASE)}")
        for cu, v in sorted(rates.get("rates", {}).items()):
            print(f"  1 {cu} = {v} {rates.get('base', DEFAULT_BASE)}")
    return 0


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------------
# 基金定投与资产配置
# ----------------------------------------------------------------------------
FUND_TYPES = ["货币型", "债券型", "指数型", "股票型", "混合型", "QDII", "ETF"]

# 风险偏好 → 资产类别配置（比例合计为 1.0）
# 每项：(资产类别, 目标比例, 建议基金类型, 说明)
RISK_PRESETS = {
    "low": [
        ("货币基金/现金(应急)", 0.20, "货币型", "保留 3-6 个月开支的应急垫"),
        ("纯债/固收+", 0.50, "债券型", "稳健底仓"),
        ("宽基指数", 0.25, "指数型", "沪深300/中证500"),
        ("主动/行业", 0.05, "混合型", "少量增强"),
    ],
    "medium": [
        ("货币基金/现金(应急)", 0.10, "货币型", "应急垫"),
        ("纯债/固收+", 0.30, "债券型", "底仓"),
        ("宽基指数", 0.40, "指数型", "沪深300+中证500 双核"),
        ("主动/行业", 0.15, "混合型", "卫星增强"),
        ("海外/QDII", 0.05, "QDII", "全球分散"),
    ],
    "high": [
        ("货币基金/现金(应急)", 0.05, "货币型", "应急垫"),
        ("纯债/固收+", 0.15, "债券型", "底仓"),
        ("宽基指数", 0.45, "指数型", "核心仓位"),
        ("主动/行业", 0.25, "混合型", "卫星进攻"),
        ("海外/QDII", 0.10, "QDII", "全球分散"),
    ],
}

# 资产类别 → 参与再平衡的基金类型集合
CLASS_TO_TYPES = {
    "货币基金/现金(应急)": ["货币型"],
    "纯债/固收+": ["债券型"],
    "宽基指数": ["指数型"],
    "主动/行业": ["混合型", "股票型"],
    "海外/QDII": ["QDII"],
}


def load_funds(p):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def load_dca_plans(p):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _fund_by_code(funds, code):
    for f in funds:
        if f.get("code") == code:
            return f
    return None


def _find_dca(plans, pid):
    for x in plans:
        if x.get("id") == pid:
            return x
    return None


def _append_ledger_expense(p, date_iso, account, amount_neg, category, subcategory, merchant, note):
    """记录一笔基金相关的账本支出（基准币种 CNY，fx=1）。"""
    rates = load_rates(p["rates"])
    base = rates.get("base", DEFAULT_BASE)
    rate_table = rates.get("rates", {})
    cur = "CNY"
    fx = rate_table.get(cur, 1.0)
    row = {
        "id": next_id(p["ledger"]),
        "date": date_iso,
        "account": account or "未指定",
        "currency": cur,
        "amount": round(amount_neg, 2),
        "category": category,
        "subcategory": subcategory,
        "merchant": merchant,
        "note": note,
        "fx_rate": fx,
        "amount_base": round(amount_neg * fx, 2),
        "confidence": 1.0,
    }
    append_rows(p["ledger"], [row])


def _print_funds(funds):
    if not funds:
        print("（暂无基金持仓）")
        return
    print(f"{'代码':<10}{'名称':<16}{'类型':<8}{'份额':>12}{'本金':>12}{'净值':>9}{'市值':>12}{'收益':>12}{'收益率':>9}")
    tot_p = tot_mv = 0.0
    for f in funds:
        sh = _as_float(f.get("shares"))
        pr = _as_float(f.get("principal"))
        nav = _as_float(f.get("nav"))
        mv = sh * nav
        profit = mv - pr
        rate = profit / pr * 100 if pr else 0
        tot_p += pr
        tot_mv += mv
        print(f"{f.get('code',''):<10}{(f.get('name','') or '')[:14]:<16}{f.get('type',''):<8}"
              f"{sh:>12.2f}{pr:>12.2f}{nav:>9.4f}{mv:>12.2f}{profit:>12.2f}{rate:>8.1f}%")
    tp = tot_mv - tot_p
    print("-" * 102)
    print(f"{'合计':<10}{'':<16}{'':<8}{'':>12}{tot_p:>12.2f}{'':>9}{tot_mv:>12.2f}{tp:>12.2f}"
          f"{(tp / tot_p * 100 if tot_p else 0):>8.1f}%")


def cmd_fund(args):
    p = paths(resolve_data_dir(args.data_dir))
    funds = load_funds(p["funds"])
    if args.action == "add":
        if not args.code:
            print("⚠️ 请提供 --code"); return 1
        if args.type and args.type not in FUND_TYPES:
            print(f"⚠️ 非常规类型 '{args.type}'，已知类型：{FUND_TYPES}")
        nav = args.nav or 0.0
        shares = args.shares if args.shares is not None else (args.amount / nav if nav else 0.0)
        existing = _fund_by_code(funds, args.code)
        if existing:
            existing["shares"] = _as_float(existing.get("shares")) + shares
            existing["principal"] = _as_float(existing.get("principal")) + args.amount
            if nav:
                existing["nav"] = nav
                existing["nav_date"] = args.nav_date or date.today().isoformat()
            if args.name:
                existing["name"] = args.name
            if args.type:
                existing["type"] = args.type
            rec = existing
        else:
            rec = {
                "code": args.code, "name": args.name or args.code,
                "type": args.type or "其他", "shares": shares,
                "principal": args.amount, "nav": nav,
                "nav_date": args.nav_date or date.today().isoformat(),
                "auto_dca": False,
            }
            funds.append(rec)
        save_json(p["funds"], funds)
        _append_ledger_expense(p, (args.date or date.today().isoformat()), args.account,
                               -abs(args.amount), "金融", "申购",
                               f"{args.name or args.code}({args.code})", "基金申购")
        print(f"✅ 已登记基金持仓：{args.code} {args.name or ''} | 申购 {args.amount:.2f} | "
              f"份额 {shares:.4f} | 本金累计 {_as_float(rec['principal']):.2f}")
    elif args.action == "update":
        f = _fund_by_code(funds, args.code)
        if not f:
            print("⚠️ 未找到该基金，先用 fund add 登记"); return 1
        if args.nav:
            f["nav"] = args.nav
            f["nav_date"] = args.nav_date or date.today().isoformat()
        save_json(p["funds"], funds)
        mv = _as_float(f.get("shares")) * _as_float(f.get("nav"))
        print(f"✅ 已更新净值：{args.code} 净值 {f['nav']} | 市值 {mv:.2f} | "
              f"收益 {mv - _as_float(f['principal']):.2f}")
    elif args.action == "list":
        _print_funds(funds)
    return 0


def cmd_dca(args):
    p = paths(resolve_data_dir(args.data_dir))
    plans = load_dca_plans(p["dca"])
    funds = load_funds(p["funds"])
    if args.action == "add":
        if not args.code or args.amount is None:
            print("⚠️ 请提供 --code 与 --amount"); return 1
        pid = max([x.get("id", 0) for x in plans], default=0) + 1
        plans.append({
            "id": pid, "code": args.code, "name": args.name or args.code,
            "amount_per_month": float(args.amount),
            "source_account": args.account or "未指定",
            "day_of_month": args.day or 1,
            "start_date": args.start or date.today().isoformat(),
            "status": "active", "last_executed": None,
        })
        f = _fund_by_code(funds, args.code)
        if f:
            f["auto_dca"] = True
            save_json(p["funds"], funds)
        save_json(p["dca"], plans)
        print(f"✅ 定投计划 #{pid}：{args.code} {args.name or ''} 每月 {args.amount} 元"
              f"（账户 {args.account or '未指定'}，每月 {args.day or 1} 日）")
    elif args.action == "list":
        if not plans:
            print("（暂无定投计划）")
        for x in plans:
            print(f"#{x['id']} {x['code']} {x['name']} | 每月 {x['amount_per_month']} | "
                  f"账户 {x['source_account']} | 状态 {x['status']} | 上次执行 {x.get('last_executed')}")
    elif args.action in ("pause", "resume"):
        x = _find_dca(plans, args.id)
        if not x:
            print("⚠️ 未找到计划"); return 1
        x["status"] = "paused" if args.action == "pause" else "active"
        save_json(p["dca"], plans)
        print(f"✅ 计划 #{args.id} 已{'暂停' if args.action == 'pause' else '恢复'}")
    elif args.action == "execute":
        month = args.month or date.today().strftime("%Y-%m")
        y, m = int(month[:4]), int(month[5:7])
        total_invest = 0.0
        for x in plans:
            if x["status"] != "active":
                continue
            if x.get("last_executed") == month:
                print(f"  · 跳过 {x['code']}：{month} 已执行")
                continue
            f = _fund_by_code(funds, x["code"])
            nav = _as_float(f.get("nav")) if f else 0.0
            if nav <= 0:
                print(f"  ⚠️ 跳过 {x['code']}：无净值，请先 fund update 设置")
                continue
            amt = x["amount_per_month"]
            sh = amt / nav
            if f:
                f["shares"] = _as_float(f.get("shares")) + sh
                f["principal"] = _as_float(f.get("principal")) + amt
            else:
                funds.append({"code": x["code"], "name": x["name"], "type": "其他",
                              "shares": sh, "principal": amt, "nav": nav,
                              "nav_date": date(y, m, 1).isoformat(), "auto_dca": True})
                f = _fund_by_code(funds, x["code"])
            dom = min(x.get("day_of_month", 1), 28)
            try:
                d = date(y, m, dom).isoformat()
            except Exception:
                d = date(y, m, 1).isoformat()
            _append_ledger_expense(p, d, x["source_account"], -amt, "金融", "定投",
                                   f"{x['name']}({x['code']})", f"月度定投 {month}")
            x["last_executed"] = month
            total_invest += amt
            print(f"  ✓ {x['code']} {x['name']}：定投 {amt} 元 → 份额 {sh:.4f}（净值 {nav}）")
        save_json(p["dca"], plans)
        save_json(p["funds"], funds)
        print(f"✅ {month} 定投执行完成，共投入 {total_invest:.2f} 元")
    return 0


def cmd_allocate(args):
    p = paths(resolve_data_dir(args.data_dir))
    preset = RISK_PRESETS.get(args.risk)
    if not preset:
        print(f"⚠️ 风险等级需为 low/medium/high，收到：{args.risk}")
        return 1
    monthly = args.monthly or 0.0
    assets = args.assets or 0.0
    print(f"# 🧭 月度资产配置方案（风险偏好：{args.risk}）")
    print()
    print(f"- 每月可投金额：{monthly:.2f}")
    if assets:
        print(f"- 当前可配置总资产：{assets:.2f}")
    print()
    print("## 资产类别配置")
    print(f"{'资产类别':<20}{'目标比例':>10}{'每月定投':>12}  {'建议基金类型':<12}说明")
    total_pct = 0.0
    for cls, pct, ftype, note in preset:
        total_pct += pct
        print(f"{cls:<20}{pct * 100:>9.0f}%{monthly * pct:>12.2f}  {ftype:<12}{note}")
    print(f"{'合计':<20}{total_pct * 100:>9.0f}%{monthly:>12.2f}")
    funds = load_funds(p["funds"])
    if funds and assets:
        print()
        print("## 当前持仓再平衡对照")
        mv_total = sum(_as_float(f.get("shares")) * _as_float(f.get("nav")) for f in funds)
        for cls, pct, ftype, note in preset:
            types = CLASS_TO_TYPES.get(cls, [])
            cur = sum(_as_float(f.get("shares")) * _as_float(f.get("nav"))
                      for f in funds if f.get("type") in types)
            cur_pct = cur / mv_total * 100 if mv_total else 0
            target_val = assets * pct
            diff = target_val - cur
            flag = "补仓" if diff > 0 else "减仓/持有"
            print(f"- {cls}：当前 {cur:.2f}（{cur_pct:.1f}%）/ 目标 {target_val:.2f}"
                  f"（{pct * 100:.0f}%）→ {flag} {abs(diff):.2f}")
    elif funds:
        print()
        print("（提示：传入 --assets 可生成当前持仓的再平衡对照）")
    return 0


# ----------------------------------------------------------------------------
# 薪酬结构与目标规划（业绩反推）
# ----------------------------------------------------------------------------
def load_comp(p):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"period": "month", "base": 0.0, "commission": [{"up_to": None, "rate": 0.0}],
            "bonus": [], "deductions": 0.0, "currency": DEFAULT_BASE}


def save_comp(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def commission_at(perf, tiers):
    """阶梯提成（累进）：每个区间 rate 作用于该区间内的业绩切片。"""
    total = 0.0
    lower = 0.0
    for t in tiers or []:
        up = t.get("up_to")
        rate = _as_float(t.get("rate"))
        if up is None:
            if perf > lower:
                total += (perf - lower) * rate
            break
        if perf > lower:
            total += (min(perf, up) - lower) * rate
        lower = up
        if perf <= up:
            break
    return total


def commission_by_tier(perf, tiers):
    """返回每档 [区间下限, 区间上限, 税率, 该档提成] 用于展示。"""
    rows = []
    lower = 0.0
    for t in tiers or []:
        up = t.get("up_to")
        rate = _as_float(t.get("rate"))
        if up is None:
            if perf > lower:
                amt = (perf - lower) * rate
            else:
                amt = 0.0
            rows.append((lower, None, rate, amt))
            break
        if perf > lower:
            amt = (min(perf, up) - lower) * rate
        else:
            amt = 0.0
        rows.append((lower, up, rate, amt))
        lower = up
        if perf <= up:
            break
    return rows


def bonus_at(perf, rules):
    """奖金：target 型（达标一次性）、tiered 型（取已达档位最高额）。均随业绩非递减。"""
    total = 0.0
    for r in rules or []:
        if r.get("type") == "target":
            if perf >= _as_float(r.get("threshold")):
                total += _as_float(r.get("amount"))
        elif r.get("type") == "tiered":
            best = 0.0
            for tier in r.get("tiers", []):
                if perf >= _as_float(tier.get("perf")):
                    best = max(best, _as_float(tier.get("amount")))
            total += best
    return total


def income_at(perf, comp):
    """给定业绩下的总收入（净额 = 底薪 + 提成 + 奖金 - 扣除）。"""
    base = _as_float(comp.get("base"))
    comm = commission_at(perf, comp.get("commission"))
    bonus = bonus_at(perf, comp.get("bonus"))
    ded = _as_float(comp.get("deductions"))
    return base + comm + bonus - ded


def required_performance(target, comp):
    """反推：达到目标净额所需的最小业绩。收入随业绩单调非递减，故可用二分。
    返回 (perf, feasible)。"""
    if income_at(0.0, comp) >= target:
        return 0.0, True
    hi = 1e9
    if income_at(hi, comp) < target:
        return None, False
    lo = 0.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if income_at(mid, comp) >= target:
            hi = mid
        else:
            lo = mid
    return hi, True


def cmd_comp(args):
    p = paths(resolve_data_dir(args.data_dir))
    comp = load_comp(p["comp"])
    if args.action == "set":
        if args.json:
            new_comp = json.loads(args.json)
            comp.update(new_comp)
        else:
            comp["base"] = args.base if args.base is not None else comp.get("base", 0.0)
            if args.rate is not None:
                comp["commission"] = [{"up_to": None, "rate": args.rate}]
            if args.deductions is not None:
                comp["deductions"] = args.deductions
            if args.period:
                comp["period"] = args.period
        comp.setdefault("period", "month")
        comp.setdefault("commission", [{"up_to": None, "rate": 0.0}])
        comp.setdefault("bonus", [])
        save_comp(p["comp"], comp)
        print(f"✅ 薪酬结构已保存（周期 {comp['period']}）："
              f"底薪 {comp.get('base',0):.2f} | 提成档 {len(comp['commission'])} 档 | "
              f"奖金规则 {len(comp.get('bonus', []))} 条 | 扣除 {comp.get('deductions',0):.2f}")
    else:
        c = load_comp(p["comp"])
        print(f"# 当前薪酬结构（周期：{c.get('period','month')}，币种：{c.get('currency', DEFAULT_BASE)}）")
        print(f"- 底薪：{_as_float(c.get('base')):.2f}")
        print("- 提成（累进）：")
        lower = 0.0
        for t in c.get("commission", []):
            up = "∞" if t.get("up_to") is None else f"{_as_float(t.get('up_to')):.0f}"
            print(f"    · 业绩 {lower:,.0f}–{up}：{_as_float(t.get('rate'))*100:.1f}%")
            if t.get("up_to") is not None:
                lower = _as_float(t.get("up_to"))
        print("- 奖金：")
        for r in c.get("bonus", []):
            if r.get("type") == "target":
                print(f"    · 达标奖：业绩≥{_as_float(r.get('threshold')):.0f} 奖 {_as_float(r.get('amount')):.0f}")
            elif r.get("type") == "tiered":
                for tier in r.get("tiers", []):
                    print(f"    · 阶梯奖：业绩≥{_as_float(tier.get('perf')):.0f} 奖 {_as_float(tier.get('amount')):.0f}")
        print(f"- 固定扣除：{_as_float(c.get('deductions')):.2f}")
    return 0


def cmd_plan(args):
    p = paths(resolve_data_dir(args.data_dir))
    comp = load_comp(p["comp"])
    if comp.get("base", 0) == 0 and not comp.get("commission") and not comp.get("bonus"):
        print("⚠️ 尚未配置薪酬结构，请先 `comp set`（可用 --json 完整描述或 --base/--rate 简配）。")
        return 1

    # 解析目标 → 目标净额（target_income）
    if args.target_income is not None:
        target = args.target_income
        goal_desc = f"目标收入 {target:.2f}/{comp.get('period','month')}"
    elif args.goal_amount is not None and args.months:
        monthly_need = args.goal_amount / args.months
        if args.monthly_expense:
            monthly_need += args.monthly_expense
        target = monthly_need
        goal_desc = (f"目标 {args.goal_amount:.2f} 在 {args.months} 个月内达成"
                     + (f"（含月开销 {args.monthly_expense:.2f}）" if args.monthly_expense else "")
                     + f" → 每月需净收入 {target:.2f}")
    else:
        print("⚠️ 请提供 --target-income <金额> 或 --goal-amount <总额> --months <月数>。")
        return 1

    perf, feasible = required_performance(target, comp)
    cur = comp.get("currency", DEFAULT_BASE)
    print(f"# 🎯 目标规划 · 业绩反推（{goal_desc}）")
    print()
    if not feasible:
        print(f"⚠️ 按当前薪酬结构，即便做到极大业绩也无法达到目标净额 {target:.2f}。"
              f"当前封顶收入约 {income_at(1e9, comp):.2f}。建议调高底薪/提成率或降低目标。")
        return 0

    if perf == 0.0:
        print(f"✅ 底薪（{_as_float(comp.get('base')):.2f}）已覆盖目标净额 {target:.2f}，"
              f"无需额外业绩。")
        return 0

    # 收入拆解
    base = _as_float(comp.get("base"))
    ded = _as_float(comp.get("deductions"))
    comm_total = commission_at(perf, comp.get("commission"))
    bonus_total = bonus_at(perf, comp.get("bonus"))
    net = base + comm_total + bonus_total - ded
    print(f"## 达成目标所需业绩门槛：{perf:,.2f} {cur}（/{comp.get('period','month')}）")
    print()
    print("## 对应收入说明（在该业绩下）")
    print(f"- 底薪：{base:.2f}")
    for lower, up, rate, amt in commission_by_tier(perf, comp.get("commission")):
        up_s = "∞" if up is None else f"{up:,.0f}"
        print(f"- 提成（业绩 {lower:,.0f}–{up_s}，{rate*100:.1f}%）：{amt:,.2f}")
    if bonus_total:
        print(f"- 奖金：{bonus_total:,.2f}")
    if ded:
        print(f"- 扣除（社保/税等）：-{ded:.2f}")
    print(f"- **净收入合计：{net:,.2f}**（目标 {target:,.2f}）")
    print()

    # 工作规划派生
    if args.avg_deal:
        deals = perf / args.avg_deal
        print(f"## 工作规划参考（按平均客单价 {args.avg_deal:,.2f}）")
        print(f"- 需成交约 {deals:,.0f} 单/{comp.get('period','month')}")
        if args.workdays:
            print(f"- 日均业绩目标：{perf/args.workdays:,.2f}；日均约 {deals/args.workdays:,.1f} 单"
                  f"（按 {args.workdays} 个工作日）")
        print()
    elif args.workdays:
        print(f"## 工作规划参考（{args.workdays} 个工作日）")
        print(f"- 日均业绩目标：{perf/args.workdays:,.2f} {cur}")
        print()

    # 敏感度表
    print("## 业绩—收入对照")
    for mult in (0.8, 1.0, 1.2):
        pf = perf * mult
        print(f"- 业绩 {pf:,.0f} → 净收入 {income_at(pf, comp):,.2f}")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="个人财务助理 - 财务引擎")
    ap.add_argument("--version", action="version", version=f"finance_engine {__version__}")
    ap.add_argument("--data-dir", help="数据目录（默认 ~/.personal-finance-assistant）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="录入交易")
    a.add_argument("--json", help="JSON 数组或对象，含 date/account/currency/amount/category/merchant/note")
    a.add_argument("--csv", help="CSV 文件路径（列名兼容 date,account,currency,amount,category,merchant,note）")
    a.add_argument("--text", help="自由文本（兜底解析）")
    a.add_argument("--account", help="自由文本模式下的默认账户")
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("list", help="列出交易")
    l.add_argument("--account")
    l.add_argument("--category")
    l.add_argument("--currency")
    l.add_argument("--since")
    l.add_argument("--until")
    l.add_argument("--limit", type=int, default=0)
    l.set_defaults(func=cmd_list)

    r = sub.add_parser("report", help="生成周期性分析报告")
    r.add_argument("--period", choices=["month", "quarter", "year"], default="month")
    r.add_argument("--when", help="指定周期，如 2026-10（month）/ 2026-3（quarter）/ 2026（year）")
    r.set_defaults(func=cmd_report)

    b = sub.add_parser("budget", help="设置/查看预算")
    b.add_argument("action", choices=["set", "list"])
    b.add_argument("category", nargs="?", default=None)
    b.add_argument("amount", nargs="?", default=None, type=float)
    b.set_defaults(func=cmd_budget)

    g = sub.add_parser("goal", help="储蓄/债务目标")
    g.add_argument("action", choices=["add", "update", "delete", "list"])
    g.add_argument("--type", choices=["savings", "debt"], default="savings")
    g.add_argument("--name")
    g.add_argument("--amount", type=float)
    g.add_argument("--date")
    g.add_argument("--current", type=float)
    g.add_argument("--id", type=int)
    g.add_argument("--note")
    g.set_defaults(func=cmd_goal)

    rt = sub.add_parser("rate", help="设置/查看汇率")
    rt.add_argument("action", choices=["set", "list"])
    rt.add_argument("currency", nargs="?", default=None)
    rt.add_argument("value", nargs="?", default=None, type=float)
    rt.add_argument("--base", help="设置基准币种")
    rt.set_defaults(func=cmd_rate)

    fu = sub.add_parser("fund", help="基金持仓：登记/更新净值/列表")
    fu.add_argument("action", choices=["add", "update", "list"])
    fu.add_argument("--code")
    fu.add_argument("--name")
    fu.add_argument("--type", help="货币型/债券型/指数型/股票型/混合型/QDII/ETF")
    fu.add_argument("--amount", type=float, default=0.0)
    fu.add_argument("--shares", type=float)
    fu.add_argument("--nav", type=float)
    fu.add_argument("--nav-date")
    fu.add_argument("--account")
    fu.add_argument("--date")
    fu.set_defaults(func=cmd_fund)

    dc = sub.add_parser("dca", help="基金定投计划：增/查/暂停/恢复/执行")
    dc.add_argument("action", choices=["add", "list", "pause", "resume", "execute"])
    dc.add_argument("--code")
    dc.add_argument("--name")
    dc.add_argument("--amount", type=float)
    dc.add_argument("--account")
    dc.add_argument("--day", type=int)
    dc.add_argument("--start")
    dc.add_argument("--id", type=int)
    dc.add_argument("--month")
    dc.set_defaults(func=cmd_dca)

    al = sub.add_parser("allocate", help="月度资产配置方案")
    al.add_argument("--monthly", type=float, default=0.0)
    al.add_argument("--risk", choices=["low", "medium", "high"], default="medium")
    al.add_argument("--assets", type=float, default=0.0)
    al.set_defaults(func=cmd_allocate)

    cp = sub.add_parser("comp", help="薪酬结构：配置/查看（底薪/提成/奖金）")
    cp.add_argument("action", choices=["set", "show"])
    cp.add_argument("--json", help="完整薪酬结构 JSON（推荐，支持阶梯提成与奖金规则）")
    cp.add_argument("--base", type=float, help="底薪（简配）")
    cp.add_argument("--rate", type=float, help="单一提成比例（简配，如 0.05）")
    cp.add_argument("--deductions", type=float, help="固定扣除（简配）")
    cp.add_argument("--period", help="计算周期 month/quarter/year")
    cp.set_defaults(func=cmd_comp)

    pl = sub.add_parser("plan", help="目标规划：反推所需业绩门槛")
    pl.add_argument("--target-income", type=float, help="目标净收入（按薪酬周期）")
    pl.add_argument("--goal-amount", type=float, help="总目标额（如存够 30 万）")
    pl.add_argument("--months", type=int, help="达成总目标所需月数")
    pl.add_argument("--monthly-expense", type=float, help="月生活开销（计入所需净收入）")
    pl.add_argument("--avg-deal", type=float, help="平均客单价，用于推算成交单数")
    pl.add_argument("--workdays", type=int, help="每月工作天数，用于推算日均目标")
    pl.set_defaults(func=cmd_plan)

    return ap


def main():
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except Exception as e:
        print(f"❌ 错误：{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
