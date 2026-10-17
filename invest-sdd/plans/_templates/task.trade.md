---
decision: {{ID}}
kind: trade
op: {{OP}}
status: READY
filled: false
fill_price:
fill_qty:
fill_date:
blocked_reason:
---

# 交易执行卡：{{NAME}}（{{ID}}）· {{OP}}

> `op`：buy | sell | add | reduce
> `status`：READY → IN_PROGRESS → DONE ／ 任意阶段可 BLOCKED（必须写 blocked_reason）
> `filled`：true 表示已真实成交，需同时填 fill_price / fill_qty / fill_date

## 一、操作计划

- **操作**：{{OP}}
- **计划金额 / 价位 / 数量**：
- **是否在决策书计划内**：是 / 否（否 → 必须先新开决策书）

## 二、验收清单（全勾才能 DONE）

- [ ] 对应决策书状态 = accepted（未 accepted 不得执行）
- [ ] 操作符合决策书计划（仓位不超限）
- [ ] 成交记录已登记（价格 / 数量 / 时间 / 手续费）
- [ ] 持仓卡已同步更新

## 三、成交记录

| 日期 | 方向 | 价格 | 数量 | 金额 | 手续费 | 备注 |
|---|---|---|---|---|---|---|
| | | | | | | |

## 四、阻塞说明（status = BLOCKED 时必填）

-
