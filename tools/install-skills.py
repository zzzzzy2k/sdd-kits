#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install-skills.py — 把 skills/ 下的技能定义安装到 ~/.workbuddy/skills/

为什么需要它：
    skill 目录（C 盘）和本仓库（可能在 D 盘）是两处，如果让代码只存一份，
    就必须有个东西把「定义」部署过去，并告诉它「代码现在在哪」。
    这样整个 SDD规范 目录随便移动，双击一次这个脚本就全部修好。

做三件事：
    1. 复制 skills/<名字>/SKILL.md → ~/.workbuddy/skills/<名字>/SKILL.md
    2. 写入 sdd-root.txt（当前 SDD规范 的绝对路径）—— skill 靠它找代码
    3. 报告哪些是新装、哪些是更新、哪些没变

用法：
    python tools/install-skills.py            # 安装 / 更新
    python tools/install-skills.py --check    # 只检查，不写入
    python tools/install-skills.py --list     # 列出已安装的技能
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # SDD规范/
SRC = ROOT / "skills"
DEST = Path(os.environ.get("USERPROFILE") or Path.home()) / ".workbuddy" / "skills"

NEW = "  [新装] "
UPD = "  [更新] "
SAME = "  [不变] "
ERR = "  [!!] "


def _init_stdout() -> None:
    try:
        if sys.stdout.isatty() or "PYTHONIOENCODING" in os.environ:
            return
        if os.name != "nt":
            return
        import ctypes
        enc = "cp%d" % ctypes.windll.kernel32.GetOEMCP()
        sys.stdout.reconfigure(encoding=enc, errors="replace")
    except Exception:
        pass


def find_skills() -> list[Path]:
    if not SRC.is_dir():
        return []
    return sorted(p for p in SRC.iterdir()
                  if p.is_dir() and (p / "SKILL.md").exists())


def read_name(skill_md: Path) -> str:
    """从 frontmatter 里取 name，取不到就用目录名。"""
    try:
        lines = skill_md.read_text(encoding="utf-8").splitlines()
    except OSError:
        return skill_md.parent.name
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() in ("---", "..."):
                break
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip().strip("\"'") or skill_md.parent.name
    return skill_md.parent.name


def install(check_only: bool = False) -> int:
    skills = find_skills()
    if not skills:
        print(ERR + f"没找到任何技能定义（{SRC} 为空或不存在）")
        return 2

    print(f"  源目录：{SRC}")
    print(f"  目标目录：{DEST}")
    print(f"  体系路径：{ROOT}")
    print("  " + "-" * 60)

    n_new = n_upd = n_same = 0
    for sdir in skills:
        src_md = sdir / "SKILL.md"
        name = read_name(src_md)
        dst_dir = DEST / name
        dst_md = dst_dir / "SKILL.md"

        content = src_md.read_text(encoding="utf-8")
        same = dst_md.exists() and dst_md.read_text(encoding="utf-8") == content \
            and (dst_dir / "sdd-root.txt").exists() \
            and (dst_dir / "sdd-root.txt").read_text(encoding="utf-8").strip() == str(ROOT)

        if same:
            print(SAME + f"{name}")
            n_same += 1
            continue

        tag = UPD if dst_md.exists() else NEW
        if check_only:
            print(tag + f"{name}  （--check：未写入）")
            if dst_md.exists():
                n_upd += 1
            else:
                n_new += 1
            continue

        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst_md.write_text(content, encoding="utf-8", newline="\n")
            # skill 靠这一行找到代码 —— 目录移动后重跑本脚本即可修复
            (dst_dir / "sdd-root.txt").write_text(str(ROOT), encoding="utf-8", newline="\n")
        except OSError as exc:
            print(ERR + f"{name} 写入失败：{exc}")
            return 2
        print(tag + f"{name}  → {dst_dir}")
        if dst_md.exists():
            n_upd += 1
        else:
            n_new += 1

    print("  " + "-" * 60)
    print(f"  新装 {n_new} · 更新 {n_upd} · 未变 {n_same}")
    if check_only:
        print("  （--check 模式，什么都没写）")
    elif n_new or n_upd:
        print("  → 重启会话或刷新技能列表后生效")
    else:
        print("  → 已是最新，无需操作")
    return 0


def list_installed() -> int:
    if not DEST.is_dir():
        print(f"  {DEST} 不存在")
        return 2
    found = []
    for d in sorted(DEST.iterdir()):
        if not d.is_dir() or not (d / "SKILL.md").exists():
            continue
        root_file = d / "sdd-root.txt"
        root = root_file.read_text(encoding="utf-8").strip() if root_file.exists() else ""
        if not root:
            continue
        ok = (Path(root) / "README.md").exists()
        found.append((d.name, root, ok))

    if not found:
        print("  没有由本仓库安装的技能")
        return 0

    print("  由本仓库安装的技能：")
    for name, root, ok in found:
        mark = "✓" if ok else "✗ 路径失效"
        print(f"    {name:<14} {mark}  {root}")
    if any(not ok for _, _, ok in found):
        print("\n  → 有路径失效的，重跑本脚本即可修复")
    return 0


def main(argv: list[str]) -> int:
    _init_stdout()
    if "--list" in argv:
        return list_installed()
    return install(check_only="--check" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
