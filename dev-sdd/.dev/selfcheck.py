#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selfcheck.py — dev-sdd 护栏回归测试

护栏最危险的失效方式是「静默放行」：没报错，但规则其实没生效。
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

SPEC_TPL = """---
id: {sid}
title: {title}
type: feature
status: {status}
priority: P1
owner: 自己
adr: {adr}
module: {module}
depends_on: {depends}
updated: 2026-10-17
---

# 需求规格：{title}（{sid}）

## 一、背景与问题（为什么做）

- **现状**：{cur}
- **问题**：{prob}

## 二、目标 / 不做什么

### deliverables（交付物）

- [ ] 登录接口
- [ ] 鉴权中间件

### out-of-scope（不做什么）

{scope}

## 三、需求描述

- **用户故事**：作为已注册用户，我希望登录后访问自己的数据。
- **主流程**：
  1. 输入账号密码

## 四、技术方案与风险

- **方案概要**：JWT

## 五、验收标准（validation）

{acc}

## 六、变更记录

| 日期 | 变更 | 原因 | 影响 |
|---|---|---|---|
| | | | |
"""

REVIEW_TPL = """---
spec: {sid}
reviewed_on: {date}
reviewer: 自己
verdict: {verdict}
goal_achieved: {goal}
---

# 评审 / 复盘：{title}（{sid}）

## 事前评审（review 阶段，accepted 前必填）

| 日期 | 评审人 | 挑战点 | 结论 |
|---|---|---|---|
| {date} | 自己 | 边界清楚吗？ | 通过 |

- **评审结论**：通过

## 事后复盘（done 阶段，done 前必填）

- **实际用时**：预估 5 天 ／ 实际 6 天
- **返工次数**：1
- **踩到的坑**：{pits}
- **经验**：{exp}
"""

TASK_TPL = """---
spec: {sid}
task: {tid}
kind: {kind}
status: {status}
estimate_hours: {hours}
updated: 2026-10-17
---

# 任务卡：{tid} {title}

## 一、做什么

- **内容**：实现登录

## 二、验收清单（全勾才能 DONE）

{checks}

## 四、阻塞说明（BLOCKED 时必填）

- {blocked}
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
    tmp = Path(tempfile.mkdtemp(prefix="dev-sdd-test-"))
    dst = tmp / "dev-sdd"
    shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns(
        "__pycache__", ".state", "examples"))
    for sub in ("specs", "tasks", "modules"):
        base = dst / sub
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if p.name == "_templates":
                continue
            if p.is_dir():
                shutil.rmtree(p)
    adr = dst / "adr"
    if adr.is_dir():
        for p in adr.glob("*.md"):
            p.unlink()
    return dst


def run(cwd: Path, *args: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([PY, *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


ACC_OK = ("- [ ] 正确账号密码返回 200 与 token\n"
          "- [ ] 错误密码返回 401\n"
          "- [ ] 不带 token 访问受保护接口返回 401")


def make_spec(root: Path, sid: str = "SPEC-001", title: str = "登录",
              status: str = "draft", cur: str = "系统没有登录，任何人可访问全部数据。",
              prob: str = "客户要求多用户隔离。",
              scope: str = "- ❌ 不做第三方登录\n- ❌ 不做密码找回",
              acc: str = ACC_OK, adr: str = "", module: str = "",
              depends: str = "") -> Path:
    p = root / "specs" / sid / "spec.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(SPEC_TPL.format(sid=sid, title=title, status=status, cur=cur,
                                 prob=prob, scope=scope, acc=acc, adr=adr,
                                 module=module, depends=depends),
                 encoding="utf-8")
    return p


def make_review(root: Path, sid: str = "SPEC-001", title: str = "登录",
                verdict: str = "pass", date: str = "2026-10-17",
                goal: str = "", pits: str = "并发下计数丢失。",
                exp: str = "沉淀到模块包。") -> Path:
    p = root / "specs" / sid / "review.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(REVIEW_TPL.format(sid=sid, title=title, verdict=verdict,
                                   date=date, goal=goal, pits=pits, exp=exp),
                 encoding="utf-8")
    return p


def make_task(root: Path, sid: str = "SPEC-001", tid: str = "T-001",
              title: str = "登录接口", kind: str = "feature",
              status: str = "READY", hours: str = "4",
              checked: int = 4, test_checked: bool = True,
              with_test: bool = True, blocked: str = "") -> Path:
    """checked = 前 N 项已勾；with_test=False 表示这张卡根本没有测试验收项。"""
    items = ["需求规格状态 = accepted 或 implementing", "功能按验收标准实现"]
    if with_test:
        items.append("单元测试已写且通过")
    items.append("无回归：原有测试全部通过")

    lines = []
    for i, it in enumerate(items):
        mark = "x" if i < checked else " "
        if with_test and i == 2 and not test_checked:
            mark = " "
        lines.append(f"- [{mark}] {it}")

    p = root / "tasks" / sid / f"{tid}-{kind}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(TASK_TPL.format(sid=sid, tid=tid, title=title, kind=kind,
                                 status=status, hours=hours,
                                 checks="\n".join(lines), blocked=blocked),
                 encoding="utf-8")
    return p


def make_adr(root: Path, aid: str = "ADR-001", status: str = "accepted",
             options: int = 2) -> Path:
    rows = "\n".join(f"| {chr(65 + i)}. 方案{i + 1} | 优点 | 缺点 | 可行 |"
                     for i in range(options))
    p = root / "adr" / f"{aid}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"""---
id: {aid}
title: 选数据库
status: {status}
date: 2026-10-17
supersedes:
---

# {aid}：选数据库

## 一、背景

- **要解决的问题**：存数据

## 二、选项对比

| 选项 | 优点 | 缺点 | 可行性 |
|---|---|---|---|
{rows}

## 三、决策

> 选定：A

## 四、后果

- **好处**：简单
- **什么情况下应该重新考虑这条决策**：数据量增长十倍时
""", encoding="utf-8")
    return p


def make_module(root: Path, mid: str = "auth-jwt", status: str = "accepted",
                review_ok: bool = True) -> Path:
    d = root / "modules" / mid
    d.mkdir(parents=True, exist_ok=True)
    (d / "module.md").write_text(f"""---
id: {mid}
name: JWT 方案
version: 1.0
status: {status}
updated: 2026-10-17
---

# 方案包

## 一、适用场景

- **什么时候用**：单体后端
- **什么时候不用**：需要即时踢下线
""", encoding="utf-8")
    (d / "module_review.md").write_text(
        "---\nmodule: %s\nreviewed_on: 2026-10-17\nverdict: %s\n---\n\n# 评审\n"
        % (mid, "pass" if review_ok else "reject"), encoding="utf-8")
    return d


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
    make_spec(root, status="accepted", cur="", prob="", scope="- ❌ 不做：", acc="")
    make_review(root, verdict="pending", date="", goal="")
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "应当退出码 1")
    c.expect(has(out, "verdict"), "应报评审未通过")
    c.expect(has(out, "out-of-scope"), "应报不做什么为空")
    c.expect(has(out, "验收标准只有 0 条"), "应报验收标准为空")


@case
def t02_填完整应通过(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="accepted")
    make_review(root, verdict="pass")
    make_task(root, status="DONE", checked=4)
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 0, f"合规应通过，实际 {code}\n{out}")
    c.expect("0 个错误" in out, "应为 0 错误")


@case
def t03_敷衍词必须被拦(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="accepted", prob="先这样吧，后面再想。")
    make_review(root, verdict="pass")
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "应当退出码 1")
    c.expect(has(out, "敷衍表述"), "应报强模糊词")


@case
def t04_弱模糊词草稿只提醒_接受后报错(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="draft", prob="登录功能待定。")
    code1, out1 = run(root, "bin/guard_dev.py")
    c.expect(code1 == 0, "草稿阶段不应因弱词失败")
    c.expect(has(out1, "模糊表述"), "草稿阶段应给警告")

    make_spec(root, status="accepted", prob="登录功能待定。")
    make_review(root, verdict="pass")
    code2, out2 = run(root, "bin/guard_dev.py")
    c.expect(code2 == 1, "accepted 后弱词应升级为错误")
    c.expect(has(out2, "已 accepted，必须改成明确描述"), "应提示改明确")


@case
def t05_空泛验收项必须被拦(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="accepted",
              acc="- [ ] 功能正常\n- [ ] 没问题\n- [ ] 可以了")
    make_review(root, verdict="pass")
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "空泛验收必须拦")
    c.expect(has(out, "太笼统"), "应报验收项笼统")


@case
def t06_验收条数不足应拦(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="accepted", acc="- [ ] 只写一条验收标准")
    make_review(root, verdict="pass")
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "条数不足应拦")
    c.expect(has(out, "只有 1 条"), "应报只有 1 条")


@case
def t07_不做什么为空应拦(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="accepted", scope="- ❌ 不做：\n- ❌ 不做：")
    make_review(root, verdict="pass")
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "out-of-scope 空必须拦")
    c.expect(has(out, "out-of-scope"), "应报不做什么为空")


@case
def t08_需求未接受就开工必须被拦(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="review")
    make_review(root, verdict="pass")
    make_task(root, status="IN_PROGRESS", checked=1)
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "提前开工必须拦")
    c.expect(has(out, "不能开工"), "应报任务早于 accepted")


@case
def t09_任务DONE但验收未勾必须被拦(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="implementing")
    make_review(root, verdict="pass")
    make_task(root, status="DONE", checked=2)
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "验收未勾不能 DONE")
    c.expect(has(out, "验收未勾"), "应报验收未勾")


@case
def t10_功能任务无测试必须被拦(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="implementing")
    make_review(root, verdict="pass")
    # 验收全勾，但整张卡里根本没有测试项（「无回归」不算写测试）
    make_task(root, status="DONE", checked=3, with_test=False)
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "无测试必须拦")
    c.expect(has(out, "必须有测试"), "应报测试要求")


@case
def t11_关掉测试要求后放行(c: Case) -> None:
    root = sandbox()
    p = root / "RULES.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "require_tests = true", "require_tests = false"), encoding="utf-8")
    make_spec(root, status="implementing")
    make_review(root, verdict="pass")
    make_task(root, status="DONE", checked=3, with_test=False)
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 0, f"关掉后应通过，实际 {code}\n{out}")


@case
def t12_工时超限应提醒(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="implementing")
    make_review(root, verdict="pass")
    make_task(root, status="READY", hours="20", checked=0)
    code, out = run(root, "bin/guard_dev.py")
    c.expect(has(out, "该拆了"), "应提醒拆任务")


@case
def t13_阻塞无原因应提醒(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="implementing")
    make_review(root, verdict="pass")
    make_task(root, status="BLOCKED", blocked="", checked=0)
    code, out = run(root, "bin/guard_dev.py")
    c.expect(has(out, "blocked_reason"), "应提醒写阻塞原因")


@case
def t14_需求done但任务没做完必须被拦(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="done")
    make_review(root, verdict="pass", goal="yes")
    make_task(root, tid="T-001", status="DONE", checked=4)
    make_task(root, tid="T-002", status="READY", checked=0)
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "任务没做完不能 done")
    c.expect(has(out, "没 DONE"), "应报未完成任务")


@case
def t15_无复盘不能done(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="done")
    make_review(root, verdict="pass", goal="", pits="", exp="")
    make_task(root, status="DONE", checked=4)
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "无复盘不能 done")
    c.expect(has(out, "goal_achieved"), "应报达成结果未填")
    c.expect(has(out, "复盘必须留下点什么"), "应报复盘为空")


@case
def t16_引用未接受方案包必须被拦(c: Case) -> None:
    root = sandbox()
    make_module(root, "auth-jwt", status="draft")
    make_spec(root, status="accepted", module="auth-jwt")
    make_review(root, verdict="pass")
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "引用 draft 方案包必须拦")
    c.expect(has(out, "只有 accepted 才能被引用"), "应报方案包未接受")


@case
def t17_引用不存在的ADR应拦(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="accepted", adr="ADR-999")
    make_review(root, verdict="pass")
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "引用不存在 ADR 必须拦")
    c.expect(has(out, "不存在的 ADR"), "应报 ADR 缺失")


@case
def t18_依赖成环必须被拦(c: Case) -> None:
    root = sandbox()
    for sid, dep in (("SPEC-001", "SPEC-002"), ("SPEC-002", "SPEC-001")):
        make_spec(root, sid=sid, depends=dep)
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "依赖成环必须拦")
    c.expect(has(out, "成环"), "应报依赖环")


@case
def t19_孤儿任务目录应提醒(c: Case) -> None:
    root = sandbox()
    make_task(root, sid="SPEC-999", tid="T-001", status="READY", checked=0)
    code, out = run(root, "bin/guard_dev.py")
    c.expect(has(out, "孤儿任务"), "应报孤儿任务")


@case
def t20_ADR只有一个选项应提醒(c: Case) -> None:
    root = sandbox()
    make_adr(root, options=1)
    make_spec(root, status="accepted")
    make_review(root, verdict="pass")
    code, out = run(root, "bin/guard_dev.py")
    c.expect(has(out, "少于 2 个候选"), "应提醒选项不足")


@case
def t21_状态回退应提醒(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="accepted")
    make_review(root, verdict="pass")
    run(root, "bin/guard_dev.py")
    make_spec(root, status="draft")
    code, out = run(root, "bin/guard_dev.py")
    c.expect(has(out, "回退"), "应提示状态回退")


@case
def t22_模板未替换应被拦(c: Case) -> None:
    root = sandbox()
    tpl = (root / "specs" / "_templates" / "spec.md").read_text(encoding="utf-8")
    p = root / "specs" / "SPEC-001" / "spec.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(tpl, encoding="utf-8")
    code, out = run(root, "bin/guard_dev.py")
    c.expect(code == 1, "模板副本必须拦")
    c.expect(has(out, "占位符"), "应报未替换占位符")


@case
def t23_脚手架与状态表可用(c: Case) -> None:
    root = sandbox()
    code1, _ = run(root, "bin/init_dev.py", "spec", "SPEC-002", "导出报表")
    c.expect(code1 == 0, "新建需求应成功")
    c.expect((root / "specs/SPEC-002/spec.md").exists(), "spec.md 应生成")
    txt = (root / "specs/SPEC-002/spec.md").read_text(encoding="utf-8")
    c.expect("{{" not in txt, "占位符应全部替换")

    code2, _ = run(root, "bin/init_dev.py", "task", "SPEC-002", "feature", "导出接口")
    c.expect(code2 == 0, "生成任务应成功")
    c.expect((root / "tasks/SPEC-002/T-001-feature.md").exists(), "任务号应自增到 001")
    run(root, "bin/init_dev.py", "task", "SPEC-002", "fix", "导出乱码")
    c.expect((root / "tasks/SPEC-002/T-002-fix.md").exists(), "第二个任务号应为 002")

    code3, out3 = run(root, "bin/init_dev.py", "status")
    c.expect(code3 == 0, "status 应成功")
    c.expect("草稿" in out3, "状态表应显示中文状态")

    code4, _ = run(root, "bin/init_dev.py", "adr", "选数据库")
    c.expect((root / "adr/ADR-001.md").exists(), "ADR 号应自动生成")


@case
def t24_幂等不覆盖(c: Case) -> None:
    root = sandbox()
    make_spec(root, status="draft", prob="已经写好的问题描述。")
    before = (root / "specs/SPEC-001/spec.md").read_text(encoding="utf-8")
    code, out = run(root, "bin/init_dev.py", "spec", "SPEC-001", "登录")
    after = (root / "specs/SPEC-001/spec.md").read_text(encoding="utf-8")
    c.expect(before == after, "默认不覆盖已有文件")
    c.expect("跳过" in out, "应提示跳过")


@case
def t25_demo生成完整样例(c: Case) -> None:
    root = sandbox()
    code, out = run(root, "bin/init_dev.py", "demo")
    c.expect(code == 0, "demo 应成功")
    c.expect((root / "examples/SPEC-001/spec.md").exists(), "样例需求应生成")
    c.expect((root / "examples/ADR-001.md").exists(), "样例 ADR 应生成")


# ── 主流程 ──────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 66)
    print("  dev-sdd 护栏回归测试")
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
