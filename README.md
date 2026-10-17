# SDD 规范工具箱

> 同一套内核，三个领域包：**投资决策 / 通用开发 / 小说写作**。
> 全部零依赖（纯 Python 标准库）、数据是本地 Markdown、每条纪律都有脚本兜底。
>
> 📦 <https://github.com/zzzzzy2k/sdd-kits>

---

## 这是什么

**规范驱动开发（Spec-Driven Development）** 的落地实现，不是文档架子。

核心主张只有一句：

> **不靠「记住」，把约束外化成磁盘上能被机器校验的结构。**

三个包解决的是同一个问题的三个面：

| 包 | 解决什么 | 一句话 |
|---|---|---|
| `invest-sdd/` | 交易决策不可追溯 | 写决策书 → 评审拍板 → 按计划执行 → 复盘对照假设 |
| `dev-sdd/` | 需求膨胀、做完对不上 | 先写清做什么和**不做什么** → 拆任务 → 验收 → 沉淀方案 |
| `novel-sdd/` | 长篇设定 / 伏笔 / 用词打架 | 世界观冻结 + 术语禁止写法 + 伏笔交叉校验 |

---

## 目录

```
SDD规范/
├── SDD设计方案.txt      ★ 三套的共同上游：最初的设计讨论稿
├── invest-sdd/          投资领域包
├── dev-sdd/             通用开发领域包
├── novel-sdd/           小说写作领域包
├── skills/              三个 AI 技能定义（不存代码，只指向各自包）
└── tools/
    └── install-skills.py  把技能部署到 ~/.workbuddy/skills/
```

每个包内部结构一致：

```
<包>/
├── README.md            体系入口（先看这个）
├── RULES.md             领域纪律基准（机器可读块，脚本读它）
├── bin/
│   ├── init_*.py        脚手架
│   ├── guard_*.py       ★ 护栏（核心）
│   └── demo.py          生成完整流程样例
├── */_templates/        各层模板（模板即真源）
├── examples/            跑完全程的样例（不参与校验）
├── .dev/selfcheck.py    回归测试
└── 一键校验.bat          双击即跑
```

---

## 共同内核

四个包共享同一套机制，换领域只换语义：

| 机制 | 作用 |
|---|---|
| **状态机** | 每层文档带 `status`，非法跳级 / 回退由脚本拦 |
| **三重约束** | deliverables（要交付什么）/ out-of-scope（不做什么）/ validation（怎么算做完） |
| **frontmatter 元数据** | 机器读头部，人读正文，互不干扰 |
| **`RULES-BEGIN/END` 块** | 纪律写成键值对，脚本能读，你能改 |
| **错误码分段** | `D/S/W/T/F`… 每组一类，报错直接定位到层 |
| **回归测试** | 每条规则配一个「故意违规 → 必须被拦」的反向用例 |

### 三个领域包对照

| | 投资版 | 开发版 | 小说版 |
|---|---|---|---|
| 真源 | `decisions/` | `specs/` | `stories/` |
| 执行 | `plans/` | `tasks/` | `chapters/` |
| 可复利资产 | `strategies/` | `modules/` + `adr/` | `worlds/` |
| 领域校验 | 假设可证伪 / 仓位漂移 | 验收可测 / 依赖成环 | 术语一致 / 伏笔闭环 |
| 校验条数 | 8 类 | 14 类 | 16 类 |
| 回归用例 | 18 | 25 | 26 |

---

## 快速开始

```bash
cd invest-sdd && python bin/init_invest.py
cd dev-sdd    && python bin/init_dev.py
cd novel-sdd  && python bin/init_novel.py
```

想看「写到什么程度才算到位」，任意一套都能生成样例：

```bash
python bin/init_<领域>.py demo
```

---

## 安装为 AI 技能（可选）

`skills/` 下是三个技能定义（`invest-sdd` / `dev-sdd` / `novel-sdd`），
`tools/install-skills.py` 负责把它们部署到 `~/.workbuddy/skills/`。

```bash
python tools/install-skills.py           # 安装 / 更新
python tools/install-skills.py --list    # 检查已装的技能，路径是否还有效
```

双击 `安装技能.bat` 也行。

### 为什么技能里不存代码

技能目录（C 盘）和本仓库（D 盘）是两处。如果把代码也复制进技能目录，就会出现
**两份真源**——改哪一份？版本管理、备份、推 GitHub 全在仓库这边，技能目录那份会逐渐腐化。

所以技能里只有：

```
~/.workbuddy/skills/<名字>/
├── SKILL.md        说明 + 触发条件 + 铁律
└── sdd-root.txt    一行：本仓库现在的绝对路径
```

**代码永远只有这一份。** 技能靠 `sdd-root.txt` 找过来。

### 移动目录了怎么办

整个 `SDD规范/` 随便搬。搬完重跑一次：

```bash
python tools/install-skills.py
```

它会重写所有 `sdd-root.txt`。**只修复路径失效的那几个**，其余的判为「未变」跳过。

就算你忘了跑，技能里的 SKILL.md 也写了自愈步骤：读不到 `sdd-root.txt` 或路径失效时，
会自动 Glob 搜索 `**/<包>/bin/guard_*.py`，找到后写回，找不到才来问你——**绝不会自己新建一个空目录**。

---

## 为什么是一个仓库

三套不是三个独立项目，是**一套知识的三次投影**：

- 改内核（比如修正 Markdown 解析的某个边界）往往三套一起改，一个 commit 能说清一件事
- `SDD设计方案.txt` 是所有包的上游，设计和产物必须在同一份版本历史里
- 新增领域包只需加目录，不用新建仓库

**私有数据不会入库**：真实决策书 / 项目需求 / 世界观正文，由各子项目自己的
`.gitignore` 排除 —— 它们知道哪些是模板、哪些是私人内容。

---

## 维护

改任何一个 `guard_*.py` 之后，**必须**跑对应包的回归测试：

```bash
cd dev-sdd && python .dev/selfcheck.py
```

护栏最危险的失效方式是**静默放行**——不报错，但规则其实没生效。
所以每个包里都有一半用例是「故意违规，必须被拦」。

---

*最初的设计讨论稿见 `SDD设计方案.txt`。各包的详细说明见各自 README。*
