# examples/ — 完整样例

一个世界观 + 两篇故事，用来对照「这套体系真正在管什么」。

人物、故事全部虚构。

## 先看这三个地方

### 1. `worlds/W-001/world.md` → 看「六、术语表」

```
| 术语 | 唯一写法 | 禁止写法（出现即拦） | 释义 |
| 井   | 井       | 水井、神井、灵井     | 街心那口古井 |
```

**这一列是整套体系最实用的东西。** 同一个概念在十章里出现三种叫法，是世界崩塌最快的方式。
现在 `guard_novel.py` 会真的扫出来。ST-001 的第二稿里写过一次"水井"，就是被这个拦下的。

### 2. `stories/ST-001/threads.md` → 看伏笔怎么交叉校验

| F-001 | 井水上飘着不是陈默的铜钱 | ch-01 | ch-03 | paid |

表里说 `ch-03` 回收，而 `chapters/ST-001/ch-03-铜钱.md` 的 frontmatter 必须写着 `pays: F-001,F-002`。
两边对不上，脚本就报错。**这样"写忘了"这件事就变成了机器问题，不是记性问题。**

### 3. `stories/ST-002/story.md` → 看第二篇怎么复用同一个世界

ST-002 的设定书里**一个字都没重复定义世界规则**，只写「本篇要干什么」。
世界观改了，两篇一起受影响 —— 这正是你要的那个结构。

它只新增了一条 `N-003：井水照不出重来过的人`，并标注「待定」——
**新设定先在故事里记着，值不值得提升到世界观，等写第二遍时再决定。**

## 目录对照真实用法

```
examples/worlds/      →  实际在 worlds/
examples/stories/     →  实际在 stories/
examples/chapters/    →  实际在 chapters/
```

`examples/` **不参与 guard_novel.py 校验**（它是档案，不是活数据）。

## 一个说明

样例正文是节选（每章 600~2000 字），低于 RULES 里单章 1500 字的下限。
这是正常的 —— 档案不参与校验。你自己写的时候按 RULES 的标准来。

## 想从头跑一遍

```bash
python bin/init_novel.py world W-002 你的世界名
python bin/init_novel.py character W-002 主角名
python bin/init_novel.py story ST-001 你的故事 --world W-002 --form short
python bin/init_novel.py chapter ST-001 第一章标题
```
