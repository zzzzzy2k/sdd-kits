# examples/ — 样例档案

这里放的是**跑完全程的样例**，用来对照「一份合格的决策书长什么样」。

标的、代码、数字**全部虚构**，不构成任何投资建议。

## 怎么用

1. 先看 `DEMO-001/decision.md` —— 注意「零、状态流转记录」，那是一条完整的生命线
2. 再看 `DEMO-001/review.md` —— 事前评审是「防冲动」，事后复盘是「防遗忘」，两张表不是一回事
3. 看 `DEMO-001/plan.md` + 三张 task 卡 —— 计划怎么落成可验收的执行卡
4. 最后看 `demo-dividend/strategy.md` —— 经验怎么从一笔决策变成可复用的资产

## 注意

`examples/` 不在 `guard_invest.py` 的校验范围内（它是档案，不是活数据）。
真实使用时，决策书在 `decisions/<标的id>/`，执行卡在 `plans/<标的id>/`。

想自己从头跑一遍，先删掉 `decisions/` 和 `plans/` 下的实例，然后：

```bash
python bin/init_invest.py decision 000000 你的标的
```
