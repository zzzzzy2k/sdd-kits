#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
guard_dev.py — dev-sdd 护栏脚本

把工程纪律变成不可绕过的机器校验。对应通用 SDD 的三重约束
（deliverables / out-of-scope / validation）+ 状态机 + 任务卡验收。

校验分组：
  S 需求规格    状态机 / 完整性 / 模糊词 / 验收可测试性 / 依赖环
  T 任务卡      关联性 / 验收勾选 / 测试要求 / 工时上限
  A 架构决策    选项对比 / 重新考虑条件
  M 方案包      评审 / 引用合法性
  R 规则文件    RULES.md 解析

用法：
    python bin/guard_dev.py                   # 全量校验
    python bin/guard_dev.py SPEC-001          # 只校验某个需求
    python bin/guard_dev.py --strict          # 警告也算失败
    python bin/guard_dev.py --quiet           # 只输出问题

退出码：0 通过 / 1 有错误 / 2 环境或解析问题
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 状态机 ──────────────────────────────────────────────────────────────────

SPEC_STATES = ["draft", "review", "accepted", "implementing", "done", "archived"]
SPEC_CN = {
    "draft": "草稿", "review": "评审中", "accepted": "已批准",
    "implementing": "实现中", "done": "已完成", "archived": "已归档",
}
TASK_STATES = ["READY", "IN_PROGRESS", "DONE", "BLOCKED"]
TASK_CN = {"READY": "待开始", "IN_PROGRESS": "进行中", "DONE": "完成", "BLOCKED": "阻塞"}
ADR_STATES = ["proposed", "accepted", "deprecated", "superseded"]
MODULE_STATES = ["draft", "review", "accepted", "deprecated"]

SPEC_LOCKED = set(SPEC_STATES[SPEC_STATES.index("accepted"):])
SPEC_FINISHED = {"done", "archived"}
GOAL_RESULTS = {"yes", "partial", "no"}

# ── 词表 ────────────────────────────────────────────────────────────────────

# 强模糊词：任何阶段出现都拦（纯粹是敷衍，没有信息量）
VAGUE_STRONG = [
    "差不多就行", "先这样吧", "应该没问题", "能跑就行", "先上线再说",
    "随手改改", "看着办", "大概齐", "先凑合",
]
# 弱模糊词：草稿阶段只提醒，accepted 之后必须量化
# 注意：故意不含「可能 / 临时 / 暂时」—— 技术文档里「可能导致内存泄漏」「临时文件」
# 是正当表述，加了会天天误报，喊狼来了的护栏等于没有护栏。
VAGUE_WEAK = [
    "大概", "也许是", "优化一下", "完善一下", "待定", "TODO",
    "后续再说", "后面再补", "了再说", "有空再说",
]
# 空泛验收词：验收项写成这样等于没写（只在验收项内匹配）
VAGUE_ACCEPT = ["功能正常", "一切正常", "没问题", "可以了", "能用就行", "看着没问题"]

SKIP_DIRS = {"_templates"}

LEVEL_ORDER = {"ERROR": 0, "WARN": 1, "OK": 2, "INFO": 3}
LEVEL_TAG = {"ERROR": "[ERR ]", "WARN": "[WARN]", "OK": "[ OK ]", "INFO": "[INFO]"}


def _init_stdout() -> None:
    """管道 / 重定向且未显式指定编码时，跟随控制台 OEM 代码页，避免 GBK 乱码。"""
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


# ── Markdown 解析（与 invest-sdd 同一套，踩过的坑已修） ─────────────────────

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def split_frontmatter(text: str) -> tuple[dict, str]:
    """切出 YAML frontmatter（只支持扁平 key: value，够用且不会解析出错）。"""
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
                v = re.sub(r"\s+#.*$", "", v).strip()
                meta[k.strip()] = v
            return meta, "\n".join(lines[i + 1:])
    return {}, text


def inline_field(body: str, names: list[str]) -> str:
    """回退解析 `- 状态：draft` 这类正文行内字段。"""
    for name in names:
        m = re.search(r"^[ \t>*-]*" + name + r"[ \t]*[：:][ \t\u3000]*([^\n|]+)", body, re.M)
        if m:
            return m.group(1).strip()
    return ""


def section(body: str, keyword: str) -> str:
    """取标题中含 keyword 的那一段（到同级或更高级标题为止）。

    支持 2~6 级标题：`### deliverables` 这种三级段也能正确切出来，
    否则 `## 二、目标` 里嵌套的 `### deliverables` 会被并进上一段、永远取不到。
    """
    out: list[str] = []
    start = 0
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})[ \t]", line)
        if m:
            lv = len(m.group(1))
            if start:
                if lv <= start:
                    break           # 同级或更高级 → 本段结束
                continue            # 更深的子标题：跳过标题行，内容仍归本段
            if lv >= 2 and keyword in line:
                start = lv
            continue
        if start:
            out.append(line)
    return "\n".join(out)


def is_test_item(content: str) -> bool:
    """判断验收项是否算「为本次改动写了测试」。

    ★ 「无回归：原有测试全部通过」不算 —— 它是防退化，不是新写测试。
    只按「含测试二字」匹配会把这条当成写测试的证据，导致 require_tests 形同虚设。
    """
    if "回归" in content:
        return False
    return "测试" in content or "用例" in content


def bullet_items(text: str) -> list[str]:
    """取列表项的实际内容，剥掉 bullet、❌、「不做：」这类装饰前缀。

    「不做第三方登录」和「不做：第三方登录」要能同等识别 —— 只认带冒号的格式
    太脆弱，用户换个写法护栏就瞎了（在 invest-sdd 上吃过这个亏）。
    """
    items = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(">") or s.startswith("#"):
            continue
        s = re.sub(r"^[-*+]\s*", "", s)
        s = re.sub(r"^❌\s*", "", s)
        s = re.sub(r"^不做\s*[：:]\s*", "", s)
        s = s.strip()
        if len(s) >= 4 and "{{" not in s:
            items.append(s)
    return items


def field_in(text: str, label: str) -> str:
    """取 `- **标签**（说明）：值` 冒号后的值。

    注意：冒号后只吃空格/制表符，**不能吃换行** —— 否则值为空时会读到下一行
    （在 invest-sdd 上踩过，导致护栏静默漏报）。
    """
    m = re.search(r"\*\*" + re.escape(label) + r"\*\*[^\n]*?[：:][ \t\u3000]*([^\n]*)", text)
    return m.group(1).strip() if m else ""


def is_blank(value: str) -> bool:
    """空 / 仍是占位 / 只有下划线。"""
    v = (value or "").strip()
    if not v:
        return True
    if set(v) <= set("_-— 　"):
        return True
    if "{{" in v and "}}" in v:
        return True
    if v.startswith("<") and v.endswith(">"):
        return True
    return False


def checkboxes(text: str) -> list[tuple[bool, str]]:
    """返回 [(是否已勾, 内容)]，内容为空的不算。

    ★ 全用 `[^\\n]*` / `[ \\t\\u3000]*`，绝不用 `\\s*` —— `\\s` 含换行，
    会把「- [ ] 空行」和下一行合并成一个匹配（这个坑在 invest-sdd 踩过一次，
    这里又踩了一次：3 个空验收项被数成 1 个）。
    """
    out = []
    for m in re.finditer(r"^[ \t]*-[ \t]*\[([ xX])\][ \t\u3000]*([^\n]*)$", text, re.M):
        content = m.group(2).strip()
        if content:
            out.append((m.group(1).lower() == "x", content))
    return out


def numbered_items(text: str) -> list[str]:
    return [m.group(1).strip()
            for m in re.finditer(r"^[ \t]*\d+[.、)][ \t]*([^\n]+)$", text, re.M)
            if m.group(1).strip()]


# ── RULES.md ───────────────────────────────────────────────────────────────

DEFAULT_RULES = {
    "max_task_hours": 8.0,
    "min_acceptance_items": 3.0,
    "max_acceptance_items": 8.0,
    "require_tests": "true",
    "require_adr_accepted": "true",
    "forbid": "硬编码密钥, 直接改生产库, 未评审的破坏性变更",
}


def truthy(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def load_rules(issues: list[Issue]) -> dict:
    path = ROOT / "RULES.md"
    if not path.exists():
        issues.append(Issue("WARN", "R001", "RULES.md",
                            "未找到 RULES.md，使用内置默认规范"))
        return dict(DEFAULT_RULES)
    text = read_text(path)
    m = re.search(r"<!--\s*RULES-BEGIN\s*-->(.*?)<!--\s*RULES-END\s*-->", text, re.S)
    if not m:
        issues.append(Issue("WARN", "R002", "RULES.md",
                            "未找到 RULES-BEGIN/RULES-END 规则块，使用内置默认规范"))
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
                                f"未知规则键 `{k}`（拼错了？有效键：{'/'.join(DEFAULT_RULES)}）"))
            continue
        rules[k] = v
    for k in ("max_task_hours", "min_acceptance_items", "max_acceptance_items"):
        try:
            rules[k] = float(rules[k])
        except (TypeError, ValueError):
            issues.append(Issue("ERROR", "R004", "RULES.md",
                                f"`{k}` 不是合法数字：{rules[k]!r}，已回退默认值"))
            rules[k] = DEFAULT_RULES[k]
    return rules


# ── 数据模型 ───────────────────────────────────────────────────────────────

class Spec:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.id = folder.name
        self.path = folder / "spec.md"
        self.review_path = folder / "review.md"
        self.exists = self.path.exists()
        self.meta: dict = {}
        self.body = ""
        self.text = ""
        self.status = ""
        self.review_meta: dict = {}
        self.review_body = ""
        if self.exists:
            self.text = read_text(self.path)
            self.meta, self.body = split_frontmatter(self.text)
            raw = get(self.meta, self.body, "status", ["状态"])
            self.status = raw.split("|")[0].strip().lower()
        if self.review_path.exists():
            rt = read_text(self.review_path)
            self.review_meta, self.review_body = split_frontmatter(rt)

    @property
    def rel(self) -> str:
        return f"specs/{self.id}/spec.md"

    @property
    def index(self) -> int:
        return SPEC_STATES.index(self.status) if self.status in SPEC_STATES else -1

    @property
    def title(self) -> str:
        return self.meta.get("title", "") or self.id

    @property
    def depends_on(self) -> list[str]:
        raw = self.meta.get("depends_on", "") or ""
        return [x.strip() for x in re.split(r"[,，\s]+", raw) if x.strip()]


def get(meta: dict, body: str, key: str, cn: list[str] | None = None) -> str:
    v = (meta.get(key) or "").strip()
    if v:
        return v
    return inline_field(body, cn) if cn else ""


def subdirs(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(p for p in path.iterdir() if p.is_dir() and p.name not in SKIP_DIRS)


def md_files(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(p for p in path.glob("*.md") if p.is_file())


def collect_specs(only: str | None) -> list[Spec]:
    out = []
    for d in subdirs(ROOT / "specs"):
        if only and d.name != only:
            continue
        out.append(Spec(d))
    return out


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
    p = state_file()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


# ── S：需求规格校验 ────────────────────────────────────────────────────────

def check_spec(spec: Spec, rules: dict, snap: dict, issues: list[Issue]) -> None:
    if not spec.exists:
        issues.append(Issue("ERROR", "S001", f"specs/{spec.id}",
                            "目录存在但没有 spec.md（先跑 init_dev.py spec）"))
        return
    if "{{" in spec.text and "}}" in spec.text:
        issues.append(Issue("ERROR", "S002", spec.rel,
                            "文件里还有未替换的 {{占位符}}，这是模板副本不是真实需求"))
        return

    if not spec.status:
        issues.append(Issue("ERROR", "S003", spec.rel,
                            "缺少 status 字段（frontmatter 里加 `status: draft`）"))
        return
    if spec.status not in SPEC_STATES:
        issues.append(Issue("ERROR", "S004", spec.rel,
                            f"非法状态 `{spec.status}`，合法值：{' / '.join(SPEC_STATES)}"))
        return

    prev = snap.get(spec.id)
    if prev in SPEC_STATES and spec.index < SPEC_STATES.index(prev):
        issues.append(Issue("WARN", "S005", spec.rel,
                            f"状态从 `{prev}` 回退到 `{spec.status}` —— 允许（比如方案作废），"
                            "但要在「变更记录」里写清原因"))
    snap[spec.id] = spec.status

    locked = spec.status in SPEC_LOCKED

    # 事前评审
    if locked:
        if not spec.review_path.exists():
            issues.append(Issue("ERROR", "S006", spec.rel,
                                f"状态 `{spec.status}` 但缺少 review.md —— "
                                "draft→accepted 必须过评审，不允许跳级"))
        else:
            verdict = (spec.review_meta.get("verdict", "") or "").strip().lower()
            if verdict != "pass":
                issues.append(Issue("ERROR", "S007", f"specs/{spec.id}/review.md",
                                    f"verdict = `{verdict or '未填'}`，accepted 前必须为 pass"))
            if is_blank(spec.review_meta.get("reviewed_on", "")):
                issues.append(Issue("ERROR", "S008", f"specs/{spec.id}/review.md",
                                    "reviewed_on 未填 —— 评审必须有日期，否则无法追溯"))

    # 三重约束：背景 / 目标 / out-of-scope / 验收
    bg = section(spec.body, "背景与问题")
    for label, key, code in (
        ("现状", "现状", "S009"),
        ("问题", "问题", "S010"),
    ):
        if is_blank(field_in(bg, key)):
            issues.append(Issue("ERROR" if locked else "WARN", code, spec.rel,
                                f"「背景与问题」里的「{label}」为空 —— " +
                                ("已 accepted，先补全再开工" if locked
                                 else "建议尽早写清楚，否则做完也不知道解决了个啥")))

    # deliverables
    deliv = section(spec.body, "deliverables")
    deliv_items = checkboxes(deliv)
    if not deliv_items:
        issues.append(Issue("ERROR" if locked else "WARN", "S011", spec.rel,
                            "deliverables 没有任何带内容的交付项 —— 交付物是什么必须列出来"))

    # out-of-scope（三重约束里最容易被忽略、也最重要的一条）
    scope_items = bullet_items(section(spec.body, "out-of-scope"))
    if not scope_items:
        issues.append(Issue("ERROR" if locked else "WARN", "S012", spec.rel,
                            "out-of-scope（不做什么）为空 —— 这一节不写，需求一定会膨胀"))

    # 验收标准
    val = section(spec.body, "验收标准")
    acc = checkboxes(val)
    n_min = int(rules["min_acceptance_items"])
    n_max = int(rules["max_acceptance_items"])
    if len(acc) < n_min:
        issues.append(Issue("ERROR" if locked else "WARN", "S013", spec.rel,
                            f"验收标准只有 {len(acc)} 条，RULES 要求至少 {n_min} 条 —— "
                            "验收标准是需求的验收凭据，不是可选项"))

    # 空泛验收项
    for _, content in acc:
        for w in VAGUE_ACCEPT:
            if w in content:
                issues.append(Issue("ERROR", "S014", spec.rel,
                                    f"验收项「{content[:24]}」太笼统 —— "
                                    "要写成能测的形式（给输入 → 期望输出）"))

    # 模糊词
    for idx, line in enumerate(spec.body.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith(">"):
            continue
        for w in VAGUE_STRONG:
            if w in s:
                issues.append(Issue("ERROR", "S015", f"{spec.rel}:{idx}",
                                    f"敷衍表述「{w}」—— 需求里出现这种词，说明还没想清楚"))
        for w in VAGUE_WEAK:
            if w in s:
                issues.append(Issue("ERROR" if locked else "WARN", "S016", f"{spec.rel}:{idx}",
                                    f"模糊表述「{w}」—— " +
                                    ("已 accepted，必须改成明确描述" if locked
                                     else "写完记得回来补实")))

    # 完成态：复盘闭环
    if spec.status in SPEC_FINISHED:
        if not spec.review_path.exists():
            issues.append(Issue("ERROR", "S017", spec.rel,
                                f"状态 {spec.status} 但没有 review.md —— 复盘闭环断裂"))
        else:
            goal_done = (spec.review_meta.get("goal_achieved", "") or "").strip().lower()
            if goal_done not in GOAL_RESULTS:
                issues.append(Issue("ERROR", "S018", f"specs/{spec.id}/review.md",
                                    f"goal_achieved = `{goal_done or '未填'}`，"
                                    f"done 前必须填 {' / '.join(sorted(GOAL_RESULTS))}"))
            retro = section(spec.review_body, "事后复盘")
            pits = field_in(retro, "踩到的坑")
            exp = field_in(retro, "经验")
            if is_blank(pits) and is_blank(exp):
                issues.append(Issue("ERROR", "S019", f"specs/{spec.id}/review.md",
                                    "「事后复盘」的踩坑与经验都为空 —— 复盘必须留下点什么"))

    # 引用的决策记录 / 方案包
    adr_id = (spec.meta.get("adr", "") or "").strip()
    if adr_id:
        check_adr_ref(adr_id, spec.rel, rules, issues, "S020")
    mod_id = (spec.meta.get("module", "") or "").strip()
    if mod_id:
        check_module_ref(mod_id, spec.rel, rules, issues, locked, "S021")


def check_adr_ref(adr_id: str, where: str, rules: dict, issues: list[Issue],
                  code: str) -> None:
    p = ROOT / "adr" / f"{adr_id}.md"
    if not p.exists():
        p2 = ROOT / "adr" / adr_id / "adr.md"
        p = p2 if p2.exists() else p
    if not p.exists():
        issues.append(Issue("ERROR", code, where,
                            f"引用了不存在的 ADR `{adr_id}`（adr/{adr_id}.md）"))
        return
    meta, _ = split_frontmatter(read_text(p))
    st = (meta.get("status", "") or "").strip().lower()
    if st != "accepted" and truthy(rules.get("require_adr_accepted", "true")):
        issues.append(Issue("WARN", code, where,
                            f"引用的 ADR `{adr_id}` 状态为 `{st or '未填'}`，建议先定下来"))


def check_module_ref(mod_id: str, where: str, rules: dict, issues: list[Issue],
                     locked: bool, code: str) -> None:
    p = ROOT / "modules" / mod_id / "module.md"
    if not p.exists():
        issues.append(Issue("ERROR", code, where,
                            f"引用了不存在的方案包 `{mod_id}`（modules/{mod_id}/module.md）"))
        return
    meta, _ = split_frontmatter(read_text(p))
    st = (meta.get("status", "") or "").strip().lower()
    if st != "accepted":
        issues.append(Issue("ERROR" if locked else "WARN", code, where,
                            f"引用的方案包 `{mod_id}` 状态为 `{st or '未填'}`，只有 accepted 才能被引用"))


# ── T：任务卡校验 ──────────────────────────────────────────────────────────

def check_tasks(spec: Spec, rules: dict, all_specs: dict[str, Spec],
                issues: list[Issue]) -> None:
    folder = ROOT / "tasks" / spec.id
    files = md_files(folder) if folder.is_dir() else []
    seen: dict[str, str] = {}
    done_count = 0
    total = 0

    for f in files:
        rel = f"tasks/{spec.id}/{f.name}"
        text = read_text(f)
        if "{{" in text and "}}" in text:
            issues.append(Issue("ERROR", "T001", rel, "还有未替换的 {{占位符}}"))
            continue
        meta, body = split_frontmatter(text)
        status = (meta.get("status", "") or "").strip().upper()
        kind = (meta.get("kind", "") or "").strip().lower()
        tid = (meta.get("task", "") or f.stem.split("-")[0]).strip()
        total += 1

        if status not in TASK_STATES:
            issues.append(Issue("ERROR", "T002", rel,
                                f"非法任务状态 `{status or '未填'}`，"
                                f"合法值：{' / '.join(TASK_STATES)}"))
            continue
        if status == "DONE":
            done_count += 1

        if tid in seen:
            issues.append(Issue("ERROR", "T003", rel, f"任务 id `{tid}` 与 {seen[tid]} 重复"))
        seen[tid] = rel

        # 工时
        raw_h = (meta.get("estimate_hours", "") or "").strip()
        if is_blank(raw_h):
            issues.append(Issue("WARN", "T004", rel, "estimate_hours 未填 —— 没估时就没法判断该不该拆"))
        else:
            try:
                h = float(raw_h)
                if h > float(rules["max_task_hours"]):
                    issues.append(Issue("WARN", "T005", rel,
                                        f"预估 {h:g} 小时，超过 RULES 的 {rules['max_task_hours']:g} 小时上限"
                                        " —— 该拆了"))
            except ValueError:
                issues.append(Issue("WARN", "T004", rel, f"estimate_hours 不是数字：`{raw_h}`"))

        # 关联需求必须已 accepted 才能真开工
        linked = (meta.get("spec", "") or "").strip()
        if linked and linked != spec.id:
            issues.append(Issue("WARN", "T006", rel,
                                f"任务放在 `tasks/{spec.id}/` 下，但 frontmatter 关联的是 `{linked}`"))
        sp = all_specs.get(spec.id)
        if sp and status in ("IN_PROGRESS", "DONE") and sp.index < SPEC_STATES.index("accepted"):
            issues.append(Issue("ERROR", "T007", rel,
                                f"任务已 `{status}`，但需求 `{spec.id}` 状态还是 `{sp.status}`"
                                " —— 没有 accepted 的需求不能开工"))

        boxes = checkboxes(body)
        # DONE 前验收清单必须全勾
        if status == "DONE":
            unchecked = [c for ok, c in boxes if not ok]
            if unchecked:
                issues.append(Issue("ERROR", "T008", rel,
                                    f"状态 DONE 但还有 {len(unchecked)} 项验收未勾："
                                    f"「{unchecked[0][:24]}」"))
            # 测试要求
            if truthy(rules.get("require_tests", "true")) and kind in ("feature", "fix"):
                has_test = any(ok and is_test_item(c) for ok, c in boxes)
                if not has_test:
                    issues.append(Issue("ERROR", "T009", rel,
                                        "功能/缺陷任务 DONE 了但没有勾选任何测试相关验收项"
                                        " —— RULES 要求必须有测试"))
            n_max = int(rules["max_acceptance_items"])
            if len(boxes) > n_max:
                issues.append(Issue("WARN", "T010", rel,
                                    f"验收项 {len(boxes)} 条，超过上限 {n_max} —— 这个任务可能该拆"))

        if status == "BLOCKED":
            reason = (meta.get("blocked_reason", "") or "").strip()
            if is_blank(reason):
                issues.append(Issue("WARN", "T011", rel,
                                    "状态 BLOCKED 但没写 blocked_reason —— 卡在哪必须记下来"))

    # 需求 done 但任务没做完
    if spec.status in SPEC_FINISHED and total and done_count < total:
        issues.append(Issue("ERROR", "T012", f"specs/{spec.id}/spec.md",
                            f"需求已 `{spec.status}`，但 {total} 个任务里还有 "
                            f"{total - done_count} 个没 DONE"))

    # 孤儿任务目录
    return


def check_orphan_tasks(all_specs: dict[str, Spec], issues: list[Issue]) -> None:
    base = ROOT / "tasks"
    if not base.is_dir():
        return
    for d in subdirs(base):
        if d.name not in all_specs:
            issues.append(Issue("WARN", "T013", f"tasks/{d.name}",
                                f"任务目录 `{d.name}` 没有对应的需求 —— 孤儿任务没有依据"))


# ── 依赖环 ─────────────────────────────────────────────────────────────────

def check_dep_cycles(specs: dict[str, Spec], issues: list[Issue]) -> None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in specs}
    path: list[str] = []

    def dfs(node: str) -> bool:
        color[node] = GRAY
        path.append(node)
        for nxt in specs[node].depends_on:
            if nxt not in specs:
                issues.append(Issue("ERROR", "S022", specs[node].rel,
                                    f"depends_on 指向不存在的需求 `{nxt}`"))
                continue
            if color[nxt] == GRAY:
                cyc = path[path.index(nxt):] + [nxt]
                issues.append(Issue("ERROR", "S023", specs[node].rel,
                                    "需求依赖成环：" + " → ".join(cyc)))
                return True
            if color[nxt] == WHITE and dfs(nxt):
                return True
        path.pop()
        color[node] = BLACK
        return False

    reported = set()
    for k in specs:
        if color[k] == WHITE and dfs(k):
            reported.add(k)


# ── A：ADR 校验 ────────────────────────────────────────────────────────────

def check_adrs(issues: list[Issue]) -> None:
    base = ROOT / "adr"
    if not base.is_dir():
        return
    paths = [p for p in base.glob("*.md") if p.name != "README.md"]
    seen: dict[str, str] = {}
    for f in sorted(set(paths)):
        text = read_text(f)
        rel = f"adr/{f.name}"
        if "{{" in text and "}}" in text:
            issues.append(Issue("ERROR", "A001", rel, "还有未替换的 {{占位符}}"))
            continue
        meta, body = split_frontmatter(text)
        status = (meta.get("status", "") or "").strip().lower()
        aid = (meta.get("id", "") or f.stem).strip()
        if status not in ADR_STATES:
            issues.append(Issue("ERROR", "A002", rel,
                                f"非法 ADR 状态 `{status or '未填'}`，"
                                f"合法值：{' / '.join(ADR_STATES)}"))
        if aid in seen:
            issues.append(Issue("ERROR", "A003", rel, f"ADR id `{aid}` 与 {seen[aid]} 重复"))
        seen[aid] = rel

        # 选项至少两条 —— 只有一个选项的"决策"不是决策，是通知
        opts = section(body, "选项对比")
        rows = [ln for ln in opts.splitlines()
                if ln.strip().startswith("|") and not re.match(r"^\s*\|[\s:|-]+\|\s*$", ln)]
        data_rows = [r for r in rows if not re.search(r"选项\s*\|", r)]
        if len(data_rows) < 2:
            issues.append(Issue("WARN", "A004", rel,
                                "「选项对比」少于 2 个候选 —— 只列一个方案的决策，"
                                "事后看不出你权衡过什么"))

        # 重新考虑条件
        cons = section(body, "后果")
        if "重新考虑" not in cons and is_blank(cons):
            issues.append(Issue("WARN", "A005", rel,
                                "缺少「什么情况下应该重新考虑」—— 没有它这条 ADR 会变成没人敢动的历史包袱"))


# ── M：方案包校验 ──────────────────────────────────────────────────────────

def check_modules(issues: list[Issue]) -> None:
    for d in subdirs(ROOT / "modules"):
        f = d / "module.md"
        rel = f"modules/{d.name}/module.md"
        if not f.exists():
            issues.append(Issue("WARN", "M001", f"modules/{d.name}",
                                "目录存在但没有 module.md"))
            continue
        text = read_text(f)
        if "{{" in text and "}}" in text:
            issues.append(Issue("ERROR", "M002", rel, "还有未替换的 {{占位符}}"))
            continue
        meta, body = split_frontmatter(text)
        status = (meta.get("status", "") or "").strip().lower()
        if status not in MODULE_STATES:
            issues.append(Issue("ERROR", "M003", rel,
                                f"非法方案包状态 `{status or '未填'}`，"
                                f"合法值：{' / '.join(MODULE_STATES)}"))
        if status == "accepted":
            rv = d / "module_review.md"
            if not rv.exists():
                issues.append(Issue("ERROR", "M004", rel,
                                    "状态 accepted 但缺少 module_review.md"))
            else:
                rm, _ = split_frontmatter(read_text(rv))
                if (rm.get("verdict", "") or "").strip().lower() != "pass":
                    issues.append(Issue("ERROR", "M005", rel,
                                        "状态 accepted 但方案评审 verdict 不是 pass"))
        # 适用边界
        use = section(body, "适用场景")
        if is_blank(field_in(use, "什么时候不用")) and "什么时候不用" in use:
            issues.append(Issue("WARN", "M006", rel,
                                "「什么时候不用」为空 —— 边界不写清楚，这包会被乱用"))


# ── 入口 ────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    _init_stdout()
    only = None
    strict = "--strict" in argv
    quiet = "--quiet" in argv
    for a in argv:
        if not a.startswith("-"):
            only = a

    issues: list[Issue] = []
    rules = load_rules(issues)
    specs = collect_specs(only)
    all_specs = {s.id: s for s in collect_specs(None)}

    if only and not specs:
        print(f"找不到需求 `{only}`（specs/{only}/ 不存在）")
        return 2

    snap = load_snapshot()
    for s in specs:
        check_spec(s, rules, snap, issues)
        if s.exists and s.status in SPEC_STATES:
            check_tasks(s, rules, all_specs, issues)
    if not only:
        check_orphan_tasks(all_specs, issues)
        check_dep_cycles(all_specs, issues)
        check_adrs(issues)
        check_modules(issues)
    save_snapshot(snap)

    errors = [i for i in issues if i.level == "ERROR"]
    warns = [i for i in issues if i.level == "WARN"]

    show = sorted((i for i in issues if i.level in ("ERROR", "WARN")),
                  key=lambda i: (LEVEL_ORDER[i.level], i.where))

    if not quiet:
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        print("=" * 64)
        print(f"  dev-sdd 护栏校验   {now}")
        print("=" * 64)
        print(f"  规范基准：单任务 ≤ {rules['max_task_hours']:g}h · "
              f"验收 ≥ {int(rules['min_acceptance_items'])} 条 · "
              f"测试 {'必须有' if truthy(rules['require_tests']) else '可省'}")
        names = ", ".join(f"{s.id}({s.status})" for s in specs) or "（暂无需求）"
        print(f"  需求 {len(specs)} 份：{names}")
        print("-" * 64)

    if show:
        for i in show:
            print(f"{LEVEL_TAG[i.level]} {i.where}")
            print(f"        {i.msg}")
        print("-" * 64)
    elif not quiet:
        if not specs:
            print("[ OK ] 暂无待校验的需求。用 init_dev.py spec 建第一份。")
        else:
            print("[ OK ] 全部通过，没有发现问题。")
        print("-" * 64)

    print(f"结果：{len(errors)} 个错误 · {len(warns)} 个警告 · 共检查 {len(specs)} 份需求")
    if errors:
        print("→ 有错误必须处理完（accepted / done 状态不放行）。")
        return 1
    if warns and strict:
        print("→ --strict 模式下警告也算失败。")
        return 1
    if warns:
        print("→ 没有硬错误，但警告值得看一眼。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
