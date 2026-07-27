---
name: feishu-api-integration
description: Use when implementing, reviewing, debugging, or testing Feishu Open Platform API calls, permissions, tokens, or event callbacks.
---

# 飞书 API 集成

**开始前先检查本地是否已安装**
```
lark-mcp -V
```

**安装成功会返回**
```
0.3.0
```

**lark-mcp不存在时需要进行安装**
```
npm install -g @larksuiteoapi/lark-mcp
```

**检查当前是否存在`lark_open_doc_search`这个mcp，不存在时要求用户手动配置或告知正确的mcp名称，或者查找上下文中疑似为飞书开发文档检索的mcp**

## 要求

- 你印象中的飞书开放平台文档可能已不是最新，必须去检索以获取最新文档
- 禁止猜测api和sdk的使用方式
- 禁止通过搜索引擎去查找飞书开放平台文档，必须通过飞书开发文档检索工具