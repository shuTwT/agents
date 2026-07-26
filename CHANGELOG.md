# Changelog

所有重要变更都记录在此文件。版本号遵循 Semantic Versioning。

## [0.1.0] - 2026-07-26

- 建立 Feishu Open Platform 插件市场源码与 marketplace manifest。
- 支持生成 Codex 和 OpenCode harness 产物。
- 增加插件、Agent、Skill、Command 的自动目录与一致性校验。
- 采用轻量生成物发布策略：仅提交 Codex/Cursor Registry、Gemini Manifest 和目录文档，其他 Harness 转换树改为按需生成。
- 对齐上游 `tools/` 目录和公共接口，并保留本地全 Harness、逐字节漂移、版本与中文文档增强。
