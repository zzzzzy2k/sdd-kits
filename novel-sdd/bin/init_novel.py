#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_novel.py — novel-sdd 脚手架

用法：
    python bin/init_novel.py                               # 初始化目录（幂等）
    python bin/init_novel.py world W-001 青石镇
    python bin/init_novel.py character W-001 陈默
    python bin/init_novel.py story ST-001 井底的铜钱 --world W-001 --form short
    python bin/init_novel.py chapter ST-001 井边             # 自动 ch-01 / ch-02
    python bin/init_novel.py status                        # 全局一览
    python bin/init_novel.py demo                          # 生成完整样例

选项：--force 覆盖已有文件
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DIRS = [
    "bin",
    "worlds/_templates",
    "stories/_templates",
    "chapters/_templates",
    ".state",
]

WORLD_STATES = ["draft", "review", "accepted", "revising", "deprecated"]
WORLD_CN = {"draft": "草稿", "review": "评审中", "accepted": "已定稿",
            "revising": "修订中", "deprecated": "已废弃"}
STORY_STATES = ["idea", "outlining", "drafting", "revising", "done", "archived"]
STORY_CN = {"idea": "想法", "outlining": "写纲中", "drafting": "初稿中",
            "revising": "修改中", "done": "已完成", "archived": "已归档"}
FORMS = ["flash", "short", "novella", "novel"]

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


def patch_fm(text: str, **kv) -> str:
    """就地改 frontmatter 字段（只在前部范围内替换）。"""
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
        if val is None or val == "":
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


def next_chapter_id(story_id: str) -> str:
    d = ROOT / "chapters" / story_id
    nums = []
    if d.is_dir():
        for f in d.glob("ch-*.md"):
            m = re.search(r"ch-(\d+)", f.name)
            if m:
                nums.append(int(m.group(1)))
    return "ch-%02d" % (max(nums) + 1 if nums else 1)


# ── 脚手架 ──────────────────────────────────────────────────────────────────

def new_world(wid: str, name: str, force: bool = False) -> None:
    folder = ROOT / "worlds" / wid
    mapping = {"ID": wid, "NAME": name, "DATE": today()}
    write_file(folder / "world.md",
               render(read_tpl("worlds/_templates/world.md"), mapping), force)
    write_file(folder / "world_review.md",
               render(read_tpl("worlds/_templates/world_review.md"), mapping), force)
    (folder / "characters").mkdir(parents=True, exist_ok=True)
    print(f"\n下一步：填 worlds/{wid}/world.md 的「二、世界规则」和「六、术语表」")
    print(f"        术语表的「禁止写法」列是脚本查用词不一致的依据，认真填")
    print(f"        状态推进：draft → review → accepted（定稿后冻结）")


def new_character(wid: str, name: str, force: bool = False) -> None:
    if not (ROOT / "worlds" / wid / "world.md").exists():
        print(ERR + f"世界观 `{wid}` 不存在。先建：python bin/init_novel.py world {wid} 名字")
        sys.exit(2)
    cid = re.sub(r"\s+", "-", name.strip())
    content = render(read_tpl("worlds/_templates/character.md"),
                     {"ID": cid, "NAME": name, "WORLD": wid, "DATE": today()})
    write_file(ROOT / "worlds" / wid / "characters" / f"{cid}.md", content, force)


def new_place(wid: str, name: str, force: bool = False) -> None:
    if not (ROOT / "worlds" / wid / "world.md").exists():
        print(ERR + f"世界观 `{wid}` 不存在。先建 world")
        sys.exit(2)
    pid = re.sub(r"\s+", "-", name.strip())
    content = render(read_tpl("worlds/_templates/place.md"),
                     {"ID": pid, "NAME": name, "WORLD": wid, "DATE": today()})
    write_file(ROOT / "worlds" / wid / "places" / f"{pid}.md", content, force)


def new_change(wid: str, title: str, force: bool = False) -> None:
    if not (ROOT / "worlds" / wid / "world.md").exists():
        print(ERR + f"世界观 `{wid}` 不存在。先建 world")
        sys.exit(2)
    d = ROOT / "worlds" / wid / "changes"
    d.mkdir(parents=True, exist_ok=True)
    nums = []
    for f in d.glob("CHG-*.md"):
        m = re.search(r"CHG-(\d+)", f.name)
        if m:
            nums.append(int(m.group(1)))
    cid = "CHG-%03d" % (max(nums) + 1 if nums else 1)
    content = render(read_tpl("worlds/_templates/change.md"),
                     {"ID": wid, "NAME": title, "CID": cid, "DATE": today()})
    write_file(d / f"{cid}-{title}.md", content, force)
    print(f"\n下一步：填「三、影响哪些已写故事」——这一节空着等于说没有故事受影响")


def new_story(sid: str, title: str, world: str = "", form: str = "short",
              force: bool = False) -> None:
    if not world:
        print(ERR + "必须指定世界观：--world W-001")
        print("      一个故事必须挂在一个世界观下，否则设定没有依据")
        sys.exit(2)
    if not (ROOT / "worlds" / world / "world.md").exists():
        print(ERR + f"世界观 `{world}` 不存在。先建：python bin/init_novel.py world {world} 名字")
        sys.exit(2)
    if form not in FORMS:
        print(ERR + f"未知篇幅 `{form}`，可选：{' / '.join(FORMS)}")
        sys.exit(2)

    folder = ROOT / "stories" / sid
    mapping = {"ID": sid, "NAME": title, "WORLD": world, "FORM": form, "DATE": today()}
    write_file(folder / "story.md",
               render(read_tpl("stories/_templates/story.md"), mapping), force)
    write_file(folder / "threads.md",
               render(read_tpl("stories/_templates/threads.md"), mapping), force)
    write_file(folder / "review.md",
               render(read_tpl("stories/_templates/review.md"), mapping), force)
    if form in ("novella", "novel"):
        write_file(folder / "outline.md",
                   render(read_tpl("stories/_templates/outline.md"), mapping), force)
    print(f"\n下一步：填 stories/{sid}/story.md 的「一、一句话故事」和「二、不写什么」")
    print(f"        动笔前状态推到 drafting，且 review.md 的 verdict 要 pass")


def new_chapter(sid: str, title: str, force: bool = False) -> None:
    if not (ROOT / "stories" / sid).is_dir():
        print(ERR + f"故事 `{sid}` 不存在。先建 story")
        sys.exit(2)
    cid = next_chapter_id(sid)
    content = render(read_tpl("chapters/_templates/chapter.md"),
                     {"ID": sid, "CID": cid, "NAME": title, "DATE": today()})
    write_file(ROOT / "chapters" / sid / f"{cid}-{title}.md", content, force)


# ── status ──────────────────────────────────────────────────────────────────

def txt_width(s: str) -> int:
    return sum(2 if ord(c) > 0x2E80 else 1 for c in s)


def pad(s: str, w: int) -> str:
    return s + " " * max(0, w - txt_width(s))


def read_fm(path: Path) -> dict:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta = {}
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            for raw in lines[1:i]:
                if ":" in raw and not raw.strip().startswith("#"):
                    k, v = raw.split(":", 1)
                    meta[k.strip()] = v.strip()
            break
    return meta


def show_status() -> None:
    worlds = sorted(p for p in (ROOT / "worlds").iterdir()
                    if p.is_dir() and p.name != "_templates") if (ROOT / "worlds").is_dir() else []
    stories = sorted(p for p in (ROOT / "stories").iterdir()
                     if p.is_dir() and p.name != "_templates") if (ROOT / "stories").is_dir() else []

    if not worlds and not stories:
        print("还没有内容。先建世界观：python bin/init_novel.py world W-001 名字")
        return

    if worlds:
        print("  世界观")
        heads = ("id", "名称", "状态", "版本", "人物", "故事")
        rows = []
        for d in worlds:
            meta = read_fm(d / "world.md")
            st = meta.get("status", "?")
            nchar = len(list((d / "characters").glob("*.md"))) if (d / "characters").is_dir() else 0
            nstory = sum(1 for s in stories if read_fm(s / "story.md").get("world") == d.name)
            rows.append((d.name, meta.get("name", d.name),
                         f"{st}({WORLD_CN.get(st, '?')})",
                         meta.get("version", "1.0"), str(nchar), str(nstory)))
        widths = [max(txt_width(str(r[i])) for r in rows + [heads]) for i in range(6)]
        print("  " + "  ".join(pad(h, widths[i]) for i, h in enumerate(heads)))
        print("  " + "  ".join("-" * widths[i] for i in range(6)))
        for r in rows:
            print("  " + "  ".join(pad(str(r[i]), widths[i]) for i in range(6)))
        print()

    if stories:
        print("  故事")
        heads = ("id", "标题", "世界观", "篇幅", "状态", "章节", "字数")
        rows = []
        for d in stories:
            meta = read_fm(d / "story.md")
            st = meta.get("status", "?")
            cdir = ROOT / "chapters" / d.name
            nch = len(list(cdir.glob("*.md"))) if cdir.is_dir() else 0
            total = 0
            if cdir.is_dir():
                for f in cdir.glob("*.md"):
                    w = read_fm(f).get("words", "")
                    try:
                        total += int(float(w)) if w else 0
                    except ValueError:
                        pass
            rows.append((d.name, meta.get("title", d.name), meta.get("world", "-"),
                         meta.get("form", "-"), f"{st}({STORY_CN.get(st, '?')})",
                         str(nch), str(total) if total else "-"))
        widths = [max(txt_width(str(r[i])) for r in rows + [heads]) for i in range(7)]
        print("  " + "  ".join(pad(h, widths[i]) for i, h in enumerate(heads)))
        print("  " + "  ".join("-" * widths[i] for i in range(7)))
        for r in rows:
            print("  " + "  ".join(pad(str(r[i]), widths[i]) for i in range(7)))


# ── 入口 ────────────────────────────────────────────────────────────────────

USAGE = """novel-sdd 脚手架

  python bin/init_novel.py                              初始化目录
  python bin/init_novel.py world <id> <名称>             新建世界观
  python bin/init_novel.py character <世界观id> <姓名>    新建人物卡
  python bin/init_novel.py place <世界观id> <地名>        新建地点卡
  python bin/init_novel.py change <世界观id> <变更标题>   新建世界观变更单（定稿后改设定必须走）
  python bin/init_novel.py story <id> <标题> --world <世界观id> [--form short]
  python bin/init_novel.py chapter <故事id> <章标题>      新建章节卡（自动编号）
  python bin/init_novel.py status                       查看世界观与故事进度
  python bin/init_novel.py demo                         生成完整样例

篇幅 form：flash(≤2000字) / short(短篇) / novella(中篇) / novel(长篇)
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
        print(f"  novel-sdd 初始化   {ROOT}")
        print("  " + "-" * 56)
        for d in DIRS:
            print(OK + d + "/")
        for t in sorted(ROOT.glob("**/_templates/*.md")):
            print("  [tpl] " + t.relative_to(ROOT).as_posix())
        if not (ROOT / "RULES.md").exists():
            print(ERR + "RULES.md 缺失")
        print()
        print("  下一步：python bin/init_novel.py world W-001 你的世界名")
        return 0

    if cmd == "world":
        if len(args) < 3:
            print(ERR + "用法：init_novel.py world <id> <名称>")
            return 2
        new_world(args[1], args[2], force)
        return 0

    if cmd == "character":
        if len(args) < 3:
            print(ERR + "用法：init_novel.py character <世界观id> <姓名>")
            return 2
        new_character(args[1], args[2], force)
        return 0

    if cmd == "place":
        if len(args) < 3:
            print(ERR + "用法：init_novel.py place <世界观id> <地名>")
            return 2
        new_place(args[1], args[2], force)
        return 0

    if cmd == "change":
        if len(args) < 3:
            print(ERR + "用法：init_novel.py change <世界观id> <变更标题>")
            return 2
        new_change(args[1], args[2], force)
        return 0

    if cmd == "story":
        if len(args) < 3:
            print(ERR + "用法：init_novel.py story <id> <标题> --world <世界观id> [--form short]")
            return 2
        world, form = "", "short"
        rest = args[3:]
        i = 0
        while i < len(rest):
            if rest[i] == "--world" and i + 1 < len(rest):
                world = rest[i + 1]
                i += 2
            elif rest[i] == "--form" and i + 1 < len(rest):
                form = rest[i + 1]
                i += 2
            else:
                i += 1
        new_story(args[1], args[2], world, form, force)
        return 0

    if cmd == "chapter":
        if len(args) < 3:
            print(ERR + "用法：init_novel.py chapter <故事id> <章标题>")
            return 2
        new_chapter(args[1], args[2], force)
        return 0

    if cmd == "status":
        show_status()
        return 0

    if cmd == "demo":
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "novel_demo", Path(__file__).resolve().parent / "demo.py")
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
