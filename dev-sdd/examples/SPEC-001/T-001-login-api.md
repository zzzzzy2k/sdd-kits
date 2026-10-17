---
spec: SPEC-001
task: T-001
kind: feature
status: DONE
estimate_hours: 6
updated: 2026-06-15
---

# 任务卡：T-001 登录接口

- **关联需求**：`specs/SPEC-001/spec.md`
- **状态**：READY → IN_PROGRESS → DONE

## 一、做什么

- **内容**：POST /api/auth/login，校验账号密码，签发 JWT
- **涉及文件**：`api/auth/login.py`、`services/auth.py`
- **依赖**：无

## 二、验收清单（全勾才能 DONE）

- [x] 需求规格状态 = accepted 或 implementing
- [x] 功能按验收标准逐条实现并自测过
- [x] 单元测试已写且通过
- [x] 无回归：原有测试全部通过
- [x] 代码已自查（命名 / 异常 / 边界 / 无调试残留）

## 三、测试记录

| 类型 | 内容 | 结果 |
|---|---|---|
| 单元测试 | 正确密码 / 错误密码 / 不存在账号 3 个用例 | 全绿 |
| 手动验证 | Postman 调用，token 可被中间件识别 | 通过 |

## 四、阻塞说明（BLOCKED 时必填）

- 无
