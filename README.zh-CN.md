# cpa-plugin-commandcode-session

CLIProxyAPI 的 **Command Code** 插件：一键接入、限额面板、Codex 请求改写。

插件 ID 是 `commandcode-session`，避免和商店里的原生 `commandcode` Provider 插件撞名。

## 能力

- ID：`commandcode-session`
- `request_interceptor` / `management_api` / `quota_provider` / `usage_plugin` / `scheduler`

## 做什么

1. **快捷接入**：在插件页粘贴 Command Code API Key（`user_…`），会请求官方 `/provider/v1/models` 和 `/alpha/billing/credits`，然后写入名为 `commandcode` 的 openai-compatibility 渠道（只收 chat-completions 模型）。Key 默认继承 CPA 全局 `proxy-url`。可选同时写 Claude 兼容渠道。
2. **限额管理**：读 `/alpha/billing/credits` 的 5 小时 / 周窗口，月额度按套餐剩余 credits 估算。
3. **没有 session 头**：Provider API 不需要 `x-opencode-session`。可选 `zdr: true` 才发 `x-cmd-zdr: 1`。
4. **Codex JSON 改写**：`xhigh` / `json_schema` / function tools。其它渠道不动。
5. **本机累计 Token**：成功请求计入输入 / 输出 / 缓存，写在 CPA 目录的 `commandcode-session-tokens.json`。

管理页：

```text
/v0/resource/plugins/commandcode-session/status
```

## 安装

```yaml
plugins:
  enabled: true
  dir: plugins
  configs:
    commandcode-session:
      enabled: true
      priority: 10
```

## License

MIT
