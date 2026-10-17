---
name: invest-sdd
description: "投资决策的规范驱动体系（SDD）：把每一笔交易当成一次可验收的任务——写决策书 → 评审拍板 → 按计划执行 → 复盘对照假设。核心价值是把「凭感觉」变成「可追溯」，把「忘了」变成「强制」。TRIGGER: 用户要记录买入/卖出/加仓决策、写投资决策书、推进某个标的的决策状态（idea/research/review/accepted/holding/closed）、复盘某笔交易、检查持仓是否违反纪律、修改投资纪律 RULES 时。DO NOT TRIGGER: 纯行情查询、个股基本面分析、生成持仓汇总表格（那是「持仓整理」skill 的事）、与投资无关的通用文档写作。"
version: 1.1.0
allowed-tools: Bash, Read, Glob, Grep, Edit, AskUserQuestion
---

# invest-sdd · 投资决策 SDD

## 第一步：定位体系目录（★ 不要跳过）

**这个体系可能被移动过位置，所以不要假设路径固定。**

1. 读同目录下的 `sdd-root.txt` —— 里面一行就是 `SDD规范` 的绝对路径
2. 用它拼出本包目录：`<根目录>/invest-sdd/`
3. 验证 `bin/guard_invest.py` 存在
4. **若 `sdd-root.txt` 不存在、或拼出来的路径失效**（说明目录被移动或删除）：
   - 用 Glob 搜索 `D:/Data/Study/Project/**/invest-sdd/bin/guard_invest.py`
   - 只有一处命中 → 把 `SDD规范` 的绝对路径写回 `sdd-root.txt`，继续
   - 多处命中或没找到 → 停下来问用户，**不要自己新建目录**

## 包内结构

| 路径 | 作用 |
|---|---|
| `README.md` | 入口文档，第一次用先读 |
| `RULES.md` | 纪律基准（**规则定义权在用户手里，AI 不替他改数值**） |
| `bin/init_invest.py` | 脚手架 |
| `bin/guard_invest.py` | **护栏（核心，绕过它等于没有体系）** |
| `.dev/selfcheck.py` | 回归测试 |

## 核心机制

状态机 `idea → research → review → accepted → executing → holding → closed → archived`

三条铁律，护栏会拦：

1. **accepted 前不许有真实成交** —— 先斩后奏也叫停
2. **accepted 必须过评审**（review.md 里 `verdict: pass` + `reviewed_on` 有日期）
3. **closed 前必须做「假设兑现对照」** —— 写了投资假设不对账 = 缺陷

## 怎么用

```bash
cd "<根目录>/invest-sdd"

# 新建一个标的的决策书
python bin/init_invest.py decision 600519 贵州茅台 --type stock --strategy dividend

# 每次改状态后校验（必须 0 错误才继续）
python bin/guard_invest.py 600519

# 看一眼所有标的的状态
python bin/init_invest.py status
```

Windows 上系统 Python 或 Anaconda 的都能跑（**纯标准库，不 import numpy**）。

## 关键原则

- **AI 只起草，不代签**。`review → accepted` 必须用户自己拍板，你不要替他改 status。
- **决策书就是投资 ADR**：背景 / 选项对比 / 决定 / 理由。**选项表必须列出「观望」和「放弃」**，否则看不出权衡过什么。
- **证伪条件比目标价重要**。用户写「看涨」要追问「什么情况证明你看错了」，逼出可验证指标。
- 用户说「差不多」「感觉会涨」「再看看」时，**不要替他润色成通顺句子**——那是帮他把模糊表述藏起来。直接指出护栏会拦，让他给数字。

## 不要做的事

- 不要修改 `RULES.md` 里 `RULES-BEGIN/END` 之间的数值（那是用户的风险偏好）
- 不要在 `decisions/` 之外自己发明目录结构
- 不要跳过 `guard_invest.py` 直接说「已经记好了」
- **找不到体系目录时，不要新建一个** —— 先搜，搜不到问用户

## 维护

改 `bin/guard_invest.py` 之后必须跑：

```bash
python .dev/selfcheck.py    # 18 个用例，一半是「故意违规必须被拦」
```
