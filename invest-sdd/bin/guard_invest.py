#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
guard_invest.py — invest-sdd 护栏脚本

把投资纪律变成不可绕过的机器校验。对应设计方案 4.5 节的 8 条校验逻辑：

  1. 状态机强制         idea→accepted 必须有评审记录，不能跳 review，不能回退
  2. 决策书完整性       缺投资假设 / 证伪条件 / 止损线 → 拦截
  3. 模糊词检测         "差不多 / 感觉会涨 / 可能吧" 这类不可证伪表述 → 拦截
  4. accepted 前无成交  plans/ 下出现真实成交但决策书未 accepted → 违规
  5. 持仓漂移检测       仓位超 RULES 上限 / 止损线被删 → 报警
  6. 复盘闭环           closed 但 review.md 无复盘记录 → 拦截
  7. 策略包引用校验     决策书引用的策略包必须 accepted
  8. 任务卡验收         DONE 前验收全勾，BLOCKED 必须登记原因

用法：
    python bin/guard_invest.py                # 全量校验
    python bin/guard_invest.py 600519         # 只校验某个标的
    python bin/guard_invest.py --strict       # 警告也算失败
    python bin/guard_invest.py --quiet        # 只输出问题

退出码：0 通过 / 1 有错误 / 2 环境或解析问题
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ── 常量 ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
STATE_ORDER = [
    "idea", "research", "review", "accepted",
    "executing", "holding", "closed", "archived",
]
STATE_CN = {
    "idea": "想法", "research": "调研中", "review": "评审中",
    "accepted": "已批准", "executing": "执行中", "holding": "持有中",
    "closed": "已完结", "archived": "已归档",
}
# accepted 及之后的状态，决策书必须是完整的
LOCKED_STATES = set(STATE_ORDER[STATE_ORDER.index("accepted"):])
CLOSED_STATES = {"closed", "archived"}
TASK_STATES = {"READY", "IN_PROGRESS", "DONE", "BLOCKED"}
VALID_RESULTS = {"fulfilled", "failed", "partial"}

# 强模糊词：任何阶段出现都拦，属于「根本没法验收」的表述
VAGUE_STRONG = [
    "感觉会涨", "感觉不错", "看着办", "到时候再说", "说不定",
    "应该会涨", "大概率会涨", "随便买", "再看吧", "跟着感觉",
]
# 弱模糊词：草稿阶段只提醒，accepted 之后必须量化
VAGUE_WEAK = ["差不多", "可能", "也许", "大概", "应该会", "大概率",
              "待定", "后续再说", "了再说", "看情况"]

# 止损线：必须紧邻数字，且不许跨过分号/逗号（防止把「止盈 +20%」当成止损线）
STOP_RE = re.compile(r"止损线[^；;，,。\n]{0,8}?([-－]?\d+(?:\.\d+)?)\s*%")

SKIP_DIRS = {"_templates"}

# ── 输出 ────────────────────────────────────────────────────────────────────

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


# ── Markdown 解析 ───────────────────────────────────────────────────────────

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
    """回退解析 `- 状态：idea` 这类正文行内字段。"""
    for name in names:
        m = re.search(r"^[\s>*-]*" + name + r"\s*[：:][ \t\u3000]*([^\n|]+)", body, re.M)
        if m:
            return m.group(1).strip()
    return ""


def get_meta(meta: dict, body: str, key: str, cn_names: list[str] | None = None) -> str:
    v = meta.get(key, "").strip()
    if v:
        return v
    if cn_names:
        return inline_field(body, cn_names)
    return ""


def section(body: str, keyword: str) -> str:
    """取 `## ...keyword...` 到下一个 `## ` 之间的正文。"""
    lines = body.splitlines()
    out: list[str] = []
    grabbing = False
    for line in lines:
        if re.match(r"^##\s", line):
            if grabbing:
                break
            grabbing = keyword in line
            continue
        if grabbing:
            out.append(line)
    return "\n".join(out)


def field_in(text: str, label: str) -> str:
    """取 `- **标签**（说明）：值` 冒号后的值。

    注意：冒号后只吃空格/制表符，**不能吃换行** —— 否则值为空时会读到下一行
    （曾因此漏报「投资假设为空」，护栏静默失效）。
    """
    m = re.search(r"\*\*" + re.escape(label) + r"\*\*[^\n]*?[：:][ \t\u3000]*([^\n]*)", text)
    return m.group(1).strip() if m else ""


def is_blank(value: str) -> bool:
    """判断值是否为空 / 仍是占位。"""
    v = (value or "").strip()
    if not v:
        return True
    if set(v) <= set("_-— 　"):
        return True
    if "{{" in v and "}}" in v:
        return True
    if v.startswith("<") and v.endswith(">"):
        return True
    if re.fullmatch(r"[_\-—\s　]*", v):
        return True
    return False


def pct_in(text: str) -> float | None:
    """抓「止损线」后面紧跟的百分数，返回绝对值（-8% → 8.0）。

    必须紧邻，且不许跨过分号/逗号 —— 否则「止损线 ；止盈 +20%」里的 20
    会被当成止损线，导致空止损被误判为合规（曾因此漏报）。
    """
    m = STOP_RE.search(text)
    if not m:
        return None
    try:
        return abs(float(m.group(1).replace("－", "-")))
    except ValueError:
        return None


# ── RULES.md ───────────────────────────────────────────────────────────────

DEFAULT_RULES = {
    "max_single_weight": 20.0,
    "max_equity_weight": 80.0,
    "stop_loss_pct": -8.0,
    "forbid": "杠杆, 融资, 追涨停, T+0, ST, 退市风险股",
    "require_strategy_accepted": "true",
}


def load_rules(issues: list[Issue]) -> dict:
    path = ROOT / "RULES.md"
    if not path.exists():
        issues.append(Issue("WARN", "R001", "RULES.md",
                            "未找到 RULES.md，使用内置默认纪律"))
        return dict(DEFAULT_RULES)
    text = read_text(path)
    m = re.search(r"<!--\s*RULES-BEGIN\s*-->(.*?)<!--\s*RULES-END\s*-->", text, re.S)
    if not m:
        issues.append(Issue("WARN", "R002", "RULES.md",
                            "未找到 RULES-BEGIN/RULES-END 规则块，使用内置默认纪律"))
        return dict(DEFAULT_RULES)
    rules = dict(DEFAULT_RULES)
    seen = set()
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
        seen.add(k)
        rules[k] = v
    for req in ("max_single_weight", "max_equity_weight", "stop_loss_pct"):
        try:
            rules[req] = float(str(rules[req]))
        except (TypeError, ValueError):
            issues.append(Issue("ERROR", "R004", "RULES.md",
                                f"`{req}` 不是合法数字：{rules[req]!r}，已回退默认值"))
            rules[req] = DEFAULT_RULES[req]
    return rules


# ── 数据收集 ───────────────────────────────────────────────────────────────

def subdirs(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(p for p in path.iterdir() if p.is_dir() and p.name not in SKIP_DIRS)


def md_files(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(p for p in path.glob("*.md") if p.is_file())


class Decision:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.id = folder.name
        self.path = folder / "decision.md"
        self.review_path = folder / "review.md"
        self.exists = self.path.exists()
        self.meta: dict = {}
        self.body: str = ""
        self.text: str = ""
        self.status: str = ""
        self.review_meta: dict = {}
        self.review_body: str = ""
        if self.exists:
            self.text = read_text(self.path)
            self.meta, self.body = split_frontmatter(self.text)
            raw = get_meta(self.meta, self.body, "status", ["状态"])
            self.status = raw.split("|")[0].strip().lower().replace("　", "")
        if self.review_path.exists():
            rt = read_text(self.review_path)
            self.review_meta, self.review_body = split_frontmatter(rt)

    @property
    def rel(self) -> str:
        return f"decisions/{self.id}/decision.md"

    @property
    def index(self) -> int:
        return STATE_ORDER.index(self.status) if self.status in STATE_ORDER else -1

    @property
    def name(self) -> str:
        return self.meta.get("name", "") or self.id

    def value(self, *keys: str, cn: list[str] | None = None) -> str:
        for k in keys:
            v = self.meta.get(k, "").strip()
            if v:
                return v
        return inline_field(self.body, cn) if cn else ""


def collect_decisions(only: str | None) -> list[Decision]:
    out = []
    for d in subdirs(ROOT / "decisions"):
        if only and d.name != only:
            continue
        out.append(Decision(d))
    return out


# ── 状态快照（用于检测回退） ────────────────────────────────────────────────

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


# ── 校验主体 ───────────────────────────────────────────────────────────────

def check_decision(dec: Decision, rules: dict, snap: dict, issues: list[Issue]) -> None:
    if not dec.exists:
        issues.append(Issue("ERROR", "D001", f"decisions/{dec.id}",
                            "文件夹存在但没有 decision.md（先跑 init_invest.py decision）"))
        return

    # 0. 占位符未替换
    if "{{" in dec.text and "}}" in dec.text:
        issues.append(Issue("ERROR", "D002", dec.rel,
                            "文件里还有未替换的 {{占位符}}，这份是模板副本不是真实决策书"))
        return

    # 1. 状态合法性
    if not dec.status:
        issues.append(Issue("ERROR", "D003", dec.rel,
                            "缺少 status 字段（frontmatter 里加 `status: idea`）"))
        return
    if dec.status not in STATE_ORDER:
        issues.append(Issue("ERROR", "D004", dec.rel,
                            f"非法状态 `{dec.status}`，合法值：{' / '.join(STATE_ORDER)}"))
        return

    # 2. 状态回退
    prev = snap.get(dec.id)
    if prev in STATE_ORDER and dec.index < STATE_ORDER.index(prev):
        issues.append(Issue("WARN", "D005", dec.rel,
                            f"状态从 `{prev}` 回退到 `{dec.status}` —— 允许（比如计划作废），"
                            "但请确认不是为了绕过评审"))
    snap[dec.id] = dec.status

    locked = dec.status in LOCKED_STATES

    # 3. 评审记录（idea→accepted 不能跳 review）
    has_review = dec.review_path.exists()
    verdict = (dec.review_meta.get("verdict", "") or "").strip().lower()
    reviewed_on = (dec.review_meta.get("reviewed_on", "") or "").strip()
    if locked:
        if not has_review:
            issues.append(Issue("ERROR", "D006", dec.rel,
                                f"状态 `{dec.status}` 但缺少 review.md —— "
                                "idea→accepted 必须过 review，不允许跳级"))
        else:
            if verdict != "pass":
                issues.append(Issue("ERROR", "D007", f"decisions/{dec.id}/review.md",
                                    f"verdict = `{verdict or '未填'}`，accepted 前必须为 pass"))
            if is_blank(reviewed_on):
                issues.append(Issue("ERROR", "D008", f"decisions/{dec.id}/review.md",
                                    "reviewed_on 未填 —— 评审必须有日期，否则无法追溯"))

    # 4. 决策书完整性（accepted 之后必须全）
    hyp = section(dec.body, "投资假设")
    logic = field_in(hyp, "逻辑")
    keyhyp = field_in(hyp, "关键假设")
    falsify = field_in(hyp, "证伪条件")
    for label, val, code in (
        ("逻辑（为什么买）", logic, "D009"),
        ("关键假设", keyhyp, "D010"),
        ("证伪条件", falsify, "D011"),
    ):
        if is_blank(val):
            issues.append(Issue("ERROR" if locked else "WARN", code, dec.rel,
                                f"「{label}」为空 —— " +
                                ("已 accepted 不得留空，先补全再交易" if locked
                                 else "建议尽早写清楚，否则无法验收")))

    # 止损线
    stop_val = pct_in(dec.body)
    if stop_val is None:
        issues.append(Issue("ERROR" if locked else "WARN", "D012", dec.rel,
                            "未找到止损线数值 —— " +
                            ("RULES.md 要求交易前必须设定止损" if locked
                             else "deliverables 里请写明止损线（如 -8%）")))
    elif locked:
        rule_stop = abs(float(rules["stop_loss_pct"]))
        if stop_val > rule_stop + 0.01:
            issues.append(Issue("WARN", "D021", dec.rel,
                                f"止损线 -{stop_val:g}% 比 RULES 纪律的 -{rule_stop:g}% 更松"
                                " —— 等于自己给自己放水，确认是有意为之"))

    # 5. 模糊词
    for idx, line in enumerate(dec.body.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        for w in VAGUE_STRONG:
            if w in stripped:
                issues.append(Issue("ERROR", "D013", f"{dec.rel}:{idx}",
                                    f"不可验收表述「{w}」—— 必须量化（价位/比例/指标）"))
        for w in VAGUE_WEAK:
            if w in stripped:
                issues.append(Issue("ERROR" if locked else "WARN", "D014", f"{dec.rel}:{idx}",
                                    f"模糊表述「{w}」—— " +
                                    ("已 accepted，必须改成可验证指标" if locked
                                     else "写完记得回来量化")))

    # 6. 策略包引用
    sid = dec.value("strategy")
    if sid:
        sp = ROOT / "strategies" / sid / "strategy.md"
        if not sp.exists():
            issues.append(Issue("ERROR", "D015", dec.rel,
                                f"引用了不存在的策略包 `{sid}`（strategies/{sid}/strategy.md）"))
        else:
            smeta, sbody = split_frontmatter(read_text(sp))
            sstatus = (smeta.get("status", "") or inline_field(sbody, ["状态"])).strip().lower()
            need = str(rules.get("require_strategy_accepted", "true")).lower() in ("1", "true", "yes")
            if sstatus != "accepted":
                lvl = "ERROR" if (locked and need) else "WARN"
                issues.append(Issue(lvl, "D016", dec.rel,
                                    f"引用的策略包 `{sid}` 状态为 `{sstatus or '未填'}`，"
                                    "只有 accepted 才能被引用"))

    # 7. 复盘闭环（closed / archived）
    if dec.status in CLOSED_STATES:
        if not has_review:
            issues.append(Issue("ERROR", "D017", dec.rel,
                                "状态 closed 但没有 review.md —— 复盘闭环断裂"))
        else:
            result = (dec.review_meta.get("hypothesis_result", "") or "").strip().lower()
            if result not in VALID_RESULTS:
                issues.append(Issue("ERROR", "D018", f"decisions/{dec.id}/review.md",
                                    f"hypothesis_result = `{result or '未填'}`，"
                                    f"closed 前必须填 {' / '.join(sorted(VALID_RESULTS))}"))
            retro = section(dec.review_body, "事后复盘")
            if is_blank(retro) or len(retro.strip()) < 40:
                issues.append(Issue("ERROR", "D019", f"decisions/{dec.id}/review.md",
                                    "「事后复盘」章节为空或过于简略 —— 必须做假设兑现对照"))

    # 8. archived 前经验必须落地
    if dec.status == "archived":
        exp = field_in(section(dec.review_body, "事后复盘"), "经验")
        if is_blank(exp):
            issues.append(Issue("WARN", "D020", f"decisions/{dec.id}/review.md",
                                "归档前「经验」为空 —— 经验没进 RULES.md / 策略包，等于白复盘"))


def check_plans(dec: Decision, issues: list[Issue]) -> None:
    """第 4、8 条：accepted 前不得有真实成交；任务卡验收清单。"""
    folder = ROOT / "plans" / dec.id
    if not folder.is_dir():
        return
    for f in md_files(folder):
        text = read_text(f)
        meta, body = split_frontmatter(text)
        rel = f"plans/{dec.id}/{f.name}"
        kind = (meta.get("kind", "") or "").strip().lower()
        status = (meta.get("status", "") or "").strip().upper()
        filled = (meta.get("filled", "") or "").strip().lower()

        if status and status not in TASK_STATES:
            issues.append(Issue("ERROR", "P001", rel,
                                f"非法任务状态 `{status}`，合法值：{' / '.join(sorted(TASK_STATES))}"))
        if ("{{" in text and "}}" in text):
            issues.append(Issue("ERROR", "P002", rel, "还有未替换的 {{占位符}}"))

        # 真实成交但决策书未 accepted → 先斩后奏
        if kind == "trade" and filled in ("true", "yes", "1"):
            if dec.index < STATE_ORDER.index("accepted"):
                issues.append(Issue("ERROR", "P003", rel,
                                    f"已登记真实成交，但决策书状态是 `{dec.status}` "
                                    "（未 accepted）—— 这笔交易没有决策依据"))
            for k in ("fill_price", "fill_qty", "fill_date"):
                if is_blank(meta.get(k, "")):
                    issues.append(Issue("ERROR", "P004", rel,
                                        f"filled=true 但 {k} 为空 —— 成交记录不完整"))

        # DONE 前验收清单必须全勾
        if status == "DONE":
            unchecked = len(re.findall(r"^\s*-\s*\[ \]", body, re.M))
            if unchecked:
                issues.append(Issue("ERROR", "P005", rel,
                                    f"状态 DONE 但还有 {unchecked} 项验收清单未勾"))
        if status == "BLOCKED":
            reason = (meta.get("blocked_reason", "") or "").strip()
            if is_blank(reason):
                issues.append(Issue("WARN", "P006", rel,
                                    "状态 BLOCKED 但没写 blocked_reason —— 卡在哪必须记下来"))


def check_holdings(rules: dict, decisions: dict[str, Decision], issues: list[Issue]) -> None:
    """第 5 条：持仓漂移检测。"""
    limit = float(rules["max_single_weight"])
    for f in md_files(ROOT / "holdings"):
        text = read_text(f)
        meta, body = split_frontmatter(text)
        rel = f"holdings/{f.name}"
        if "{{" in text and "}}" in text:
            issues.append(Issue("ERROR", "H001", rel, "还有未替换的 {{占位符}}"))
            continue

        raw_w = (meta.get("weight", "") or "").strip()
        try:
            weight = abs(float(raw_w.rstrip("%").strip()))
        except ValueError:
            issues.append(Issue("ERROR", "H002", rel,
                                f"weight 不是数字：`{raw_w}`（填 12.5 表示 12.5%）"))
            weight = None
        if weight is not None and weight > limit:
            issues.append(Issue("ERROR", "H003", rel,
                                f"仓位 {weight}% 超过 RULES 单标的上限 {limit}% —— 持仓漂移"))

        if is_blank(meta.get("stop_loss", "")):
            issues.append(Issue("WARN", "H004", rel,
                                "stop_loss 未填 —— 没有止损线的持仓等于裸奔"))

        did = (meta.get("decision", "") or f.stem).strip()
        dec = decisions.get(did)
        if dec is None:
            issues.append(Issue("WARN", "H005", rel,
                                f"关联的决策书 `{did}` 不存在 —— 持仓没有决策依据"))
        elif dec.status in CLOSED_STATES:
            issues.append(Issue("WARN", "H006", rel,
                                f"决策书已 `{dec.status}` 但持仓卡还在 —— 清仓后请归档持仓卡"))


def check_strategies(issues: list[Issue]) -> None:
    """策略包自身的完整性。"""
    seen: dict[str, str] = {}
    for d in subdirs(ROOT / "strategies"):
        f = d / "strategy.md"
        if not f.exists():
            issues.append(Issue("WARN", "S001", f"strategies/{d.name}",
                                "目录存在但没有 strategy.md"))
            continue
        text = read_text(f)
        meta, body = split_frontmatter(text)
        rel = f"strategies/{d.name}/strategy.md"
        if "{{" in text and "}}" in text:
            issues.append(Issue("ERROR", "S002", rel, "还有未替换的 {{占位符}}"))
            continue
        status = (meta.get("status", "") or inline_field(body, ["状态"])).strip().lower()
        if status not in {"draft", "review", "accepted", "deprecated"}:
            issues.append(Issue("ERROR", "S003", rel,
                                f"非法策略状态 `{status or '未填'}`"
                                "（draft / review / accepted / deprecated）"))
        sid = (meta.get("id", "") or d.name).strip()
        if sid in seen:
            issues.append(Issue("ERROR", "S004", rel, "策略 id 重复"))
        seen[sid] = rel
        # accepted 必须有策略评审
        if status == "accepted":
            sr = d / "strategy_review.md"
            if not sr.exists():
                issues.append(Issue("ERROR", "S005", rel,
                                    "状态 accepted 但缺少 strategy_review.md"))
            else:
                rm, _ = split_frontmatter(read_text(sr))
                if (rm.get("verdict", "") or "").strip().lower() != "pass":
                    issues.append(Issue("ERROR", "S006", rel,
                                        "状态 accepted 但策略评审 verdict 不是 pass"))


# ── 入口 ────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    _init_stdout()
    only = None
    strict = "--strict" in argv
    quiet = "--quiet" in argv
    for a in argv:
        if not a.startswith("-") and a not in ("strict", "quiet"):
            only = a

    issues: list[Issue] = []
    rules = load_rules(issues)
    decisions = collect_decisions(only)
    dec_map = {d.id: d for d in collect_decisions(None)}

    if only and not decisions:
        print(f"找不到标的 `{only}`（decisions/{only}/ 不存在）")
        return 2

    snap = load_snapshot()
    for d in decisions:
        check_decision(d, rules, snap, issues)
        if d.exists and d.status in STATE_ORDER:
            check_plans(d, issues)
    if not only:
        check_holdings(rules, dec_map, issues)
        check_strategies(issues)
    save_snapshot(snap)

    errors = [i for i in issues if i.level == "ERROR"]
    warns = [i for i in issues if i.level == "WARN"]

    # ── 打印 ──
    show = [i for i in issues if i.level in ("ERROR", "WARN")]
    show.sort(key=lambda i: (LEVEL_ORDER[i.level], i.where))

    if not quiet:
        now = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
        print("=" * 64)
        print(f"  invest-sdd 护栏校验   {now}")
        print("=" * 64)
        print(f"  规则基准：单标的上限 {rules['max_single_weight']:g}% · "
              f"权益上限 {rules['max_equity_weight']:g}% · "
              f"止损 {rules['stop_loss_pct']:g}%")
        names = ", ".join(f"{d.id}({d.status})" for d in decisions) or "（暂无决策书）"
        print(f"  决策书 {len(decisions)} 份：{names}")
        print("-" * 64)

    if show:
        for i in show:
            print(f"{LEVEL_TAG[i.level]} {i.where}")
            print(f"        {i.msg}")
        print("-" * 64)
    elif not quiet:
        if not decisions:
            print("[ OK ] 暂无待校验的决策书。用 init_invest.py decision 建第一份。")
        else:
            print("[ OK ] 全部通过，没有发现问题。纪律守住了。")
        print("-" * 64)

    print(f"结果：{len(errors)} 个错误 · {len(warns)} 个警告 · 共检查 {len(decisions)} 份决策书")
    if errors:
        print("→ 有错误必须处理完才能继续交易（accepted / closed 状态不放行）。")
        return 1
    if warns and strict:
        print("→ --strict 模式下警告也算失败。")
        return 1
    if warns:
        print("→ 没有硬错误，但警告值得看一眼。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
