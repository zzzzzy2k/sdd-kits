---
name: dev-sdd
description: "通用软件开发的规范驱动体系（SDD）：需求规格 → 评审 → 任务卡 → 验收 → 复盘沉淀，不限技术栈和语言。核心价值是把「需求膨胀」和「做完对不上」变成可机器校验的约束。TRIGGER: 用户要写需求规格/SPEC、拆开发任务卡、做技术选型决策记录（ADR）、沉淀可复用方案包（modules）、建立工程规范 RULES、复盘一个已完成的开发需求、或者问「这个东西该怎么规划」时。DO NOT TRIGGER: 直接写代码/改 bug（写代码本身不需要 SDD 流程）、投资决策记录、小说创作。"
version: 1.1.0
allowed-tools: Bash, Read, Glob, Grep, Edit, AskUserQuestion
---

# dev-sdd · 通用开发 SDD

## 第一步：定位体系目录（★ 不要跳过）

**这个体系可能被移动过位置，所以不要假设路径固定。**

1. 读同目录下的 `sdd-root.txt` —— 里面一行就是 `SDD规范` 的绝对路径
2. 用它拼出本包目录：`<根目录>/dev-sdd/`
3. 验证 `bin/guard_dev.py` 存在
4. **若 `sdd-root.txt` 不存在、或拼出来的路径失效**（说明目录被移动或删除）：
   - 用 Glob 搜索 `D:/Data/Study/Project/**/dev-sdd/bin/guard_dev.py`
   - 只有一处命中 → 把 `SDD规范` 的绝对路径写回 `sdd-root.txt`，继续
   - 多处命中或没找到 → 停下来问用户，**不要自己新建目录**

## 四层结构

| 层 | 回答什么 | 什么时候写 |
|---|---|---|
| `specs/` | 做什么、**不做什么**、怎么算做完 | 动手前 |
| `tasks/` | 具体怎么拆、做到哪了 | 需求 accepted 后 |
| `adr/` | 为什么选这个技术 | 做了不可逆选型时 |
| `modules/` | 这套做法下次怎么复用 | 同一件事做第二遍时 |

后两层是「可复利资产」——**别一开始就建，做第二遍的时候再抽**。第一遍就抽包，抽出来的是想象不是经验。

## 核心机制

状态机 `draft → review → accepted → implementing → done → archived`

四条铁律，护栏会拦：

1. **accepted 前不许开工** —— 任务 IN_PROGRESS 但需求还在 draft，直接报错
2. **accepted 后四件套缺一不可**：背景问题 / deliverables / **out-of-scope** / ≥3 条验收标准
3. **验收不许写「功能正常」「没问题」** —— 要能写成测试用例
4. **done 前所有任务必须 DONE** —— 不许「主要做完了先算完成」

## 怎么用

```bash
cd "<根目录>/dev-sdd"

python bin/init_dev.py spec SPEC-001 用户登录
python bin/init_dev.py task SPEC-001 feature 登录接口
python bin/init_dev.py adr 会话用JWT还是Session
python bin/init_dev.py module auth-jwt JWT认证方案

# 随时校验
python bin/guard_dev.py
python bin/init_dev.py status
```

## 关键原则

- **out-of-scope 比 deliverables 更重要**。用户描述需求时，主动问「这次明确不做什么」，并帮他写进第二节。需求膨胀从来不发生在「少做了」，全在「顺手多做一点」。
- **ADR 必须写「什么情况下应该重新考虑」**。缺这句，这条决策半年后就变成没人敢动的历史包袱。写 ADR 时若用户没提，主动追问。
- **缺陷卡必须有「根因」和「为什么之前没发现」**。只修症状的 bug 会以别的形式回来。
- 用户说「大概」「待定」「优化一下」时，指出来让他量化——别替他圆场。

## 不要做的事

- 不要修改 `RULES.md` 里 `RULES-BEGIN/END` 之间的数值
- 不要在需求还没 accepted 时就开始写代码（那正是这套体系要防的）
- 不要把 `examples/` 当真实数据（它不参与校验）
- **找不到体系目录时，不要新建一个** —— 先搜，搜不到问用户

## 维护

改 `bin/guard_dev.py` 之后必须跑：

```bash
python .dev/selfcheck.py    # 25 个用例，一半是「故意违规必须被拦」
```
