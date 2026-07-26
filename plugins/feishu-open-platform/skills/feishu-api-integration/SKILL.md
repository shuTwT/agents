---
name: feishu-api-integration
description: 为 TypeScript/Node.js 项目设计和实现飞书开放平台 API 集成。Use when implementing, reviewing, debugging, or testing Feishu Open Platform API calls, permissions, tokens, or event callbacks.
---

# 飞书 API 集成

这个 Skill 提供一个以证据为先的飞书开放平台 API 开发流程。它不复制飞书文档；当 API 契约、权限或事件字段不确定时，优先使用用户已配置的飞书官方文档检索 MCP。

## 快速流程

1. 说明业务目标、数据对象、调用方和运行环境。
2. 检索官方文档，确认接口、权限、token 类型、请求/响应字段和限制。
3. 记录已确认事实、推断和待确认问题。
4. 设计 TypeScript/Node.js 客户端、配置和测试方案。
5. 检查分页、重试、超时、幂等、错误映射和敏感信息日志。
6. 给出最小可运行验证步骤和上线前检查清单。

## 决策规则

- 不确定的 endpoint、权限、字段或 token 规则不能凭记忆补全。
- 应用身份和用户身份必须分开说明；不要把一种 token 当作另一种 token 使用。
- API 调用封装应接收依赖注入的 HTTP 客户端，避免把网络请求写死在业务逻辑中。
- 批量读取必须处理分页；写操作必须考虑重试是否会造成重复副作用。
- 事件回调必须考虑验证、去重、快速响应和重复投递。

## 交付物

- API 选择和权限矩阵。
- TypeScript 类型、请求函数和错误类型的实现建议。
- 配置项和单元测试/mock 的设计建议。
- 未确认事项和手工验证步骤。

详细检查项见 `references/api-contract-checklist.md`。
