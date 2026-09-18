# cpa-plugin-commandcode-session

CLIProxyAPI plugin for **Command Code** ([commandcode.ai](https://commandcode.ai)): one-click connect, quota windows, and Codex-style JSON rewrite.

Plugin ID is `commandcode-session` so it does not collide with the store's native `commandcode` executor plugin.

[中文说明](README.zh-CN.md)

## Capability

- ID: `commandcode-session`
- Capabilities: `request_interceptor`, `management_api`, `quota_provider`, `usage_plugin`, `scheduler`
- Author: tianheil3

## What you get

1. **快捷接入** — paste a Command Code API key (`user_…`) on the plugin page. It probes `GET /provider/v1/models` and `GET /alpha/billing/credits`, then writes an `openai-compatibility` provider named `commandcode` (chat-completions models only, `disable-cooling`, `request-retry`). Keys inherit CPA `proxy-url` unless you set `proxy_url`. Optional Claude-compatible channel at `https://api.commandcode.ai/provider`.
2. **限额管理** — 5h / weekly windows from `/alpha/billing/credits` (`windowLimits`), plus a derived monthly remaining from plan credits. Same card style as Codex/Claude. `QuotaProvider` identifier is `commandcode`.
3. **No session header** — Provider API does not require `x-opencode-session` / `x-session-id`. Optional `zdr: true` sends `x-cmd-zdr: 1`.
4. **Codex JSON rewrite** — clamp `xhigh`, drop `json_schema`, flatten function tools. Other providers are left unchanged.
5. **Local token totals** — successful Command Code requests accumulate input / output / cache-read / cache-write. Stored as `commandcode-session-tokens.json` next to CPA config.

Management UI:

```text
/v0/resource/plugins/commandcode-session/status
```

| Route | Purpose |
|---|---|
| `GET /v0/management/plugins/commandcode-session/status` | Masked keys, quota windows, model list, local token totals |
| `GET /v0/management/plugins/commandcode-session/auth-files` | Synthetic Auth Files cards |
| `PATCH /v0/management/plugins/commandcode-session/auth-files/status` | `{ "name": "commandcode-…", "disabled": true }` |
| `DELETE /v0/management/plugins/commandcode-session/auth-files` | `{ "names": ["commandcode-…"] }` |
| `POST /v0/management/plugins/commandcode-session/connect` | `{ "api_key": "user_...", "include_claude": false }` |
| `POST /v0/management/plugins/commandcode-session/sync-models` | Refresh chat-completions models |
| `POST /v0/management/plugins/commandcode-session/refresh` | Same as status |
| `POST /v0/management/plugins/commandcode-session/tokens/reset` | Clear local token totals |

## Install

```yaml
plugins:
  enabled: true
  dir: plugins
  configs:
    commandcode-session:
      enabled: true
      priority: 10
```

Restart CLIProxyAPI. One-click connect writes the provider for you.

CPA 7.2.x hardcodes 配额管理 / 认证文件 to a few OAuth providers. After OpenCode Go's panel patch is in place:

```bash
python3 scripts/patch-cpa-quota-page.py /opt/cliproxy-api/static/management.html
```

Keep `remote-management.disable-auto-update-panel: true` so CPA does not overwrite the file on boot. Hard-refresh the management center. Command Code then shows on both pages; models and quota load from the plugin after you connect a key.

## Plugin config

| Key | Default | Meaning |
|---|---|---|
| `rewrite_body` | `true` | Rewrite request JSON |
| `clamp_reasoning` | `true` | Clamp unsupported reasoning levels |
| `drop_json_schema` | `true` | Drop json_schema / encrypted include |
| `function_tools` | `true` | Keep only `type=function` tools |
| `cpa_config_path` | `config.yaml` | Config file for one-click connect |
| `provider_name` | `commandcode` | openai-compatibility provider name |
| `base_url` | `https://api.commandcode.ai/provider/v1` | Provider API base |
| `alpha_base_url` | `https://api.commandcode.ai` | Quota/whoami root |
| `proxy_url` | empty | Per-key proxy; empty inherits CPA `proxy-url` |
| `zdr` | `false` | Send `x-cmd-zdr: 1` |
| `include_claude` | `false` | Also write Claude-compatible channel |
| `match_models` / `match_prefixes` / `skip_models` | empty | Limit body rewrite |

## Build

Requires Go 1.26+ and CGO.

```bash
make test
make build VERSION=0.1.0
```

## License

MIT
