#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selfcheck.py — invest-sdd 护栏回归测试

护栏脚本最危险的失效方式是「静默放行」：没报错，但规则其实没生效。
所以每条规则都必须有一个「故意违规 → 必须被拦」的反向用例。

跑法：
    python .dev/selfcheck.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
PY = sys.executable

DEC = """---
id: {sid}
name: {name}
type: stock
granularity: symbol
status: {status}
strategy: {strategy}
updated: 2026-10-17
---

# 决策书：{name}（{sid}）

## 一、投资假设（★核心，必须可证伪）

- **逻辑**（为什么买，一句话）：{logic}
- **关键假设**（可验证指标）：{keyhyp}
- **证伪条件**（什么情况证明我看错了）：{falsify}
- **验证方式**（数据从哪看、多久看一次）：每季度财报核对一次

## 二、deliverables（本次交易的交付）

- [ ] **买入计划**：1.00 元以下分批，仓位 10%
- [ ] **卖出计划**：止损线 {stop}；止盈 +20%
- [ ] **持有期预期**：6 到 24 个月

## 三、out-of-scope（不做什么）

- ❌ **不做**：T+0、追涨、计划外加仓
- ❌ **不因**：单日跌幅超过 3% 就卖出

## 五、validation（验收依据 → 引用 RULES.md）

- [ ] 仓位 10% 小于上限
"""

REV = """---
decision: {sid}
reviewed_on: {date}
reviewer: 自己
verdict: {verdict}
hypothesis_result: {result}
---

# 评审 / 复盘：{name}（{sid}）

## 事前评审（review 阶段，accepted 前必填）

| 日期 | 评审人 | 挑战点 | 结论 |
|---|---|---|---|
| {date} | 自己 | 假设是否可证伪？ | 通过 |
| {date} | 自己 | 仓位是否超限？ | 通过 |

- **评审结论**：通过

## 事后复盘（closed 阶段，closed 前必填）

{retro}
"""


# ── 工具 ────────────────────────────────────────────────────────────────────

class Case:
    def __init__(self, name: str) -> None:
        self.name = name
        self.failed = False
        self.note = ""

    def expect(self, cond: bool, msg: str) -> "Case":
        if not cond:
            self.failed = True
            self.note += f"\n      ✗ {msg}"
        return self


def sandbox() -> Path:
    """复制一份干净副本，避免污染真实数据。"""
    tmp = Path(tempfile.mkdtemp(prefix="invest-sdd-test-"))
    dst = tmp / "invest-sdd"
    shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns(
        "__pycache__", ".state", "examples"))
    for sub in ("decisions", "plans", "strategies", "holdings"):
        base = dst / sub
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if p.name == "_templates":
                continue
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
    return dst


def run(cwd: Path, *args: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([PY, *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def write_decision(root: Path, sid: str = "600519", name: str = "测试标的",
                   status: str = "idea", strategy: str = "",
                   logic: str = "白酒需求复苏，龙头份额持续提升。",
                   keyhyp: str = "营收增速达到 12% 以上。",
                   falsify: str = "连续两个季度营收负增长。",
                   stop: str = "-8%") -> Path:
    p = root / "decisions" / sid / "decision.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(DEC.format(sid=sid, name=name, status=status, strategy=strategy,
                            logic=logic, keyhyp=keyhyp, falsify=falsify, stop=stop),
                 encoding="utf-8")
    return p


def write_review(root: Path, sid: str = "600519", name: str = "测试标的",
                 verdict: str = "pass", date: str = "2026-10-17",
                 result: str = "", retro: str = "") -> Path:
    p = root / "decisions" / sid / "review.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not retro:
        retro = ("- 假设兑现对照表：营收增速 14%，高于 12% 的目标。\n"
                 "- 纪律检查：止损未触发，无计划外操作。\n"
                 "- 情绪反思：下跌期间没有恐慌卖出。\n"
                 "- 经验：沉淀到 RULES 第四章。")
    p.write_text(REV.format(sid=sid, name=name, verdict=verdict, date=date,
                            result=result, retro=retro), encoding="utf-8")
    return p


def write_holding(root: Path, sid: str = "600519", weight: str = "10",
                  stop_loss: str = "-8%", decision: str = "600519") -> Path:
    p = root / "holdings" / f"{sid}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"""---
id: {sid}
name: 测试标的
decision: {decision}
weight: {weight}
cost: 100.00
stop_loss: {stop_loss}
updated: 2026-10-17
---

# 持仓卡
""", encoding="utf-8")
    return p


def write_strategy(root: Path, sid: str = "s1", status: str = "accepted") -> Path:
    d = root / "strategies" / sid
    d.mkdir(parents=True, exist_ok=True)
    (d / "strategy.md").write_text(f"""---
id: {sid}
name: 测试策略
version: 1.0
status: {status}
updated: 2026-10-17
---

# 策略包
""", encoding="utf-8")
    (d / "strategy_review.md").write_text("""---
strategy: s1
reviewed_on: 2026-10-17
verdict: pass
---

# 策略评审
""", encoding="utf-8")
    return d


def write_task(root: Path, sid: str = "600519", status: str = "READY",
               filled: str = "false", name: str = "task-01-buy.md",
               unchecked: int = 1, blocked: str = "") -> Path:
    p = root / "plans" / sid / name
    p.parent.mkdir(parents=True, exist_ok=True)
    box = "[ ]" if unchecked else "[x]"
    p.write_text(f"""---
decision: {sid}
kind: trade
op: buy
status: {status}
filled: {filled}
fill_price: {"1.00" if filled == "true" else ""}
fill_qty: {"1000" if filled == "true" else ""}
fill_date: {"2026-10-17" if filled == "true" else ""}
blocked_reason: {blocked}
---

# 交易执行卡

## 二、验收清单（全勾才能 DONE）

- {box} 对应决策书状态 = accepted
""", encoding="utf-8")
    return p


def set_rules_weight(root: Path, value: str) -> None:
    p = root / "RULES.md"
    text = p.read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("max_single_weight"):
            lines.append(f"max_single_weight = {value}")
        else:
            lines.append(line)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def has(out: str, *needles: str) -> bool:
    return all(n in out for n in needles)


# ── 用例 ────────────────────────────────────────────────────────────────────

CASES: list = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def t01_空模板直接接受必须被拦(c: Case) -> None:
    root = sandbox()
    p = write_decision(root, status="accepted", logic="", keyhyp="", falsify="", stop="")
    write_review(root, verdict="pending", date="")
    code, out = run(root, "bin/guard_invest.py", "600519")
    c.expect(code == 1, "应当退出码 1")
    c.expect(has(out, "verdict"), "应报评审未通过")
    c.expect(has(out, "证伪条件"), "应报证伪条件为空")
    c.expect(has(out, "止损线"), "应报缺止损线")


@case
def t02_填完整走通全程应通过(c: Case) -> None:
    root = sandbox()
    write_decision(root, status="accepted")
    write_review(root, verdict="pass")
    write_holding(root)
    code, out = run(root, "bin/guard_invest.py")
    c.expect(code == 0, f"合规决策书应通过，实际退出码 {code}\n{out}")
    c.expect("0 个错误" in out, "应为 0 错误")


@case
def t03_模糊词必须被拦(c: Case) -> None:
    root = sandbox()
    write_decision(root, status="accepted",
                   logic="感觉会涨，先买点。")
    write_review(root, verdict="pass")
    code, out = run(root, "bin/guard_invest.py", "600519")
    c.expect(code == 1, "应当退出码 1")
    c.expect(has(out, "不可验收表述"), "应报强模糊词")


@case
def t04_弱模糊词在草稿只提醒_接受后报错(c: Case) -> None:
    root = sandbox()
    write_decision(root, status="research", logic="可能因为消费复苏吧。")
    code1, out1 = run(root, "bin/guard_invest.py", "600519")
    c.expect(code1 == 0, "草稿阶段不应因弱模糊词失败")
    c.expect(has(out1, "模糊表述"), "草稿阶段应给警告")

    write_decision(root, status="accepted", logic="可能因为消费复苏吧。")
    write_review(root, verdict="pass")
    code2, out2 = run(root, "bin/guard_invest.py", "600519")
    c.expect(code2 == 1, "accepted 后弱模糊词应升级为错误")
    c.expect(has(out2, "已 accepted，必须改成可验证指标"), "应提示改成可验证指标")


@case
def t05_未接受就成交必须被拦(c: Case) -> None:
    root = sandbox()
    write_decision(root, status="review")
    write_review(root, verdict="pass")
    write_task(root, status="DONE", filled="true", unchecked=0)
    code, out = run(root, "bin/guard_invest.py", "600519")
    c.expect(code == 1, "先斩后奏必须拦")
    c.expect(has(out, "未 accepted"), "应报交易早于 accepted")


@case
def t06_持仓超上限必须被拦(c: Case) -> None:
    root = sandbox()
    write_decision(root, status="holding")
    write_review(root, verdict="pass")
    write_holding(root, weight="35")
    code, out = run(root, "bin/guard_invest.py")
    c.expect(code == 1, "仓位超限必须拦")
    c.expect(has(out, "超过 RULES"), "应报仓位漂移")


@case
def t07_改RULES数值应立即生效(c: Case) -> None:
    root = sandbox()
    set_rules_weight(root, "40")
    write_decision(root, status="holding")
    write_review(root, verdict="pass")
    write_holding(root, weight="35")
    code, out = run(root, "bin/guard_invest.py")
    c.expect(code == 0, f"上限调到 40 后 35% 应合规，实际 {code}\n{out}")


@case
def t08_清仓无复盘必须被拦(c: Case) -> None:
    root = sandbox()
    write_decision(root, status="closed")
    write_review(root, verdict="pass", result="")
    code, out = run(root, "bin/guard_invest.py", "600519")
    c.expect(code == 1, "无复盘不能 closed")
    c.expect(has(out, "hypothesis_result"), "应报假设兑现结果未填")


@case
def t09_复盘到位则放行(c: Case) -> None:
    root = sandbox()
    write_decision(root, status="closed")
    write_review(root, verdict="pass", result="fulfilled")
    code, out = run(root, "bin/guard_invest.py", "600519")
    c.expect(code == 0, f"复盘齐全应通过，实际 {code}\n{out}")


@case
def t10_引用未接受的策略包必须被拦(c: Case) -> None:
    root = sandbox()
    write_strategy(root, "draft-strat", status="draft")
    write_decision(root, status="accepted", strategy="draft-strat")
    write_review(root, verdict="pass")
    code, out = run(root, "bin/guard_invest.py", "600519")
    c.expect(code == 1, "引用 draft 策略包必须拦")
    c.expect(has(out, "只有 accepted 才能被引用"), "应报策略包未接受")


@case
def t11_引用已接受策略包应放行(c: Case) -> None:
    root = sandbox()
    write_strategy(root, "ok-strat", status="accepted")
    write_decision(root, status="accepted", strategy="ok-strat")
    write_review(root, verdict="pass")
    code, out = run(root, "bin/guard_invest.py", "600519")
    c.expect(code == 0, f"应通过，实际 {code}\n{out}")


@case
def t12_任务卡DONE但验收未勾必须被拦(c: Case) -> None:
    root = sandbox()
    write_decision(root, status="accepted")
    write_review(root, verdict="pass")
    write_task(root, status="DONE", filled="false", unchecked=1)
    code, out = run(root, "bin/guard_invest.py", "600519")
    c.expect(code == 1, "验收未勾不能 DONE")
    c.expect(has(out, "未勾"), "应报验收清单未勾")


@case
def t13_状态回退应给警告(c: Case) -> None:
    root = sandbox()
    write_decision(root, status="accepted")
    write_review(root, verdict="pass")
    run(root, "bin/guard_invest.py", "600519")   # 建立快照
    write_decision(root, status="idea")
    code, out = run(root, "bin/guard_invest.py", "600519")
    c.expect(has(out, "回退"), "应提示状态回退")
    c.expect(code == 0, "回退是警告不是错误")


@case
def t14_模板未替换应被拦(c: Case) -> None:
    root = sandbox()
    tpl = (root / "decisions" / "_templates" / "decision.md")
    p = root / "decisions" / "600519" / "decision.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(tpl.read_text(encoding="utf-8"), encoding="utf-8")
    code, out = run(root, "bin/guard_invest.py", "600519")
    c.expect(code == 1, "模板副本必须拦")
    c.expect(has(out, "占位符"), "应报未替换占位符")


@case
def t15_持有卡止损线为空应提醒(c: Case) -> None:
    root = sandbox()
    write_decision(root, status="holding")
    write_review(root, verdict="pass")
    write_holding(root, stop_loss="")
    code, out = run(root, "bin/guard_invest.py")
    c.expect(has(out, "stop_loss"), "应提醒止损线缺失")


@case
def t16_脚手架与状态表可用(c: Case) -> None:
    root = sandbox()
    code1, out1 = run(root, "bin/init_invest.py", "decision", "000001", "平安银行")
    c.expect(code1 == 0, "新建决策书应成功")
    c.expect((root / "decisions/000001/decision.md").exists(), "decision.md 应生成")
    c.expect((root / "decisions/000001/review.md").exists(), "review.md 应生成")
    c.expect("{{" not in (root / "decisions/000001/decision.md").read_text(encoding="utf-8"),
             "占位符应全部替换")

    code2, out2 = run(root, "bin/init_invest.py", "status")
    c.expect(code2 == 0, "status 应成功")
    c.expect("想法" in out2, "状态表应显示中文状态")

    code3, _ = run(root, "bin/init_invest.py", "task", "000001", "buy")
    c.expect(code3 == 0, "生成任务卡应成功")
    code4, _ = run(root, "bin/init_invest.py", "task", "000001", "add")
    c.expect((root / "plans/000001/task-02-add.md").exists(), "序号应自增到 02")


@case
def t17_幂等不覆盖(c: Case) -> None:
    root = sandbox()
    write_decision(root, status="idea", logic="已经写好的内容。")
    before = (root / "decisions/600519/decision.md").read_text(encoding="utf-8")
    code, out = run(root, "bin/init_invest.py", "decision", "600519", "测试标的")
    after = (root / "decisions/600519/decision.md").read_text(encoding="utf-8")
    c.expect(before == after, "默认不覆盖已有文件")
    c.expect("跳过" in out, "应提示跳过")


@case
def t18_全文demo无硬错误(c: Case) -> None:
    root = sandbox()
    code, out = run(root, "bin/init_invest.py", "demo")
    c.expect(code == 0, "demo 应成功")
    c.expect((root / "examples/DEMO-001/decision.md").exists(), "样例决策书应生成")


# ── 主流程 ──────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 66)
    print("  invest-sdd 护栏回归测试")
    print("=" * 66)
    results: list[tuple[str, Case]] = []
    for fn in CASES:
        title = fn.__name__
        c = Case(title)
        try:
            fn(c)
        except Exception as exc:  # noqa: BLE001
            c.failed = True
            c.note += f"\n      ✗ 异常：{exc!r}"
        results.append((title, c))
        print(f"  {'FAIL' if c.failed else 'PASS'}  {title}{c.note if c.failed else ''}")

    bad = [t for t, c in results if c.failed]
    print("-" * 66)
    print(f"  {len(results) - len(bad)} / {len(results)} 通过")
    if bad:
        print("  失败用例：" + "、".join(bad))
        return 1
    print("  护栏有效：每条规则都拦得住。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
