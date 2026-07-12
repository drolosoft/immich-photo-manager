---
name: immich-status
description: Check Immich connection and library stats
allowed-tools: ["mcp__immich__*"]
---

## ⚠️ Connection Required — ALWAYS CHECK FIRST

**Before doing ANYTHING else in this skill, call `ping` on the Immich MCP server.**

- If `ping` succeeds → proceed with the skill normally.
- If `ping` fails or the MCP tools are not available → **STOP. Do not continue.** Tell the user:

> ❌ **Immich is not connected.** This plugin needs a running Immich MCP server to work.
>
> Run **/setup-immich-photo-manager** to configure your Immich connection. You'll need:
> 1. Your Immich server URL (e.g., `http://192.168.1.100:2283`)
> 2. An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
> 3. The MCP server configured (see **/setup-immich-photo-manager**)
>
> Nothing in this plugin will work until the connection is configured.

**Do NOT skip this check. Do NOT try to run any other tool first. Always ping, always block if it fails.**

Connect to Immich and report the current library status.

1. Call `get_statistics` to get total counts
2. Call `list_albums` to get album count and names

Present a concise dashboard:

```
📊 Immich Library Status
━━━━━━━━━━━━━━━━━━━━━━
Photos: {count}
Videos: {count}
Albums: {count} ({shared_count} shared)
Storage: {size}

Recent albums:
- {album_name} ({asset_count} items)
```

If the connection fails, explain what went wrong and suggest checking IMMICH_URL and IMMICH_API_KEY environment variables.
