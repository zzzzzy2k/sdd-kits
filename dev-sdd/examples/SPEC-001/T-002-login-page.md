---
spec: SPEC-001
task: T-002
kind: feature
status: DONE
estimate_hours: 5
updated: 2026-06-17
---

# 任务卡：T-002 前端登录页

- **关联需求**：`specs/SPEC-001/spec.md`
- **状态**：READY → IN_PROGRESS → DONE

## 一、做什么

- **内容**：登录表单、错误提示、token 存储与请求拦截器
- **涉及文件**：`web/login.html`、`web/login.js`、`web/request.js`
- **依赖**：T-001（接口要先有）

## 二、验收清单（全勾才能 DONE）

- [x] 需求规格状态 = accepted 或 implementing
- [x] 功能按验收标准逐条实现并自测过
- [x] 单元测试已写且通过（请求拦截器有测试）
- [x] 无回归：原有测试全部通过
- [x] 代码已自查（命名 / 异常 / 边界 / 无调试残留）

## 三、测试记录

| 类型 | 内容 | 结果 |
|---|---|---|
| 单元测试 | 拦截器自动带 token / 401 跳登录页 | 全绿 |
| 手动验证 | 登录 → 刷新 → 仍保持登录态 | 通过 |

## 四、阻塞说明（BLOCKED 时必填）

- 无
