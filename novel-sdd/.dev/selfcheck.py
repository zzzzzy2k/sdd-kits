#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selfcheck.py — novel-sdd 护栏回归测试

这套护栏的价值全在「能不能真的拦住不一致」。所以每条规则都要有一个
「故意写错 → 必须被拦」的反向用例。

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

LONG_BODY = "这是一段用来凑字数的测试正文，写了很多句。" * 200

WORLD_TPL = """---
id: {wid}
name: 测试世界
version: {version}
status: {status}
changelog_count: 0
updated: 2026-10-17
---

# 世界观：测试世界（{wid}）

## 一、一句话核心

> 说明：一句话规则。

这世界有一条硬规则。

## 二、世界规则（硬约束）

{ruletxt}

## 三、基调与禁忌

- **基调**：冷峻
- **绝对不能有**：{taboo}

## 四、时空背景

- **时代**：古代

## 六、术语表（专有名词的唯一写法）

| 术语 | 唯一写法 | 禁止写法（出现即拦） | 释义 |
|---|---|---|---|
| 井 | 井 | 水井、神井 | 街心那口井 |
| 铜钱 | 铜钱 | 铜子、古钱 | 出生分到的旧钱 |

## 七、变更记录

{changelog}
"""

STORY_TPL = """---
id: {sid}
title: {title}
world: {world}
form: {form}
status: {status}
pov: 第三人称限知
tense: 过去时
word_target: 5000
updated: 2026-10-17
---

# 故事设定书：{title}（{sid}）

## 一、一句话故事

> 说明：谁，想要什么，什么挡着，付出什么代价。

{one}

## 二、不写什么（out-of-scope）★

> 说明：短篇写崩都是想塞太多。

{scope}

## 三、人物

| 人物 id | 在本篇的角色 | 本篇的欲望 |
|---|---|---|
{people}

## 四、结构

- **开头（钩子）**：有人来

## 五、验收标准

{acc}

## 七、变更记录

| 日期 | 变更 | 原因 |
|---|---|---|
| | | |
"""

CHAPTER_TPL = """---
story: {sid}
chapter: {cid}
title: {title}
status: {status}
words:
plants: {plants}
pays: {pays}
updated: 2026-10-17
---

# 第 {cid} 章：{title}

## 一、本章要完成的一件事

> 说明：一句话。

让主角发现铜钱。

## 四、验收清单（全勾才能 DONE）

{checks}

## 五、正文

{body}
"""

CHAR_TPL = """---
id: {cid}
name: {name}
world: {wid}
role: 配角
status: {cstatus}
age: 30
death_chapter: {death}
first_seen: ST-001
updated: 2026-10-17
---

# 人物：{name}（{cid}）

## 三、性格与动机

- **想要什么**（外在目标）：{want}
- **真正需要什么**（内在缺口）：有人相信他
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
    tmp = Path(tempfile.mkdtemp(prefix="novel-sdd-test-"))
    dst = tmp / "novel-sdd"
    shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns(
        "__pycache__", ".state", "examples"))
    for sub in ("worlds", "stories", "chapters"):
        base = dst / sub
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if p.name == "_templates":
                continue
            if p.is_dir():
                shutil.rmtree(p)
    return dst


def run(cwd: Path, *args: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([PY, *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def make_world(root: Path, wid: str = "W-001", status: str = "accepted",
               version: str = "1.0", ruletxt: str = "1. 井水映出七天后\n2. 铜钱可重来一次",
               taboo: str = "不能有超能力打斗",
               changelog: str = "| 2026-05-20 | 1.0 | 初版 | 建立 | 无 |",
               with_chars: bool = True) -> Path:
    folder = root / "worlds" / wid
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "world.md").write_text(
        WORLD_TPL.format(wid=wid, status=status, version=version, ruletxt=ruletxt,
                         taboo=taboo, changelog=changelog), encoding="utf-8")
    (folder / "world_review.md").write_text(
        f"---\nworld: {wid}\nreviewed_on: 2026-05-20\nverdict: pass\n---\n\n# 评审\n",
        encoding="utf-8")
    if with_chars:
        make_char(folder, "陈默", want="想知道预兆是什么意思")
        make_char(folder, "阿箬", want="想离开镇子", cstatus="dead",
                  death="ST-001/ch-02")
    return folder


def make_char(world_folder: Path, name: str, want: str = "想活下去",
              cstatus: str = "alive", death: str = "") -> Path:
    d = world_folder / "characters"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(CHAR_TPL.format(cid=name, name=name, wid=world_folder.name,
                                 cstatus=cstatus, death=death, want=want),
                 encoding="utf-8")
    return p


ACC_OK = ("- [ ] 结尾读者能自己推出真相\n"
          "- [ ] 老周的手指只提两处\n"
          "- [ ] 最后一句落在物件上")


def make_story(root: Path, sid: str = "ST-001", title: str = "井底的铜钱",
               world: str = "W-001", form: str = "short", status: str = "drafting",
               one: str = "陈默想知道井里的预兆，最后付出了记忆的代价。",
               scope: str = "- ❌ 不写妻子生前回忆\n- ❌ 不解释井的来历",
               people: str = "| 陈默 | 主角 | 想知道预兆 |",
               acc: str = ACC_OK, verdict: str = "pass",
               thesis: str = "") -> Path:
    folder = root / "stories" / sid
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "story.md").write_text(
        STORY_TPL.format(sid=sid, title=title, world=world, form=form, status=status,
                         one=one, scope=scope, people=people, acc=acc),
        encoding="utf-8")
    (folder / "review.md").write_text(
        f"---\nstory: {sid}\nreviewed_on: 2026-05-25\nreviewer: 自己\n"
        f"verdict: {verdict}\nthesis_kept: {thesis}\n---\n\n"
        "# 评审 / 复盘\n\n## 事后复盘（done 之前必填）\n\n- **经验**：留白比解释有力。\n",
        encoding="utf-8")
    (folder / "threads.md").write_text(
        f"---\nstory: {sid}\n---\n\n# 伏笔追踪\n\n"
        "| id | 伏笔内容 | 埋设章 | 计划回收章 | 状态 | 备注 |\n"
        "|---|---|---|---|---|---|\n"
        "| F-001 | 井上飘着铜钱 | ch-01 | ch-02 | paid | 结尾揭示 |\n"
        "|---|---|---|---|---|---|\n\n"
        "## 已放弃的伏笔\n\n"
        "| id | 为什么放弃 | 下一篇能否沿用 |\n|---|---|---|\n| | | |\n",
        encoding="utf-8")
    return folder


def make_chapter(root: Path, sid: str = "ST-001", cid: str = "ch-01",
                 status: str = "DONE", plants: str = "", pays: str = "F-001",
                 body: str = LONG_BODY, checked: int = 5) -> Path:
    boxes = ["x" if i < checked else " " for i in range(5)]
    checks = "\n".join(f"- [{b}] 验收项 {i + 1}" for i, b in enumerate(boxes))
    d = root / "chapters" / sid
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{cid}-测试.md"
    p.write_text(CHAPTER_TPL.format(sid=sid, cid=cid, title="测试章", status=status,
                                    plants=plants, pays=pays, checks=checks, body=body),
                 encoding="utf-8")
    return p


def has(out: str, *needles: str) -> bool:
    return all(n in out for n in needles)


# ── 用例 ────────────────────────────────────────────────────────────────────

CASES: list = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def t01_合规的最小集合应通过(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root)
    make_chapter(root)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 0, f"合规应通过，实际 {code}\n{out}")
    c.expect("0 个错误" in out, "应为 0 错误")


@case
def t02_空世界观定稿必须被拦(c: Case) -> None:
    root = sandbox()
    make_world(root, status="accepted", ruletxt="", taboo="")
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "空世界规则定稿必须拦")
    c.expect(has(out, "世界规则"), "应报世界规则为空")


@case
def t03_禁止写法出现在正文必须被拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root)
    make_chapter(root, body="他走到水井边上，往下看。" + LONG_BODY)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "禁止写法必须拦")
    c.expect(has(out, "禁止写法"), "应报禁止写法")
    c.expect(has(out, "水井"), "应指出具体是哪个词")
    c.expect(has(out, "井"), "应给出正确写法")


@case
def t04_禁止写法在设定书里也要拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root, one="陈默站在水井边上，想知道预兆是什么意思。")
    make_chapter(root)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "设定书里的禁止写法也要拦")


@case
def t05_伏笔未回收就完结必须被拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root, status="done", thesis="yes")
    make_chapter(root, pays="")
    # 把 F-001 改回 open
    p = root / "stories/ST-001/threads.md"
    p.write_text(p.read_text(encoding="utf-8").replace("| paid |", "| open |"),
                 encoding="utf-8")
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "伏笔未回收不能完结")
    c.expect(has(out, "还是 open"), "应报伏笔仍未回收")


@case
def t06_伏笔标了paid但章节没标注应提醒(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root)
    make_chapter(root, pays="")
    code, out = run(root, "bin/guard_novel.py")
    c.expect(has(out, "没有任何章节卡标注"), "应提醒 pays 缺标注")


@case
def t07_章节引用不存在的伏笔应拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root)
    make_chapter(root, pays="F-999")
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "引用不存在伏笔必须拦")
    c.expect(has(out, "threads.md 里没有这条伏笔"), "应报伏笔不存在")


@case
def t08_章节DONE但验收未勾应拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root)
    make_chapter(root, checked=3)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "验收未勾不能 DONE")
    c.expect(has(out, "验收未勾"), "应报验收未勾")


@case
def t09_字数不足应拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root)
    make_chapter(root, body="太短了。")
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "字数不足必须拦")
    c.expect(has(out, "低于下限"), "应报字数不足")


@case
def t10_字数超上限应提醒(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root)
    make_chapter(root, body="字" * 9000)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(has(out, "超过上限"), "应提醒拆章")


@case
def t11_引用未定稿世界观应拦(c: Case) -> None:
    root = sandbox()
    make_world(root, status="draft")
    make_story(root, status="drafting")
    make_chapter(root)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "引用未定稿世界观必须拦")
    c.expect(has(out, "尚未定稿"), "应报世界观未定稿")


@case
def t12_人物引用不存在应拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root, people="| 张三 | 主角 | 想知道 |")
    make_chapter(root)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "人物无卡必须拦")
    c.expect(has(out, "没有人物卡"), "应报人物不存在")


@case
def t13_已故人物出场应提醒(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root)
    make_chapter(root, cid="ch-03", body="阿箬站在井边。" + LONG_BODY)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(has(out, "已故人物"), "应提醒已故人物出场")


@case
def t14_已故人物死在本章不提醒(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root)
    make_chapter(root, cid="ch-02", body="阿箬站在井边。" + LONG_BODY)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(not has(out, "已故人物"), "死在本章不该报警")


@case
def t15_故事完结但没填thesis应拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root, status="done", thesis="")
    make_chapter(root)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "完结必须填 thesis_kept")
    c.expect(has(out, "thesis_kept"), "应报 thesis_kept 未填")


@case
def t16_一句话故事为空应拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root, one="")
    make_chapter(root)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "一句话故事为空必须拦")
    c.expect(has(out, "一句话故事"), "应报一句话故事为空")


@case
def t17_验收标准笼统应拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root, acc="- [ ] 好看\n- [ ] 精彩\n- [ ] 不错")
    make_chapter(root)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "笼统验收必须拦")
    c.expect(has(out, "太笼统"), "应报验收笼统")


@case
def t18_不写什么为空应拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root, scope="- ❌\n- ❌")
    make_chapter(root)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "不写什么为空必须拦")
    c.expect(has(out, "不写什么"), "应报不写什么为空")


@case
def t19_中篇缺章纲应拦(c: Case) -> None:
    root = sandbox()
    make_world(root)
    make_story(root, form="novella")
    make_chapter(root)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "中篇必须有章纲")
    c.expect(has(out, "outline.md"), "应报缺章纲")


@case
def t20_改版本号但无变更记录应拦(c: Case) -> None:
    root = sandbox()
    make_world(root, version="1.1", changelog="")
    make_story(root)
    make_chapter(root)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(code == 1, "改设定必须留痕")
    c.expect(has(out, "变更记录为空"), "应报变更记录缺失")


@case
def t21_世界观只列一种术语写法不报错(c: Case) -> None:
    """术语表正常填了，就不该报 W008/W009。"""
    root = sandbox()
    make_world(root)
    make_story(root)
    make_chapter(root)
    code, out = run(root, "bin/guard_novel.py")
    c.expect(not has(out, "术语表为空"), "术语表已填不该报空")
    c.expect(not has(out, "少于 3 列"), "三列齐全不该报")


@case
def t22_脚手架与状态表可用(c: Case) -> None:
    root = sandbox()
    code1, _ = run(root, "bin/init_novel.py", "world", "W-002", "第二个世界")
    c.expect(code1 == 0, "建世界观应成功")
    c.expect((root / "worlds/W-002/world.md").exists(), "world.md 应生成")
    txt = (root / "worlds/W-002/world.md").read_text(encoding="utf-8")
    c.expect("{{" not in txt, "占位符应全部替换")

    code2, _ = run(root, "bin/init_novel.py", "character", "W-002", "李四")
    c.expect((root / "worlds/W-002/characters/李四.md").exists(), "人物卡应生成")

    code3, _ = run(root, "bin/init_novel.py", "story", "ST-009", "新故事",
                   "--world", "W-002", "--form", "flash")
    c.expect(code3 == 0, "建故事应成功")
    c.expect((root / "stories/ST-009/story.md").exists(), "story.md 应生成")
    c.expect((root / "stories/ST-009/threads.md").exists(), "threads.md 应生成")

    code4, _ = run(root, "bin/init_novel.py", "chapter", "ST-009", "开头")
    c.expect((root / "chapters/ST-009/ch-01-开头.md").exists(), "章节应生成 ch-01")
    run(root, "bin/init_novel.py", "chapter", "ST-009", "第二")
    c.expect((root / "chapters/ST-009/ch-02-第二.md").exists(), "章节号应自增到 ch-02")

    code5, out5 = run(root, "bin/init_novel.py", "status")
    c.expect(code5 == 0, "status 应成功")
    c.expect("草稿" in out5, "状态表应显示中文")


@case
def t23_故事必须指定世界观(c: Case) -> None:
    root = sandbox()
    make_world(root)
    code, out = run(root, "bin/init_novel.py", "story", "ST-010", "没爹的故事")
    c.expect(code == 2, "不指定世界观应拒绝")
    c.expect(has(out, "必须指定世界观"), "应提示必须指定世界观")


@case
def t24_幂等不覆盖(c: Case) -> None:
    root = sandbox()
    make_world(root)
    before = (root / "worlds/W-001/world.md").read_text(encoding="utf-8")
    code, out = run(root, "bin/init_novel.py", "world", "W-001", "测试世界")
    after = (root / "worlds/W-001/world.md").read_text(encoding="utf-8")
    c.expect(before == after, "默认不覆盖已有文件")
    c.expect("跳过" in out, "应提示跳过")


@case
def t25_demo可生成(c: Case) -> None:
    root = sandbox()
    code, _ = run(root, "bin/init_novel.py", "demo")
    c.expect(code == 0, "demo 应成功")
    c.expect((root / "examples/worlds/W-001/world.md").exists(), "样例世界观应生成")
    c.expect((root / "examples/stories/ST-001/story.md").exists(), "样例故事应生成")


@case
def t26_变更单生成并解除变更警告(c: Case) -> None:
    root = sandbox()
    make_world(root, version="1.1", changelog="| 2026-06-01 | 1.1 | 加了新规则 | 需要 | ST-001 |")
    make_story(root)
    make_chapter(root)
    code1, out1 = run(root, "bin/guard_novel.py")
    c.expect(has(out1, "没有变更单"), "版本升级但没变更单，应提醒")

    code2, _ = run(root, "bin/init_novel.py", "change", "W-001", "补一条世界规则")
    c.expect(code2 == 0, "change 命令应成功")
    c.expect((root / "worlds/W-001/changes/CHG-001-补一条世界规则.md").exists(),
             "变更单应生成且自动编号")

    code3, out3 = run(root, "bin/guard_novel.py")
    c.expect(not has(out3, "没有变更单"), "建了变更单后不该再提醒")


# ── 主流程 ──────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 68)
    print("  novel-sdd 护栏回归测试")
    print("=" * 68)
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
    print("-" * 68)
    print(f"  {len(results) - len(bad)} / {len(results)} 通过")
    if bad:
        print("  失败用例：" + "、".join(bad))
        return 1
    print("  护栏有效：设定、伏笔、用词都能拦住。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
