# dev-sdd · 通用开发的规范驱动体系

> **先写清楚要做什么，再写代码。** 需求（spec）→ 评审（review）→ 任务（task）→ 验收（validation）→ 复盘沉淀。
>
> 面向个人开发 / 小团队的通用 SDD 骨架，不限技术栈、不限语言：
> Python、Java、前端、脚本、甚至写文档都套得上。零依赖（纯 Python 标准库），全部数据是本地 Markdown。

---

## 一句话

**SDD 不解决「你想得对不对」，它解决「你想过没有、怎么想的、做完对上了没有」。**

脚本校验不了「这个方案好不好」，但能保证四件事：
需求有边界（out-of-scope 不许空）、任务有凭据（没 accepted 不许开工）、
完成有验收（验收项不许写"功能正常"）、经验有归处（复盘不许空手而过）。

---

## 30 秒上手

```bash
# 1. 看一眼规范基准，把数字改成适合你的（这是你的工作节奏，不是我的）
#    改 RULES.md 里 RULES-BEGIN / RULES-END 之间的值

# 2. 建第一个需求
python bin/init_dev.py spec SPEC-001 用户登录

# 3. 填「一、背景与问题」和「二、目标 / 不做什么」，然后每一步都校验
python bin/guard_dev.py SPEC-001
```

想看「一层一层写到什么程度才算到位」：

```bash
python bin/init_dev.py demo
```

生成 `examples/` —— 一个需求从 `draft` 一路走到 `archived`，带 3 张任务卡、1 条 ADR、1 个方案包。

双击 `一键校验.bat` 也行。

---

## 状态机

```
draft（草稿：一句话想法）
  ↓ 写清背景 / 边界 / 验收标准
review（评审中：自己挑刺，或让 AI 扮演挑刺的）
  ↓ 评审通过（★ 人拍板）
accepted（已批准：★ 此时才允许写业务代码）
  ↓ 拆分任务卡，逐张执行
implementing（实现中）
  ↓ 所有任务 DONE + 验收逐条过
done（已完成：★ 必须附复盘，目标达成对照 + 踩的坑）
  ↓ 沉淀经验
archived（已归档：经验进 ADR / 方案包 / RULES.md）
```

**硬规则（`guard_dev.py` 强制，绕不过去）：**

1. `draft → accepted` 必须经过 `review` 且有评审记录 —— 防"想当然就开工"
2. **accepted 之前不许开工** —— 任务卡一旦 IN_PROGRESS/DONE，需求还停在 draft 就报错
3. `accepted` 后**四件套缺一不可**：背景问题 / deliverables / out-of-scope / ≥3 条验收标准
4. `done` 前**所有任务必须 DONE** —— 不许"主要功能做完了先算完成"
5. `done` 前必须复盘（目标达成对照 + 踩坑/经验）—— 否则经验留不下来

---

## 四层结构

```
dev-sdd/
├── README.md                    ← 你在看的这份
├── RULES.md                     ★ 工程规范基准（你改，脚本读）
├── bin/
│   ├── init_dev.py              脚手架
│   ├── guard_dev.py             ★ 护栏（14 类校验）
│   └── demo.py                  生成完整流程样例
├── specs/                       ★ 需求层（唯一真源）
│   ├── _templates/
│   │   ├── spec.md              需求规格（三重约束）
│   │   └── review.md            评审 + 复盘
│   └── <需求id>/
│       ├── spec.md              带状态机
│       └── review.md
├── tasks/                       执行层
│   ├── _templates/
│   │   ├── task.feature.md      新功能
│   │   ├── task.fix.md          缺陷修复
│   │   └── task.refactor.md     重构
│   └── <需求id>/
│       ├── T-001-feature.md
│       └── T-002-fix.md
├── adr/                         ★ 架构决策记录（可复利资产）
│   ├── _templates/adr.md
│   └── ADR-001.md
├── modules/                     ★ 方案包（可复利资产）
│   ├── _templates/
│   │   ├── module.md
│   │   └── module_review.md
│   └── <方案id>/
└── examples/                    跑完全程的样例（不被校验）
```

### 四层各管什么

| 层 | 回答的问题 | 什么时候写 |
|---|---|---|
| **specs/** | 要做**什么**、**不做什么**、怎么算做完 | 动手前 |
| **tasks/** | 具体**怎么拆**、做到哪了 | 需求 accepted 后 |
| **adr/** | 为什么选**这个技术**，不选别的 | 做了不可逆选型时 |
| **modules/** | 这套做法**下次怎么复用** | 同一件事做了第二遍时 |

后两层就是「可复利资产」——**别一开始就建，做第二遍的时候再抽**。
第一遍就抽包，抽出来的是想象，不是经验。

---

## 日常流程

### 开新需求

```bash
python bin/init_dev.py spec SPEC-001 用户登录
# 填：背景与问题 / deliverables / out-of-scope / 验收标准
# 状态 draft → review，填 review.md 的事前评审表
# 评审通过 → status 改 accepted，verdict 改 pass
python bin/guard_dev.py SPEC-001        # 必须 0 错误
```

### 拆任务开工

```bash
python bin/init_dev.py task SPEC-001 feature 登录接口
python bin/init_dev.py task SPEC-001 fix 并发计数丢失
# 开工前 status 改 IN_PROGRESS，做完勾验收清单，再改 DONE
```

### 遇到技术选型

```bash
python bin/init_dev.py adr 会话状态用JWT还是Session
# 填：背景 / 选项对比（至少 2 个）/ 决策 / 后果
# 最关键的是第四节最后那句「什么情况下应该重新考虑」
```

### 做完复盘

```bash
# status → done，review.md 的 goal_achieved 填 yes/partial/no
# 「事后复盘」写：实际用时 / 返工次数 / 目标达成对照 / 踩的坑 / 经验
python bin/guard_dev.py SPEC-001        # 复盘没写就过不了

# 经验成体系了 → 抽成 modules/ 方案包
python bin/init_dev.py module auth-jwt JWT认证方案
```

---

## 护栏拦什么（14 类校验）

| # | 校验项 | 触发条件 |
|---|---|---|
| 1 | **状态机强制** | accepted 后缺 review.md / verdict 不是 pass / 无评审日期 |
| 2 | **需求完整性** | 背景「现状 / 问题」为空 |
| 3 | **deliverables 空** | 一个带内容的交付项都没有 |
| 4 | **out-of-scope 空** | 「不做什么」一条都没写 ★ |
| 5 | **验收标准不足** | 少于 RULES 规定的条数（默认 3） |
| 6 | **验收项笼统** | 写「功能正常 / 没问题 / 可以了」 |
| 7 | **敷衍词** | 「先这样吧 / 差不多就行 / 能跑就行」一律拦 |
| 8 | **模糊词** | 「大概 / 待定 / TODO / 优化一下」accepted 后升级为错误 |
| 9 | **提前开工** | 任务 IN_PROGRESS/DONE 但需求还没 accepted ★ |
| 10 | **验收未勾** | 任务 DONE 但清单还有未勾项 |
| 11 | **无测试** | 功能/缺陷任务 DONE 但没有测试项 ★ |
| 12 | **任务过大** | 预估工时超 RULES 上限（默认 8h） |
| 13 | **阻塞无因** | BLOCKED 但没写 blocked_reason |
| 14 | **需求提前完成** | 需求 done 但还有任务没 DONE |

**额外还查：**

- **引用完整性**：引用的 ADR / 方案包是否存在、是否已 accepted
- **依赖成环**：`depends_on` 互相依赖，DFS 检测
- **孤儿任务**：`tasks/xxx/` 没有对应需求
- **占位符残留**：模板复制完没替换
- **状态回退**：从 accepted 退回 draft（警告，但要在变更记录里写原因）
- **ADR 只列一个选项**：不是决策，是通知

### 退出码

| 码 | 含义 |
|---|---|
| 0 | 通过（可能有警告） |
| 1 | 有错误，或 `--strict` 下算上警告 |
| 2 | 环境 / 解析问题 |

```bash
python bin/guard_dev.py              # 全量
python bin/guard_dev.py SPEC-001     # 单项
python bin/guard_dev.py --strict     # 警告也算失败
python bin/guard_dev.py --quiet      # 只输出问题
```

---

## 三个关键设计决策

### 1. out-of-scope 比 deliverables 更重要

需求膨胀从来不发生在"少做了"，全都发生在"顺手多做一点"。
所以「不做什么」是护栏的第 4 条硬校验 —— 空着直接拦。

样例里那个需求砍掉了三项：第三方登录、短信登录、密码找回，每一项都写了为什么不在这做。

### 2. ADR 必须写「什么情况下应该重新考虑」

这是整个 ADR 里最重要的一句，也是最多人漏的一句。
没有它，半年后这条决策就变成**没人敢动的历史包袱**——大家都不知道当初为什么这么定，也没人敢推翻。

样例里的 ADR-001 明确写了三条重新考虑的条件（要即时踢下线 / 要单点登录 / 多实例共享登录态）。

### 3. 缺陷卡必须有「根因」和「为什么之前没发现」

只修症状的 bug 会**以别的形式回来**。
所以 `task.fix.md` 的验收里有一条是「复现步骤已固化成测试用例」，
样例里的 T-003 就是这么把「并发丢计数」这个坑彻底钉死的。

---

## 与 invest-sdd 的关系

`../invest-sdd/` 是同一套内核的**投资领域包**。两套对照着看：

| 通用开发版 | 投资版 | 共同内核 |
|---|---|---|
| `specs/` 需求规格 | `decisions/` 标的决策书 | 都带 8 态状态机 + 三重约束 |
| `tasks/` 任务卡 | `plans/` 交易执行卡 | 都要求验收清单全勾才能完成 |
| `adr/` 架构决策 | 决策书本身即 ADR | ADR 思维 |
| `modules/` 方案包 | `strategies/` 策略包 | 可复利资产，必须 accepted 才能被引用 |
| `RULES.md` 工程规范 | `RULES.md` 投资纪律 | 机器可读块，脚本读数值 |

**两套的护栏脚本逻辑是一脉相承的**（同一套 Markdown 解析 + 错误码分段 + 回归测试），
所以踩过的坑也是共通的 —— 见下方。

---

## 维护

### 改模板

模板即真源，改 `_templates/` 下的文件，之后新建的就跟着变（已有文件不动）。

### 改规范

只改 `RULES.md` 里 `RULES-BEGIN / RULES-END` 之间的键值对。**格式别动**，脚本靠它解析。

| 键 | 作用 |
|---|---|
| `max_task_hours` | 单任务工时上限，超了提醒拆 |
| `min_acceptance_items` | 需求最少几条验收标准 |
| `max_acceptance_items` | 单任务最多几条验收项 |
| `require_tests` | 功能/缺陷任务是否必须有测试 |
| `require_adr_accepted` | 引用的 ADR 是否必须 accepted |
| `forbid` | 禁止项清单 |

### 改护栏逻辑

错误码分段：`S`（spec）/ `T`（task）/ `A`（adr）/ `M`（module）/ `R`（rules）。

**改完必须跑回归**：

```bash
python .dev/selfcheck.py
```

25 个用例，一半是「故意违规 → 必须被拦」的反向用例。
**护栏最危险的失效方式是静默放行**——不报错但规则没生效，比报错可怕得多。

---

## 已知陷阱（改代码前必读）

前两条是在投资版上踩的，这套又踩了第三条，都是同一类根因。

1. **正则 `\s*` 会吃掉换行** —— 解析 Markdown 时，冒号后的 `\s*` 会跨行读到下一行内容，
   导致字段为空时静默漏报。**单行解析一律用 `[ \t\u3000]*` / `[^\n]*`。**
2. **`checkboxes()` 也踩了同一个坑** —— `- \[([ xX])\]\s*(.*)` 里 `\s*` 吃掉换行，
   把 3 个空验收项合并成 1 个。已改成 `[^\n]*`。
3. **标题层级解析不能只认 `##`** —— `### deliverables` 是三级标题，
   只匹配 `^##\s` 会把子段并进上一段，导致 deliverables 永远"为空"。
   现在 `section()` 支持 2~6 级，并按标题级别判断段落边界。
4. **「含测试二字」不等于"写了测试"** —— 「无回归：原有测试全部通过」含"测试"，
   但它只是防退化。用子串匹配会让 `require_tests` 形同虚设。已单独排除含「回归」的项。
5. **规则校验要么紧邻、要么明确** —— 投资版上「止盈 +20%」的 20 曾被当成止损线。
   宁可写严格的正则，也不要写宽松的"大概能匹配上"。

---

## 待办

- [ ] 跑 2~3 个真实需求后，回来沉淀第一个 modules/ 方案包
- [ ] 可选：`guard_dev.py --fix` 自动补全空的 frontmatter 字段
- [ ] 可选：生成需求依赖图（`depends_on` 已经有环检测，画图是下一步）

---

_设计依据：`../SDD设计方案.txt`（讨论稿 v0.1）的通用化改造。
投资领域包见 `../invest-sdd/`。_
