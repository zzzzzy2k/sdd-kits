#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_dev.py — dev-sdd 脚手架

所有文件都从各层 _templates/ 生成，模板即真源：改了模板，之后新建的都跟着变。

用法：
    python bin/init_dev.py                               # 初始化目录骨架（幂等）
    python bin/init_dev.py spec SPEC-001 用户登录
    python bin/init_dev.py spec SPEC-002 导出报表 --type feature --priority P0
    python bin/init_dev.py spec SPEC-003 支付回调 --adr ADR-001 --depends SPEC-001,SPEC-002
    python bin/init_dev.py task SPEC-001 feature 登录接口
    python bin/init_dev.py task SPEC-001 fix 重复提交
    python bin/init_dev.py adr 选数据库
    python bin/init_dev.py module auth-jwt JWT认证方案
    python bin/init_dev.py status                        # 一览所有需求与任务进度

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
    "specs/_templates",
    "tasks/_templates",
    "adr/_templates",
    "modules/_templates",
    ".state",
]

SPEC_STATES = ["draft", "review", "accepted", "implementing", "done", "archived"]
SPEC_CN = {
    "draft": "草稿", "review": "评审中", "accepted": "已批准",
    "implementing": "实现中", "done": "已完成", "archived": "已归档",
}
TASK_KINDS = {"feature": "task.feature.md", "fix": "task.fix.md",
              "refactor": "task.refactor.md"}
TASK_STATES = ["READY", "IN_PROGRESS", "DONE", "BLOCKED"]

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


def patch_frontmatter(text: str, **kv) -> str:
    """就地改 frontmatter 字段（只在文件头范围内替换，不碰正文）。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return text
    for key, val in kv.items():
        if not val:
            continue
        found = False
        for i in range(1, end):
            if re.match(r"^\s*" + key + r"\s*:", lines[i]):
                lines[i] = f"{key}: {val}"
                found = True
                break
        if not found:
            lines.insert(end, f"{key}: {val}")
            end += 1
    return "\n".join(lines) + "\n"


# ── 脚手架 ──────────────────────────────────────────────────────────────────

def next_num(pattern: str) -> int:
    nums = []
    for p in ROOT.glob(pattern):
        m = re.search(r"(\d+)", p.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1 if nums else 1


def new_spec(sid: str, title: str, stype: str = "feature", priority: str = "P1",
             adr: str = "", module: str = "", depends: str = "",
             force: bool = False) -> None:
    folder = ROOT / "specs" / sid
    content = render(read_tpl("specs/_templates/spec.md"),
                     {"ID": sid, "NAME": title, "TYPE": stype, "DATE": today()})
    content = patch_frontmatter(content, priority=priority, adr=adr,
                                module=module, depends_on=depends)
    write_file(folder / "spec.md", content, force)

    review = render(read_tpl("specs/_templates/review.md"),
                    {"ID": sid, "NAME": title, "DATE": today()})
    write_file(folder / "review.md", review, force)

    print(f"\n下一步：填 specs/{sid}/spec.md 的「一、背景与问题」和「二、目标 / 不做什么」")
    print(f"        状态推进：draft → review → accepted，每推进一步跑：")
    print(f"        python bin/guard_dev.py {sid}")


def new_task(spec_id: str, kind: str, title: str, force: bool = False) -> None:
    kind = kind.lower()
    if kind not in TASK_KINDS:
        print(ERR + f"未知任务类型 `{kind}`，可选：{' / '.join(TASK_KINDS)}")
        sys.exit(2)
    if not (ROOT / "specs" / spec_id / "spec.md").exists():
        print(ERR + f"需求 `{spec_id}` 不存在（specs/{spec_id}/spec.md）")
        print("      先建需求：python bin/init_dev.py spec " + spec_id + " 名称")
        sys.exit(2)

    tid = "T-%03d" % next_num("tasks/" + spec_id + "/T-*.md")
    path = ROOT / "tasks" / spec_id / f"{tid}-{kind}.md"
    content = render(read_tpl(f"tasks/_templates/{TASK_KINDS[kind]}"),
                     {"ID": spec_id, "TID": tid, "NAME": title, "DATE": today()})
    write_file(path, content, force)


def new_adr(title: str, adr_id: str = "", force: bool = False) -> None:
    if not adr_id:
        adr_id = f"ADR-{next_num(f'adr/ADR-*.md'):03d}"
    path = ROOT / "adr" / f"{adr_id}.md"
    content = render(read_tpl("adr/_templates/adr.md"),
                     {"ID": adr_id, "NAME": title, "DATE": today()})
    write_file(path, content, force)


def new_module(mid: str, name: str, force: bool = False) -> None:
    folder = ROOT / "modules" / mid
    mapping = {"ID": mid, "NAME": name, "DATE": today()}
    write_file(folder / "module.md",
               render(read_tpl("modules/_templates/module.md"), mapping), force)
    write_file(folder / "module_review.md",
               render(read_tpl("modules/_templates/module_review.md"), mapping), force)


# ── status 一览 ─────────────────────────────────────────────────────────────

def txt_width(s: str) -> int:
    return sum(2 if ord(c) > 0x2E80 else 1 for c in s)


def pad(s: str, w: int) -> str:
    return s + " " * max(0, w - txt_width(s))


def show_status() -> None:
    base = ROOT / "specs"
    folders = sorted(p for p in base.iterdir()
                     if p.is_dir() and p.name != "_templates") if base.is_dir() else []
    if not folders:
        print("还没有需求。用 `python bin/init_dev.py spec SPEC-001 需求名` 建第一份。")
        return

    rows = []
    for d in folders:
        f = d / "spec.md"
        if not f.exists():
            rows.append((d.name, "-", "-", "缺 spec.md", "-", "-"))
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

        # 任务进度
        tf = ROOT / "tasks" / d.name
        total = done = blocked = 0
        if tf.is_dir():
            for t in tf.glob("*.md"):
                tt = t.read_text(encoding="utf-8-sig", errors="replace")
                m = re.search(r"^status:\s*(\S+)", tt, re.M)
                if not m:
                    continue
                total += 1
                s = m.group(1).upper()
                if s == "DONE":
                    done += 1
                elif s == "BLOCKED":
                    blocked += 1
        prog = f"{done}/{total}" if total else "-"
        if blocked:
            prog += f" ({blocked}阻塞)"

        rows.append((
            d.name,
            meta.get("title", d.name),
            meta.get("priority", "-"),
            f"{status}({SPEC_CN.get(status, '?')})",
            prog,
            meta.get("updated", "") or "-",
        ))

    heads = ("需求", "标题", "优先级", "状态", "任务", "更新")
    widths = [max(txt_width(str(r[i])) for r in rows + [heads]) for i in range(6)]
    widths = [max(w, 6) for w in widths]
    print("  " + "  ".join(pad(h, widths[i]) for i, h in enumerate(heads)))
    print("  " + "  ".join("-" * widths[i] for i in range(6)))
    for r in rows:
        print("  " + "  ".join(pad(str(r[i]), widths[i]) for i in range(6)))

    counter: dict[str, int] = {}
    for r in rows:
        k = str(r[3]).split("(")[0]
        counter[k] = counter.get(k, 0) + 1
    print()
    print("  " + " · ".join(f"{SPEC_CN.get(k, k)} {v}" for k, v in
                            sorted(counter.items(),
                                   key=lambda kv: SPEC_STATES.index(kv[0])
                                   if kv[0] in SPEC_STATES else 99)))


# ── 入口 ────────────────────────────────────────────────────────────────────

USAGE = """dev-sdd 脚手架

  python bin/init_dev.py                          初始化目录骨架
  python bin/init_dev.py spec <id> <标题>          新建需求规格
  python bin/init_dev.py task <需求id> <类型> <标题>  新建任务卡（类型: feature/fix/refactor）
  python bin/init_dev.py adr <标题>                新建架构决策记录
  python bin/init_dev.py module <id> <名称>        新建方案包
  python bin/init_dev.py status                    查看需求与任务进度
  python bin/init_dev.py demo                      生成完整流程样例

选项：--force 覆盖已有文件
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
        print(f"  dev-sdd 初始化   {ROOT}")
        print("  " + "-" * 56)
        for d in DIRS:
            print(OK + d + "/")
        for t in sorted(ROOT.glob("**/_templates/*.md")):
            print("  [tpl] " + t.relative_to(ROOT).as_posix())
        if not (ROOT / "RULES.md").exists():
            print(ERR + "RULES.md 缺失 —— 规范基准不在，护栏无从校验")
        print()
        print("  下一步：改 RULES.md 里 RULES-BEGIN/END 之间的数值")
        print("          然后 python bin/init_dev.py spec SPEC-001 你的第一个需求")
        return 0

    if cmd == "spec":
        if len(args) < 3:
            print(ERR + "用法：init_dev.py spec <需求id> <标题> [--type feature] "
                        "[--priority P1] [--adr ADR-001] [--module <id>] [--depends SPEC-001]")
            return 2
        stype, priority, adr, module, depends = "feature", "P1", "", "", ""
        rest = args[3:]
        i = 0
        while i < len(rest):
            a = rest[i]
            if a in ("--type", "--priority", "--adr", "--module", "--depends") and i + 1 < len(rest):
                v = rest[i + 1]
                if a == "--type":
                    stype = v
                elif a == "--priority":
                    priority = v
                elif a == "--adr":
                    adr = v
                elif a == "--module":
                    module = v
                elif a == "--depends":
                    depends = v
                i += 2
            else:
                i += 1
        new_spec(args[1], args[2], stype, priority, adr, module, depends, force)
        return 0

    if cmd == "task":
        if len(args) < 4:
            print(ERR + "用法：init_dev.py task <需求id> <feature|fix|refactor> <标题>")
            return 2
        new_task(args[1], args[2], args[3], force)
        return 0

    if cmd == "adr":
        if len(args) < 2:
            print(ERR + "用法：init_dev.py adr <标题> [--id ADR-001]")
            return 2
        aid = ""
        if "--id" in args:
            idx = args.index("--id")
            if idx + 1 < len(args):
                aid = args[idx + 1]
        new_adr(args[1], aid, force)
        return 0

    if cmd == "module":
        if len(args) < 3:
            print(ERR + "用法：init_dev.py module <id> <名称>")
            return 2
        new_module(args[1], args[2], force)
        return 0

    if cmd == "status":
        show_status()
        return 0

    if cmd == "demo":
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "dev_demo", Path(__file__).resolve().parent / "demo.py")
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
