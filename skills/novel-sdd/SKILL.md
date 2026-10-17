---
name: novel-sdd
description: "小说/短文/短故事的规范驱动体系（SDD）：用一个可复用的世界观包 + 术语禁写表 + 伏笔追踪，解决长篇写作中设定矛盾、伏笔断线、用词不一致的问题。核心价值是不靠「记住」，而是把一致性外化成能被脚本校验的结构。TRIGGER: 用户要写小说/短篇/小故事/连载、建立或修改世界观、写人物卡、追踪伏笔回收、检查前后设定是否矛盾、想在同一世界观下开新故事时。DO NOT TRIGGER: 通用文档写作、需求规格/技术方案、投资决策记录。"
version: 1.1.0
allowed-tools: Bash, Read, Glob, Grep, Edit, Write, AskUserQuestion
---

# novel-sdd · 小说写作 SDD

## 第一步：定位体系目录（★ 不要跳过）

**这个体系可能被移动过位置，所以不要假设路径固定。**

1. 读同目录下的 `sdd-root.txt` —— 里面一行就是 `SDD规范` 的绝对路径
2. 用它拼出本包目录：`<根目录>/novel-sdd/`
3. 验证 `bin/guard_novel.py` 存在
4. **若 `sdd-root.txt` 不存在、或拼出来的路径失效**（说明目录被移动或删除）：
   - 用 Glob 搜索 `D:/Data/Study/Project/**/novel-sdd/bin/guard_novel.py`
   - 只有一处命中 → 把 `SDD规范` 的绝对路径写回 `sdd-root.txt`，继续
   - 多处命中或没找到 → 停下来问用户，**不要自己新建目录**

## 三层结构

```
worlds/W-001/     世界观包（可复用资产）：world.md + world_review.md + characters/ + changes/
stories/ST-001/   故事（= spec）：story.md + review.md + threads.md + outline.md
chapters/ST-001/  章节（= task）：ch-01-xxx.md（含正文）
```

**一个世界观可以挂 N 篇故事**。故事里只写「这一篇要干什么」，设定一律引用世界观，**一个字都不重复定义**。

## 核心机制

世界观 `draft → review → accepted`（**定稿后冻结**）
故事 `idea → outlining → drafting → revising → done → archived`

三个杀招，护栏会拦：

1. **术语表的「禁止写法」列** —— 例如规定「井」禁止写「水井/神井」，脚本扫每章正文，命中即报错并指出正确写法。这是解决「同一东西三种叫法」的唯一有效手段。
2. **伏笔交叉校验** —— `threads.md`（埋设章/计划回收章/状态）× 章节卡 frontmatter 的 `plants`/`pays`。故事完结还有 `open` 伏笔 → 拦。
3. **世界观冻结** —— accepted 后改它必须建 `changes/` 变更单，写清「影响哪些已写故事」。

## 怎么用

```bash
cd "<根目录>/novel-sdd"

# 建世界观 → 填世界规则 + 术语表
python bin/init_novel.py world W-001 青石镇
python bin/init_novel.py character W-001 陈默

# 写故事（必须指定 world）
python bin/init_novel.py story ST-001 井底的铜钱 --world W-001 --form short
python bin/init_novel.py chapter ST-001 井边

# 随时校验
python bin/guard_novel.py
```

## 关键原则

- **开新故事时，先问「用哪个世界观」**。不要新建世界观，除非用户明确说要新世界——这是这套体系最重要的复用点。
- **写正文前先看术语表**，确认专有名词的唯一写法。写完跑一次 guard，禁写词会被抓出来。
- **不要替用户改世界观**。他觉得设定要调整时，引导他走变更流程：版本号 +0.1 → 写变更记录 → 建 `changes/` 变更单 → 写清影响哪些故事。
- **短篇先写「不写什么」**。`story.md` 第二节是刹车，用户容易跳过，要主动问。
- 用户想加新设定时，先记在 `story.md` 第六节「本篇新增的设定」，标「待定」。**别急着提升到世界观**——等写第二遍时看它是否真的被复用了。

## 不要做的事

- 不要在 `stories/` 里重复定义世界规则
- 不要为了「让故事更精彩」而违反 `world.md` 的世界规则（那是硬约束）
- 不要在故事完结时留着 `open` 伏笔不处理（要么收，要么标 `dropped` 并写原因）
- **找不到体系目录时，不要新建一个** —— 先搜，搜不到问用户

## 维护

改 `bin/guard_novel.py` 之后必须跑：

```bash
python .dev/selfcheck.py    # 26 个用例，一半是「故意写错必须被拦」
```
