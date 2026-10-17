#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
guard_novel.py — novel-sdd 护栏脚本

解决的核心问题：**长文写作时，前后设定 / 伏笔 / 用词会互相打架。**

不是靠"记住"，而是把一致性外化成可以机器校验的结构：

  W 世界观    状态机 / 冻结保护 / 核心章节 / 术语表格式
  S 故事      状态机 / 引用合法性 / 完整性 / 篇幅匹配
  C 章节      状态机 / 验收清单 / 字数区间
  F 伏笔      埋了没回收 / 收了没埋 / 放弃没理由
  T 一致性    禁止写法扫描 / 已故人物出场 / 人物引用
  P 人物卡    字段完整性

用法：
    python bin/guard_novel.py                 # 全量
    python bin/guard_novel.py ST-001          # 只查某个故事
    python bin/guard_novel.py --strict
    python bin/guard_novel.py --quiet

退出码：0 通过 / 1 有错误 / 2 环境问题
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 状态机 ──────────────────────────────────────────────────────────────────

WORLD_STATES = ["draft", "review", "accepted", "revising", "deprecated"]
WORLD_CN = {"draft": "草稿", "review": "评审中", "accepted": "已定稿",
            "revising": "修订中", "deprecated": "已废弃"}

STORY_STATES = ["idea", "outlining", "drafting", "revising", "done", "archived"]
STORY_CN = {"idea": "想法", "outlining": "写纲中", "drafting": "初稿中",
            "revising": "修改中", "done": "已完成", "archived": "已归档"}

CHAPTER_STATES = ["TODO", "DRAFT", "REVISED", "DONE"]
FORM_WORDS = {"flash": (0, 2000), "short": (0, 15000),
              "novella": (10000, 80000), "novel": (60000, 10 ** 9)}

# 故事进入这些状态后，评审必须是 pass
STORY_NEED_REVIEW = {"drafting", "revising", "done", "archived"}
# 这些状态表示"本篇已经定稿"，要开始清算伏笔
STORY_FINISHED = {"done", "archived"}
# 世界观在这些状态下被"冻结"
WORLD_FROZEN = {"accepted", "revising"}

LEVEL_TAG = {"ERROR": "[ERR ]", "WARN": "[WARN]", "OK": "[ OK ]", "INFO": "[INFO]"}
LEVEL_ORDER = {"ERROR": 0, "WARN": 1, "OK": 2, "INFO": 3}

# 统计字数时剔除的字符：空白 + 中英文标点。
# 中文引号一律用 \u 转义 —— 直接写会截断 raw string，导致后面的 \- 变成非法转义。
PUNCT_RE = re.compile(
    r"[\s\u3000"
    r"，。！？；：、（）《》〈〉【】…—－·"
    r"\u201c\u201d\u2018\u2019"
    r",.!?;:'\"()\[\]{}<>/\\"
    r"*#>|`~_\-+=]"
)

# 空泛验收词（写进验收标准等于没写）
VAGUE_ACCEPT = ["好看", "流畅", "精彩", "不错", "引人入胜", "有感染力", "文字优美"]


def _init_stdout() -> None:
    """管道 / 重定向且未显式指定编码时，跟随控制台 OEM 代码页。"""
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


class Issue:
    __slots__ = ("level", "code", "where", "msg")

    def __init__(self, level: str, code: str, where: str, msg: str) -> None:
        self.level = level
        self.code = code
        self.where = where
        self.msg = msg


# ── Markdown 解析（第三次实现，前两次的坑全部固化进写法） ────────────────────
#
# ★ 铁律：单行解析一律用 [^\n]* / [ \t\u3000]*，绝不用 .* / \s*
#   —— `\s` 含换行，会让空字段读到下一行、把多行 checkbox 合并成一个。
#   这个坑在 invest-sdd 和 dev-sdd 上各踩过一次。

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def split_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            meta: dict[str, str] = {}
            for raw in lines[1:i]:
                if not raw.strip() or raw.strip().startswith("#") or ":" not in raw:
                    continue
                k, v = raw.split(":", 1)
                meta[k.strip()] = re.sub(r"\s+#.*$", "", v).strip()
            return meta, "\n".join(lines[i + 1:])
    return {}, text


def section(body: str, keyword: str) -> str:
    """取标题含 keyword 的整段（到同级或更高级标题为止），支持 2~6 级标题。"""
    out: list[str] = []
    start = 0
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})[ \t]", line)
        if m:
            lv = len(m.group(1))
            if start:
                if lv <= start:
                    break
                continue
            if lv >= 2 and keyword in line:
                start = lv
            continue
        if start:
            out.append(line)
    return "\n".join(out)


def checkboxes(text: str) -> list[tuple[bool, str]]:
    out = []
    for m in re.finditer(r"^[ \t]*-[ \t]*\[([ xX])\][ \t\u3000]*([^\n]*)$", text, re.M):
        c = m.group(2).strip()
        if c:
            out.append((m.group(1).lower() == "x", c))
    return out


def bullet_items(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(">") or s.startswith("#"):
            continue
        s = re.sub(r"^[-*+]\s*", "", s)
        s = re.sub(r"^❌\s*", "", s)
        s = s.strip()
        if len(s) >= 2 and "{{" not in s:
            items.append(s)
    return items


def hint_free_text(text: str) -> str:
    """去掉 `> 说明：` 引导行后剩下的实际内容（引用标记剥掉）。

    模板的格式提示统一以 `> 说明：` 开头，所以「哪些是提示、哪些是用户写的」
    不靠猜措辞 —— 用户想用引用块写正文也行。
    """
    parts = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(">"):
            inner = s.lstrip(">").strip()
            if inner.startswith("说明："):
                continue
            parts.append(inner)
        else:
            if re.fullmatch(r"（[^）]*）", s) or s.startswith("<!--"):
                continue
            parts.append(s)
    return "".join(parts)


def parse_table(text: str) -> list[list[str]]:
    """解析 Markdown 表格，返回数据行（不含表头与分隔行）。"""
    rows: list[list[str]] = []
    header_seen = False
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        if re.match(r"^\|[\s:|-]+\|$", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not header_seen:
            header_seen = True
            continue          # 第一行是表头
        if cells and any(cells):
            rows.append(cells)
    return rows


def field_in(text: str, label: str) -> str:
    m = re.search(r"\*\*" + re.escape(label) + r"\*\*[^\n]*?[：:][ \t\u3000]*([^\n]*)", text)
    return m.group(1).strip() if m else ""


def is_blank(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return True
    if set(v) <= set("_-— 　"):
        return True
    if "{{" in v and "}}" in v:
        return True
    return False


def count_words(text: str) -> int:
    """中文字数：去掉空白与中英文标点后的字符数。"""
    cleaned = re.sub(PUNCT_RE, "", text)
    return len(cleaned)


def subdirs(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(p for p in path.iterdir() if p.is_dir() and p.name not in {"_templates"})


def md_files(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(p for p in path.glob("*.md") if p.is_file())


# ── RULES ───────────────────────────────────────────────────────────────────

DEFAULT_RULES = {
    "min_words_per_chapter": 1500.0,
    "max_words_per_chapter": 8000.0,
    "require_outline_for": "novella, novel",
    "require_thread_close": "true",
    "freeze_accepted_world": "true",
    "check_banned_terms": "true",
}


def truthy(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def load_rules(issues: list[Issue]) -> dict:
    path = ROOT / "RULES.md"
    if not path.exists():
        issues.append(Issue("WARN", "R001", "RULES.md", "未找到 RULES.md，用内置默认纪律"))
        return dict(DEFAULT_RULES)
    text = read_text(path)
    m = re.search(r"<!--\s*RULES-BEGIN\s*-->(.*?)<!--\s*RULES-END\s*-->", text, re.S)
    if not m:
        issues.append(Issue("WARN", "R002", "RULES.md", "未找到规则块，用内置默认纪律"))
        return dict(DEFAULT_RULES)
    rules = dict(DEFAULT_RULES)
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k not in DEFAULT_RULES:
            issues.append(Issue("WARN", "R003", "RULES.md",
                                f"未知规则键 `{k}`（有效键：{'/'.join(DEFAULT_RULES)}）"))
            continue
        rules[k] = v
    for k in ("min_words_per_chapter", "max_words_per_chapter"):
        try:
            rules[k] = float(rules[k])
        except (TypeError, ValueError):
            issues.append(Issue("ERROR", "R004", "RULES.md", f"`{k}` 不是数字，已回退默认"))
            rules[k] = DEFAULT_RULES[k]
    return rules


# ── 数据模型 ───────────────────────────────────────────────────────────────

class World:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.id = folder.name
        self.path = folder / "world.md"
        self.review_path = folder / "world_review.md"
        self.exists = self.path.exists()
        self.meta: dict = {}
        self.body = ""
        self.text = ""
        self.status = ""
        if self.exists:
            self.text = read_text(self.path)
            self.meta, self.body = split_frontmatter(self.text)
            self.status = (self.meta.get("status", "") or "").strip().lower()

    @property
    def rel(self) -> str:
        return f"worlds/{self.id}/world.md"

    @property
    def name(self) -> str:
        return self.meta.get("name", "") or self.id

    @property
    def characters(self) -> dict[str, Path]:
        out = {}
        d = self.folder / "characters"
        for f in md_files(d):
            out[f.stem] = f
        return out

    @property
    def banned_terms(self) -> dict[str, str]:
        """返回 {禁止写法: 正确写法}。"""
        out: dict[str, str] = {}
        tbl = section(self.body, "术语表")
        for row in parse_table(tbl):
            if len(row) < 2:
                continue
            canon = row[1] if len(row) > 1 else row[0]
            banned_cell = row[2] if len(row) > 2 else ""
            for bad in re.split(r"[、,，/／;；]", banned_cell):
                bad = bad.strip()
                if bad and bad != canon:
                    out[bad] = canon
        return out


class Story:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.id = folder.name
        self.path = folder / "spec.md"
        if not self.path.exists():
            self.path = folder / "story.md"
        self.review_path = folder / "review.md"
        self.outline_path = folder / "outline.md"
        self.threads_path = folder / "threads.md"
        self.exists = self.path.exists()
        self.meta: dict = {}
        self.body = ""
        self.text = ""
        self.status = ""
        self.form = ""
        self.world_id = ""
        if self.exists:
            self.text = read_text(self.path)
            self.meta, self.body = split_frontmatter(self.text)
            self.status = (self.meta.get("status", "") or "").strip().lower()
            self.form = (self.meta.get("form", "") or "short").strip().lower()
            self.world_id = (self.meta.get("world", "") or "").strip()
        self.review_meta: dict = {}
        if self.review_path.exists():
            self.review_meta, _ = split_frontmatter(read_text(self.review_path))

    @property
    def rel(self) -> str:
        return f"stories/{self.id}/{self.path.name}"

    @property
    def title(self) -> str:
        return self.meta.get("title", "") or self.id

    @property
    def chapters_dir(self) -> Path:
        return ROOT / "chapters" / self.id

    @property
    def chapter_files(self) -> list[Path]:
        return md_files(self.chapters_dir)

    def threads(self) -> dict[str, dict]:
        """解析伏笔表：{F-001: {content, plant, pay, status}}。"""
        out: dict[str, dict] = {}
        if not self.threads_path.exists():
            return out
        _, body = split_frontmatter(read_text(self.threads_path))
        tbl = section(body, "伏笔追踪") or body
        for row in parse_table(tbl):
            if len(row) < 5:
                continue
            fid = row[0].strip()
            if not re.match(r"^F-\d+", fid):
                continue
            out[fid] = {
                "content": row[1].strip(),
                "plant": row[2].strip(),
                "pay": row[3].strip(),
                "status": row[4].strip().lower(),
            }
        return out


# ── 校验：世界观 ────────────────────────────────────────────────────────────

def check_world(w: World, fields: list[Issue]) -> None:
    if not w.exists:
        fields.append(Issue("ERROR", "W001", f"worlds/{w.id}",
                            "目录存在但没有 world.md"))
        return
    if "{{" in w.text and "}}" in w.text:
        fields.append(Issue("ERROR", "W002", w.rel, "还有未替换的 {{占位符}}"))
        return
    if w.status not in WORLD_STATES:
        fields.append(Issue("ERROR", "W003", w.rel,
                            f"非法状态 `{w.status or '未填'}`，合法值：{' / '.join(WORLD_STATES)}"))
        return

    if w.status in WORLD_FROZEN:
        if not w.review_path.exists():
            fields.append(Issue("ERROR", "W004", w.rel,
                                f"状态 `{w.status}` 但缺少 world_review.md"))
        else:
            rm, _ = split_frontmatter(read_text(w.review_path))
            if (rm.get("verdict", "") or "").strip().lower() != "pass":
                fields.append(Issue("ERROR", "W005", f"worlds/{w.id}/world_review.md",
                                    "verdict 不是 pass —— 世界观定稿前必须过评审"))

    # 核心章节
    rules_txt = section(w.body, "世界规则")
    if not bullet_items(rules_txt) and not re.search(r"^\s*\d+[.、)]", rules_txt, re.M):
        fields.append(Issue("ERROR" if w.status in WORLD_FROZEN else "WARN", "W006", w.rel,
                            "「世界规则」为空 —— 没有硬约束的世界，写出来一定前后矛盾"))

    taboo = section(w.body, "基调与禁忌")
    if is_blank(field_in(taboo, "绝对不能有")):
        fields.append(Issue("WARN", "W007", w.rel,
                            "「绝对不能有」为空 —— 这条防的是写着写着跑偏成别的类型"))

    # 术语表
    terms = section(w.body, "术语表")
    rows = parse_table(terms)
    if not rows:
        fields.append(Issue("ERROR" if w.status in WORLD_FROZEN else "WARN", "W008", w.rel,
                            "术语表为空 —— 没有唯一写法表，同一个概念迟早会出现三种叫法"))
    else:
        for r in rows:
            if len(r) < 3:
                fields.append(Issue("WARN", "W009", w.rel,
                                    f"术语行「{'|'.join(r)}」少于 3 列，缺少「禁止写法」列"))
                break

    # 变更记录：有了版本号却没有任何变更记录 = 偷偷改过
    try:
        ver = float((w.meta.get("version", "1.0") or "1.0").strip())
    except ValueError:
        ver = 1.0
    changelog = section(w.body, "变更记录")
    if ver > 1.0 and len(parse_table(changelog)) == 0:
        fields.append(Issue("ERROR", "W010", w.rel,
                            f"版本号是 {ver:g} 但变更记录为空 —— 改设定必须留痕，"
                            "否则下一篇就不知道哪里变了"))
    if ver > 1.0:
        cdir = w.folder / "changes"
        n_changes = len([p for p in cdir.glob("*.md")]) if cdir.is_dir() else 0
        if n_changes == 0:
            fields.append(Issue("WARN", "W011", w.rel,
                                f"版本号是 {ver:g} 但 changes/ 里没有变更单 —— "
                                "改世界观要留一张单，写清「影响哪些已写故事」"))


def check_characters(w: World, fields: list[Issue]) -> dict[str, dict]:
    """校验人物卡，返回 {人物id: {name, status}}。"""
    out: dict[str, dict] = {}
    for cid, f in w.characters.items():
        rel = f"worlds/{w.id}/characters/{f.name}"
        text = read_text(f)
        if "{{" in text and "}}" in text:
            fields.append(Issue("ERROR", "P001", rel, "还有未替换的 {{占位符}}"))
            continue
        meta, body = split_frontmatter(text)
        name = (meta.get("name", "") or cid).strip()
        status = (meta.get("status", "") or "alive").strip().lower()
        if status not in ("alive", "dead", "missing", "unknown"):
            fields.append(Issue("WARN", "P002", rel,
                                f"status = `{status}`，建议用 alive/dead/missing/unknown"))
        # 动机是人物站得住的根本，缺了就只是个名字
        want = field_in(section(body, "性格与动机"), "想要什么")
        if is_blank(want):
            fields.append(Issue("WARN", "P003", rel,
                                "「想要什么」为空 —— 没有欲望的人物不会推动情节"))
        out[cid] = {"name": name, "status": status, "rel": rel}
        out[name] = {"name": name, "status": status, "rel": rel}   # 允许用姓名引用
    return out


# ── 校验：故事 ──────────────────────────────────────────────────────────────

def check_story(s: Story, rules: dict, worlds: dict[str, World],
                snap: dict, fields: list[Issue]) -> None:
    if not s.exists:
        fields.append(Issue("ERROR", "S001", f"stories/{s.id}",
                            "目录存在但没有 story.md / spec.md"))
        return
    if "{{" in s.text and "}}" in s.text:
        fields.append(Issue("ERROR", "S002", s.rel, "还有未替换的 {{占位符}}"))
        return
    if s.status not in STORY_STATES:
        fields.append(Issue("ERROR", "S003", s.rel,
                            f"非法状态 `{s.status or '未填'}`，合法值：{' / '.join(STORY_STATES)}"))
        return

    prev = snap.get(s.id)
    if prev in STORY_STATES and STORY_STATES.index(s.status) < STORY_STATES.index(prev):
        fields.append(Issue("WARN", "S004", s.rel,
                            f"状态从 `{prev}` 回退到 `{s.status}` —— 在「变更记录」里写清原因"))
    snap[s.id] = s.status

    # 引用的世界观必须存在且已定稿
    w = worlds.get(s.world_id)
    if not s.world_id:
        fields.append(Issue("ERROR", "S005", s.rel,
                            "frontmatter 缺少 `world:` —— 每个故事都必须挂在一个世界观下"))
    elif w is None:
        fields.append(Issue("ERROR", "S005", s.rel,
                            f"引用的世界观 `{s.world_id}` 不存在（worlds/{s.world_id}/）"))
    elif w.exists and w.status not in WORLD_FROZEN:
        fields.append(Issue("ERROR" if s.status in STORY_NEED_REVIEW else "WARN",
                            "S006", s.rel,
                            f"引用的世界观状态是 `{w.status}`，尚未定稿 —— "
                            "没定稿的世界观写出来的故事，改设定时要返工"))

    # 评审
    if s.status in STORY_NEED_REVIEW:
        if not s.review_path.exists():
            fields.append(Issue("ERROR", "S007", s.rel,
                                f"状态 `{s.status}` 但缺少 review.md"))
        else:
            verdict = (s.review_meta.get("verdict", "") or "").strip().lower()
            if verdict != "pass":
                fields.append(Issue("ERROR", "S008", f"stories/{s.id}/review.md",
                                    f"verdict = `{verdict or '未填'}`，动笔前必须为 pass"))

    # 一句话故事四要素
    one_text = hint_free_text(section(s.body, "一句话故事"))
    if len(one_text) < 8:
        fields.append(Issue("ERROR" if s.form in ("short", "novella", "novel") else "WARN",
                            "S009", s.rel,
                            "「一句话故事」为空 —— 谁、想要什么、什么挡着、付出什么代价，"
                            "缺一个都还不算故事"))

    # 不写什么
    scope = bullet_items(section(s.body, "不写什么"))
    if not scope:
        fields.append(Issue("ERROR" if s.status in STORY_NEED_REVIEW else "WARN",
                            "S010", s.rel,
                            "「不写什么」为空 —— 短篇写崩基本都是想塞太多，这一节是刹车"))

    # 验收标准
    acc = checkboxes(section(s.body, "验收标准"))
    if len(acc) < 3:
        fields.append(Issue("ERROR" if s.status in STORY_NEED_REVIEW else "WARN",
                            "S011", s.rel,
                            f"验收标准只有 {len(acc)} 条，至少要 3 条"))
    for _, c in acc:
        for w2 in VAGUE_ACCEPT:
            if w2 in c:
                fields.append(Issue("ERROR", "S012", s.rel,
                                    f"验收项「{c[:20]}」太笼统 —— 「{w2}」没法验收，"
                                    "要写成能判断的具体现象"))

    # 篇幅与章纲
    need_outline = [x.strip() for x in
                    (rules["require_outline_for"] or "").split(",") if x.strip()]
    if s.form in need_outline and not s.outline_path.exists():
        fields.append(Issue("ERROR", "S013", s.rel,
                            f"form = `{s.form}` 必须有 outline.md 章纲，否则长篇会写飞"))

    # 人物引用
    chars: dict[str, dict] = {}
    if w is not None:
        chars = check_characters(w, fields)
    people = parse_table(section(s.body, "人物"))
    for row in people:
        pid = row[0].strip()
        if not pid or "{{" in pid:
            continue
        if w is None:
            break
        if pid not in chars:
            fields.append(Issue("ERROR", "S014", s.rel,
                                f"人物 `{pid}` 在世界观 `{w.id}` 里没有人物卡 —— "
                                "先建卡再让他出场"))

    # 完结：复盘 + 伏笔清算
    if s.status in STORY_FINISHED:
        goal = (s.review_meta.get("thesis_kept", "") or "").strip().lower()
        if goal not in ("yes", "partial", "no"):
            fields.append(Issue("ERROR", "S015", f"stories/{s.id}/review.md",
                                f"thesis_kept = `{goal or '未填'}`，done 前必须填 yes/partial/no"))
        retro = section(read_text(s.review_path) if s.review_path.exists() else "", "事后复盘")
        if is_blank(field_in(retro, "经验")) and is_blank(retro):
            fields.append(Issue("WARN", "S016", f"stories/{s.id}/review.md",
                                "事后复盘为空 —— 写完了什么都没留下，下一篇还会踩同样的坑"))


# ── 校验：章节 ──────────────────────────────────────────────────────────────

def check_chapters(s: Story, rules: dict, worlds: dict[str, World],
                   fields: list[Issue]) -> tuple[list[dict], dict[str, dict]]:
    """返回 (章节信息列表, {人物名: 首次出场章})。"""
    infos: list[dict] = []
    seen: dict[str, str] = {}
    minw = int(rules["min_words_per_chapter"])
    maxw = int(rules["max_words_per_chapter"])

    for f in s.chapter_files:
        rel = f"chapters/{s.id}/{f.name}"
        text = read_text(f)
        if "{{" in text and "}}" in text:
            fields.append(Issue("ERROR", "C001", rel, "还有未替换的 {{占位符}}"))
            continue
        meta, body = split_frontmatter(text)
        cid = (meta.get("chapter", "") or f.stem).strip()
        status = (meta.get("status", "") or "").strip().upper()
        if status not in CHAPTER_STATES:
            fields.append(Issue("ERROR", "C002", rel,
                                f"非法章节状态 `{status or '未填'}`，"
                                f"合法值：{' / '.join(CHAPTER_STATES)}"))
            continue
        if cid in seen:
            fields.append(Issue("ERROR", "C003", rel, f"章节 id `{cid}` 与 {seen[cid]} 重复"))
        seen[cid] = rel

        # 字数
        main = section(body, "正文")
        counted = count_words(main) if main.strip() else count_words(body)
        declared = (meta.get("words", "") or "").strip()
        try:
            words = int(float(declared)) if declared else counted
        except ValueError:
            words = counted
        if not declared:
            words = counted

        infos.append({"id": cid, "rel": rel, "status": status, "words": words,
                     "counted": counted, "meta": meta, "body": body})

        if status == "DONE":
            boxes = checkboxes(body)
            unchecked = [c for ok, c in boxes if not ok]
            if unchecked:
                fields.append(Issue("ERROR", "C004", rel,
                                    f"DONE 但还有 {len(unchecked)} 项验收未勾：「{unchecked[0][:20]}」"))
            if words < minw:
                fields.append(Issue("ERROR", "C005", rel,
                                    f"字数 {words} 低于下限 {minw} —— 这章还没写完，或者该并章"))
        if words > maxw:
            fields.append(Issue("WARN", "C006", rel,
                                f"字数 {words} 超过上限 {maxw} —— 读者会累，考虑拆章"))

        # 已故人物出场
        w = worlds.get(s.world_id)
        if w is not None and status in ("REVISED", "DONE"):
            for cid2, f2 in w.characters.items():
                meta2, _ = split_frontmatter(read_text(f2))
                if (meta2.get("status", "") or "").lower() != "dead":
                    continue
                nm = (meta2.get("name", "") or cid2).strip()
                if not nm or nm not in body:
                    continue
                death_ch = (meta2.get("death_chapter", "") or "").strip()
                # 死在本章是正常的；没登记死亡章节就没法判断，只能提醒
                if death_ch and death_ch.split("/")[-1] == cid:
                    continue
                fields.append(Issue("WARN", "T001", rel,
                                    f"已故人物「{nm}」在本章正文出现 —— "
                                    f"死亡章节登记为 `{death_ch or '未填'}`，"
                                    "确认这是回忆/提及，不是又活了"))

    return infos, seen


# ── 校验：伏笔闭环 ──────────────────────────────────────────────────────────

def check_threads(s: Story, rules: dict, chapters: list[dict],
                  fields: list[Issue]) -> None:
    if not s.threads_path.exists():
        if chapters:
            fields.append(Issue("ERROR", "F001", s.rel,
                                "已经有章节了但没有 threads.md 伏笔追踪表 —— "
                                "埋下的线没有任何地方记着，迟早断"))
        return

    threads = s.threads()
    if not threads:
        return

    order = {c["id"]: i for i, c in enumerate(chapters)}
    chapter_ids = set(order)
    max_idx = len(chapters) - 1

    # 章节卡里声明的 plants / pays
    planted: dict[str, list[str]] = {}
    paid: dict[str, list[str]] = {}
    for c in chapters:
        for raw_key, bucket in (("plants", planted), ("pays", paid)):
            raw = (c["meta"].get(raw_key, "") or "").strip()
            for fid in re.split(r"[,，、\s]+", raw):
                fid = fid.strip()
                if not fid or fid in ("-", "无"):
                    continue
                bucket.setdefault(fid, []).append(c["id"])

    # 引用了不存在的伏笔
    for fid, chs in paid.items():
        if fid not in threads:
            fields.append(Issue("ERROR", "F002", f"chapters/{s.id}/{chs[0]}",
                                f"本章标注回收 `{fid}`，但 threads.md 里没有这条伏笔"))
    for fid, chs in planted.items():
        if fid not in threads:
            fields.append(Issue("ERROR", "F003", f"chapters/{s.id}/{chs[0]}",
                                f"本章标注埋下 `{fid}`，但 threads.md 里没有这条伏笔"))

    # 每条伏笔的状态
    for fid, t in threads.items():
        st = t["status"]
        if st not in ("open", "paid", "dropped"):
            fields.append(Issue("ERROR", "F004", f"stories/{s.id}/threads.md",
                                f"伏笔 `{fid}` 状态是 `{st}`，只能是 open / paid / dropped"))
            continue

        if st == "paid" and fid not in paid:
            fields.append(Issue("WARN", "F005", f"stories/{s.id}/threads.md",
                                f"伏笔 `{fid}` 标了 paid，但没有任何章节卡标注 pays `{fid}` —— "
                                "要么补标注，要么其实没收"))

        if st == "dropped":
            why = (t.get("content", "") or "")
            dropped_tbl = parse_table(section(read_text(s.threads_path), "已放弃"))
            if not dropped_tbl:
                fields.append(Issue("WARN", "F006", f"stories/{s.id}/threads.md",
                                    f"伏笔 `{fid}` 放弃了，但「已放弃的伏笔」表里没写原因"))

        if st == "open" and s.status in STORY_FINISHED and truthy(rules["require_thread_close"]):
            fields.append(Issue("ERROR", "F007", f"stories/{s.id}/threads.md",
                                f"故事已 `{s.status}`，但伏笔 `{fid}` 还是 open —— "
                                "挖坑不填，读者会记仇"))

        # 该收没收到期
        if st == "open" and t["pay"] in chapter_ids and s.status not in STORY_FINISHED:
            if order[t["pay"]] <= max_idx and t["pay"] not in paid.get(fid, []):
                fields.append(Issue("WARN", "F008", f"stories/{s.id}/threads.md",
                                    f"伏笔 `{fid}` 计划在 `{t['pay']}` 回收，"
                                    f"那章已经写了但没收 —— 是改了计划还是忘了"))


# ── 校验：术语一致性 ────────────────────────────────────────────────────────

def check_terms(s: Story, worlds: dict[str, World], rules: dict,
                chapters: list[dict], fields: list[Issue]) -> None:
    if not truthy(rules.get("check_banned_terms", "true")):
        return
    w = worlds.get(s.world_id)
    if w is None or not w.exists:
        return
    banned = w.banned_terms
    if not banned:
        return
    for c in chapters:
        for bad, canon in banned.items():
            if bad in c["body"]:
                fields.append(Issue("ERROR", "T002", c["rel"],
                                    f"出现了禁止写法「{bad}」—— 术语表规定统一写「{canon}」"))
    # 故事设定书本身也要查
    for bad, canon in banned.items():
        if bad in s.body:
            fields.append(Issue("ERROR", "T003", s.rel,
                                f"设定书里出现禁止写法「{bad}」—— 统一写「{canon}」"))


# ── 入口 ────────────────────────────────────────────────────────────────────

def state_file() -> Path:
    return ROOT / ".state" / "guard-state.json"


def load_snapshot() -> dict:
    p = state_file()
    if not p.exists():
        return {}
    try:
        return json.loads(read_text(p))
    except Exception:
        return {}


def save_snapshot(snap: dict) -> None:
    try:
        state_file().parent.mkdir(parents=True, exist_ok=True)
        state_file().write_text(json.dumps(snap, ensure_ascii=False, indent=2),
                                encoding="utf-8")
    except OSError:
        pass


def main(argv: list[str]) -> int:
    _init_stdout()
    only = None
    strict = "--strict" in argv
    quiet = "--quiet" in argv
    for a in argv:
        if not a.startswith("-"):
            only = a

    fields: list[Issue] = []
    rules = load_rules(fields)

    worlds = {d.name: World(d) for d in subdirs(ROOT / "worlds")}
    stories = [Story(d) for d in subdirs(ROOT / "stories")]
    if only:
        stories = [s for s in stories if s.id == only]
        if not stories:
            print(f"找不到故事 `{only}`（stories/{only}/ 不存在）")
            return 2

    if not only:
        for w in worlds.values():
            check_world(w, fields)

    snap = load_snapshot()
    for s in stories:
        check_story(s, rules, worlds, snap, fields)
        if not s.exists:
            continue
        chapters, _ = check_chapters(s, rules, worlds, fields)
        check_threads(s, rules, chapters, fields)
        check_terms(s, worlds, rules, chapters, fields)
    save_snapshot(snap)

    errors = [i for i in fields if i.level == "ERROR"]
    warns = [i for i in fields if i.level == "WARN"]
    show = sorted((i for i in fields if i.level in ("ERROR", "WARN")),
                  key=lambda i: (LEVEL_ORDER[i.level], i.where))

    if not quiet:
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        print("=" * 66)
        print(f"  novel-sdd 一致性校验   {now}")
        print("=" * 66)
        wdesc = ", ".join(f"{w.id}({w.status})" for w in worlds.values()) or "（暂无世界观）"
        print(f"  世界观 {len(worlds)} 个：{wdesc}")
        sdesc = ", ".join(f"{s.id}({s.status})" for s in stories) or "（暂无故事）"
        print(f"  故事 {len(stories)} 篇：{sdesc}")
        print("-" * 66)

    if show:
        for i in show:
            print(f"{LEVEL_TAG[i.level]} {i.where}")
            print(f"        {i.msg}")
        print("-" * 66)
    elif not quiet:
        if not stories and not worlds:
            print("[ OK ] 暂无内容。用 init_novel.py world 建第一个世界观。")
        else:
            print("[ OK ] 全部通过。设定一致，伏笔闭环。")
        print("-" * 66)

    print(f"结果：{len(errors)} 个错误 · {len(warns)} 个警告 · "
          f"{len(worlds)} 个世界观 / {len(stories)} 篇故事")
    if errors:
        print("→ 有错误必须处理（已定稿的世界观和已完结的故事不放行）。")
        return 1
    if warns and strict:
        print("→ --strict 模式下警告也算失败。")
        return 1
    if warns:
        print("→ 没有硬错误，但警告值得看一眼。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
