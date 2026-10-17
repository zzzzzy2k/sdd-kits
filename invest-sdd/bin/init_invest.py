#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_invest.py — invest-sdd 脚手架

所有文件都从 decisions/_templates/ 等模板目录生成，模板即真源：
你改了模板，之后新建的决策书就跟着变。

用法：
    python bin/init_invest.py                     # 初始化目录骨架（幂等，不覆盖）
    python bin/init_invest.py decision 600519 贵州茅台
    python bin/init_invest.py decision 510880 红利ETF --type etf --strategy dividend
    python bin/init_invest.py strategy dividend 红利低波
    python bin/init_invest.py holding 600519
    python bin/init_invest.py plan 600519
    python bin/init_invest.py task 600519 buy      # 生成交易执行卡
    python bin/init_invest.py monitor 600519       # 生成持仓跟踪卡
    python bin/init_invest.py status               # 一览所有决策书状态
    python bin/init_invest.py demo                 # 生成一份走完全流程的样例

选项：
    --force     覆盖已存在的文件（默认跳过）
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DIRS = [
    "bin",
    "decisions/_templates",
    "plans/_templates",
    "strategies/_templates",
    "holdings/_templates",
    ".state",
]

STATE_ORDER = [
    "idea", "research", "review", "accepted",
    "executing", "holding", "closed", "archived",
]
STATE_CN = {
    "idea": "想法", "research": "调研中", "review": "评审中",
    "accepted": "已批准", "executing": "执行中", "holding": "持有中",
    "closed": "已完结", "archived": "已归档",
}
TRADE_OPS = {"buy": "买入", "sell": "卖出", "add": "加仓", "reduce": "减仓"}

OK = "  [OK] "
SKIP = "  [--] "
ERR = "  [!!] "


def today() -> str:
    return datetime.date.today().isoformat()


def ensure_dirs() -> None:
    for d in DIRS:
        (ROOT / d).mkdir(parents=True, exist_ok=True)


def read_tpl(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        print(ERR + f"模板缺失：{rel}")
        print("      模板目录是本体系的真源，缺了没法生成新文件。")
        print("      请从设计方案重新导出 templates 目录。")
        sys.exit(2)
    return p.read_text(encoding="utf-8")


def render(text: str, mapping: dict) -> str:
    for k, v in mapping.items():
        text = text.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{\w+\}\}", text)
    if left:
        print(ERR + f"模板里有未定义的占位符：{', '.join(sorted(set(left)))}")
        sys.exit(2)
    return text


def write_file(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        print(SKIP + f"已存在，跳过：{path.relative_to(ROOT).as_posix()}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(OK + f"已生成：{path.relative_to(ROOT).as_posix()}")
    return True


# ── 各类型脚手架 ────────────────────────────────────────────────────────────

def new_decision(sid: str, name: str, dtype: str = "stock",
                 gran: str = "symbol", strategy: str = "", force: bool = False) -> None:
    mapping = {
        "ID": sid, "NAME": name, "TYPE": dtype,
        "GRANULARITY": gran, "DATE": today(),
    }
    content = render(read_tpl("decisions/_templates/decision.md"), mapping)
    if strategy:
        content = content.replace("strategy:\n", f"strategy: {strategy}\n", 1)

    folder = ROOT / "decisions" / sid
    write_file(folder / "decision.md", content, force)

    review = render(read_tpl("decisions/_templates/review.md"),
                    {"ID": sid, "NAME": name, "DATE": today()})
    write_file(folder / "review.md", review, force)

    print(f"\n下一步：填 decisions/{sid}/decision.md 的「一、投资假设」")
    print(f"        状态推进：idea → research → review → accepted")
    print(f"        每推进一步跑一次：python bin/guard_invest.py {sid}")


def new_strategy(sid: str, name: str, force: bool = False) -> None:
    folder = ROOT / "strategies" / sid
    mapping = {"ID": sid, "NAME": name, "DATE": today()}
    write_file(folder / "strategy.md",
               render(read_tpl("strategies/_templates/strategy.md"), mapping), force)
    write_file(folder / "strategy_review.md",
               render(read_tpl("strategies/_templates/strategy_review.md"), mapping), force)


def new_holding(sid: str, name: str = "", force: bool = False) -> None:
    content = render(read_tpl("holdings/_templates/holding.md"),
                     {"ID": sid, "NAME": name or sid, "DATE": today()})
    write_file(ROOT / "holdings" / f"{sid}.md", content, force)


def new_plan(sid: str, name: str = "", force: bool = False) -> None:
    content = render(read_tpl("plans/_templates/plan.md"),
                     {"ID": sid, "NAME": name or sid, "DATE": today()})
    write_file(ROOT / "plans" / sid / "plan.md", content, force)


def next_seq(folder: Path) -> int:
    if not folder.is_dir():
        return 1
    nums = [int(m.group(1)) for f in folder.glob("task-*.md")
            if (m := re.match(r"task-(\d+)", f.name))]
    return max(nums) + 1 if nums else 1


def new_task(sid: str, op: str = "buy", name: str = "", force: bool = False) -> None:
    op = op.lower()
    if op not in TRADE_OPS:
        print(ERR + f"未知操作 `{op}`，可选：{' / '.join(TRADE_OPS)}")
        sys.exit(2)
    folder = ROOT / "plans" / sid
    seq = next_seq(folder)
    path = folder / f"task-{seq:02d}-{op}.md"
    content = render(read_tpl("plans/_templates/task.trade.md"),
                     {"ID": sid, "NAME": name or sid, "DATE": today(), "OP": op})
    write_file(path, content, force)


def new_monitor(sid: str, name: str = "", force: bool = False) -> None:
    folder = ROOT / "plans" / sid
    seq = next_seq(folder)
    path = folder / f"task-{seq:02d}-monitor.md"
    content = render(read_tpl("plans/_templates/task.monitor.md"),
                     {"ID": sid, "NAME": name or sid, "DATE": today()})
    write_file(path, content, force)


# ── status 一览 ─────────────────────────────────────────────────────────────

def show_status() -> None:
    base = ROOT / "decisions"
    folders = sorted(p for p in base.iterdir()
                     if p.is_dir() and p.name != "_templates") if base.is_dir() else []
    if not folders:
        print("还没有任何决策书。用 `python bin/init_invest.py decision <id> <名称>` 建第一份。")
        return

    def txt_width(s: str) -> int:
        return sum(2 if ord(c) > 0x2E80 else 1 for c in s)

    def pad(s: str, w: int) -> str:
        return s + " " * max(0, w - txt_width(s))

    rows = []
    for d in folders:
        f = d / "decision.md"
        if not f.exists():
            rows.append((d.name, "-", "-", "缺 decision.md", "", ""))
            continue
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        meta = {}
        lines = text.splitlines()
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() in ("---", "..."):
                    for raw in lines[1:i]:
                        if ":" in raw and not raw.strip().startswith("#"):
                            k, v = raw.split(":", 1)
                            meta[k.strip()] = v.strip()
                    break
        status = meta.get("status", "?")
        verdict = ""
        rv = d / "review.md"
        if rv.exists():
            rtext = rv.read_text(encoding="utf-8-sig", errors="replace")
            m = re.search(r"^verdict:\s*(\S+)", rtext, re.M)
            verdict = m.group(1) if m else ""
        rows.append((
            d.name,
            meta.get("name", d.name),
            meta.get("type", ""),
            state_cell(status),
            verdict or "-",
            meta.get("updated", "") or "-",
        ))

    heads = ("标的", "名称", "类型", "状态", "评审", "更新")
    widths = [max(txt_width(str(r[i])) for r in rows + [heads]) for i in range(6)]
    widths = [max(w, 6) for w in widths]

    print("  " + "  ".join(pad(h, widths[i]) for i, h in enumerate(heads)))
    print("  " + "  ".join("-" * widths[i] for i in range(6)))
    for r in rows:
        print("  " + "  ".join(pad(str(r[i]), widths[i]) for i in range(6)))

    counter: dict[str, int] = {}
    for d in folders:
        f = d / "decision.md"
        if not f.exists():
            continue
        m = re.search(r"^status:\s*(\S+)", f.read_text(encoding="utf-8-sig", errors="replace"), re.M)
        if m:
            counter[m.group(1)] = counter.get(m.group(1), 0) + 1
    print()
    print("  " + " · ".join(f"{STATE_CN.get(k, k)} {v}" for k, v in
                            sorted(counter.items(), key=lambda kv: STATE_ORDER.index(kv[0])
                                   if kv[0] in STATE_ORDER else 99)))


def state_cell(status: str) -> str:
    return f"{status}({STATE_CN.get(status, '?')})" if status in STATE_CN else str(status)


# ── 入口 ────────────────────────────────────────────────────────────────────

USAGE = """invest-sdd 脚手架

  python bin/init_invest.py                      初始化目录骨架
  python bin/init_invest.py decision <id> <名称>  新建决策书
  python bin/init_invest.py strategy <id> <名称>  新建策略包
  python bin/init_invest.py holding <id>         新建持仓卡
  python bin/init_invest.py plan <id>            新建交易计划
  python bin/init_invest.py task <id> <op>       新建交易执行卡（op: buy/sell/add/reduce）
  python bin/init_invest.py monitor <id>         新建持仓跟踪卡
  python bin/init_invest.py status               查看所有决策书状态
  python bin/init_invest.py demo                 生成完整流程样例
"""


def main(argv: list[str]) -> int:
    force = "--force" in argv
    args = [a for a in argv if a != "--force"]
    cmd = args[0].lower() if args else "init"

    if cmd in ("-h", "--help", "help"):
        print(USAGE)
        return 0

    ensure_dirs()

    if cmd == "init":
        print(f"  invest-sdd 初始化   {ROOT}")
        print(f"  " + "-" * 56)
        for d in DIRS:
            print(OK + d + "/")
        for t in sorted(ROOT.glob("**/_templates/*.md")):
            print("  [tpl] " + t.relative_to(ROOT).as_posix())
        if not (ROOT / "RULES.md").exists():
            print(ERR + "RULES.md 缺失 —— 纪律基准不在，护栏无从校验")
        print()
        print("  下一步：改 RULES.md 里 RULES-BEGIN/END 之间的数值（那是你的纪律）")
        print("          然后 python bin/init_invest.py decision 600519 贵州茅台")
        return 0

    if cmd == "decision":
        if len(args) < 3:
            print(ERR + "用法：init_invest.py decision <标的id> <名称> [--type stock|etf] "
                        "[--granularity symbol|trade] [--strategy <策略id>]")
            return 2
        dtype, gran, strategy = "stock", "symbol", ""
        rest = args[3:]
        i = 0
        while i < len(rest):
            if rest[i] == "--type" and i + 1 < len(rest):
                dtype = rest[i + 1]
                i += 2
            elif rest[i] == "--granularity" and i + 1 < len(rest):
                gran = rest[i + 1]
                i += 2
            elif rest[i] == "--strategy" and i + 1 < len(rest):
                strategy = rest[i + 1]
                i += 2
            else:
                i += 1
        new_decision(args[1], args[2], dtype, gran, strategy, force)
        return 0

    if cmd == "strategy":
        if len(args) < 3:
            print(ERR + "用法：init_invest.py strategy <策略id> <名称>")
            return 2
        new_strategy(args[1], args[2], force)
        return 0

    if cmd == "holding":
        if len(args) < 2:
            print(ERR + "用法：init_invest.py holding <标的id> [名称]")
            return 2
        new_holding(args[1], args[2] if len(args) > 2 else "", force)
        return 0

    if cmd == "plan":
        if len(args) < 2:
            print(ERR + "用法：init_invest.py plan <标的id> [名称]")
            return 2
        new_plan(args[1], args[2] if len(args) > 2 else "", force)
        return 0

    if cmd == "task":
        if len(args) < 2:
            print(ERR + "用法：init_invest.py task <标的id> [op]")
            return 2
        new_task(args[1], args[2] if len(args) > 2 else "buy",
                 args[3] if len(args) > 3 else "", force)
        return 0

    if cmd == "monitor":
        if len(args) < 2:
            print(ERR + "用法：init_invest.py monitor <标的id>")
            return 2
        new_monitor(args[1], args[2] if len(args) > 2 else "", force)
        return 0

    if cmd == "status":
        show_status()
        return 0

    if cmd == "demo":
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "invest_demo", Path(__file__).resolve().parent / "demo.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.build_demo(ROOT)
        return 0

    print(ERR + f"未知命令 `{cmd}`")
    print()
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
