# Claude Code Plugin Installation Guide for `immich-photo-manager`

Lessons learned from first-time installation. This document covers every pitfall encountered and how to fix each one, so future users (and contributors) can install the plugin cleanly on the first try.

## Prerequisites

- Claude Code installed and working (`claude --version`)
- Git with push access to the plugin repository
- The `immich-photo-manager` repo cloned locally:

```bash
git clone https://github.com/drolosoft/immich-photo-manager.git
cd immich-photo-manager
```

## Quick Install (if everything is already correct)

```bash
# 1. Add the plugin's self-hosted marketplace
claude plugin marketplace add ~/immich-photo-manager

# 2. Install the plugin
claude plugin install immich-photo-manager
```

If that works, you're done. If not, read on — the fixes below address every error we encountered.

## Common Errors and Fixes

### Error 1: `Invalid schema: marketplace.json`

```
✘ Failed to add marketplace: Failed to parse marketplace file at
.claude-plugin/marketplace.json: Invalid schema: name: Invalid input:
expected string, received undefined, owner: Invalid input: expected object,
received undefined, plugins.0.author: Invalid input: expected object, received string
```

**Cause:** The `marketplace.json` file is missing required top-level fields or uses wrong types.

**Fix:** Claude Code expects this exact structure:

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "immich-photo-manager-marketplace",
  "description": "Immich Photo Manager plugin marketplace",
  "owner": {
    "name": "Drolosoft",
    "email": "forge@drolosoft.com"
  },
  "plugins": [
    {
      "name": "immich-photo-manager",
      "description": "MCP server for intelligent photo management with Immich",
      "author": {
        "name": "Drolosoft",
        "email": "forge@drolosoft.com"
      },
      "source": {
        "source": "url",
        "url": "https://github.com/drolosoft/immich-photo-manager.git"
      },
      "homepage": "https://drolosoft.com/immich-photo-manager.html"
    }
  ]
}
```

Key rules:

| Field | Must be | Common mistake |
|-------|---------|----------------|
| `name` (top-level) | A string | Missing entirely |
| `owner` | An object `{ "name": "...", "email": "..." }` | Missing entirely |
| `plugins[].author` | An object `{ "name": "...", "email": "..." }` | Passing a plain string like `"Drolosoft"` |
| `plugins[].source` | An object `{ "source": "url", "url": "..." }` | Passing a plain string like `"."` |

### Error 2: `plugins.0.source: Invalid input`

```
✘ Failed to add marketplace: Failed to parse marketplace file at
.claude-plugin/marketplace.json: Invalid schema: plugins.0.source: Invalid input
```

**Cause:** The `source` field was a plain string (e.g. `"."` or `"./plugins/my-plugin"`).

**Fix:** For plugins hosted on GitHub, use:

```json
"source": {
  "source": "url",
  "url": "https://github.com/drolosoft/immich-photo-manager.git"
}
```

Other valid source formats:

```json
// GitHub shorthand
"source": {
  "source": "github",
  "repo": "owner/repo-name"
}

// Git subdirectory
"source": {
  "source": "git-subdir",
  "url": "owner/repo-name",
  "path": "plugins/my-plugin",
  "ref": "main",
  "sha": "abc123..."
}
```

Note: A plain string like `"source": "./plugins/my-plugin"` only works for plugins that live as subdirectories inside an official Anthropic marketplace repo. For self-hosted marketplaces, always use the object format.

### Error 3: `Unrecognized key: "icon"`

```
✘ Failed to install plugin "immich-photo-manager": Plugin has an invalid
manifest file at .claude-plugin/plugin.json. Validation errors:
: Unrecognized key: "icon"
```

**Cause:** Claude Code uses strict schema validation on `plugin.json`. Any field not in the official schema causes a hard failure — there's no "ignore unknown fields" behavior.

**Fix:** Remove the `"icon"` field from `.claude-plugin/plugin.json`.

Valid `plugin.json`:

```json
{
  "name": "immich-photo-manager",
  "version": "X.Y.Z",
  "description": "MCP server for intelligent photo management with Immich...",
  "mcpServers": "./.mcp.json",
  "author": {
    "name": "Drolosoft",
    "email": "forge@drolosoft.com",
    "url": "https://drolosoft.com"
  },
  "repository": "https://github.com/drolosoft/immich-photo-manager",
  "homepage": "https://drolosoft.com",
  "license": "MIT",
  "keywords": ["immich", "photos", "mcp", "claude"]
}
```

Fields that are **NOT** allowed (will cause validation failure):
- `"icon"` — not in the schema, even though it seems like it should be
- Any other custom/undocumented field

### Error 4: `claude install` vs `claude plugin install`

```
✘ Installation failed
Invalid channel: immich-photo-manager-vX.Y.Z.plugin. Use 'stable' or 'latest'
```

**Cause:** `claude install` is for installing/updating Claude Code itself, not plugins.

**Fix:** Use `claude plugin install`:

```bash
# Wrong
claude install immich-photo-manager-vX.Y.Z.plugin

# Right
claude plugin install immich-photo-manager
```

### Error 5: `Permission denied` when pushing

```
remote: Permission to drolosoft/immich-photo-manager.git denied to your-other-username.
fatal: unable to access '...': The requested URL returned error: 403
```

**Cause:** Your Git credentials are for a different GitHub account than the repo owner.

**Fix options:**

```bash
# Option A: Use SSH with the correct key
git remote set-url origin git@github.com:drolosoft/immich-photo-manager.git

# Option B: Switch GitHub CLI user
gh auth login

# Option C: Use a Personal Access Token
git remote set-url origin https://USERNAME:PAT@github.com/drolosoft/immich-photo-manager.git
```

Important: The `claude plugin install` command clones from the remote Git URL, not your local files. So any fixes to `plugin.json` or `marketplace.json` must be pushed before install will work.

## Multi-machine / Multi-repo Setup

If the repository exists under multiple GitHub organizations (e.g. `drolosoft` and `juanatsap`), set up Git to push to both simultaneously:

```bash
# Set up dual push (run once)
git remote set-url --add --push origin git@github.com:drolosoft/immich-photo-manager.git
git remote set-url --add --push origin git@github.com:juanatsap/immich-photo-manager.git

# Verify
git remote -v
# origin  git@github.com:drolosoft/immich-photo-manager.git (fetch)
# origin  git@github.com:drolosoft/immich-photo-manager.git (push)
# origin  git@github.com:juanatsap/immich-photo-manager.git (push)

# Now every push goes to both
git push origin main
```

## Full Installation Walkthrough (from scratch)

```bash
# 1. Clone
git clone https://github.com/drolosoft/immich-photo-manager.git
cd immich-photo-manager

# 2. Register the marketplace
claude plugin marketplace add .

# 3. Install the plugin
claude plugin install immich-photo-manager

# 4. Verify
claude plugin list
```

## File Reference

### `.claude-plugin/plugin.json` — Plugin manifest

Defines the plugin name, version, description, MCP server config, and author. No unknown keys allowed.

### `.claude-plugin/marketplace.json` — Self-hosted marketplace manifest

Required for `claude plugin marketplace add`. Must include `$schema`, `name`, `owner` (object), and `plugins[]` with `author` (object) and `source` (object).

### `.mcp.json` — MCP server configuration

Tells Claude Code how to connect to the Immich MCP server:

```json
{
  "mcpServers": {
    "immich": {
      "type": "http",
      "url": "http://localhost:8626/mcp"
    }
  }
}
```
